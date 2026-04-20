"""
submit_ats.py
=============
Submits applications through company ATS portals (Greenhouse, Ashby, etc.)
using Playwright — the counterpart of submit_applications.py for non-LinkedIn jobs.

Usage:
    python pipeline/submit_ats.py --url "https://job-boards.greenhouse.io/anthropic/jobs/4816198008" --company "Anthropic" --title "Software Engineer, Claude Code"
    python pipeline/submit_ats.py --all-tailored   # submits all tracker rows with status "Tailored" and non-LinkedIn URLs
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
from pathlib import Path

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

sys.path.insert(0, str(Path(__file__).parent))

from profile import PROFILE, application_email
from ats.detector import detect as detect_ats
from ats.filler import build_fill_script, DISCOVER_JS
from ats.greenhouse import (
    standard_field_map as gh_standard_fields,
    fill_script as gh_fill_script,
    DISCOVER_QUESTIONS_JS as GH_DISCOVER_Q_JS,
    EEO_ANSWERS,
)
from ats.combobox import build_select_many_script
from ats.qa_matcher import match_questions
from ats.auto_log import CONFIRM_JS, log_application, find_resume_for_application

# Playwright's page.evaluate() expects an expression, not statements.
# The ATS modules generate function declarations + calls (designed for
# chrome extension's javascript_tool). Wrap them in an IIFE for Playwright.
def _pw_fill(page, field_map: dict[str, str]) -> dict:
    """Fill form fields via Playwright. Uses Playwright's native arg passing."""
    result = page.evaluate("""(fieldMap) => {
        const results = {};
        for (const [selector, value] of Object.entries(fieldMap)) {
            const el = document.getElementById(selector)
                    || document.querySelector('[name="' + selector + '"]')
                    || document.querySelector('[data-testid="' + selector + '"]')
                    || document.querySelector(selector);
            if (!el) { results[selector] = 'NOT_FOUND'; continue; }
            const proto = el.tagName === 'TEXTAREA'
                ? HTMLTextAreaElement.prototype
                : HTMLInputElement.prototype;
            const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
            if (setter) setter.call(el, value); else el.value = value;
            el.dispatchEvent(new Event('input',  { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
            el.dispatchEvent(new Event('blur',   { bubbles: true }));
            results[selector] = 'OK';
        }
        return results;
    }""", field_map)
    return result or {}


def _pw_select_many(page, selections: dict[str, str]) -> dict:
    """Select combobox options via Playwright. Async via evaluate_handle."""
    result = page.evaluate("""async (selections) => {
        const results = {};
        for (const [labelText, optionText] of Object.entries(selections)) {
            const allLabels = Array.from(document.querySelectorAll('label, [class*="label"], legend'));
            const label = allLabels.find(el =>
                el.innerText && el.innerText.trim().replace(/\\s+/g, ' ').includes(labelText)
            );
            if (!label) { results[labelText] = 'LABEL_NOT_FOUND'; continue; }
            const forId = label.getAttribute('for');
            let trigger = forId ? document.getElementById(forId) : null;
            if (!trigger) {
                const container = label.closest('[class*="field"], [class*="select"], .field, li') || label.parentElement;
                trigger = container ? container.querySelector('[role="combobox"], button, select, [class*="control"]') : null;
            }
            if (trigger && trigger.tagName === 'SELECT') {
                const opt = Array.from(trigger.options).find(o => o.text.trim().includes(optionText));
                if (opt) { trigger.value = opt.value; trigger.dispatchEvent(new Event('change', {bubbles:true})); results[labelText] = 'OK'; }
                else results[labelText] = 'OPTION_NOT_FOUND';
                continue;
            }
            if (!trigger) { results[labelText] = 'TRIGGER_NOT_FOUND'; continue; }
            trigger.dispatchEvent(new MouseEvent('mousedown', {bubbles:true, cancelable:true}));
            trigger.click();
            await new Promise(r => setTimeout(r, 300));
            const match = Array.from(document.querySelectorAll('[role="option"], [class*="option"], li'))
                .find(el => el.innerText && (el.innerText.trim() === optionText || el.innerText.trim().startsWith(optionText)));
            if (match) { match.click(); results[labelText] = 'OK'; }
            else { document.dispatchEvent(new KeyboardEvent('keydown', {key:'Escape', bubbles:true})); results[labelText] = 'OPTION_NOT_FOUND'; }
            await new Promise(r => setTimeout(r, 150));
        }
        return results;
    }""", selections)
    return result or {}


REPO_ROOT = Path(__file__).parent.parent
TRACKER_FILE = REPO_ROOT / "jobs" / "application_tracker.csv"
APPLICATIONS_DIR = REPO_ROOT / "applications"
BROWSER_PROFILE = Path.home() / ".job-seeker-ats"

# Global flag — set to True in headed mode so handlers pause before submit
_HEADED_MODE = False

# Ashby reCAPTCHA v3 site key (extracted from Ashby's JS bundle)
ASHBY_RECAPTCHA_SITEKEY = "6LeFb_YUAAAAALUD5h-BiQEp8JaFChe0e0A6r49Y"
CAPSOLVER_API_KEY = os.environ.get("CAPSOLVER_API_KEY", "")


