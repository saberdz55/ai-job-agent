"""Configuration loading and validation.

Keeps profile validation strict and runtime LLM configuration explicit so the
agent can use either Anthropic or the OpenAI Responses API without changing the
job pipeline.
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError, field_validator

from job_agent.seniority import LEVEL_NAMES

DEFAULT_PROVIDER = "anthropic"
DEFAULT_MODEL = "claude-haiku-4-5"
DEFAULT_OPENAI_MODEL = "gpt-5.6-luna"

SourceName = str


class SourceRef(BaseModel):
    """One board to fetch: which ATS, and the board/company identifier."""

    ats: str
    board: str
    model_config = {"extra": "forbid"}


class LocationRule(BaseModel):
    remote_ok: bool = True
    allowed_countries: list[str] = Field(default_factory=lambda: ["US"])
    model_config = {"extra": "forbid"}


class SearchProfile(BaseModel):
    keywords: list[str] = Field(min_length=1)
    location: LocationRule = Field(default_factory=LocationRule)
    sources: list[SourceRef] = Field(min_length=1)
    candidate_summary: str = ""
    max_seniority: str | None = None
    experience_years: int | None = Field(default=None, ge=0)
    model_config = {"extra": "forbid"}

    _KNOWN_ATS = {"greenhouse", "lever", "ashby", "smartrecruiters",
                  "sr-search", "remotive", "remoteok"}

    @field_validator("max_seniority")
    @classmethod
    def _known_level(cls, v: str | None) -> str | None:
        if v is None:
            return None
        level = v.strip().lower()
        if level not in LEVEL_NAMES:
            raise ValueError(
                f"max_seniority must be one of {sorted(LEVEL_NAMES)}; got {v!r}"
            )
        return level

    def unknown_sources(self) -> list[str]:
        return sorted({s.ats for s in self.sources if s.ats not in self._KNOWN_ATS})


class Settings(BaseModel):
    """Runtime configuration. Keys are never persisted by the application."""

    provider: str = DEFAULT_PROVIDER
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    model: str = DEFAULT_MODEL
    openai_model: str = DEFAULT_OPENAI_MODEL
    data_dir: Path = Path("data")

    @field_validator("provider")
    @classmethod
    def _provider(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in {"anthropic", "openai"}:
            raise ValueError("JOB_AGENT_PROVIDER must be 'anthropic' or 'openai'")
        return value

    def has_llm_key(self) -> bool:
        return bool(self.openai_api_key if self.provider == "openai" else self.anthropic_api_key)

    def active_model(self) -> str:
        return self.openai_model if self.provider == "openai" else self.model


def load_settings() -> Settings:
    load_dotenv()
    provider = os.environ.get("JOB_AGENT_PROVIDER", DEFAULT_PROVIDER).strip().lower()
    return Settings(
        provider=provider,
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY") or None,
        openai_api_key=os.environ.get("OPENAI_API_KEY") or None,
        model=os.environ.get("JOB_AGENT_MODEL") or DEFAULT_MODEL,
        openai_model=os.environ.get("OPENAI_MODEL") or DEFAULT_OPENAI_MODEL,
        data_dir=Path(os.environ.get("JOB_AGENT_DATA_DIR", "data")),
    )


def load_profile(path: str | Path) -> SearchProfile:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"Search profile not found: {path}. "
            f"Copy search_profile.example.yaml to {path} and edit it."
        )
    try:
        raw = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"Could not parse {path} as YAML: {exc}") from exc
    try:
        return SearchProfile.model_validate(raw)
    except ValidationError as exc:
        raise ValueError(f"Invalid search profile {path}:\n{exc}") from exc
