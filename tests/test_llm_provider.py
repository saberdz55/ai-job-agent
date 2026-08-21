"""Provider boundary tests that never call a real model."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from job_agent.config import Settings
from job_agent.llm import LLMConfigurationError, openai_json


def test_openai_settings_select_openai_model():
    settings = Settings(provider="openai", openai_api_key="secret", openai_model="gpt-test")
    assert settings.has_llm_key()
    assert settings.active_model() == "gpt-test"


def test_invalid_provider_is_rejected():
    with pytest.raises(ValueError, match="JOB_AGENT_PROVIDER"):
        Settings(provider="unknown")


def test_openai_json_validates_and_returns_output_text():
    calls = {}

    class Responses:
        def create(self, **kwargs):
            calls.update(kwargs)
            return SimpleNamespace(output_text='{"ok":true}')

    client = SimpleNamespace(responses=Responses())
    result = openai_json(
        client,
        model="gpt-test",
        system="system",
        user="user",
        schema={"type": "object", "properties": {"ok": {"type": "boolean"}},
                "required": ["ok"], "additionalProperties": False},
        name="test_schema",
    )
    assert result == '{"ok":true}'
    assert calls["text"]["format"]["type"] == "json_schema"
    assert calls["text"]["format"]["strict"] is True


def test_openai_json_rejects_empty_output():
    class Responses:
        def create(self, **kwargs):
            return SimpleNamespace(output_text="")

    with pytest.raises(ValueError, match="no structured output"):
        openai_json(SimpleNamespace(responses=Responses()), model="m",
                    system="s", user="u", schema={"type": "object"}, name="x")
