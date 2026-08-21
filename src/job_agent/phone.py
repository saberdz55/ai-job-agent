"""Android/Pydroid-friendly local runtime.

This mode deliberately does NOT import Playwright. The phone runs the agent
backend and responsive dashboard in the same Android Python process, while the
user's Android browser remains the real browser for application pages.

The application-form filling path is the MV3 extension path: the extension
runs in the user's browser, asks this local backend for a grounded fill plan,
and fills visible fields. Real submission is still performed by the user.

Run:
    python -m job_agent.phone
    # or, after installation:
    job-agent-phone

The server binds to 127.0.0.1 by default. This is intentional: career facts,
answer banks, and generated resumes are personal data. Do not change the bind
address unless a separately authenticated remote deployment is implemented.
"""

from __future__ import annotations

import argparse
import threading
import time
import webbrowser
from pathlib import Path


def _phone_app(*, data_dir: Path, profile: Path):
    """Create the normal dashboard and add a phone-safe guard.

    The normal dashboard contains optional Playwright routes. Android Python
    runtimes generally cannot provide the desktop Playwright browser binary,
    so phone mode makes those routes fail explicitly instead of producing a
    confusing import/browser crash. Search, scoring, tailoring, tracking,
    resume viewing, application opening, and the extension API remain usable.
    """
    try:
        from fastapi.responses import JSONResponse
    except ImportError as exc:
        raise RuntimeError(
            "Phone mode needs FastAPI. Install with: pip install -e '.[phone]'"
        ) from exc

    from job_agent.dashboard.app import create_app

    app = create_app(data_dir=data_dir, profile_path=profile)
    blocked = {
        "/api/apply/preview",
        "/api/apply/start",
        "/api/apply/rescan",
        "/api/apply/edit",
        "/api/apply/submit",
        "/api/apply/cancel",
    }

    @app.middleware("http")
    async def phone_guard(request, call_next):
        if request.url.path in blocked:
            return JSONResponse(
                status_code=501,
                content={
                    "ok": False,
                    "phone_mode": True,
                    "error": (
                        "This desktop Playwright route is disabled in phone mode. "
                        "Open the application in the Android browser and use the "
                        "Job Agent extension for visible form filling."
                    ),
                },
            )
        return await call_next(request)

    @app.get("/api/phone")
    def phone_info() -> dict:
        return {
            "ok": True,
            "mode": "android-phone",
            "browser_fill": "extension",
            "desktop_playwright": False,
            "bind": "127.0.0.1",
            "blocked_desktop_routes": sorted(blocked),
        }

    return app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="job-agent-phone",
        description="Run job-agent locally on an Android/Pydroid phone.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Bind address; keep 127.0.0.1 on a phone.")
    parser.add_argument("--port", type=int, default=8642)
    parser.add_argument("--profile", default="search_profile.yaml")
    parser.add_argument("--data-dir", default=None)
    parser.add_argument("--no-open", action="store_true", help="Do not open the dashboard automatically.")
    args = parser.parse_args(argv)

    if args.host != "127.0.0.1":
        raise SystemExit(
            "Refusing non-local bind in phone mode. Keep --host 127.0.0.1; "
            "remote access requires an authenticated deployment."
        )

    try:
        import uvicorn
    except ImportError as exc:
        raise SystemExit(
            "Phone mode needs FastAPI + Uvicorn. Run: pip install -e '.[phone]'"
        ) from exc

    from job_agent.config import load_settings

    settings = load_settings()
    data_dir = Path(args.data_dir) if args.data_dir else settings.data_dir
    profile = Path(args.profile)
    app = _phone_app(data_dir=data_dir, profile=profile)
    url = f"http://127.0.0.1:{args.port}/"

    print("job-agent phone mode")
    print(f"Dashboard: {url}")
    print("Browser automation: Android extension path (no Playwright)")
    print("Submission: always remains a human action")

    if not args.no_open:
        def _open() -> None:
            time.sleep(0.7)
            try:
                webbrowser.open(url)
            except Exception:
                pass

        threading.Thread(target=_open, daemon=True).start()

    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
