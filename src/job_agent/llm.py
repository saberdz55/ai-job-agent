"""Provider-neutral LLM helpers.

The job pipeline keeps model access behind this small boundary. OpenAI uses the
Responses API with strict JSON Schema output; Anthropic keeps the existing
structured-output path. This makes provider failures local and testable.
"""

from __future__ import annotations

import json
from typing import Any


class LLMConfigurationError(RuntimeError):
    """The selected provider is not configured correctly."""


def create_client(provider: str, *, anthropic_api_key: str | None = None,
                  openai_api_key: str | None = None):
    provider = provider.lower().strip()
    if provider == "anthropic":
        if not anthropic_api_key:
            raise LLMConfigurationError("ANTHROPIC_API_KEY is not set")
        import anthropic
        return anthropic.Anthropic(api_key=anthropic_api_key)
    if provider == "openai":
        if not openai_api_key:
            raise LLMConfigurationError("OPENAI_API_KEY is not set")
        from openai import OpenAI
        return OpenAI(api_key=openai_api_key)
    raise LLMConfigurationError(f"Unsupported LLM provider: {provider!r}")


def openai_json(client, *, model: str, system: str, user: str,
                schema: dict[str, Any], name: str) -> str:
    """Return strict JSON from the OpenAI Responses API.

    The API's structured-output contract is used instead of asking the model to
    "please return JSON" and hoping the parser succeeds.
    """
    response = client.responses.create(
        model=model,
        instructions=system,
        input=user,
        text={
            "format": {
                "type": "json_schema",
                "name": name,
                "strict": True,
                "schema": schema,
            }
        },
    )
    text = getattr(response, "output_text", "") or ""
    if not text:
        raise ValueError("OpenAI returned no structured output")
    # Validate JSON locally as a second boundary. Schema validation is handled
    # by the API, while this catches SDK/transport anomalies before persistence.
    json.loads(text)
    return text
