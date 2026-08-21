from pathlib import Path


def test_agent_server_keeps_the_bridge_local():
    source = Path("src/job_agent/agent_server.py").read_text(encoding="utf-8")
    assert 'default="127.0.0.1"' in source
    assert "refuses non-local bind" in source
    assert 'db_path=str(db_path)' in source


def test_agent_cli_uses_persistent_session_store():
    source = Path("src/job_agent/agent_cli.py").read_text(encoding="utf-8")
    assert 'db_path=str(data_dir / "agent_sessions.db")' in source
    assert "max_turns=12" in source
