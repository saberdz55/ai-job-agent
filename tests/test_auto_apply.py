from job_agent.auto_apply import auto_apply_enabled


def test_auto_apply_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("JOB_AGENT_AUTO_APPLY", raising=False)
    assert auto_apply_enabled() is False


def test_auto_apply_requires_explicit_enable(monkeypatch):
    monkeypatch.setenv("JOB_AGENT_AUTO_APPLY", "true")
    assert auto_apply_enabled() is True


def test_auto_apply_rejects_other_values(monkeypatch):
    for value in ("1 OR 1=1", "maybe", "submit", "TRUE "):
        monkeypatch.setenv("JOB_AGENT_AUTO_APPLY", value)
        assert auto_apply_enabled() is (value.strip().lower() == "true")
