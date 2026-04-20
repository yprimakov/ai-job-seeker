"""
auth_linkedin.py - Launch headed browser to refresh LinkedIn session cookies.
Run this on the local machine, log in to LinkedIn. The script polls for login
completion automatically and exits when the session is detected.
Cookies persist in ~/.job-seeker-linkedin for use by the scraper and submitter.
"""
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

LINKEDIN_PROFILE = Path.home() / ".job-seeker-linkedin"
MAX_WAIT_SECONDS = 600

with sync_playwright() as pw:
    context = pw.chromium.launch_persistent_context(
        str(LINKEDIN_PROFILE),
        headless=False,
        viewport={"width": 1280, "height": 900},
    )
    page = context.new_page()
    page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")
    print("\n>>> Log in to LinkedIn in the browser window.")
    print(">>> Script will auto-detect login completion (checking every 3s, max 10 min).\n")

    deadline = time.time() + MAX_WAIT_SECONDS
    detected = False
    while time.time() < deadline:
        time.sleep(3)
        try:
            cookies = context.cookies("https://www.linkedin.com")
            li_at = next((c for c in cookies if c["name"] == "li_at"), None)
            url = page.url
            if li_at and "login" not in url and "checkpoint" not in url:
                detected = True
                print(f"[ok] Login detected at {url}")
                break
            else:
                print(f"    waiting... url={url[:80]} li_at={'yes' if li_at else 'no'}")
        except Exception as e:
            print(f"    poll error: {e}")

    if detected:
        try:
            page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2000)
        except Exception:
            pass
        cookies = context.cookies()
        li_at = next((c for c in cookies if c["name"] == "li_at"), None)
        if li_at:
            print(f"[ok] li_at cookie saved (expires: {li_at.get('expires', 'session')})")
        print(f"[ok] Profile saved to: {LINKEDIN_PROFILE}")
    else:
        print("[warn] Timed out waiting for login. Profile may not be authenticated.")

    context.close()