def _solve_recaptcha_v3(page) -> bool:
    """Solve reCAPTCHA v3 via CapSolver and inject the token into the page."""
    import requests as _requests

    api_key = CAPSOLVER_API_KEY
    if not api_key:
        print("    [CapSolver] No API key set (CAPSOLVER_API_KEY). Skipping reCAPTCHA solve.")
        return False

    page_url = page.url
    print(f"    [CapSolver] Solving reCAPTCHA v3 for {page_url[:60]}...")

    try:
        # Create task
        resp = _requests.post("https://api.capsolver.com/createTask", json={
            "clientKey": api_key,
            "task": {
                "type": "ReCaptchaV3TaskProxyLess",
                "websiteURL": page_url,
                "websiteKey": ASHBY_RECAPTCHA_SITEKEY,
                "pageAction": "submit",
                "minScore": 0.7,
            }
        }, timeout=30)
        data = resp.json()
        if data.get("errorId", 0) != 0:
            print(f"    [CapSolver] Create task error: {data.get('errorDescription', 'unknown')}")
            return False

        task_id = data.get("taskId")
        if not task_id:
            # Some tasks return solution immediately
            token = data.get("solution", {}).get("gRecaptchaResponse")
            if token:
                page.evaluate(f"""
                    () => {{
                        const el = document.querySelector('textarea[name="g-recaptcha-response"]')
                                || document.getElementById('g-recaptcha-response');
                        if (el) {{ el.value = '{token}'; el.style.display = 'none'; }}
                        // Also override grecaptcha.execute to return our token
                        if (window.grecaptcha && window.grecaptcha.execute) {{
                            const origExecute = window.grecaptcha.execute;
                            window.grecaptcha.execute = function() {{
                                return Promise.resolve('{token}');
                            }};
                        }}
                    }}
                """)
                print(f"    [CapSolver] Token injected (immediate).")
                return True

        # Poll for result
        for attempt in range(30):
            time.sleep(2)
            resp = _requests.post("https://api.capsolver.com/getTaskResult", json={
                "clientKey": api_key,
                "taskId": task_id,
            }, timeout=15)
            result = resp.json()
            status = result.get("status", "")
            if status == "ready":
                token = result.get("solution", {}).get("gRecaptchaResponse", "")
                if token:
                    page.evaluate(f"""
                        () => {{
                            const el = document.querySelector('textarea[name="g-recaptcha-response"]')
                                    || document.getElementById('g-recaptcha-response');
                            if (el) {{ el.value = '{token}'; el.style.display = 'none'; }}
                            if (window.grecaptcha && window.grecaptcha.execute) {{
                                window.grecaptcha.execute = function() {{
                                    return Promise.resolve('{token}');
                                }};
                            }}
                        }}
                    """)
                    print(f"    [CapSolver] Token injected (poll attempt {attempt + 1}).")
                    return True
                break
            elif status == "failed":
                print(f"    [CapSolver] Task failed: {result.get('errorDescription', 'unknown')}")
                return False

        print(f"    [CapSolver] Timed out waiting for solution.")
        return False

    except Exception as e:
        print(f"    [CapSolver] Error: {e}")
        return False


def _solve_recaptcha_v3_override(page) -> bool:
    """Solve reCAPTCHA v3 via CapSolver and override grecaptcha.execute globally
    so Ashby's submit handler uses our token."""
    import requests as _requests

    api_key = CAPSOLVER_API_KEY
    if not api_key:
        print("    [CapSolver] No API key. Skipping.")
        return False

    page_url = page.url
    print(f"    [CapSolver] Solving reCAPTCHA v3 for {page_url[:60]}...")

    try:
        resp = _requests.post("https://api.capsolver.com/createTask", json={
            "clientKey": api_key,
            "task": {
                "type": "ReCaptchaV3TaskProxyLess",
                "websiteURL": page_url,
                "websiteKey": ASHBY_RECAPTCHA_SITEKEY,
                "pageAction": "submit",
                "minScore": 0.7,
            }
        }, timeout=30)
        data = resp.json()
        if data.get("errorId", 0) != 0:
            print(f"    [CapSolver] Error: {data.get('errorDescription', 'unknown')}")
            return False

        task_id = data.get("taskId")
        token = data.get("solution", {}).get("gRecaptchaResponse")

        if not token and task_id:
            for attempt in range(30):
                time.sleep(2)
                resp = _requests.post("https://api.capsolver.com/getTaskResult", json={
                    "clientKey": api_key,
                    "taskId": task_id,
                }, timeout=15)
                result = resp.json()
                if result.get("status") == "ready":
                    token = result.get("solution", {}).get("gRecaptchaResponse", "")
                    break
                elif result.get("status") == "failed":
                    print(f"    [CapSolver] Failed: {result.get('errorDescription', '')}")
                    return False

        if not token:
            print(f"    [CapSolver] No token received.")
            return False

        # Override grecaptcha + intercept fetch to inject token into GraphQL
        page.evaluate("""
            (token) => {
                // 1. Override grecaptcha enterprise + standard
                if (window.grecaptcha && window.grecaptcha.enterprise) {
                    window.grecaptcha.enterprise.execute = function() { return Promise.resolve(token); };
                    window.grecaptcha.enterprise.ready = function(cb) { cb(); };
                }
                if (window.grecaptcha) {
                    window.grecaptcha.execute = function() { return Promise.resolve(token); };
                    window.grecaptcha.ready = function(cb) { cb(); };
                }
                // 2. Hidden textarea
                const el = document.querySelector('textarea[name="g-recaptcha-response"]')
                        || document.getElementById('g-recaptcha-response');
                if (el) el.value = token;

                // 3. Intercept fetch — replace recaptchaToken in Ashby's GraphQL mutation
                const origFetch = window.fetch;
                window.fetch = function(url, opts) {
                    if (opts && opts.body && typeof url === 'string' && url.includes('non-user-graphql')) {
                        try {
                            if (typeof opts.body === 'string') {
                                const parsed = JSON.parse(opts.body);
                                if (parsed.variables && 'recaptchaToken' in parsed.variables) {
                                    parsed.variables.recaptchaToken = token;
                                    opts = {...opts, body: JSON.stringify(parsed)};
                                }
                            }
                        } catch(e) {}
                    }
                    return origFetch.apply(this, [url, opts]);
                };

                // 4. Also intercept XMLHttpRequest for good measure
                const origXHRSend = XMLHttpRequest.prototype.send;
                XMLHttpRequest.prototype.send = function(body) {
                    if (body && typeof body === 'string' && body.includes('recaptchaToken')) {
                        try {
                            const parsed = JSON.parse(body);
                            if (parsed.variables && 'recaptchaToken' in parsed.variables) {
                                parsed.variables.recaptchaToken = token;
                                body = JSON.stringify(parsed);
                            }
                        } catch(e) {}
                    }
                    return origXHRSend.call(this, body);
                };

                console.log('[CapSolver] Full intercept installed (grecaptcha + fetch + XHR)');
            }
        """, token)
        print(f"    [CapSolver] Full intercept installed (grecaptcha + fetch + XHR).")
        return True

    except Exception as e:
        print(f"    [CapSolver] Error: {e}")
        return False


