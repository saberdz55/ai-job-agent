# job-agent

An AI job-hunting agent. It discovers roles freshly posted on companies' public
Applicant Tracking System (ATS) boards, filters them to what you actually want,
and uses an LLM to score how well each one fits you — then prints a ranked table.

> **Status: Slices 1–4 shipped, plus a local dashboard, Chrome extension, and a
> production-oriented OpenAI Agent runtime for Android/Pydroid.**

## Real OpenAI Agent on Android/Pydroid

The Agent runtime is separate from the deterministic job pipeline: the model
plans and selects bounded Python tools while the local process performs the real
work. The Agent has persistent SQLite session memory and a localhost-only HTTP
bridge for a phone UI. The OpenAI API key remains server-side and is never sent
to the browser/extension.

The Agent intentionally has **no submit tool**. It can discover jobs, inspect
matches, read verified candidate facts, and prepare an application plan. CAPTCHA,
login, 2FA, legal attestations, and unknown sensitive questions remain human
stop conditions; final submission stays with the user.

### Agent setup

```bash
cp .env.example .env
# Required for the Agent runtime:
# JOB_AGENT_PROVIDER=openai
# OPENAI_API_KEY=...
# OPENAI_MODEL=gpt-5.6-luna

cp search_profile.example.yaml search_profile.yaml
pip install -e '.[phone-agent]'
python -m job_agent.agent_cli
```

For the phone HTTP bridge:

```bash
python -m job_agent.agent_server --host 127.0.0.1 --port 8643
```

The bridge exposes `/api/agent/health` and `/api/agent/chat`. Session history is
stored in `data/agent_sessions.db`, so restarting Pydroid does not erase the
conversation. Requests for the same session are serialized to prevent SQLite
history races.

The default `.env.example` still uses Anthropic because the original CLI search
pipeline supports both providers. **The OpenAI Agent runtime requires
`JOB_AGENT_PROVIDER=openai` and `OPENAI_API_KEY`.**

## Why this exists

Company career pages are backed by a handful of ATS vendors that expose **public,
no-auth JSON APIs**. Instead of scraping aggregators (which violates their terms),
`job-agent` reads these official endpoints directly, normalizes every board into
one shape, keeps only recently posted roles (default: the last 30 days) that match
your keywords and location, and spends an LLM call only on those survivors.

**Deliberate constraints:**

- **No scraping of LinkedIn / Indeed / Dice.** Discovery has two modes, both
official public APIs: **per-company** ATS board endpoints (Greenhouse, Lever,
Ashby, SmartRecruiters) enumerated from the board list in your profile, and
**cross-company** query sources (SmartRecruiters search, Remotive, RemoteOK)
that return jobs from many companies per keyword. Greenhouse/Lever/Ashby have
no cross-company index, so the `discover` subcommand grows the board list by
validating candidate company tokens against those same official APIs.
- **Application submission is never done via ATS APIs** (those submit endpoints
need the employer's private key). Submission is browser-based and always stops
at a human-approval gate.
- **Secrets and personal data are gitignored** (`.env`, `/data`, resume files).

## Quick start

The CLI has six subcommands — `search`, `tailor`, `apply`, `applications`,
`dashboard`, and `discover`. A bare invocation with no subcommand defaults to
`search`. The separate Agent entrypoint is `job-agent-agent` / `python -m
job_agent.agent_cli`.

### Demo mode — no API key, no network

```bash
pip install -e .
playwright install chromium            # one-time, only needed for CLI `apply` and
                                       # the dashboard's controlled-window flow
python -m job_agent search --demo
python -m job_agent tailor --demo
python -m job_agent apply  --demo
```

`search --demo` runs the whole discovery pipeline against bundled mock jobs.
`tailor --demo` tailors a committed fake resume to a fake job and writes an
ATS-safe sample PDF + DOCX. `apply --demo` uses a local fake form only.

## Real run

```bash
cp .env.example .env                                  # add provider key
cp search_profile.example.yaml search_profile.yaml    # edit roles / companies / location
cp data/answer_bank.example.yaml data/answer_bank.yaml # fill your real apply answers
python -m job_agent search
python -m job_agent tailor --job <ID>
python -m job_agent apply  --job <ID>
python -m job_agent dashboard
python -m job_agent applications
python -m job_agent discover
```

`search` fetches live jobs from the boards in `search_profile.yaml`, filters to
the recency window, scores each survivor, prints them ranked, and saves the run
to `data/last_search.json`.

## Architecture

```text
sources/ (official ATS APIs + cross-company sources)
   │
   ▼
search.py → filters → dedup → experience
   │
   ▼
scoring.py → ScoredJob
   │
   ├──────────────► CLI / dashboard
   │
   └──────────────► OpenAI Agent
                         │
                         ├─ search_jobs
                         ├─ get_job
                         ├─ get_candidate_facts
                         └─ prepare_application
                                  │
                                  ▼
                         Android browser/extension
                                  │
                                  ▼
                            HUMAN FINAL SUBMIT
```

The rest of this README documents the existing deterministic search, tailoring,
and assisted-apply slices.
