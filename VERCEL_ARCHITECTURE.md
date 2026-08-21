# Vercel control-plane architecture

This project has two runtimes by design:

1. **Vercel control plane** — public HTTPS API/MCP, durable workflow orchestration, job state, schedules, and ChatGPT integration.
2. **Desktop browser worker** — runs on the user's computer because the real Chrome profile and Playwright session must live where the browser is. Vercel is not the place to keep a user's interactive Chrome profile.

## Target flow

```text
ChatGPT
  -> authenticated MCP / HTTPS
  -> Vercel control plane
  -> durable Job Application Workflow
  -> browser-worker command
  -> desktop Chrome/Playwright
  -> ATS form
  -> result callback
  -> workflow resumes
  -> application tracker
```

## Durable workflow

The production control plane should use Vercel Workflow for long-running orchestration. Vercel Workflows are designed to survive crashes/redeploys, retry steps, and resume from recorded state. The workflow should own the state machine:

```text
DISCOVER
  -> FILTER
  -> MATCH
  -> TAILOR_CV
  -> WRITE_MOTIVATION
  -> PREPARE_APPLICATION
  -> CLAIM_BROWSER_JOB
  -> FILL
  -> VALIDATE
  -> SUBMIT
  -> VERIFY_CONFIRMATION
  -> TRACK
```

Each side-effecting operation is a durable step. Browser work is an external worker step, not a Vercel serverless process.

## Auto-submit mode

Auto-submit is intentionally supported only after all deterministic gates pass:

- job passed the user's configured match threshold;
- duplicate/application-history check passed;
- CV no-drift verification passed;
- motivation letter generation passed factual validation;
- every required application field has a verified answer;
- no CAPTCHA, anti-bot challenge, login/2FA blocker, or unresolved sensitive/legal attestation is present;
- the target submit control is uniquely identified;
- the run has an idempotency key so a retry cannot submit the same application twice.

The worker must never bypass CAPTCHA, authentication, rate limits, or site security. A blocker changes the workflow state to `HUMAN_REQUIRED` and the workflow resumes after the user resolves it.

## Vercel is not the browser

Do not attempt to run the user's persistent Chrome profile inside a Vercel Function. Vercel Python/FastAPI functions are serverless and are appropriate for APIs/control-plane endpoints; the browser worker stays on the desktop. Vercel Workflows provide the durable orchestration layer.

## Required production secrets

Never commit these values:

- `OPENAI_API_KEY`
- `JOB_AGENT_TOKEN`
- `MCP_SHARED_SECRET`
- database credentials
- browser-worker registration token

The browser worker receives a short-lived worker credential, not the OpenAI API key.
