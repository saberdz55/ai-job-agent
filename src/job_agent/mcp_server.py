"""Least-privilege MCP server for controlling the Job Agent.

The MCP surface exposes job discovery and the explicitly enabled autonomous
application workflow. It never exposes credentials, arbitrary shell/filesystem
execution, browser JavaScript, or anti-bot bypass. CAPTCHA/login/2FA and
unresolved sensitive/legal fields remain hard stops.
"""
from __future__ import annotations

import json
from pathlib import Path


def build_mcp_server():
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise RuntimeError("Install MCP support: pip install -e '.[mcp,phone-agent]'") from exc

    from job_agent.agent_core import build_agent
    from job_agent.auto_apply import auto_apply_enabled
    from job_agent.config import load_settings

    settings = load_settings()
    if not settings.gateway_token or len(settings.gateway_token) < 32:
        raise RuntimeError("JOB_AGENT_TOKEN must be configured with at least 32 random characters.")
    data_dir = Path(settings.data_dir)
    profile = Path("search_profile.yaml")
    agent = build_agent(data_dir=data_dir, profile=profile)
    mcp = FastMCP("Job Agent")

    @mcp.tool()
    async def agent_status() -> dict:
        """Return safe runtime capabilities; never return secrets."""
        return {
            "ok": True,
            "agent": "job-agent",
            "model": settings.active_model(),
            "memory": "sqlite/local worker",
            "browser": "desktop Playwright worker",
            "automatic_submission": auto_apply_enabled(),
            "hard_stops": ["captcha", "login", "2fa", "unknown_required_field", "sensitive_attestation"],
        }

    async def invoke_tool(name: str, payload: dict) -> dict:
        for tool in agent.tools:
            if getattr(tool, "name", "") == name:
                result = await tool.on_invoke_tool(None, json.dumps(payload))
                return json.loads(result)
        raise RuntimeError(f"{name} tool unavailable")

    @mcp.tool()
    async def search_jobs(days: int = 7, limit: int = 25) -> dict:
        """Find and rank jobs using the deterministic job pipeline."""
        return await invoke_tool("search_jobs", {"days": days, "limit": limit})

    @mcp.tool()
    async def inspect_job(job_id: str) -> dict:
        """Inspect a previously discovered job by ID."""
        return await invoke_tool("get_job", {"job_id": job_id})

    @mcp.tool()
    async def candidate_facts_status() -> dict:
        """Report whether verified candidate facts are configured, without exposing them."""
        path = data_dir / "career_facts.yaml"
        return {"configured": path.exists(), "path": "data/career_facts.yaml"}

    @mcp.tool()
    async def prepare_application(job_id: str) -> dict:
        """Prepare an application plan without submitting."""
        return await invoke_tool("prepare_application", {"job_id": job_id})

    @mcp.tool()
    async def auto_apply_job(job_id: str) -> dict:
        """Run exactly one qualified application in autonomous mode.

        Requires JOB_AGENT_AUTO_APPLY=true. Existing duplicate, factual, form,
        CAPTCHA/login/2FA and sensitive-field gates remain active.
        """
        return await invoke_tool("auto_apply_job", {"job_id": job_id})

    return mcp


def main() -> int:
    import os

    mcp = build_mcp_server()
    transport = os.environ.get("JOB_AGENT_MCP_TRANSPORT", "stdio").strip().lower()
    if transport not in {"stdio", "streamable-http"}:
        raise SystemExit("JOB_AGENT_MCP_TRANSPORT must be stdio or streamable-http")
    mcp.run(transport=transport)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
