"""Real OpenAI Agent orchestration for the job-agent project.

The LLM plans and selects tools; deterministic Python code performs job discovery,
matching and local state changes. Secrets stay server-side. Submission and
anti-bot controls are never exposed as agent tools.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from job_agent.config import load_profile, load_settings
from job_agent.seen_cache import SeenCache
from job_agent.store import load_job_record, save_search

SYSTEM = """You are Job Agent, a production-minded job-search assistant.

GOAL: find legitimate jobs that genuinely fit the candidate, explain the match,
prepare truthful application material, and guide the user through application.

RULES:
- Never invent experience, education, salary, authorization, certifications,
  metrics, dates, employers, or answers. Missing facts are UNKNOWN.
- Prefer official employer career pages and ATS sources. Respect rate limits,
  robots and site terms.
- Use tools for factual data; do not pretend a tool ran when it did not.
- Treat scoring as evidence, not truth. Show missing/uncertain requirements.
- On Android, the local Python process is the control plane and the browser
  extension is the visible form-filling plane.
- CAPTCHA, login, 2FA, legal attestations and unknown sensitive questions are
  STOP conditions for user action; never bypass them.
- There is NO submit tool. The final submission is always a human action.
- When a task is ambiguous, ask one concise question rather than guessing.
- Keep tool calls bounded: search at most 90 days and 100 returned jobs per call.
"""


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _safe_data_path(data_dir: Path, name: str) -> Path:
    root = data_dir.resolve()
    target = (root / name).resolve()
    if target != root and root not in target.parents:
        raise ValueError("path escapes data directory")
    return target


def build_agent(*, data_dir: Path, profile: Path):
    """Build an OpenAI Agents SDK Agent with lazy optional dependency loading."""
    try:
        from agents import Agent, function_tool
    except ImportError as exc:
        raise RuntimeError("Install agent support: pip install -e '.[phone-agent]'") from exc

    settings = load_settings()
    # The base CLI remains backward-compatible with Anthropic, but the Agent
    # should prefer OpenAI when the user supplied only an OpenAI key.
    if settings.provider == "anthropic" and settings.openai_api_key and not settings.anthropic_api_key:
        settings.provider = "openai"

    @function_tool
    def inspect_status() -> str:
        """Return runtime capabilities without exposing secrets."""
        return _json({
            "runtime": "android-phone",
            "provider": settings.provider,
            "model": settings.active_model(),
            "llm_configured": settings.has_llm_key(),
            "capabilities": [
                "job_discovery", "fit_scoring", "job_inspection",
                "candidate_facts", "application_preparation", "session_memory"
            ],
            "desktop_playwright": False,
            "automatic_submission": False,
        })

    @function_tool
    def search_jobs(days: int = 7, limit: int = 25) -> str:
        """Discover, filter, deduplicate and score jobs using the existing pipeline."""
        days = max(1, min(int(days), 90))
        limit = max(1, min(int(limit), 100))
        prof = load_profile(profile)
        from datetime import timedelta
        from job_agent import search
        from job_agent.scoring import score_jobs

        cache = SeenCache(_safe_data_path(data_dir, "seen.json"))
        outcome = search.run(prof, seen_cache=cache, fresh_window=timedelta(days=days))
        if not outcome.jobs:
            return _json({"ok": True, "count": 0, "warnings": outcome.warnings,
                          "pipeline": outcome.counts.model_dump()})
        scored = score_jobs(outcome.jobs, settings, prof, method="structured")
        save_search(
            scored, outcome.boards, _safe_data_path(data_dir, "last_search.json"),
            first_seen=outcome.first_seen, new_job_ids=outcome.new_job_ids,
            baseline=outcome.baseline_scan, sources_queried=len(outcome.per_source),
        )
        ranked = sorted(scored, key=lambda item: item.sort_key, reverse=True)[:limit]
        return _json({
            "ok": True,
            "count": len(ranked),
            "pipeline": outcome.counts.model_dump(),
            "warnings": outcome.warnings,
            "jobs": [
                {
                    "id": s.job.id, "title": s.job.title, "company": s.job.company,
                    "location": s.job.location, "source": s.job.source,
                    "url": s.job.url, "apply_url": s.job.apply_url,
                    "score": s.score, "verdict": s.verdict,
                    "reasons": list(s.reasons),
                    "missing_requirements": list(s.missing_requirements),
                }
                for s in ranked
            ],
        })

    @function_tool
    def get_job(job_id: str) -> str:
        """Read one previously discovered job without changing state."""
        record = load_job_record(_safe_data_path(data_dir, "last_search.json"), job_id)
        if record is None:
            return _json({"ok": False, "error": "job_not_found", "job_id": job_id})
        return _json(record)

    @function_tool
    def get_candidate_facts() -> str:
        """Read the candidate fact sheet used for truthful tailoring; secrets are excluded."""
        path = _safe_data_path(data_dir, "career_facts.yaml")
        if not path.exists():
            return _json({"ok": False, "error": "candidate_facts_missing",
                          "next": "Create data/career_facts.yaml from the template before tailoring."})
        return _json({"ok": True, "facts": path.read_text(encoding="utf-8")[:30000]})

    @function_tool
    def prepare_application(job_id: str) -> str:
        """Create a review-only application plan; never opens, fills or submits a form."""
        record = load_job_record(_safe_data_path(data_dir, "last_search.json"), job_id)
        if record is None:
            return _json({"ok": False, "error": "job_not_found", "job_id": job_id})
        return _json({
            "ok": True,
            "job": {k: record.get(k) for k in
                    ("id", "title", "company", "location", "url", "apply_url", "source")},
            "steps": [
                "Open the stored application URL in the Android browser.",
                "Use the extension to map visible fields to verified candidate facts.",
                "Stop on CAPTCHA/login/2FA/unknown sensitive question.",
                "Review all fields and the job-specific motivation letter.",
                "User performs the final submission.",
            ],
            "requires_user_review": True,
            "automatic_submission": False,
        })

    return Agent(
        name="Job Agent",
        model=settings.active_model(),
        instructions=SYSTEM,
        tools=[inspect_status, search_jobs, get_job, get_candidate_facts, prepare_application],
    )
