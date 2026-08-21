"""Reliable, provider-neutral LLM fit scoring.

The deterministic search filters run first. Only surviving jobs reach the model.
Both Anthropic and OpenAI use structured JSON output; malformed/failed calls are
retried once and then become ``unscored`` instead of crashing the entire run.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from job_agent.config import SearchProfile, Settings
from job_agent.llm import openai_json
from job_agent.models import Job, ScoredJob

SCORE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "score": {"type": "integer"},
        "verdict": {"type": "string", "enum": ["strong", "possible", "skip"]},
        "reasons": {"type": "array", "items": {"type": "string"}},
        "missing_requirements": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["score", "verdict", "reasons", "missing_requirements"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = (
    "You are a precise technical recruiter. Judge job fit using only the supplied "
    "candidate information and job posting. Do not invent experience, education, "
    "skills, sponsorship, salary, or eligibility. A missing fact is unknown, not yes. "
    "Return only the requested structured assessment."
)

Method = Literal["structured", "tool"]


def build_user_prompt(job: Job, profile: SearchProfile) -> str:
    return (
        f"CANDIDATE:\n{profile.candidate_summary.strip()}\n\n"
        f"JOB:\n"
        f"- Title: {job.title}\n"
        f"- Company: {job.company}\n"
        f"- Location: {job.location} (remote={job.remote}, country={job.country})\n"
        f"- Description: {job.description or '(no description available)'}\n\n"
        "Return score 0-100, verdict strong|possible|skip, short reasons, and "
        "missing_requirements. Treat ambiguous requirements conservatively."
    )


def _coerce(job: Job, data: dict[str, Any]) -> ScoredJob:
    score = data.get("score")
    if isinstance(score, bool) or not isinstance(score, int):
        raise ValueError("score is not an integer")
    score = max(0, min(100, score))
    verdict = data.get("verdict")
    if verdict not in {"strong", "possible", "skip"}:
        raise ValueError(f"bad verdict: {verdict!r}")
    reasons = tuple(str(r) for r in data.get("reasons", []))
    missing = tuple(str(r) for r in data.get("missing_requirements", []))
    return ScoredJob(job=job, score=score, verdict=verdict,
                     reasons=reasons, missing_requirements=missing)


def _call_anthropic_structured(client, model: str, job: Job, profile: SearchProfile) -> str:
    resp = client.messages.create(
        model=model,
        max_tokens=512,
        system=SYSTEM_PROMPT,
        output_config={"format": {"type": "json_schema", "schema": SCORE_SCHEMA}},
        messages=[{"role": "user", "content": build_user_prompt(job, profile)}],
    )
    return next((b.text for b in resp.content if b.type == "text"), "")


def _call_anthropic_tool(client, model: str, job: Job, profile: SearchProfile) -> str:
    resp = client.messages.create(
        model=model,
        max_tokens=512,
        system=SYSTEM_PROMPT,
        tools=[{"name": "record_fit", "description": "Record job fit.",
                 "input_schema": SCORE_SCHEMA}],
        tool_choice={"type": "tool", "name": "record_fit"},
        messages=[{"role": "user", "content": build_user_prompt(job, profile)}],
    )
    for block in resp.content:
        if block.type == "tool_use":
            return json.dumps(block.input)
    return ""


def _call_openai(client, model: str, job: Job, profile: SearchProfile) -> str:
    return openai_json(client, model=model, system=SYSTEM_PROMPT,
                       user=build_user_prompt(job, profile),
                       schema=SCORE_SCHEMA, name="job_fit")


def score_one(client, model: str, job: Job, profile: SearchProfile, *,
              method: Method = "structured", provider: str = "anthropic") -> ScoredJob:
    """Score one job with bounded retry and a safe unscored fallback."""
    if provider == "openai":
        call = _call_openai
    elif method == "tool":
        call = _call_anthropic_tool
    else:
        call = _call_anthropic_structured

    last_error = "unknown error"
    for attempt in (1, 2):
        try:
            raw = call(client, model, job, profile)
            return _coerce(job, json.loads(raw))
        except Exception as exc:
            last_error = str(exc)[:300] or exc.__class__.__name__
            if attempt == 2:
                return ScoredJob(
                    job=job,
                    verdict="unscored",
                    reasons=(f"LLM scoring failed safely: {last_error}",),
                )
    return ScoredJob(job=job, verdict="unscored")


def score_jobs(jobs: list[Job], settings: Settings, profile: SearchProfile, *,
               method: Method = "structured", client=None) -> list[ScoredJob]:
    """Score every job. ``client`` remains injectable for deterministic tests."""
    if client is None:
        from job_agent.llm import create_client
        client = create_client(settings.provider,
                               anthropic_api_key=settings.anthropic_api_key,
                               openai_api_key=settings.openai_api_key)
    model = settings.active_model()
    return [score_one(client, model, job, profile, method=method,
                      provider=settings.provider) for job in jobs]
