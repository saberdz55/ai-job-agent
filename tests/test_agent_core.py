from __future__ import annotations

from pathlib import Path


def test_agent_core_is_lazy_and_safe_without_sdk():
    import job_agent.agent_core as core

    assert "Never invent" in core.SYSTEM
    assert "automatic submission" in core.SYSTEM.lower()
    assert callable(core.build_agent)


def test_data_path_cannot_escape(tmp_path: Path):
    from job_agent.agent_core import _safe_data_path

    assert _safe_data_path(tmp_path, "nested/file.json").parent == tmp_path / "nested"
    try:
        _safe_data_path(tmp_path, "../outside.json")
    except ValueError:
        pass
    else:
        raise AssertionError("path traversal must be rejected")