def _pause_for_review(page, company: str):
    """In headed mode, pause so user can review/fix fields before submit."""
    if not _HEADED_MODE:
        return
    print(f"\n    >>> HEADED MODE: Browser is visible. Review the form for {company}.")
    print(f"    >>> Fix any fields that need attention, then press ENTER here to submit...")
    try:
        input()
    except EOFError:
        pass
    page.wait_for_timeout(500)


TRACKER_HEADERS = [
    "Date Applied", "Company", "Job Title", "LinkedIn URL", "Work Mode",
    "Salary Range", "Easy Apply", "Application Status", "Notes",
    "Tailored Resume File", "Follow Up Date", "Date Response Received", "Response Type",
]


# ---------------------------------------------------------------------------
# Tracker I/O
# ---------------------------------------------------------------------------

def read_tracker() -> list[dict]:
    if not TRACKER_FILE.exists():
        return []
    with TRACKER_FILE.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_tracker(rows: list[dict]) -> None:
    TRACKER_FILE.parent.mkdir(parents=True, exist_ok=True)
    with TRACKER_FILE.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=TRACKER_HEADERS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def find_app_folder(company: str, title: str) -> Path | None:
    if not APPLICATIONS_DIR.exists():
        return None
    co = _norm(company)
    title_words = re.findall(r"[a-z0-9]{3,}", _norm(title))
    best, best_score = None, -1
    for d in APPLICATIONS_DIR.iterdir():
        if not d.is_dir():
            continue
        body = _norm(d.name[9:]) if len(d.name) > 9 else _norm(d.name)
        if co not in body and not body.startswith(co[:6]):
            continue
        score = sum(1 for w in title_words if w in body)
        if score > best_score:
            best_score = score
            best = d
    return best


# ---------------------------------------------------------------------------
# ATS-specific submission strategies
# ---------------------------------------------------------------------------

