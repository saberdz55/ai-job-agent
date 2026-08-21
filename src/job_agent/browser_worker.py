"""Optional desktop browser worker for ATS/application pages.

It can inspect and fill only verified candidate facts. It never submits forms and
stops when CAPTCHA/login/2FA or sensitive consent fields are detected.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from job_agent.application_guard import classify_field, propose_field


@dataclass(frozen=True)
class BrowserInspection:
    url: str
    title: str
    forms: int
    fields: int
    has_captcha: bool
    login_detected: bool
    blocked: bool


def inspect_html(html: str, url: str = "", title: str = "") -> BrowserInspection:
    lower = html.lower()
    has_captcha = any(x in lower for x in ("captcha", "recaptcha", "hcaptcha"))
    login = any(x in lower for x in ("sign in", "log in", "create account", "type=\"password\""))
    forms = lower.count("<form")
    fields = sum(lower.count(f"<{tag}") for tag in ("input", "select", "textarea"))
    return BrowserInspection(url, title, forms, fields, has_captcha, login, has_captcha or login)


async def fill_verified_fields(page: Any, facts: dict[str, object]) -> dict[str, object]:
    """Fill safe, explicitly verified fields and return an audit report.

    The page is never submitted. Unknown fields, credentials, CAPTCHA and legal
    attestations remain untouched for the user.
    """
    text = (await page.locator("body").inner_text())[:20000].lower()
    if any(x in text for x in ("captcha", "recaptcha", "hcaptcha")):
        return {"ok": False, "blocked": "captcha", "filled": [], "skipped": []}
    if any(x in text for x in ("sign in", "log in", "create account")):
        return {"ok": False, "blocked": "login", "filled": [], "skipped": []}

    filled: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []
    locators = page.locator("input, select, textarea")
    count = min(await locators.count(), 200)
    for i in range(count):
        el = locators.nth(i)
        try:
            label = await el.get_attribute("aria-label") or ""
            name = await el.get_attribute("name") or ""
            placeholder = await el.get_attribute("placeholder") or ""
            category = classify_field(f"{label} {placeholder}", name)
            proposal = propose_field(f"{label} {placeholder}", name, facts)
            if proposal.status != "VERIFIED":
                skipped.append({"field": label or placeholder or name, "status": proposal.status})
                continue
            input_type = (await el.get_attribute("type") or "text").lower()
            if input_type in {"password", "file", "hidden"} or category in {"sponsorship", "work_authorization"}:
                skipped.append({"field": label or placeholder or name, "status": "REVIEW"})
                continue
            await el.fill(proposal.value or "")
            filled.append({"field": label or placeholder or name, "category": category})
        except Exception:
            skipped.append({"field": str(i), "status": "ERROR"})
    return {"ok": True, "blocked": None, "filled": filled, "skipped": skipped, "submitted": False}
