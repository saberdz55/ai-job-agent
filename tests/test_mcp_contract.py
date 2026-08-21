from pathlib import Path


def test_mcp_surface_has_no_submit_or_arbitrary_execution():
    source = Path("src/job_agent/mcp_server.py").read_text(encoding="utf-8")
    assert "prepare_application" in source
    assert "submit_application" not in source
    assert "shell" not in source.lower()
    assert "filesystem" not in source.lower()


def test_mcp_requires_gateway_token():
    source = Path("src/job_agent/mcp_server.py").read_text(encoding="utf-8")
    assert "JOB_AGENT_TOKEN" in source
    assert "at least 32" in source