def _submit_greenhouse(page, company: str, resume_pdf: Path) -> bool:
    """Submit a Greenhouse application form."""
    print(f"    [Greenhouse] Filling standard fields...")

    # Wait for form to load
    for sel in ["#application_form", "#main_fields", "form", "[data-controller]"]:
        try:
            page.wait_for_selector(sel, timeout=8000)
            break
        except Exception:
            pass
    page.wait_for_timeout(2000)

    # 1. Fill standard text fields
    fields = gh_standard_fields(company)
    fields["phone"] = PROFILE["phone"]
    result = _pw_fill(page, fields)
    print(f"    Standard fields: {result}")

    # 2. Upload resume
    upload = page.locator("input[type='file']")
    if upload.count() > 0:
        try:
            upload.first.set_input_files(str(resume_pdf))
            print(f"    Uploaded resume: {resume_pdf.name}")
            page.wait_for_timeout(2000)
        except Exception as e:
            print(f"    Resume upload error: {e}")
    else:
        # Try data-field for Greenhouse file inputs
        file_input = page.locator("[data-field='resume'] input[type='file'], #resume_input")
        if file_input.count() > 0:
            file_input.first.set_input_files(str(resume_pdf))
            print(f"    Uploaded resume via data-field.")
            page.wait_for_timeout(2000)

    # 3. Fill LinkedIn / website fields
    extra_text = {}
    linkedin_input = page.locator("#job_application_answers_attributes_0_text_value, input[name*='linkedin'], input[name*='url']")
    if linkedin_input.count() > 0:
        extra_text["#job_application_answers_attributes_0_text_value"] = PROFILE.get("linkedin", "")

    # 4. Discover and fill custom questions
    try:
        questions = page.evaluate(GH_DISCOVER_Q_JS)
        if questions:
            print(f"    Found {len(questions)} custom questions.")
            matched, unmatched = match_questions(questions)
            if matched:
                _pw_fill(page, matched)
                print(f"    Filled {len(matched)} matched answers.")
            if unmatched:
                print(f"    {len(unmatched)} unmatched questions:")
                for q in unmatched:
                    label = q.get("label", q.get("id", "?"))
                    print(f"      - {label}")
                    # Fill with sensible defaults based on label
                    qid = q.get("id", "")
                    if not qid:
                        continue
                    label_lower = label.lower()
                    if any(k in label_lower for k in ["salary", "compensation", "pay"]):
                        extra_text[qid] = "200000"
                    elif any(k in label_lower for k in ["year", "experience"]):
                        extra_text[qid] = "15"
                    elif any(k in label_lower for k in ["linkedin", "profile", "url", "website", "portfolio"]):
                        extra_text[qid] = PROFILE.get("linkedin", "https://www.linkedin.com/in/yuryprimakov")
                    elif any(k in label_lower for k in ["phone", "mobile"]):
                        extra_text[qid] = PROFILE["phone"]
                    elif any(k in label_lower for k in ["cover", "letter", "why", "interest", "motivation"]):
                        # Read cover letter from application folder
                        app_folder = find_app_folder(company, "")
                        cl_text = "I am excited to bring my 15+ years of engineering experience and deep AI expertise to this role."
                        if app_folder and (app_folder / "cover_letter.md").exists():
                            cl_text = (app_folder / "cover_letter.md").read_text(encoding="utf-8")[:2000]
                        extra_text[qid] = cl_text
                    elif any(k in label_lower for k in ["sponsor", "visa"]):
                        extra_text[qid] = "No"
                    elif any(k in label_lower for k in ["authorized", "eligible", "legal"]):
                        extra_text[qid] = "Yes"
                    elif any(k in label_lower for k in ["start", "available", "notice"]):
                        extra_text[qid] = "Immediately"
                    elif any(k in label_lower for k in ["refer", "hear", "source", "how did"]):
                        extra_text[qid] = "Company careers page"
                    elif any(k in label_lower for k in ["location", "city", "where"]):
                        extra_text[qid] = PROFILE.get("location", "Holmdel, NJ")
                    else:
                        extra_text[qid] = "N/A"

                if extra_text:
                    _pw_fill(page, extra_text)
                    print(f"    Filled {len(extra_text)} with defaults.")
    except Exception as e:
        print(f"    Question discovery error: {e}")

    # 5. Fill all empty required fields as fallback
    page.evaluate("""
        () => {
            const nativeIS = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
            const nativeTA = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
            document.querySelectorAll('input[required], textarea[required], [aria-required="true"]').forEach(el => {
                if ((el.value || '').trim() || el.readOnly || el.disabled) return;
                if (el.type === 'file' || el.type === 'radio' || el.type === 'checkbox') return;
                const val = el.type === 'number' ? '15' : 'N/A';
                try {
                    if (el.tagName === 'TEXTAREA') nativeTA.call(el, val);
                    else nativeIS.call(el, val);
                } catch(e) { el.value = val; }
                el.dispatchEvent(new Event('input', {bubbles: true}));
                el.dispatchEvent(new Event('change', {bubbles: true}));
            });
        }
    """)

    # 6. Handle Greenhouse-specific dropdowns and radio buttons
    #    Country, relocation, in-person, AI policy
    try:
        # Country is a React Select combobox in Greenhouse — use combobox handler
        country_result = _pw_select_many(page, {"Country": "United States"})
        print(f"    Country combobox: {country_result}")
    except Exception as e:
        print(f"    Country combobox error: {e}")

    page.wait_for_timeout(500)

    try:
        page.evaluate("""
            () => {
                const nativeIS = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                const nativeTA = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;

                // Handle ALL radio groups and select elements for yes/no questions
                function chooseAnswer(ctx) {
                    const c = ctx.toLowerCase();
                    if (c.includes('relocation') || c.includes('in-person') || c.includes('in person') || c.includes('25%') || c.includes('office'))
                        return 'yes';
                    if (c.includes('interviewed') || c.includes('before'))
                        return 'no';
                    if (c.includes('sponsor') || c.includes('visa'))
                        return 'no';
                    if (c.includes('authorized') || c.includes('eligible') || c.includes('legally'))
                        return 'yes';
                    if (c.includes('built') || c.includes('created') || c.includes('designed') || c.includes('worked') || c.includes('have you'))
                        return 'yes';
                    return null;
                }

                // Native radio inputs
                const radios = Array.from(document.querySelectorAll('input[type="radio"]'));
                const groups = {};
                radios.forEach(r => { const n = r.name; if (n && !groups[n]) groups[n] = []; if (n) groups[n].push(r); });
                Object.values(groups).forEach(group => {
                    if (group.some(r => r.checked)) return;
                    const container = group[0].closest('fieldset, li, [class*="field"], .field') || group[0].parentElement?.parentElement;
                    const ctx = container ? container.innerText : '';
                    const choice = chooseAnswer(ctx);
                    if (!choice) return;
                    const opt = group.find(r => {
                        const lbl = r.labels?.[0] || r.closest('label') || r.parentElement;
                        const t = (lbl?.innerText || r.value || '').toLowerCase().trim();
                        return t === choice || t.startsWith(choice);
                    });
                    if (opt) {
                        const lbl = opt.labels?.[0] || opt.closest('label');
                        if (lbl) lbl.click(); else opt.click();
                        opt.checked = true;
                        opt.dispatchEvent(new Event('change', {bubbles: true}));
                    }
                });

                // Select dropdowns for yes/no/country questions
                document.querySelectorAll('select').forEach(sel => {
                    if (sel.value && sel.selectedIndex > 0) return;
                    const container = sel.closest('fieldset, li, [class*="field"], .field') || sel.parentElement;
                    const ctx = container ? container.innerText : '';
                    const opts = Array.from(sel.options);

                    // Country
                    if (ctx.toLowerCase().includes('country')) {
                        const us = opts.find(o => o.text.includes('United States'));
                        if (us) { sel.value = us.value; sel.dispatchEvent(new Event('change', {bubbles:true})); }
                        return;
                    }

                    const choice = chooseAnswer(ctx);
                    if (choice) {
                        const opt = opts.find(o => o.text.trim().toLowerCase() === choice || o.text.trim().toLowerCase().startsWith(choice));
                        if (opt) { sel.value = opt.value; sel.dispatchEvent(new Event('change', {bubbles:true})); }
                    }
                });

                // Fill AI Policy textarea and other long-text fields
                document.querySelectorAll('textarea').forEach(ta => {
                    if ((ta.value || '').trim()) return;
                    const label = (document.querySelector('label[for="' + ta.id + '"]') || {}).innerText || '';
                    const ll = label.toLowerCase();
                    if (ll.includes('ai policy') || ll.includes('ai assistance') || ll.includes('ai tool')) {
                        try { nativeTA.call(ta, 'I use AI tools for resume tailoring and formatting. All technical content reflects my genuine experience.'); }
                        catch(e) { ta.value = 'I use AI tools for resume tailoring and formatting. All technical content reflects my genuine experience.'; }
                        ta.dispatchEvent(new Event('input', {bubbles: true}));
                        ta.dispatchEvent(new Event('change', {bubbles: true}));
                    } else if (ll.includes('why') && (ll.includes('anthropic') || ll.includes('company') || ll.includes('interest'))) {
                        const val = 'I am deeply aligned with Anthropic\\'s mission of building safe, beneficial AI. With 15+ years of engineering and hands-on experience building production LLM systems, RAG pipelines, and agentic workflows using the Claude API, I am excited to contribute to shaping the future of AI development tools and safety.';
                        try { nativeTA.call(ta, val); } catch(e) { ta.value = val; }
                        ta.dispatchEvent(new Event('input', {bubbles: true}));
                        ta.dispatchEvent(new Event('change', {bubbles: true}));
                    } else if (ll.includes('additional') || ll.includes('comment') || ll.includes('anything else')) {
                        try { nativeTA.call(ta, 'N/A'); } catch(e) { ta.value = 'N/A'; }
                        ta.dispatchEvent(new Event('input', {bubbles: true}));
                        ta.dispatchEvent(new Event('change', {bubbles: true}));
                    }
                });

                // Fill address field
                document.querySelectorAll('input[type="text"]').forEach(inp => {
                    if ((inp.value || '').trim()) return;
                    const label = (document.querySelector('label[for="' + inp.id + '"]') || {}).innerText || '';
                    const ll = label.toLowerCase();
                    if (ll.includes('address') || ll.includes('working from') || ll.includes('plan on working')) {
                        try { nativeIS.call(inp, 'Holmdel, NJ'); } catch(e) { inp.value = 'Holmdel, NJ'; }
                        inp.dispatchEvent(new Event('input', {bubbles: true}));
                        inp.dispatchEvent(new Event('change', {bubbles: true}));
                    }
                });
            }
        """)
        print(f"    Filled Greenhouse dropdowns, radios, and textareas.")
    except Exception as e:
        print(f"    Greenhouse extra fields error: {e}")

    # 6b. Handle EEO comboboxes
    try:
        eeo_result = _pw_select_many(page, EEO_ANSWERS)
        print(f"    EEO fields: {eeo_result}")
    except Exception as e:
        print(f"    EEO combobox error (non-fatal): {e}")

    # 7. Handle required select/dropdown fields
    page.evaluate("""
        () => {
            document.querySelectorAll('select[required], select[aria-required="true"]').forEach(sel => {
                if (sel.value && sel.selectedIndex > 0) return;
                const opts = Array.from(sel.options).filter(o => o.value && o.value !== '');
                if (opts.length) {
                    sel.value = opts[0].value;
                    sel.dispatchEvent(new Event('change', {bubbles: true}));
                }
            });
        }
    """)

    page.wait_for_timeout(1000)

    # 8. Scroll to bottom and submit
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(500)
    _pause_for_review(page, company)

    submit_btn = page.locator("button[type='submit'], input[type='submit'], button:has-text('Submit'), button:has-text('Submit application')")
    if submit_btn.count() > 0:
        submit_btn.first.scroll_into_view_if_needed()
        page.wait_for_timeout(500)
        submit_btn.first.click()
        print(f"    Clicked Submit!")
        page.wait_for_timeout(5000)

        # Check for confirmation
        confirmed = page.evaluate(CONFIRM_JS)
        if confirmed.get("confirmed"):
            print(f"    Application confirmed!")
            return True
        else:
            # Check if we're still on the form (validation errors)
            errors = page.evaluate("""
                () => {
                    const errs = Array.from(document.querySelectorAll(
                        '.field_with_errors, [class*="error"], [class*="invalid"], [aria-invalid="true"]'
                    ));
                    return errs.map(e => (e.innerText || e.textContent || '').trim().slice(0, 100))
                               .filter(t => t.length > 0).slice(0, 5);
                }
            """)
            if errors:
                print(f"    Validation errors detected: {errors}")
            else:
                # Might have succeeded despite no "thank you" page
                page_text = page.evaluate("() => document.body.innerText.slice(0, 500).toLowerCase()")
                if "thank" in page_text or "submitted" in page_text or "received" in page_text:
                    print(f"    Application likely confirmed (text match)!")
                    return True
                print(f"    Submit clicked but no confirmation detected. Current URL: {page.url[:80]}")
            return False
    else:
        print(f"    No submit button found!")
        return False


