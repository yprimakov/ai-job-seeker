"""
ATS Detector
============
Identifies which ATS is being used from the page URL.
Also provides a JS snippet for in-browser detection when the URL is ambiguous.

Supported: Greenhouse, Lever, Workday, Ashby, iCIMS, SmartRecruiters
"""

# URL substring patterns per ATS
_SIGNATURES: dict[str, list[str]] = {
    "greenhouse":      ["greenhouse.io", "job-boards.greenhouse.io"],
    "lever":           ["lever.co", "jobs.lever.co"],
    "workday":         ["myworkdayjobs.com", "wd1.myworkdayjobs.com", "wd3.myworkdayjobs.com"],
    "ashby":           ["ashbyhq.com", "jobs.ashbyhq.com"],
    "icims":           ["icims.com", "careers.icims.com"],
    "smartrecruiters": ["smartrecruiters.com"],
    "linkedin":        ["linkedin.com/jobs"],
}


def detect(url: str) -> str:
    """
    Detect ATS from a job posting URL.

    Returns one of:
        'greenhouse' | 'lever' | 'workday' | 'ashby' |
        'icims' | 'smartrecruiters' | 'linkedin' | 'unknown'
    """
    url_lower = url.lower()
    for ats_name, patterns in _SIGNATURES.items():
        if any(p in url_lower for p in patterns):
            return ats_name
    # Query-param fallbacks for white-labeled / custom-domain setups
    if "gh_jid=" in url_lower or "gh_src=" in url_lower:
        return "greenhouse"
    if "lever-source=" in url_lower or "lever_source=" in url_lower:
        return "lever"
    return "unknown"


# Injected into the browser when URL-based detection isn't conclusive.
# Returns the ATS name string directly from JS.
DETECT_JS = """
(function() {
    const url = window.location.href.toLowerCase();
    if (url.includes('greenhouse.io'))       return 'greenhouse';
    if (url.includes('lever.co'))            return 'lever';
    if (url.includes('myworkdayjobs.com'))   return 'workday';
    if (url.includes('ashbyhq.com'))         return 'ashby';
    if (url.includes('icims.com'))           return 'icims';
    if (url.includes('smartrecruiters.com')) return 'smartrecruiters';

    // DOM fallbacks for white-labeled / custom-domain setups
    if (document.querySelector('[data-automation-id="welcomeMenuDropDown"]')) return 'workday';
    if (document.querySelector('.ashby-job-posting-form'))                    return 'ashby';
    if (document.querySelector('#greenhouse-form'))                            return 'greenhouse';

    return 'unknown';
})()
"""
