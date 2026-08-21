"""OpenAI-controlled orchestration layer for job-agent.

The phone process hosts this agent; OpenAI provides the reasoning loop while
local Python tools perform deterministic operations. The model never receives
secrets, never gets a raw arbitrary shell, and never gets an automatic submit
capability. Submission is an explicit human-only action.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from job_agent.store import load_job_record


SYSTEM = """You are Job Agent, a cautious job-search and application assistant.
Your job is to find relevant legitimate vacancies, explain why they fit, tailor
only truthful application material, and prepare applications for the user.
Never invent experience, education, salary, work authorization, certifications,
metrics, or answers. Never bypass CAPTCHA, authentication, anti-bot controls,
or application safeguards. Never submit an application yourself. Before any
potentially consequential application action, present what will happen and
require the user to confirm it in the UI.
Prefer official employer/ATS sources and respect robots, rate limits, and terms.
On Android phone mode, use the browser/extension path rather than Playwright.
"""


def _safe_path(value: str | Path, root: Path) -> Path:
    p = Path(value).resolve()
    root = root.resolve()
    if p != root and root not in p.parents:
        raise ValueError("path escapes the job-agent data directory")
    return p


def build_agent(*, data_dir: Path, profile: Path):
    """Build an OpenAI Agents SDK agent. Import is lazy so phone demo mode
    still works without the optional SDK installed."""
    try:
        from agents import Agent
        from agents import function_tool
    except ImportError as exc:
        raise RuntimeError("Install the phone agent extras: pip install -e '.[phone-agent]'") from exc

    @function_tool
    def inspect_status() -> str:
        """Return the local agent mode and available capabilities."""
        return json.dumps({
            "mode": "android-phone" if Path(__file__).exists() else "unknown",
            "capabilities": ["search", "score", "tailor", "track", "browser_prepare"],
            "automatic_submission": False,
        })

    @function_tool
    def search_jobs(days: int = 7, limit: int = 25) -> str:
        """Run the existing deterministic job search pipeline and return its text result."""
        from argparse import Namespace
        from rich.console import Console
        from job_agent.cli import cmd_search
        days = max(1, min(int(days), 90))
        limit = max(1, min(int(limit), 100))
        ns = Namespace(demo=False, profile=str(profile), days=days,
                       max_age_hours=None, limit=limit, method="structured",
                       include_applied=False)
        console = Console(record=True, width=120)
        code = cmd_search(console, ns)
        return console.export_text() + f"\nexit_code={code}"

    @function_tool
    def get_job(job_id: str) -> str:
        """Read one job from the saved search without modifying it."""
        record = load_job_record(data_dir / "last_search.json", job_id)
        if record is None:
            return json.dumps({"error": "job_not_found", "job_id": job_id})
        return json.dumps(record, ensure_ascii=False, default=str)

    @function_tool
    def tailor_job(job_id: str) -> str:
        """Tailor a truthful ATS-safe resume for a selected saved job."""
        from job_agent.cli import cmd_tailor
        from argparse import Namespace
        from rich.console import Console
        facts = data_dir / "career_facts.yaml"
        out_dir = data_dir / "output"
        out_dir.mkdir(parents=True, exist_ok=True)
        ns = Namespace(demo=False, job=job_id, facts=str(facts), jd=None,
                       out_dir=str(out_dir))
        console = Console(record=True, width=120)
        code = cmd_tailor(console, ns)
        return console.export_text() + f"\nexit_code={code}"

    @function_tool
    def prepare_application(job_id: str) -> str:
        """Prepare a human-reviewable application plan; never fills or submits."""
        record = load_job_record(data_dir / "last_search.json", job_id)
        if record is None:
            return json.dumps({"error": "job_not_found", "job_id": job_id})
        return json.dumps({
            "ok": True,
            "job": {k: record.get(k) for k in ("id", "title", "company", "location", "apply_url")},
            "next_step": "Open the application in the user's Android browser and use the extension.",
            "requires_user_review": True,
            "automatic_submission": False,
        }, ensure_ascii=False)

    return Agent(
        name="Job Agent",
        model="gpt-5.6-luna",
        instructions=SYSTEM,
        tools=[inspect_status, search_jobs, get_job, tailor_job, prepare_application],
    )
