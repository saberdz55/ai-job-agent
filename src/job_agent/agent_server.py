"""Localhost HTTP bridge for the mobile Job Agent UI.

The API key stays server-side. Conversation state is persisted in SQLite so
restarting the Pydroid process does not erase the Agent's session memory.
"""
from __future__ import annotations

import asyncio
from pathlib import Path


def create_agent_app(*, data_dir: Path, profile: Path):
    try:
        from fastapi import FastAPI, HTTPException
        from pydantic import BaseModel, Field
        from agents import Runner, SQLiteSession
    except ImportError as exc:
        raise RuntimeError("Install: pip install -e '.[phone-agent]'") from exc

    from job_agent.agent_core import build_agent

    data_dir.mkdir(parents=True, exist_ok=True)
    app = FastAPI(title="Job Agent", version="0.4.0")
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

    async def session_lock(session_id: str) -> asyncio.Lock:
        async with locks_guard:
            return locks.setdefault(session_id, asyncio.Lock())

    def make_session(session_id: str) -> SQLiteSession:
        # Persistent file-backed SQLite session. A fresh object per request
        # avoids leaking open DB handles while retaining conversation history.
        return SQLiteSession(session_id, db_path=str(db_path))

    @app.get("/api/agent/health")
    async def health() -> dict:
        return {
            "ok": True,
            "agent": "job-agent",
            "runtime": "android-phone",
            "memory": "sqlite",
            "automatic_submission": False,
        }

    @app.post("/api/agent/chat", response_model=ChatResponse)
    async def chat(request: ChatRequest) -> ChatResponse:
        lock = await session_lock(request.session_id)
        async with lock:
            session = make_session(request.session_id)
            try:
                result = await Runner.run(
                    agent,
                    request.message,
                    session=session,
                    max_turns=12,
                )
                return ChatResponse(
                    ok=True,
                    output=str(result.final_output),
                    session_id=request.session_id,
                )
            except Exception as exc:
                raise HTTPException(
                    status_code=500,
                    detail=f"Agent run failed safely: {type(exc).__name__}",
                ) from exc
            finally:
                close = getattr(session, "close", None)
                if close:
                    close()

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
