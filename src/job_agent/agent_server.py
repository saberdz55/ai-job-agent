"""Small authenticated-by-localhost HTTP bridge for the mobile Agent UI.

This module deliberately binds only to localhost when used by phone mode. It
keeps the OpenAI API key server-side and stores conversation state in SQLite.
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

    app = FastAPI(title="Job Agent", version="0.3.0")
    agent = build_agent(data_dir=data_dir, profile=profile)
    sessions: dict[str, SQLiteSession] = {}

    class ChatRequest(BaseModel):
        session_id: str = Field(min_length=1, max_length=120)
        message: str = Field(min_length=1, max_length=12000)

    class ChatResponse(BaseModel):
        ok: bool
        output: str
        session_id: str

    def get_session(session_id: str) -> SQLiteSession:
        # Session ids are opaque identifiers; SQLiteSession owns persistence.
        if session_id not in sessions:
            sessions[session_id] = SQLiteSession(
                session_id,
                db_path=str(data_dir / "agent_sessions.db"),
            )
        return sessions[session_id]

    @app.get("/api/agent/health")
    async def health() -> dict:
        return {"ok": True, "agent": "job-agent", "runtime": "android-phone"}

    @app.post("/api/agent/chat", response_model=ChatResponse)
    async def chat(request: ChatRequest) -> ChatResponse:
        try:
            session = get_session(request.session_id)
            result = await Runner.run(
                agent,
                request.message,
                session=session,
                max_turns=12,
            )
            return ChatResponse(ok=True, output=str(result.final_output),
                                session_id=request.session_id)
        except Exception as exc:
            # Do not leak API keys, local paths or raw exception payloads to the UI.
            raise HTTPException(status_code=500,
                                detail=f"Agent run failed safely: {type(exc).__name__}") from exc

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