def _submit_ashby(page, company: str, resume_pdf: Path) -> bool:
    """Submit an Ashby application form."""
    print(f"    [Ashby] Filling form...")

    # Wait for Ashby form
    for sel in [".ashby-job-posting-form", "form", "[data-testid]", ".ashby-application-form-page"]:
        try:
            page.wait_for_selector(sel, timeout=10000)
            break
        except Exception:
            pass
    page.wait_for_timeout(3000)

    # Check if there's an "Apply" button we need to click first
    apply_btn = page.locator("a:has-text('Apply'), button:has-text('Apply')")
    if apply_btn.count() > 0:
        apply_btn.first.click()
        print(f"    Clicked Apply button to open form.")
        page.wait_for_timeout(3000)

    # Solve reCAPTCHA v3 early and override grecaptcha.execute so Ashby's
    # submit handler uses our token instead of requesting a new one
    _solve_recaptcha_v3_override(page)

    # 1. Discover all form fields
    fields = page.evaluate(DISCOVER_JS)
    print(f"    Found {len(fields)} form fields: {[f.get('label') or f.get('name') or f.get('id') for f in fields[:10]]}")

    # 2. Build fill map from discovered fields
    email = application_email(company)
    fill_map = {}

    for f in fields:
        fid = f.get("id") or f.get("name") or ""
        label = (f.get("label") or "").lower()
        name = (f.get("name") or "").lower()
        tag = f.get("tag", "")
        current = f.get("currentValue") or ""

        if current.strip():
            continue  # Already filled

        key = fid or name

        if not key:
            continue

        if any(k in label + name for k in ["first_name", "first name", "firstname"]):
            fill_map[key] = PROFILE["first_name"]
        elif any(k in label + name for k in ["last_name", "last name", "lastname"]):
            fill_map[key] = PROFILE["last_name"]
        elif "email" in label + name and "confirm" not in label + name:
            fill_map[key] = email
        elif any(k in label + name for k in ["phone", "mobile", "tel"]):
            fill_map[key] = PROFILE["phone"]
        elif any(k in label + name for k in ["linkedin", "profile url"]):
            fill_map[key] = PROFILE.get("linkedin", "")
        elif any(k in label + name for k in ["website", "portfolio", "url"]):
            fill_map[key] = PROFILE.get("website", PROFILE.get("linkedin", ""))
        elif any(k in label + name for k in ["location", "city", "address"]):
            fill_map[key] = PROFILE.get("location", "Holmdel, NJ")
        elif any(k in label + name for k in ["current_company", "current company", "employer"]):
            fill_map[key] = PROFILE.get("current_employer", "")
        elif any(k in label + name for k in ["salary", "compensation", "pay"]):
            fill_map[key] = "200000"
        elif any(k in label + name for k in ["year", "experience"]):
            fill_map[key] = "15"
        elif any(k in label + name for k in ["cover", "letter"]):
            app_folder = find_app_folder(company, "")
            cl = "I am excited to bring my 15+ years of engineering experience and deep AI expertise to this role."
            if app_folder and (app_folder / "cover_letter.md").exists():
                cl = (app_folder / "cover_letter.md").read_text(encoding="utf-8")[:2000]
            fill_map[key] = cl
        elif any(k in label + name for k in ["sponsor", "visa"]):
            fill_map[key] = "No"
        elif any(k in label + name for k in ["authorized", "eligible", "legal"]):
            fill_map[key] = "Yes"
        elif any(k in label + name for k in ["start", "available", "notice"]):
            fill_map[key] = "Immediately"
        elif any(k in label + name for k in ["hear", "source", "how did", "referr"]):
            fill_map[key] = "Company careers page"

    # Also try label-based discovery with broader selectors
    label_fields = page.evaluate("""
        () => {
            const results = [];
            document.querySelectorAll('label').forEach(lbl => {
                const text = (lbl.innerText || '').trim();
                const forId = lbl.getAttribute('for');
                const inp = forId ? document.getElementById(forId)
                           : lbl.closest('div, fieldset')?.querySelector('input, textarea, select');
                if (inp && text && !(inp.value || '').trim()) {
                    results.push({id: inp.id || inp.name || '', label: text, tag: inp.tagName, type: inp.type || ''});
                }
            });
            return results;
        }
    """)

    for f in label_fields:
        fid = f.get("id", "")
        label = f.get("label", "").lower()
        if not fid or fid in fill_map:
            continue
        if any(k in label for k in ["first name", "first_name"]):
            fill_map[fid] = PROFILE["first_name"]
        elif any(k in label for k in ["last name", "last_name"]):
            fill_map[fid] = PROFILE["last_name"]
        elif "email" in label:
            fill_map[fid] = email
        elif any(k in label for k in ["phone", "mobile"]):
            fill_map[fid] = PROFILE["phone"]
        elif "linkedin" in label:
            fill_map[fid] = PROFILE.get("linkedin", "")
        elif any(k in label for k in ["location", "city"]):
            fill_map[fid] = PROFILE.get("location", "Holmdel, NJ")

    if fill_map:
        result = _pw_fill(page, fill_map)
        ok_count = sum(1 for v in result.values() if v == 'OK')
        print(f"    Filled {ok_count}/{len(result)} fields.")

        # Fallback: use Playwright native fill() for Ashby React controlled inputs
        for key, value in fill_map.items():
            if not value:
                continue
            try:
                loc = page.locator(f"#{key}, [name='{key}']").first
                if loc.count() > 0 and not (loc.input_value() or "").strip():
                    loc.fill(value)
            except Exception:
                pass

    # Also fill by label text using Playwright native locators (most reliable for Ashby)
    label_fill = {
        "Name": PROFILE.get("name", f"{PROFILE['first_name']} {PROFILE['last_name']}"),
        "Full Name": PROFILE.get("name", f"{PROFILE['first_name']} {PROFILE['last_name']}"),
        "Email": application_email(company),
        "Phone": PROFILE.get("phone", ""),
        "Phone Number": PROFILE.get("phone", ""),
        "LinkedIn": PROFILE.get("linkedin", ""),
        "LinkedIn Profile": PROFILE.get("linkedin", ""),
        "LinkedIn URL": PROFILE.get("linkedin", ""),
        "LinkedIn profile URL": PROFILE.get("linkedin", ""),
        "Linkedin Profile:": PROFILE.get("linkedin", ""),
        "Portfolio, GitHub, or Personal Site": PROFILE.get("website", ""),
        "Other Website": PROFILE.get("website", ""),
        "GitHub Link": PROFILE.get("website", ""),
        "Current Company": PROFILE.get("current_employer", ""),
    }
    for label_text, value in label_fill.items():
        if not value:
            continue
        try:
            loc = page.get_by_label(label_text, exact=False).first
            if loc.count() > 0 and not (loc.input_value() or "").strip():
                loc.fill(value)
        except Exception:
            pass

    # 3. Upload resume
    upload = page.locator("input[type='file']")
    if upload.count() > 0:
        try:
            upload.first.set_input_files(str(resume_pdf))
            print(f"    Uploaded resume: {resume_pdf.name}")
            page.wait_for_timeout(2000)
        except Exception as e:
            print(f"    Resume upload error: {e}")

    # 4. Handle dropdowns/selects
    page.evaluate("""
        () => {
            document.querySelectorAll('select').forEach(sel => {
                if (sel.value && sel.selectedIndex > 0) return;
                const opts = Array.from(sel.options).filter(o => o.value && o.text.trim() !== '' && o.text !== 'Select...');
                const ctx = (sel.closest('div, fieldset')?.innerText || '').toLowerCase();
                if (ctx.includes('sponsor') || ctx.includes('visa')) {
                    const no = opts.find(o => o.text.toLowerCase().includes('no'));
                    if (no) { sel.value = no.value; sel.dispatchEvent(new Event('change', {bubbles: true})); return; }
                }
                if (ctx.includes('authorized') || ctx.includes('eligible') || ctx.includes('citizen')) {
                    const yes = opts.find(o => o.text.toLowerCase().includes('yes') || o.text.toLowerCase().includes('authorized'));
                    if (yes) { sel.value = yes.value; sel.dispatchEvent(new Event('change', {bubbles: true})); return; }
                }
                if (opts.length) {
                    sel.value = opts[0].value;
                    sel.dispatchEvent(new Event('change', {bubbles: true}));
                }
            });
        }
    """)

    # 5. Handle radio buttons
    page.evaluate("""
        () => {
            const radios = Array.from(document.querySelectorAll('input[type="radio"]'));
            const groups = {};
            radios.forEach(r => { const n = r.name || r.id; if (!groups[n]) groups[n] = []; groups[n].push(r); });
            Object.values(groups).forEach(group => {
                if (group.some(r => r.checked)) return;
                const ctx = (group[0].closest('div, fieldset')?.innerText || '').toLowerCase();
                const yes = group.find(r => (r.parentElement?.innerText || r.value || '').toLowerCase().trim() === 'yes');
                const no = group.find(r => (r.parentElement?.innerText || r.value || '').toLowerCase().trim() === 'no');
                if (ctx.includes('sponsor') || ctx.includes('visa')) { if (no) no.click(); }
                else if (yes) yes.click();
            });
        }
    """)

    page.wait_for_timeout(1000)

    # 6. Scroll and submit
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(500)
    _pause_for_review(page, company)

    submit_btn = page.locator("button[type='submit'], button:has-text('Submit'), button:has-text('Submit application'), button:has-text('Apply')")
    if submit_btn.count() > 0:
        # Find the most specific submit button
        for btn in submit_btn.all():
            txt = (btn.text_content() or "").strip().lower()
            if "submit" in txt:
                btn.scroll_into_view_if_needed()
                page.wait_for_timeout(500)
                btn.click()
                print(f"    Clicked Submit!")
                break
        else:
            submit_btn.first.scroll_into_view_if_needed()
            page.wait_for_timeout(500)
            submit_btn.first.click()
            print(f"    Clicked primary action button.")

        page.wait_for_timeout(5000)

        confirmed = page.evaluate(CONFIRM_JS)
        if confirmed.get("confirmed"):
            print(f"    Application confirmed!")
            return True
        else:
            page_text = page.evaluate("() => document.body.innerText.slice(0, 500).toLowerCase()")
            if "thank" in page_text or "submitted" in page_text or "received" in page_text:
                print(f"    Application likely confirmed (text match)!")
                return True
            errors = page.evaluate("""
                () => Array.from(document.querySelectorAll('[class*="error"], [class*="invalid"]'))
                         .map(e => (e.innerText || '').trim().slice(0, 100))
                         .filter(t => t.length > 3).slice(0, 5)
            """)
            if errors:
                print(f"    Validation errors: {errors}")
            print(f"    No confirmation detected. URL: {page.url[:80]}")
            return False
    else:
        print(f"    No submit button found!")
        return False


