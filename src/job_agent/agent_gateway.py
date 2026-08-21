"""Local browser gateway primitives for the mobile agent."""
from __future__ import annotations

import secrets
from dataclasses import dataclass

@dataclass(frozen=True)
class GatewayConfig:
    host: str = "127.0.0.1"
    port: int = 8643
    token: str = ""

def new_gateway_config() -> GatewayConfig:
    return GatewayConfig(token=secrets.token_urlsafe(32))

def valid_origin(origin: str | None) -> bool:
    return origin in (None, "http://127.0.0.1:8643", "http://localhost:8643")
