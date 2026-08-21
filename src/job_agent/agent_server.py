"""Localhost HTTP bridge for the mobile Job Agent UI and browser bridge."""
from __future__ import annotations

import asyncio
from pathlib import Path


def create_agent_app(*, data_dir: Path, profile: Path):
    try:
        from fastapi import FastAPI, HTTPException, Request
        from pydantic import BaseModel, Field
        from agents import Runner, SQLiteSession
    except ImportError as exc:
        raise RuntimeError("Install: pip install -e '.[phone-agent]'") from exc

    from job_agent.agent_core import build_agent

    data_dir.mkdir(parents=True, exist_ok=True)
    app = FastAPI(title="Job Agent", version="0.5.0")
    agent = build_agent(data_dir=data_dir, profile=profile)
    db_path = data_dir / "agent_sessions.db"
    locks: dict[str, asyncio.Lock] = {}
    locks_guard = asyncio.Lock()

    class ChatRequest(BaseModel):
        session_id: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9._:-]+$")
        message: str = Field(min_length=1, max_length=12000)

    class ChatResponse(BaseModel):
        ok: bool
        output: str
        session_id: str

    class ExtensionRequest(BaseModel):
        action: str = Field(min_length=1, max_length=40)
        tab: dict = Field(default_factory=dict)
        page: dict = Field(default_factory=dict)

    async def session_lock(session_id: str) -> asyncio.Lock:
        async with locks_guard:
            return locks.setdefault(session_id, asyncio.Lock())

    def make_session(session_id: str) -> SQLiteSession:
        return SQLiteSession(session_id, db_path=str(db_path))

    def check_local_origin(request: Request) -> None:
        origin = request.headers.get("origin")
        if origin not in (None, "http://127.0.0.1:8643", "http://localhost:8643"):
            raise HTTPException(status_code=403, detail="origin_not_allowed")

    @app.get("/api/agent/health")
    async def health() -> dict:
        return {"ok": True, "agent": "job-agent", "runtime": "android-phone", "memory": "sqlite", "automatic_submission": False, "browser_bridge": True}

    @app.post("/api/agent/chat", response_model=ChatResponse)
    async def chat(request: ChatRequest) -> ChatResponse:
        lock = await session_lock(request.session_id)
        async with lock:
            session = make_session(request.session_id)
            try:
                result = await Runner.run(agent, request.message, session=session, max_turns=12)
                return ChatResponse(ok=True, output=str(result.final_output), session_id=request.session_id)
            except Exception as exc:
                raise HTTPException(status_code=500, detail=f"Agent run failed safely: {type(exc).__name__}") from exc
            finally:
                close = getattr(session, "close", None)
                if close:
                    close()

    @app.post("/api/agent/extension")
    async def extension(request: Request, payload: ExtensionRequest) -> dict:
        check_local_origin(request)
        # The browser bridge is deliberately read/plan only. It never submits a job.
        if payload.action == "health":
            return {"ok": True, "action": "health", "browser_bridge": True}
        if payload.action == "inspect_page":
            page = payload.page
            return {
                "ok": True,
                "action": "inspect_page",
                "accepted": True,
                "page": {
                    "url": str(payload.tab.get("url", ""))[:2000],
                    "title": str(payload.tab.get("title", ""))[:500],
                    "forms": int(page.get("forms", 0) or 0),
                    "fields": min(int(page.get("fields", 0) or 0), 500),
                    "has_captcha": bool(page.get("has_captcha", False)),
                    "login_detected": bool(page.get("login_detected", False)),
                },
                "next": "human_review_if_login_or_captcha",
            }
        if payload.action == "fill_preview":
            return {"ok": True, "action": "fill_preview", "mode": "preview_only", "submit_allowed": False}
        raise HTTPException(status_code=400, detail="unsupported_extension_action")

    return app


def main() -> int:
    import argparse
    import uvicorn
    from job_agent.config import load_settings

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8643)
    parser.add_argument("--profile", default="search_profile.yaml")
    args = parser.parse_args()
    if args.host != "127.0.0.1":
        raise SystemExit("Agent server refuses non-local bind without authenticated deployment.")
    settings = load_settings()
    app = create_agent_app(data_dir=settings.data_dir, profile=Path(args.profile))
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