def _submit_generic(page, company: str, resume_pdf: Path) -> bool:
    """Generic ATS submission — discover fields, fill, submit."""
    print(f"    [Generic ATS] Attempting form fill...")

    # Wait for page to load
    page.wait_for_timeout(5000)

    # Check if there's an Apply button to click first
    apply_btn = page.locator("a:has-text('Apply'), button:has-text('Apply'), a:has-text('Apply Now'), button:has-text('Apply Now')")
    if apply_btn.count() > 0:
        apply_btn.first.click()
        print(f"    Clicked Apply button.")
        page.wait_for_timeout(3000)

    # Discover and fill all fields
    fields = page.evaluate(DISCOVER_JS)
    print(f"    Found {len(fields)} fields.")

    email = application_email(company)
    fill_map = {}
    for f in fields:
        fid = f.get("id") or f.get("name") or ""
        label = (f.get("label") or "").lower()
        name = (f.get("name") or "").lower()
        current = f.get("currentValue") or ""
        if current.strip() or not fid:
            continue
        combined = label + " " + name
        if any(k in combined for k in ["first_name", "first name", "firstname", "fname"]):
            fill_map[fid] = PROFILE["first_name"]
        elif any(k in combined for k in ["last_name", "last name", "lastname", "lname"]):
            fill_map[fid] = PROFILE["last_name"]
        elif "email" in combined and "confirm" not in combined:
            fill_map[fid] = email
        elif any(k in combined for k in ["phone", "mobile", "tel"]):
            fill_map[fid] = PROFILE["phone"]
        elif "linkedin" in combined:
            fill_map[fid] = PROFILE.get("linkedin", "")
        elif any(k in combined for k in ["location", "city"]):
            fill_map[fid] = PROFILE.get("location", "Holmdel, NJ")

    if fill_map:
        result = _pw_fill(page, fill_map)
        print(f"    Filled {sum(1 for v in result.values() if v == 'OK')}/{len(result)} fields.")

    # Upload resume
    upload = page.locator("input[type='file']")
    if upload.count() > 0:
        try:
            upload.first.set_input_files(str(resume_pdf))
            print(f"    Uploaded resume.")
            page.wait_for_timeout(2000)
        except Exception as e:
            print(f"    Upload error: {e}")

    # Dismiss any privacy/cookie/agreement dialogs blocking the form
    try:
        dialog_btn = page.locator("[role='dialog'] button:has-text('OK'), [role='dialog'] button:has-text('Accept'), [role='dialog'] button:has-text('Agree'), [role='dialog'] button:has-text('I Agree'), button:has-text('Accept All')")
        if dialog_btn.count() > 0:
            dialog_btn.first.click()
            print(f"    Dismissed privacy/agreement dialog.")
            page.wait_for_timeout(1000)
    except Exception:
        pass

    # Handle radio buttons and selects
    page.evaluate("""
        () => {
            const radios = Array.from(document.querySelectorAll('input[type="radio"]'));
            const groups = {};
            radios.forEach(r => { const n = r.name; if (n && !groups[n]) groups[n] = []; if (n) groups[n].push(r); });
            Object.values(groups).forEach(group => {
                if (group.some(r => r.checked)) return;
                const ctx = (group[0].closest('fieldset, div')?.innerText || '').toLowerCase();
                let choice = null;
                if (ctx.includes('sponsor') || ctx.includes('visa')) choice = 'no';
                else if (ctx.includes('authorized') || ctx.includes('eligible')) choice = 'yes';
                else if (ctx.includes('relocation')) choice = 'yes';
                const opt = choice && group.find(r => {
                    const t = (r.labels?.[0]?.innerText || r.parentElement?.innerText || r.value || '').toLowerCase().trim();
                    return t === choice || t.startsWith(choice);
                });
                if (opt) { opt.click(); opt.checked = true; opt.dispatchEvent(new Event('change', {bubbles:true})); }
            });
            document.querySelectorAll('select').forEach(sel => {
                if (sel.value && sel.selectedIndex > 0) return;
                const opts = Array.from(sel.options).filter(o => o.value && o.text.trim());
                if (opts.length) { sel.value = opts[0].value; sel.dispatchEvent(new Event('change', {bubbles:true})); }
            });
        }
    """)

    # Submit
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(500)
    _pause_for_review(page, company)
    submit_btn = page.locator("button[type='submit'], button:has-text('Submit'), button:has-text('Apply')")
    if submit_btn.count() > 0:
        submit_btn.first.click(force=True)
        print(f"    Clicked Submit.")
        page.wait_for_timeout(5000)

        # Check for another dialog after submit
        try:
            dialog_btn2 = page.locator("[role='dialog'] button:has-text('OK'), [role='dialog'] button:has-text('Accept')")
            if dialog_btn2.count() > 0:
                dialog_btn2.first.click()
                page.wait_for_timeout(2000)
        except Exception:
            pass

        confirmed = page.evaluate(CONFIRM_JS)
        if confirmed.get("confirmed", False):
            return True
        page_text = page.evaluate("() => document.body.innerText.slice(0, 500).toLowerCase()")
        if "thank" in page_text or "submitted" in page_text or "received" in page_text:
            print(f"    Application likely confirmed (text match)!")
            return True
        return False

    print(f"    No submit button found.")
    return False


