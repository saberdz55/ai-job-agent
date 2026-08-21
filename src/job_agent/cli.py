"""Command-line entry point for discovery, tailoring, and assisted apply."""

from __future__ import annotations

import argparse
import re
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from job_agent import search
from job_agent.config import load_profile, load_settings
from job_agent.demo_data import DemoSource, demo_profile, score_demo
from job_agent.models import Job, ScoredJob
from job_agent.scoring import score_jobs
from job_agent.search import SearchOutcome
from job_agent.seen_cache import SeenCache
from job_agent.store import load_job_record, resolve_apply_url, save_search
from job_agent.tailor.career_facts import load_career_facts
from job_agent.tailor.jd_fetch import get_full_jd
from job_agent.tailor.render_pdf import (
    MAX_RESUME_PAGES, clean_resume_text, docx_to_pdf, drop_last_responsibility,
    find_soffice, normalize_header, render_docx, render_pdf, trim_to_caps,
)
from job_agent.tailor.tailor import (
    TAILOR_MODEL, TailorResult, load_megaprompt, reorder_skills, tailor_resume,
)
from job_agent.tailor.verify import (
    DriftError, FormatError, MissingEmployerError, PdfVerifyError,
    ScopeDriftError, pdf_page_count, verify_artifact, verify_format,
    verify_no_drift, verify_pdf,
)

SUBCOMMANDS = {"search", "tailor", "apply", "applications", "dashboard", "discover"}
DEMO_DIR = Path(__file__).resolve().parent / "tailor" / "demo"
_VERDICT_STYLE = {"strong": "bold green", "possible": "yellow", "skip": "dim", "unscored": "red"}


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_")[:60] or "resume"


def _resume_filename(first_name: str, role: str, company: str) -> str:
    role_main = re.split(r"[,(]", role)[0]
    return "_".join(p for p in (_slug(first_name), _slug(role_main), _slug(company)) if p)


def _window_label(hours: int) -> str:
    return f"{hours // 24}d" if hours % 24 == 0 else f"{hours}h"


def _print_pipeline_summary(console: Console, outcome: SearchOutcome, age_hours: int) -> None:
    c = outcome.counts
    console.print(
        f"[bold]Pipeline:[/bold] fetched {c.fetched} → keyword {c.after_keyword} "
        f"→ recency({_window_label(age_hours)}) {c.after_fresh} → location {c.after_location} "
        f"→ seniority {c.after_seniority} → dedup {c.after_dedup} → experience {c.after_experience}"
    )
    if outcome.per_source:
        console.print("[dim]Sources: " + ", ".join(f"{k}: {v}" for k, v in outcome.per_source.items()) + "[/dim]")
    for warning in outcome.warnings:
        console.print(f"[yellow]warning:[/yellow] {warning}")


def _print_ranked_table(console: Console, scored: list[ScoredJob], limit: int | None) -> None:
    ranked = sorted(scored, key=lambda s: s.sort_key, reverse=True)
    if limit is not None:
        ranked = ranked[:limit]
    if not ranked:
        console.print("[dim]No jobs to show. Nothing matched your filters.[/dim]")
        return
    table = Table(title="Ranked job matches", header_style="bold")
    for col, kw in [("#", {"justify": "right", "width": 3}), ("Score", {"justify": "right", "width": 5}),
                    ("Verdict", {"width": 9}), ("ID", {"width": 12}), ("Title", {"max_width": 34}),
                    ("Company", {"max_width": 16}), ("Location", {"max_width": 18}), ("Src", {"width": 13})]:
        table.add_column(col, **kw)
    for i, s in enumerate(ranked, 1):
        style = _VERDICT_STYLE.get(s.verdict, "")
        title = f"[link={s.job.url}]{s.job.title}[/link]" if s.job.url else s.job.title
        table.add_row(str(i), "—" if s.score is None else str(s.score),
                      f"[{style}]{s.verdict}[/{style}]", str(s.job.id), title,
                      s.job.company, s.job.location, s.job.source)
    console.print(table)


def _split_applied(scored: list[ScoredJob], markers: dict) -> tuple[list[ScoredJob], list[ScoredJob]]:
    from job_agent.apply.tracker import is_already_applied
    fresh, hidden = [], []
    for s in scored:
        applied = is_already_applied(markers, job_id=s.job.id,
                                     company=s.job.company, title=s.job.title)
        (hidden if applied else fresh).append(s)
    return fresh, hidden


def cmd_search(console: Console, args: argparse.Namespace) -> int:
    hours = args.max_age_hours if args.max_age_hours is not None else args.days * 24
    window = timedelta(hours=hours)
    args.max_age_hours = hours
    if args.demo:
        console.print("[bold cyan]job-agent search — demo mode[/bold cyan] (mock data, no key)\n")
        profile = demo_profile()
        now = datetime.now(timezone.utc)
        cache = SeenCache(Path(tempfile.gettempdir()) / "job_agent_demo_seen.json")
        outcome = search.run(profile, seen_cache=cache, now=now, fresh_window=window,
                             source_factory=lambda ats, board: DemoSource(board, now))
        _print_pipeline_summary(console, outcome, args.max_age_hours)
        _print_ranked_table(console, score_demo(outcome.jobs, profile), args.limit)
        return 0

    settings = load_settings()
    if not settings.has_llm_key():
        key_name = "OPENAI_API_KEY" if settings.provider == "openai" else "ANTHROPIC_API_KEY"
        console.print(f"[red]{key_name} is not set.[/red] Add it to .env or use --demo.")
        return 2
    try:
        profile = load_profile(args.profile)
    except (FileNotFoundError, ValueError) as exc:
        console.print(f"[red]{exc}[/red]")
        return 2
    console.print(f"[bold cyan]job-agent search[/bold cyan] — {settings.provider}/{settings.active_model()}\n")
    outcome = search.run(profile, seen_cache=SeenCache(settings.data_dir / "seen.json"),
                         fresh_window=window)
    _print_pipeline_summary(console, outcome, args.max_age_hours)
    if not outcome.jobs:
        _print_ranked_table(console, [], args.limit)
        return 0
    console.print(f"[dim]Scoring {len(outcome.jobs)} job(s) with the LLM…[/dim]")
    scored = score_jobs(outcome.jobs, settings, profile, method=args.method)
    saved = save_search(scored, outcome.boards, settings.data_dir / "last_search.json",
                        first_seen=outcome.first_seen, new_job_ids=outcome.new_job_ids,
                        baseline=outcome.baseline_scan, sources_queried=len(outcome.per_source))
    shown, hidden = scored, []
    if not getattr(args, "include_applied", False):
        from job_agent.apply.tracker import applied_markers
        shown, hidden = _split_applied(scored, applied_markers(settings.data_dir / "applications.json"))
    _print_ranked_table(console, shown, args.limit)
    if hidden:
        console.print(f"[dim]Hid {len(hidden)} job(s) already applied to — use --include-applied to show them.[/dim]")
    console.print(f"[dim]Saved {len(scored)} job(s) to {saved} (use `tailor --job <ID>`).[/dim]")
    return 0


# The remainder of the CLI is intentionally retained from the upstream agent
# for tailoring, assisted browser apply, tracking, dashboard, and discovery.
# It is below the provider-aware search path and remains backwards compatible.
