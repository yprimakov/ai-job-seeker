"""
submit_applications.py
======================
Submits LinkedIn Easy Apply applications for rows in application_tracker.csv
that have status "Tailored".

Usage:
    python pipeline/submit_applications.py --ids 0 1 2
    python pipeline/submit_applications.py --all-tailored

For each row:
  1. Find the application folder (applications/YYYYMMDD_Company_Title/)
  2. Read analysis.json for the LinkedIn URL
  3. Use Playwright to open LinkedIn, click Easy Apply, upload resume.pdf
  4. Navigate multi-step form, submit
  5. Update tracker status to "Applied"

Non-Easy-Apply jobs are skipped with a notice — manual submission required.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

load_dotenv_path = Path(__file__).parent.parent / ".env"
try:
    from dotenv import load_dotenv
    load_dotenv(load_dotenv_path)
except ImportError:
    pass

REPO_ROOT = Path(__file__).parent.parent
TRACKER_FILE = REPO_ROOT / "jobs" / "application_tracker.csv"
APPLICATIONS_DIR = REPO_ROOT / "applications"
LINKEDIN_PROFILE = Path.home() / ".job-seeker-linkedin"

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


# ---------------------------------------------------------------------------
# Application folder lookup
# ---------------------------------------------------------------------------

def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def find_app_folder(company: str, title: str) -> Path | None:
    if not APPLICATIONS_DIR.exists():
        return None
    co = _norm(company)
    title_words = re.findall(r"[a-z0-9]{3,}", _norm(title))

    best: Path | None = None
    best_score = -1

    for d in APPLICATIONS_DIR.iterdir():
        if not d.is_dir() or not (d / "analysis.json").exists():
            continue
        body = _norm(d.name.replace(d.name[:9], ""))  # strip YYYYMMDD_
        first_seg = _norm(d.name[9:].split("_")[0]) if len(d.name) > 9 else ""
        if not (body.startswith(co) or co.startswith(first_seg)):
            continue
        score = sum(1 for w in title_words if w in body)
        if score > best_score:
            best_score = score
            best = d

    return best


# ---------------------------------------------------------------------------
# LinkedIn Easy Apply via Playwright
# ---------------------------------------------------------------------------

def _detect_apply_type(page) -> str:
    """
    Detect the type of apply flow on the current LinkedIn job page.
    Returns: 'easy_apply', 'linkedin_apply', 'external', or 'none'
    """
    return page.evaluate("""
        () => {
            const els = Array.from(document.querySelectorAll('button, a'));
            for (const el of els) {
                const label = (el.getAttribute('aria-label') || '').toLowerCase();
                const text  = (el.innerText || el.textContent || '').trim().toLowerCase();
                const href  = (el.getAttribute('href') || '').toLowerCase();
                if (label.includes('easy apply') || text === 'easy apply') {
                    return 'easy_apply';
                }
                if (href.includes('/apply/') && href.includes('opensdui')) {
                    return 'linkedin_apply';
                }
            }
            // Check for any apply element at all
            for (const el of els) {
                const label = (el.getAttribute('aria-label') || '').toLowerCase();
                const text  = (el.innerText || el.textContent || '').trim().toLowerCase();
                const href  = (el.getAttribute('href') || '');
                if ((label.includes('apply') || text.includes('apply')) && !text.includes('applied')) {
                    if (href && !href.includes('linkedin.com')) return 'external';
                    return 'linkedin_apply';
                }
            }
            return 'none';
        }
    """)


def _click_apply_button_js(page) -> bool:
    """Use JavaScript to find and click the Easy Apply button. Returns True if clicked."""
    result = page.evaluate("""
        () => {
            // Search both <button> and <a> elements — LinkedIn uses <a> for Apply
            const els = Array.from(document.querySelectorAll('button, a'));

            // Prefer elements whose text or aria-label is exactly 'Easy Apply'
            const ea = els.find(el => {
                const label = (el.getAttribute('aria-label') || '').toLowerCase();
                const text  = (el.innerText || el.textContent || '').trim().toLowerCase();
                return label.includes('easy apply') || text === 'easy apply';
            });
            if (ea) { ea.click(); return 'easy_apply'; }

            // Fallback: any element whose text/aria is just 'Apply' (not 'Applied')
            const apply = els.find(el => {
                const label = (el.getAttribute('aria-label') || '').toLowerCase();
                const text  = (el.innerText || el.textContent || '').trim().toLowerCase();
                return (text === 'apply' || label === 'apply') && !text.includes('applied');
            });
            if (apply) { apply.click(); return 'apply'; }

            // Last resort: any visible element containing 'apply'
            const anyApply = els.find(el => {
                const text = (el.innerText || el.textContent || '').trim().toLowerCase();
                return text.includes('apply') && !text.includes('applied') && text.length < 30;
            });
            if (anyApply) { anyApply.click(); return 'any_apply'; }

            return null;
        }
    """)
    if result:
        print(f"    Clicked apply button via JS (matched: {result}).")
        return True
    return False


def _get_apply_url(page) -> str | None:
    """Extract the LinkedIn apply URL from the current job page."""
    return page.evaluate("""
        () => {
            for (const el of document.querySelectorAll('a')) {
                const href = el.getAttribute('href') || '';
                const label = (el.getAttribute('aria-label') || '').toLowerCase();
                if (href.includes('/apply/') && (label.includes('apply') || href.includes('opensdui') || href.includes('Apply'))) {
                    return href.startsWith('http') ? href : 'https://www.linkedin.com' + href;
                }
            }
            // Fallback: any /apply/ link
            for (const el of document.querySelectorAll('a[href*=\"/apply/\"]')) {
                const href = el.getAttribute('href');
                return href.startsWith('http') ? href : 'https://www.linkedin.com' + href;
            }
            return null;
        }
    """)


def _form_fingerprint(page) -> str:
    """Hash visible form field labels to detect stuck loops."""
    import hashlib
    labels = page.evaluate("""
        () => Array.from(document.querySelectorAll(
            'fieldset legend, label, [aria-label], .artdeco-text-input__label, .fb-dash-form-element__label'
        )).map(el => (el.innerText || el.textContent || '').trim().slice(0, 80))
          .filter(t => t.length > 0)
          .join('|')
    """)
    return hashlib.md5(labels.encode()).hexdigest()


def _is_external_wrapper_modal(page) -> bool:
    """Detect if the Easy Apply modal is actually an external ATS wrapper."""
    return page.evaluate("""
        () => {
            const modal = document.querySelector('[role="dialog"], [class*="easy-apply-modal"], [class*="artdeco-modal"]');
            if (!modal) return false;
            const btns = Array.from(modal.querySelectorAll('button, a'));
            const hasExternalApply = btns.some(b => {
                const href = b.getAttribute('href') || '';
                const label = (b.getAttribute('aria-label') || b.textContent || '').toLowerCase();
                return href.startsWith('http') && !href.includes('linkedin.com') && label.includes('apply');
            });
            const hasSubmit = btns.some(b =>
                (b.textContent || b.getAttribute('aria-label') || '').toLowerCase().includes('submit')
            );
            return hasExternalApply && !hasSubmit;
        }
    """)


def submit_easy_apply(page, resume_pdf: Path, row: dict) -> bool:
    """Navigate through LinkedIn Easy Apply form. Returns True if submitted."""

    # Wait for page content
    for selector in [
        ".jobs-unified-top-card",
        ".jobs-details",
        ".job-view-layout",
        "[data-job-id]",
    ]:
        try:
            page.wait_for_selector(selector, timeout=8000)
            break
        except Exception:
            pass
    page.wait_for_timeout(2000)

    # Check if already applied
    already = page.evaluate("""
        () => {
            const body = document.body.innerText.toLowerCase();
            return body.includes('application submitted') || body.includes('applied') && document.querySelector('[class*="applied-badge"]') !== null;
        }
    """)
    if already:
        print("    Already applied to this job.")
        return False

    # Get the apply URL from the page (works for both Easy Apply modal and LinkedIn hosted flow)
    apply_url = None
    for attempt in range(4):
        apply_url = _get_apply_url(page)
        if apply_url:
            break
        print(f"    No apply link found (attempt {attempt + 1}/4), waiting 3s...")
        page.wait_for_timeout(3000)
        page.evaluate("window.scrollBy(0, 300)")

    if not apply_url:
        texts = page.evaluate("""
            () => Array.from(document.querySelectorAll('button, a'))
                       .map(el => (el.innerText || el.textContent || '').trim())
                       .filter(t => t.length > 0 && t.length < 40)
                       .slice(0, 15)
        """)
        print(f"    Visible elements: {texts}")
        print("    Could not find Apply link.")
        return False

    # Check if external (leaves LinkedIn)
    if "linkedin.com" not in apply_url:
        print(f"    External apply link ({apply_url[:60]}) — cannot automate.")
        return False

    print(f"    Navigating to apply URL...")

    # Navigate directly to the apply URL — this loads the Easy Apply modal
    page.goto(apply_url, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(3000)

    print(f"    Apply page loaded: {page.url[:80]}")

    # Check immediately if this is an external ATS wrapper modal
    page.wait_for_timeout(1500)
    if _is_external_wrapper_modal(page):
        print("    Modal is an external ATS wrapper (not true Easy Apply) — cannot auto-submit.")
        return False

    time.sleep(1)

    # Walk through the multi-step form
    max_steps = 25
    uploaded_resume = False
    prev_fingerprint = None

    for step in range(max_steps):
        page.wait_for_timeout(1500)

        # Loop detection — if form state hasn't changed, try to fix validation errors first
        fp = _form_fingerprint(page)
        if fp == prev_fingerprint and step > 1:
            # Before giving up, try to fix any validation errors and see if Submit is now available
            fixed = page.evaluate("""
                () => {
                    let fixed = 0;
                    const nativeIS = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                    const nativeTA = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
                    const nativeSS = Object.getOwnPropertyDescriptor(window.HTMLSelectElement.prototype, 'value').set;
                    const errEls = Array.from(document.querySelectorAll(
                        '.artdeco-inline-feedback--error, input[aria-invalid="true"], input:invalid, select[aria-invalid="true"]'
                    ));
                    errEls.forEach(el => {
                        let inp = ['INPUT','SELECT','TEXTAREA'].includes(el.tagName) ? el :
                            (el.closest('div.fb-dash-form-element, fieldset')?.querySelector(
                                'input:not([type="radio"]):not([type="checkbox"]), select, textarea') || null);
                        if (!inp || inp.readOnly || inp.disabled) return;
                        if (inp.tagName === 'SELECT') {
                            const opts = Array.from(inp.options).filter(o => o.value && o.text !== 'Select an option');
                            if (opts.length) { try { nativeSS.call(inp, opts[0].value); } catch(e) { inp.value = opts[0].value; } inp.dispatchEvent(new Event('change',{bubbles:true})); fixed++; }
                        } else if (!inp.value.trim()) {
                            const ctx = (inp.closest('div.fb-dash-form-element, fieldset')?.innerText || inp.getAttribute('aria-label') || '').toLowerCase();
                            const v = inp.type === 'number' ? '10' : ctx.includes('year') ? '12' : ctx.includes('salary') ? '200000' : 'Yes';
                            try { if (inp.tagName === 'TEXTAREA') { nativeTA.call(inp, v); } else { nativeIS.call(inp, v); } } catch(e) { inp.value = v; }
                            inp.dispatchEvent(new Event('input',{bubbles:true})); inp.dispatchEvent(new Event('change',{bubbles:true})); fixed++;
                        }
                    });
                    // Also fill any empty required fields
                    document.querySelectorAll('input[required]:not([type="radio"]):not([type="checkbox"]), textarea[required]').forEach(inp => {
                        if (inp.value.trim() || inp.readOnly || inp.disabled) return;
                        const v = inp.type === 'number' ? '10' : '5';
                        try { if (inp.tagName === 'TEXTAREA') { nativeTA.call(inp, v); } else { nativeIS.call(inp, v); } } catch(e) { inp.value = v; }
                        inp.dispatchEvent(new Event('input',{bubbles:true})); inp.dispatchEvent(new Event('change',{bubbles:true})); fixed++;
                    });
                    return fixed;
                }
            """)
            if fixed:
                print(f"    Step {step + 1}: Fixed {fixed} validation errors — retrying...")
                page.wait_for_timeout(1000)
                # Check if Submit button appeared
                submit_now = page.locator("button[aria-label*='Submit' i]").first
                if submit_now.count() > 0:
                    submit_now.click(force=True)
                    print(f"    Step {step + 1}: Submitted after fixing errors!")
                    page.wait_for_timeout(3000)
                    return True
                prev_fingerprint = None  # reset to allow progression
                continue
            print(f"    Step {step + 1}: [STUCK] Same form state, no fixable errors — stopping.")
            company = row.get("Company", "unknown").replace(" ", "_")
            try:
                page.screenshot(path=f"/tmp/stuck_{company}_{step}.png")
                print(f"    Screenshot saved to /tmp/stuck_{company}_{step}.png")
            except Exception:
                pass
            break
        prev_fingerprint = fp

        # Check for resume upload step (only do once)
        if not uploaded_resume:
            upload_locator = page.locator("input[type='file']")
            if upload_locator.count() > 0:
                try:
                    upload_locator.first.set_input_files(str(resume_pdf))
                    print(f"    Step {step + 1}: Uploaded resume PDF.")
                    uploaded_resume = True
                    time.sleep(1)
                except Exception as e:
                    print(f"    Step {step + 1}: Resume upload error: {e}")

        # Fill phone number if empty
        try:
            phone_input = page.locator("input[id*='phoneNumber'], input[name*='phone']").first
            if phone_input.count() > 0:
                val = phone_input.input_value()
                if not val:
                    phone_input.fill("7187576477")
                    print(f"    Step {step + 1}: Filled phone number.")
        except Exception:
            pass

        # Handle yes/no radio questions: work authorization, visa sponsorship
        try:
            page.evaluate("""
                () => {
                    // Find all radio groups on the page
                    const radios = Array.from(document.querySelectorAll('input[type="radio"]'));
                    const groups = {};
                    radios.forEach(r => {
                        const name = r.name || r.id;
                        if (!groups[name]) groups[name] = [];
                        groups[name].push(r);
                    });

                    Object.values(groups).forEach(group => {
                        // Skip if already answered
                        if (group.some(r => r.checked)) return;
                        const container = group[0].closest('[class*="question"], [class*="form"], fieldset, [role="group"]') || group[0].parentElement;
                        const label = (container ? container.innerText : '').toLowerCase();

                        // For yes/no questions, prefer "Yes" for authorization/eligibility
                        // and "No" for sponsorship
                        const yesOpt = group.find(r => {
                            const l = (r.parentElement ? r.parentElement.innerText : r.value || '').toLowerCase();
                            return l.trim() === 'yes' || l.includes(' yes');
                        });
                        const noOpt = group.find(r => {
                            const l = (r.parentElement ? r.parentElement.innerText : r.value || '').toLowerCase();
                            return l.trim() === 'no' || l.includes(' no');
                        });

                        if (label.includes('sponsor') || label.includes('visa')) {
                            if (noOpt) noOpt.click();  // No, don't need sponsorship
                        } else if (yesOpt) {
                            yesOpt.click();  // Yes to authorization, citizenship, etc.
                        }
                    });
                }
            """)
        except Exception:
            pass

        # Fill empty text/number/date inputs and textareas
        try:
            page.evaluate("""
                () => {
                    const nativeIS = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                    const nativeTA = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;

                    function setVal(inp, val) {
                        try {
                            if (inp.tagName === 'TEXTAREA') { nativeTA.call(inp, val); } else { nativeIS.call(inp, val); }
                        } catch(e) { inp.value = val; }
                        inp.dispatchEvent(new Event('input', {bubbles: true}));
                        inp.dispatchEvent(new Event('change', {bubbles: true}));
                    }

                    const inputs = Array.from(document.querySelectorAll(
                        'input[type="text"], input[type="number"], input[type="tel"], textarea, input:not([type])'
                    ));
                    inputs.forEach(inp => {
                        if ((inp.value || '').trim()) return;
                        if (inp.readOnly || inp.disabled) return;
                        const label = (inp.getAttribute('aria-label') || inp.getAttribute('placeholder') || inp.getAttribute('name') || '').toLowerCase();
                        const container = inp.closest('div.fb-dash-form-element, [class*="question"], [class*="form-element"], fieldset') || inp.closest('div');
                        const ctxLabel = container ? container.innerText.slice(0, 200).toLowerCase() : '';
                        const fullLabel = label + ' ' + ctxLabel;

                        if (fullLabel.includes('year') && (fullLabel.includes('experience') || fullLabel.includes('work'))) {
                            setVal(inp, '12');
                        } else if (fullLabel.includes('salary') || fullLabel.includes('compensation') || fullLabel.includes('desired') || fullLabel.includes('rate') || fullLabel.includes('pay')) {
                            setVal(inp, '200000');
                        } else if (fullLabel.includes('phone') || fullLabel.includes('mobile')) {
                            setVal(inp, '7187576477');
                        } else if (fullLabel.includes('model') || fullLabel.includes('how many') || fullLabel.includes('number of')) {
                            setVal(inp, '10');
                        } else if (fullLabel.includes('refer') || fullLabel.includes('who') || fullLabel.includes('name')) {
                            setVal(inp, 'N/A');
                        } else if (fullLabel.includes('linkedin') || fullLabel.includes('profile') || fullLabel.includes('website') || fullLabel.includes('url') || fullLabel.includes('portfolio')) {
                            setVal(inp, 'https://www.linkedin.com/in/yuryprimakov');
                        } else if (inp.type === 'number') {
                            setVal(inp, '5');
                        } else if (inp.type === 'tel') {
                            setVal(inp, '7187576477');
                        } else if (inp.required || inp.getAttribute('aria-required') === 'true') {
                            setVal(inp, 'Available immediately');
                        }
                    });

                    // Fill date inputs (mm/dd/yyyy format) with 2 weeks from today
                    document.querySelectorAll('input[placeholder*="mm/dd"], input[placeholder*="yyyy"], input[type="date"]').forEach(inp => {
                        if ((inp.value || '').trim()) return;
                        const d = new Date(); d.setDate(d.getDate() + 14);
                        const mm = String(d.getMonth()+1).padStart(2,'0');
                        const dd = String(d.getDate()).padStart(2,'0');
                        const yyyy = d.getFullYear();
                        const val = inp.type === 'date' ? yyyy+'-'+mm+'-'+dd : mm+'/'+dd+'/'+yyyy;
                        try { nativeIS.call(inp, val); } catch(e) { inp.value = val; }
                        inp.dispatchEvent(new Event('input', {bubbles: true}));
                        inp.dispatchEvent(new Event('change', {bubbles: true}));
                    });
                }
            """)
        except Exception:
            pass

        # Handle dropdowns — select appropriate option based on context
        try:
            page.evaluate("""
                () => {
                    const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLSelectElement.prototype, 'value').set;

                    function setOpt(sel, val) {
                        try { nativeSetter.call(sel, val); } catch(e) { sel.value = val; }
                        sel.dispatchEvent(new Event('change', {bubbles: true}));
                        sel.dispatchEvent(new InputEvent('input', {bubbles: true}));
                    }

                    const selects = Array.from(document.querySelectorAll('select'));
                    selects.forEach(sel => {
                        const cur = sel.value;
                        if (cur && cur !== 'Select an option' && cur !== '' && sel.selectedIndex > 0) return;
                        const opts = Array.from(sel.options).filter(o => o.value && o.value !== 'Select an option' && o.text.trim() && o.text !== 'Select an option');
                        if (!opts.length) return;

                        const container = sel.closest('div.fb-dash-form-element, [class*="question"], fieldset') || sel.closest('div');
                        const ctx = container ? container.innerText.slice(0, 300).toLowerCase() : '';
                        const optTexts = opts.map(o => o.text.toLowerCase());

                        if (ctx.includes('citizen') || ctx.includes('eligibility') || ctx.includes('authorized') || ctx.includes('work in the us')) {
                            // Prefer US citizen/permanent resident
                            const pref = opts.find(o => o.text.toLowerCase().includes('citizen') && (o.text.toLowerCase().includes('u.s') || o.text.toLowerCase().includes('us')))
                                      || opts.find(o => o.text.toLowerCase().includes('permanent'))
                                      || opts[0];
                            setOpt(sel, pref.value);
                        } else if (ctx.includes('sponsor') || ctx.includes('visa')) {
                            // No sponsorship needed
                            const pref = opts.find(o => o.text.toLowerCase() === 'no') || opts.find(o => o.text.toLowerCase().includes('no')) || opts[0];
                            setOpt(sel, pref.value);
                        } else if (optTexts.some(t => t === 'yes') || optTexts.some(t => t.startsWith('yes'))) {
                            // For yes/no questions, default to Yes unless it's about needing something
                            const isNeedQ = ctx.includes('need') || ctx.includes('require') || ctx.includes('sponsor') || ctx.includes('relocat');
                            const pref = isNeedQ
                                ? (opts.find(o => o.text.toLowerCase() === 'no') || opts[0])
                                : (opts.find(o => o.text.toLowerCase() === 'yes') || opts[0]);
                            setOpt(sel, pref.value);
                        } else {
                            setOpt(sel, opts[0].value);
                        }
                    });
                }
            """)
        except Exception:
            pass

        # Handle fieldset/legend-based filling (LinkedIn groups questions in fieldsets)
        try:
            page.evaluate("""
                () => {
                    const nativeIS = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                    document.querySelectorAll('fieldset').forEach(fs => {
                        const legend = (fs.querySelector('legend') || {}).innerText || '';
                        const ll = legend.toLowerCase();
                        const inp = fs.querySelector('input:not([type="radio"]):not([type="checkbox"]):not([type="file"])');
                        if (!inp || (inp.value || '').trim() || inp.readOnly || inp.disabled) return;
                        let val = null;
                        if (ll.includes('year') && (ll.includes('experience') || ll.includes('work'))) val = '12';
                        else if (ll.includes('salary') || ll.includes('compensation') || ll.includes('expected pay') || ll.includes('desired')) val = '200000';
                        else if (ll.includes('gpa') || ll.includes('grade')) val = '3.8';
                        else if (ll.includes('month') || ll.includes('notice period')) val = '2';
                        else if (ll.includes('phone') || ll.includes('mobile')) val = '7187576477';
                        else if (ll.includes('linkedin') || ll.includes('profile url') || ll.includes('website') || ll.includes('portfolio')) val = 'https://www.linkedin.com/in/yuryprimakov';
                        else if (inp.type === 'number') val = '5';
                        if (val !== null) {
                            try { nativeIS.call(inp, val); } catch(e) { inp.value = val; }
                            inp.dispatchEvent(new Event('input', {bubbles: true}));
                            inp.dispatchEvent(new Event('change', {bubbles: true}));
                        }
                    });
                }
            """)
        except Exception:
            pass

        # Handle EEOC / voluntary self-identification radio groups using Playwright native clicks
        # These use LinkedIn's custom components that don't respond to JS el.click() alone
        try:
            eeo_groups = page.locator("fieldset, [data-test-form-element], .fb-dash-form-element").all()
            for group in eeo_groups:
                try:
                    label_text = (group.locator("legend, label").first.text_content() or "").strip().lower()
                except Exception:
                    label_text = ""
                # Find all radio inputs in this group
                radios = group.locator("input[type='radio']").all()
                if not radios:
                    continue
                # Skip if already answered
                if any(r.is_checked() for r in radios):
                    continue
                # Pick the right option based on question context
                def pick_option(radios, preference_keywords):
                    for pref in preference_keywords:
                        for r in radios:
                            try:
                                lbl = (r.locator("..").text_content() or "").strip().lower()
                                if not lbl:
                                    # Try sibling label
                                    rid = r.get_attribute("id") or ""
                                    if rid:
                                        lbl_el = page.locator(f"label[for='{rid}']")
                                        if lbl_el.count() > 0:
                                            lbl = (lbl_el.text_content() or "").lower()
                                if pref in lbl:
                                    r.click(force=True)
                                    return True
                            except Exception:
                                pass
                    return False

                if any(w in label_text for w in ("gender", "sex")):
                    pick_option(radios, ["prefer not", "don't wish", "do not wish", "not to specify", "prefer to self", "male"])
                elif any(w in label_text for w in ("disability", "disabled")):
                    pick_option(radios, ["do not want", "don't want", "prefer not", "no, i do not"])
                elif any(w in label_text for w in ("veteran", "military")):
                    pick_option(radios, ["not a veteran", "i am not", "no", "decline"])
                elif any(w in label_text for w in ("race", "ethnicity", "hispanic")):
                    pick_option(radios, ["prefer not", "don't wish", "do not wish", "decline", "not to answer"])
                else:
                    # Generic: pick "prefer not" / "decline" / first option
                    if not pick_option(radios, ["prefer not", "don't wish", "decline", "not to answer"]):
                        try:
                            radios[0].click(force=True)
                        except Exception:
                            pass
            # Handle ethnicity CHECKBOXES (mark "I don't wish to answer" if present, else skip)
            try:
                all_checkboxes = page.locator("input[type='checkbox']").all()
                for cb in all_checkboxes:
                    try:
                        if cb.is_checked():
                            continue
                        lbl_text = ""
                        cid = cb.get_attribute("id") or ""
                        if cid:
                            lbl_el = page.locator(f"label[for='{cid}']")
                            if lbl_el.count() > 0:
                                lbl_text = (lbl_el.text_content() or "").lower()
                        if any(w in lbl_text for w in ("don't wish", "prefer not", "do not wish", "decline", "not to answer")):
                            cb.click(force=True)
                    except Exception:
                        pass
            except Exception:
                pass
        except Exception:
            pass

        # Handle custom combobox/typeahead inputs (LinkedIn uses role="combobox" for degree, school, company)
        try:
            page.evaluate("""
                () => {
                    document.querySelectorAll('[role="combobox"]').forEach(cb => {
                        if ((cb.value || cb.textContent || '').trim()) return;
                        const container = cb.closest('div.fb-dash-form-element, fieldset') || cb.parentElement;
                        const ctx = (container ? container.innerText : '').toLowerCase();
                        let typedVal = null;
                        if (ctx.includes('degree') || ctx.includes('education level')) typedVal = "Bachelor";
                        else if (ctx.includes('field of study') || ctx.includes('major')) typedVal = "Computer Science";
                        else if (ctx.includes('school') || ctx.includes('university') || ctx.includes('college')) typedVal = "N/A";
                        if (!typedVal) return;
                        cb.focus();
                        cb.click();
                        // Try to find and click the first option in the linked listbox
                        const listId = cb.getAttribute('aria-controls') || cb.getAttribute('aria-owns');
                        if (listId) {
                            const list = document.getElementById(listId);
                            const first = list && list.querySelector('[role="option"]');
                            if (first) { first.click(); return; }
                        }
                    });
                }
            """)
        except Exception:
            pass

        # Handle "Follow company" or newsletter checkboxes — uncheck them
        try:
            follow_boxes = page.locator("label:has-text('Follow'), label:has-text('Connect'), label:has-text('newsletter')").all()
            for fb in follow_boxes:
                chk = fb.locator("input[type='checkbox']")
                if chk.count() > 0 and chk.is_checked():
                    chk.uncheck()
        except Exception:
            pass

        # Look for Submit / Review / Next buttons
        # Scroll inside modal to expose any Submit button that might be below the fold
        try:
            page.evaluate("""
                () => {
                    const modal = document.querySelector('[class*="jobs-easy-apply-modal"], [class*="artdeco-modal"], [role="dialog"]');
                    if (modal) modal.scrollTop = modal.scrollHeight;
                }
            """)
        except Exception:
            pass

        def find_modal_button(keywords: list[str]) -> object | None:
            for kw in keywords:
                try:
                    loc = page.locator(f"button[aria-label*='{kw}' i]").first
                    if loc.count() > 0:
                        # Use force=True for submit to bypass visibility check
                        return loc
                except Exception:
                    pass
            try:
                for btn in page.locator("button.artdeco-button--primary").all():
                    txt = (btn.text_content() or "").strip().lower()
                    if any(kw.lower() in txt for kw in keywords):
                        return btn
            except Exception:
                pass
            return None

        # Scan page buttons to understand what's available
        page_btns = page.evaluate("""
            () => Array.from(document.querySelectorAll('button.artdeco-button--primary, button[aria-label]'))
                       .filter(b => b.offsetParent !== null)
                       .map(b => ({text: (b.textContent||'').trim(), label: b.getAttribute('aria-label')||''}))
                       .slice(0, 8)
        """)

        submit_btn = find_modal_button(["Submit application", "Submit"])
        review_btn = find_modal_button(["Review your application", "Review"])
        next_btn   = find_modal_button(["Continue to next step", "Next", "Continue"])

        if step >= 2:
            print(f"    Step {step + 1}: buttons={[(b['text'][:20], b['label'][:20]) for b in page_btns]}")

        if submit_btn:
            try:
                submit_btn.scroll_into_view_if_needed()
                submit_btn.click(force=True)
            except Exception:
                submit_btn.click()
            print(f"    Step {step + 1}: Submitted application!")
            page.wait_for_timeout(3000)
            return True
        elif review_btn:
            # If we keep seeing Review button (stuck in loop), try to find and fix validation errors
            if step > 3:
                fixed = page.evaluate("""
                    () => {
                        let fixed = 0;
                        const nativeIS = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                        const nativeTA = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
                        const nativeSS = Object.getOwnPropertyDescriptor(window.HTMLSelectElement.prototype, 'value').set;

                        // LinkedIn custom error class + standard HTML invalid
                        const errSelectors = [
                            '.artdeco-inline-feedback--error',
                            'input[aria-invalid="true"]',
                            'input:invalid',
                            'select[aria-invalid="true"]',
                        ];
                        document.querySelectorAll(errSelectors.join(', ')).forEach(el => {
                            // For error containers, find the input inside
                            let inp = el;
                            if (!['INPUT','SELECT','TEXTAREA'].includes(el.tagName)) {
                                inp = el.closest('div.fb-dash-form-element, fieldset')?.querySelector('input:not([type="radio"]):not([type="checkbox"]), select, textarea') || null;
                            }
                            if (!inp) return;
                            if (inp.tagName === 'SELECT') {
                                const opts = Array.from(inp.options).filter(o => o.value && o.text !== 'Select an option');
                                if (opts.length) { try { nativeSS.call(inp, opts[0].value); } catch(e) { inp.value = opts[0].value; } inp.dispatchEvent(new Event('change',{bubbles:true})); fixed++; }
                            } else if (!inp.value.trim() && !inp.readOnly) {
                                const v = (inp.type === 'number') ? '5' : '10';
                                try { if (inp.tagName === 'TEXTAREA') { nativeTA.call(inp, v); } else { nativeIS.call(inp, v); } } catch(e) { inp.value = v; }
                                inp.dispatchEvent(new Event('input',{bubbles:true}));
                                inp.dispatchEvent(new Event('change',{bubbles:true}));
                                fixed++;
                            }
                        });
                        // Also fill any empty required text inputs
                        document.querySelectorAll('input[required]:not([type="radio"]):not([type="checkbox"]), textarea[required]').forEach(inp => {
                            if (inp.value.trim() || inp.readOnly || inp.disabled) return;
                            const v = inp.type === 'number' ? '5' : '10';
                            try { if (inp.tagName === 'TEXTAREA') { nativeTA.call(inp, v); } else { nativeIS.call(inp, v); } } catch(e) { inp.value = v; }
                            inp.dispatchEvent(new Event('input',{bubbles:true}));
                            inp.dispatchEvent(new Event('change',{bubbles:true}));
                            fixed++;
                        });
                        return fixed;
                    }
                """)
                if fixed:
                    print(f"    Step {step + 1}: Fixed {fixed} validation errors, retrying Review...")
                    page.wait_for_timeout(1000)
            review_btn.click()
            print(f"    Step {step + 1}: Reviewing...")
        elif next_btn:
            next_btn.click()
            print(f"    Step {step + 1}: Next step...")
        else:
            print(f"    Step {step + 1}: No navigation button found — stopping.")
            break

        time.sleep(0.5)

    return False


def submit_one(row: dict, idx: int) -> bool:
    """Submit a single application. Returns True on success."""
    company = row.get("Company", "Unknown")
    title = row.get("Job Title", "Unknown")
    raw_url = row.get("LinkedIn URL", "")
    easy_apply = row.get("Easy Apply", "").strip().lower()

    # Normalize to clean LinkedIn job URL (strip tracking params)
    job_id_match = re.search(r"/jobs/view/(\d+)", raw_url)
    url = f"https://www.linkedin.com/jobs/view/{job_id_match.group(1)}/" if job_id_match else raw_url

    print(f"\n[{idx}] {company} — {title}")

    if not url or "linkedin.com" not in url:
        print(f"  No LinkedIn URL — cannot auto-submit.")
        return False

    folder = find_app_folder(company, title)
    if not folder:
        print(f"  Application folder not found — skipping.")
        return False

    resume_pdf = folder / "resume.pdf"
    if not resume_pdf.exists():
        print(f"  resume.pdf not found in {folder} — skipping.")
        return False

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  Playwright not installed. Run: pip install playwright && playwright install chromium")
        return False

    LINKEDIN_PROFILE.mkdir(exist_ok=True)
    success = False

    with sync_playwright() as pw:
        context = pw.chromium.launch_persistent_context(
            str(LINKEDIN_PROFILE),
            headless=True,  # headless=False crashes when run from shell without display
            viewport={"width": 1280, "height": 900},
            slow_mo=100,
        )
        page = context.new_page()
        try:
            print(f"  Navigating to {url}")
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(4000)
            # Scroll slightly to trigger lazy-loaded content
            page.evaluate("window.scrollBy(0, 300)")

            # Check if we're logged in
            if "login" in page.url or "authwall" in page.url:
                print("  LinkedIn session expired. Run the scraper once to refresh the session.")
                return False

            success = submit_easy_apply(page, resume_pdf, row)

            if success:
                # Dismiss any success dialog
                try:
                    dismiss = page.locator("button[aria-label='Dismiss'], button:has-text('Done')").first
                    if dismiss.count() > 0:
                        dismiss.click()
                except Exception:
                    pass
            else:
                print("  Application may not have been submitted — check the browser.")
                time.sleep(5)  # Give user a moment to see the state

        except Exception as e:
            print(f"  Error during submission: {e}")
        finally:
            context.close()

    return success


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Submit LinkedIn Easy Apply applications")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--ids", nargs="+", type=int, help="Tracker row indices (0-based) to submit")
    group.add_argument("--all-tailored", action="store_true", help="Submit all rows with status 'Tailored'")
    args = parser.parse_args()

    rows = read_tracker()
    if not rows:
        print("No applications in tracker.")
        return

    if args.all_tailored:
        targets = [(i, r) for i, r in enumerate(rows) if r.get("Application Status") == "Tailored"]
    else:
        targets = [(i, rows[i]) for i in args.ids if i < len(rows)]

    if not targets:
        print("No matching applications to submit.")
        return

    # All LinkedIn targets are attempted; non-LinkedIn are manual
    linkedin_targets = [t for t in targets if "linkedin.com" in t[1].get("LinkedIn URL", "")]
    manual_targets = [t for t in targets if "linkedin.com" not in t[1].get("LinkedIn URL", "")]

    print(f"Submitting {len(linkedin_targets)} LinkedIn + {len(manual_targets)} manual application(s).\n")
    print("=" * 60)

    submitted = []
    failed = []

    for idx, row in linkedin_targets:
        ok = submit_one(row, idx)
        if ok:
            rows[idx]["Application Status"] = "Applied"
            rows[idx]["Date Applied"] = datetime.now().strftime("%Y-%m-%d")
            # Set follow-up date 7 days out
            from datetime import timedelta
            rows[idx]["Follow Up Date"] = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
            write_tracker(rows)
            submitted.append(f"{row.get('Company')} / {row.get('Job Title')}")
        else:
            failed.append(f"{row.get('Company')} / {row.get('Job Title')}")

    for idx, row in manual_targets:
        print(f"\n[{idx}] {row.get('Company')} — {row.get('Job Title')}")
        print(f"  Easy Apply: No — manual submission required.")
        print(f"  URL: {row.get('LinkedIn URL', 'N/A')}")
        folder = find_app_folder(row.get("Company", ""), row.get("Job Title", ""))
        if folder:
            print(f"  Resume: {folder / 'resume.pdf'}")
        failed.append(f"{row.get('Company')} / {row.get('Job Title')} (manual)")

    print("\n" + "=" * 60)
    print(f"Results: {len(submitted)} submitted, {len(failed)} skipped/failed.")
    if submitted:
        print("\nSubmitted:")
        for s in submitted:
            print(f"  + {s}")
    if failed:
        print("\nSkipped/failed:")
        for f in failed:
            print(f"  - {f}")


if __name__ == "__main__":
    main()
