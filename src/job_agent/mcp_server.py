"""Least-privilege MCP server for controlling the Job Agent.

This server intentionally exposes discovery/inspection/preparation only. It does
not expose credentials, arbitrary filesystem access, browser JavaScript, or final
application submission. For remote ChatGPT use, place the Streamable HTTP
transport behind HTTPS and authentication; do not expose a local stdio server
publicly.
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
            "memory": "sqlite",
            "browser": "desktop worker / preview-only bridge",
            "automatic_submission": False,
        }

    @mcp.tool()
    async def search_jobs(days: int = 7, limit: int = 25) -> dict:
        """Find and rank jobs using the deterministic job pipeline."""
        # Reuse the Agent tool implementation through the SDK instead of duplicating
        # the discovery logic in the MCP layer.
        for tool in agent.tools:
            if getattr(tool, "name", "") == "search_jobs":
                result = await tool.on_invoke_tool(None, json.dumps({"days": days, "limit": limit}))
                return json.loads(result)
        raise RuntimeError("search_jobs tool unavailable")

    @mcp.tool()
    async def inspect_job(job_id: str) -> dict:
        """Inspect a previously discovered job by ID."""
        for tool in agent.tools:
            if getattr(tool, "name", "") == "get_job":
                result = await tool.on_invoke_tool(None, json.dumps({"job_id": job_id}))
                return json.loads(result)
        raise RuntimeError("get_job tool unavailable")

    @mcp.tool()
    async def candidate_facts_status() -> dict:
        """Report whether verified candidate facts are configured, without exposing them."""
        path = data_dir / "career_facts.yaml"
        return {"configured": path.exists(), "path": "data/career_facts.yaml"}

    @mcp.tool()
    async def prepare_application(job_id: str) -> dict:
        """Prepare a review-only application plan; never submit an application."""
        for tool in agent.tools:
            if getattr(tool, "name", "") == "prepare_application":
                result = await tool.on_invoke_tool(None, json.dumps({"job_id": job_id}))
                return json.loads(result)
        raise RuntimeError("prepare_application tool unavailable")

    return mcp


def main() -> int:
    import os

    mcp = build_mcp_server()
    transport = os.environ.get("JOB_AGENT_MCP_TRANSPORT", "stdio").strip().lower()
    if transport not in {"stdio", "streamable-http"}:
        raise SystemExit("JOB_AGENT_MCP_TRANSPORT must be stdio or streamable-http")
    # Streamable HTTP is intentionally opt-in. A production deployment must put
    # this endpoint behind HTTPS and an authenticated reverse proxy before exposing it.
    mcp.run(transport=transport)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
