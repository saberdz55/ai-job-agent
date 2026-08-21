# job-agent

An AI job-hunting agent. It discovers roles freshly posted on companies' public Applicant Tracking System (ATS) boards, filters them to what you actually want, and uses deterministic scoring plus an LLM agent to rank, inspect and prepare applications.

> **Status: deterministic search + assisted application + hardened OpenAI Agent runtime + least-privilege MCP control plane.**

## Production Agent

The Agent runtime is separate from the deterministic job pipeline: the model plans and selects bounded Python tools while the local process performs the real work. It has persistent SQLite session memory and an authenticated localhost HTTP bridge. The OpenAI API key remains server-side and is never sent to the browser/extension.

The Agent has **no final-submit tool**. It can discover jobs, inspect matches, read verified candidate facts, and prepare an application plan. CAPTCHA, login, 2FA, legal attestations, sensitive questions, and unknown fields are human stop conditions. Never bypass anti-bot controls, authentication, rate limits, robots rules, access controls, or site security.

### Agent setup

```bash
cp .env.example .env
# Required:
# JOB_AGENT_PROVIDER=openai
# OPENAI_API_KEY=...
# OPENAI_MODEL=gpt-5.6-luna
# JOB_AGENT_TOKEN=<strong random local gateway token>

cp search_profile.example.yaml search_profile.yaml
pip install -e '.[phone-agent]'
python -m job_agent.agent_cli
```

Generate a gateway token with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

For the authenticated local HTTP bridge:

```bash
python -m job_agent.agent_server --host 127.0.0.1 --port 8643
```

The bridge exposes `/api/agent/health`, `/api/agent/chat`, and a preview-only browser endpoint. Every bridge request requires `Authorization: Bearer <JOB_AGENT_TOKEN>`. The Chrome extension stores only this local gateway token in extension storage; it never receives the OpenAI API key.

Session history is stored in `data/agent_sessions.db`, so restarting the local process does not erase the conversation. Requests for the same session are serialized to prevent SQLite history races.

## ChatGPT / MCP control plane

The repository also contains a least-privilege MCP server in `job_agent.mcp_server`. It exposes only:

- `agent_status`
- `search_jobs`
- `inspect_job`
- `candidate_facts_status`
- `prepare_application`

It does **not** expose arbitrary shell, filesystem, credentials, browser JavaScript, or final submission. This is deliberate: the MCP layer is a control plane, not a privilege escalation layer.

Install it with:

```bash
pip install -e '.[phone-agent,mcp]'
```

Local stdio mode:

```bash
JOB_AGENT_MCP_TRANSPORT=stdio job-agent-mcp
```

For Streamable HTTP, keep it localhost-only during development:

```bash
JOB_AGENT_MCP_TRANSPORT=streamable-http job-agent-mcp
```

Do not expose the HTTP endpoint directly to the Internet. For a real ChatGPT connection, put the MCP endpoint behind HTTPS and an authenticated deployment/reverse proxy, then configure the ChatGPT/MCP integration with that public endpoint. Streamable HTTP is the current recommended MCP transport; SSE is legacy/deprecated. See the OpenAI Agents MCP guidance and MCP Python SDK deployment guidance.

## Security model

- External job pages and search results are untrusted data; embedded instructions are not agent authority.
- Candidate facts are the source of truth. Missing facts remain UNKNOWN.
- Sponsorship, right-to-work, identity, immigration and legal attestations always require human review.
- The browser bridge is localhost-only and bearer-token authenticated.
- The MCP surface is least privilege and contains no submit operation.
- No credential, CAPTCHA, anti-bot, rate-limit, robots, or access-control bypass exists.
- Output is checked for obvious authentication-secret leakage before display.
- Path traversal outside the configured data directory is rejected.
- Agent turns are bounded to prevent runaway tool loops.
- OpenAI Agent tracing/guardrail capabilities can be used for debugging and production monitoring.

## Browser layer

Desktop Playwright is optional. The worker can inspect and fill only explicitly verified candidate facts and returns an audit report. It stops on CAPTCHA/login and never submits the form. The extension is a preview/inspection bridge, not an unrestricted browser controller.

## Why this exists

Company career pages are backed by a handful of ATS vendors that expose public, no-auth JSON APIs. Instead of scraping aggregators, `job-agent` reads official endpoints directly, normalizes every board into one shape, keeps only recently posted roles that match your keywords and location, and spends an LLM call only on survivors.

**Deliberate constraints:**

- **No scraping of LinkedIn / Indeed / Dice.** Discovery uses official ATS APIs and supported cross-company sources.
- **Application submission is never done via ATS APIs.** Browser-based application remains human-controlled.
- **Secrets and personal data are gitignored** (`.env`, `/data`, resume files).

## Quick start

```bash
pip install -e .
python -m job_agent search --demo
```

For the real Agent, use the setup above and keep `JOB_AGENT_TOKEN` secret.