# ---------------------------------------------------------------------------
# Main submission flow
# ---------------------------------------------------------------------------

def submit_one(url: str, company: str, title: str, resume_pdf: Path, mode: str = "", salary: str = "", headed: bool = False) -> bool:
    """Submit one application via its ATS portal. Returns True on success."""
    from playwright.sync_api import sync_playwright

    ats = detect_ats(url)
    print(f"\n{'=' * 60}")
    print(f"  {company} — {title}")
    print(f"  URL: {url[:80]}")
    print(f"  ATS: {ats}")
    print(f"  Resume: {resume_pdf}")
    print(f"  Mode: {'HEADED (visible)' if headed else 'headless'}")
    print(f"{'=' * 60}")

    BROWSER_PROFILE.mkdir(exist_ok=True)

    # Stealth: use real Chrome channel + anti-detection args
    launch_args = [
        "--disable-blink-features=AutomationControlled",
        "--no-first-run",
        "--no-default-browser-check",
    ]

    with sync_playwright() as pw:
        context = pw.chromium.launch_persistent_context(
            str(BROWSER_PROFILE),
            headless=not headed,
            viewport={"width": 1280, "height": 900},
            slow_mo=300 if headed else 200,
            args=launch_args,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        )

        # Apply playwright-stealth patches
        try:
            from playwright_stealth import stealth_sync
            for p in context.pages:
                stealth_sync(p)
            context.on("page", lambda p: stealth_sync(p))
        except ImportError:
            pass

        page = context.new_page()
        success = False

        try:
            # Browse the job board root first to build reCAPTCHA v3 score
            board_root = "/".join(url.split("/")[:5])  # e.g. https://jobs.ashbyhq.com/company
            if board_root != url:
                page.goto(board_root, wait_until="domcontentloaded", timeout=15000)
                page.wait_for_timeout(2000)
                # Simulate human-like scrolling
                page.evaluate("window.scrollBy(0, 300)")
                page.wait_for_timeout(1000)
                page.evaluate("window.scrollBy(0, 300)")
                page.wait_for_timeout(1500)

            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)

            if ats == "greenhouse":
                success = _submit_greenhouse(page, company, resume_pdf)
            elif ats == "ashby":
                success = _submit_ashby(page, company, resume_pdf)
            else:
                success = _submit_generic(page, company, resume_pdf)

            if success:
                print(f"\n  SUCCESS: {company} / {title}")
            else:
                # Take screenshot for debugging
                ss_path = Path("/tmp") / f"ats_{_norm(company)}.png"
                try:
                    page.screenshot(path=str(ss_path))
                    print(f"\n  FAILED: {company} / {title} — screenshot: {ss_path}")
                except Exception:
                    print(f"\n  FAILED: {company} / {title}")

        except Exception as e:
            print(f"\n  ERROR: {e}")
        finally:
            context.close()

    return success


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Submit ATS applications (Greenhouse, Ashby, etc.)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--url", help="Direct application URL")
    group.add_argument("--all-tailored", action="store_true", help="Submit all non-LinkedIn tailored applications")

    parser.add_argument("--company", help="Company name (required with --url)")
    parser.add_argument("--title", help="Job title (required with --url)")
    parser.add_argument("--headed", action="store_true", help="Run browser in headed (visible) mode")
    args = parser.parse_args()

    global _HEADED_MODE
    _HEADED_MODE = args.headed

    if args.url:
        if not args.company or not args.title:
            parser.error("--company and --title are required with --url")

        resume_file = find_resume_for_application(args.company, args.title)
        if not resume_file:
            print(f"No resume found for {args.company} / {args.title}")
            return
        resume_pdf = REPO_ROOT / resume_file
        if not resume_pdf.exists():
            print(f"Resume PDF not found: {resume_pdf}")
            return

        ok = submit_one(args.url, args.company, args.title, resume_pdf, headed=args.headed)
        if ok:
            log_application(args.company, args.title, args.url, resume_file)

    elif args.all_tailored:
        rows = read_tracker()
        targets = []
        for i, r in enumerate(rows):
            if r.get("Application Status") != "Tailored":
                continue
            url = r.get("LinkedIn URL", "")
            if not url or "linkedin.com/jobs" in url:
                continue  # LinkedIn jobs handled by submit_applications.py
            targets.append((i, r))

        if not targets:
            print("No non-LinkedIn tailored applications to submit.")
            return

        print(f"Found {len(targets)} non-LinkedIn application(s) to submit.\n")

        submitted, failed = [], []
        for idx, row in targets:
            company = row.get("Company", "Unknown")
            title = row.get("Job Title", "Unknown")
            url = row.get("LinkedIn URL", "")
            mode = row.get("Work Mode", "")
            salary = row.get("Salary Range", "")

            resume_file = row.get("Tailored Resume File", "")
            if not resume_file:
                resume_file = find_resume_for_application(company, title)
            resume_pdf = REPO_ROOT / resume_file if resume_file else None

            if not resume_pdf or not resume_pdf.exists():
                print(f"[{idx}] {company} — {title}: No resume PDF found, skipping.")
                failed.append(f"{company} / {title} (no resume)")
                continue

            ok = submit_one(url, company, title, resume_pdf, mode, salary, headed=args.headed)
            if ok:
                from datetime import datetime, timedelta
                rows[idx]["Application Status"] = "Applied"
                rows[idx]["Date Applied"] = datetime.now().strftime("%Y-%m-%d")
                rows[idx]["Follow Up Date"] = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
                write_tracker(rows)
                submitted.append(f"{company} / {title}")
            else:
                failed.append(f"{company} / {title}")

        print(f"\n{'=' * 60}")
        print(f"Results: {len(submitted)} submitted, {len(failed)} failed.")
        if submitted:
            print("\nSubmitted:")
            for s in submitted:
                print(f"  + {s}")
        if failed:
            print("\nFailed:")
            for f in failed:
                print(f"  - {f}")


if __name__ == "__main__":
    main()
