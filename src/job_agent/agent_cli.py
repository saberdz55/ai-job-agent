"""Interactive entrypoint for the OpenAI-controlled job agent."""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

from job_agent.agent_core import build_agent


async def run() -> int:
    try:
        from agents import Runner, SQLiteSession
    except ImportError as exc:
        print("Install with: pip install -e '.[phone-agent]'")
        return 2
    if not os.getenv("OPENAI_API_KEY"):
        print("OPENAI_API_KEY is not configured.")
        return 2
    from job_agent.config import load_settings
    settings = load_settings()
    data_dir = Path(settings.data_dir)
    profile = Path("search_profile.yaml")
    agent = build_agent(data_dir=data_dir, profile=profile)
    session = SQLiteSession("job-agent-phone")
    print("Job Agent ready. Type 'exit' to quit.")
    while True:
        try:
            user = input("You › ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if user.lower() in {"exit", "quit"}:
            return 0
        if not user:
            continue
        try:
            result = await Runner.run(agent, user, session=session)
            print(f"Agent › {result.final_output}")
        except Exception as exc:
            print(f"Agent error › {exc}")
    

def main() -> int:
    return asyncio.run(run())


if __name__ == "__main__":
    raise SystemExit(main())
