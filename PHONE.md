# Android / Pydroid mode

The project now has a phone-first runtime that does not import Playwright.
This matters because Playwright's Python package targets desktop/server OSes;
its official Android support is an experimental Android-device automation path
that requires ADB and Chrome-on-device, so it is not a sensible dependency for
an ordinary Pydroid installation.

## Install on the phone

From the repository directory in Pydroid's terminal:

```bash
pip install -e '.[phone]'
```

Then:

```bash
python -m job_agent.phone
```

Open `http://127.0.0.1:8642/` in the phone browser if it does not open
automatically.

## What works on the phone

- job discovery and filtering
- LLM scoring through the configured backend API
- resume tailoring and PDF generation
- application tracking
- the responsive dashboard
- opening the real application URL in the Android browser
- browser-extension form filling through the local extension API
- human review before any submission

## What is intentionally different

The desktop Playwright routes are disabled in phone mode. The phone should not
pretend that a missing browser binary is a recoverable application-form error.
Instead, the Android browser is the real browser and the extension talks to the
local backend at `127.0.0.1:8642`.

The extension never submits the application. File upload inputs still require
a real user tap because browsers do not allow an extension to silently choose a
local file.

## Browser note

Standard Chrome for Android does not provide desktop Chrome extension support.
Use an Android Chromium browser that explicitly supports extensions. Kiwi used
to be a common choice, but the Kiwi project is archived and no longer maintained;
prefer a currently maintained browser/extension environment rather than making
Kiwi a hard dependency.

## Security

Phone mode refuses `--host 0.0.0.0` and binds only to `127.0.0.1`. This prevents
another device on the network from reaching career facts, answer-bank data, or
local generated files. Do not weaken this guard without adding real
authentication and HTTPS.
