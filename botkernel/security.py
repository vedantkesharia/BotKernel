"""Operator and agent authorization for the private gateway."""
import hashlib
import hmac
import os
import re
from pathlib import Path

from fastapi import HTTPException, Request


_AGENT_ROUTES = {
    ("GET", "/telemetry"),
    ("POST", "/actions"),
}
_AGENT_PATH = re.compile(r"^/agents/[a-zA-Z0-9_-]{1,100}(?:/decision|/action-by-key)?$")


def _secret(name: str, *, required: bool) -> str:
    file_name = os.getenv(name + "_FILE", "").strip()
    value = os.getenv(name, "")
    if file_name and value:
        raise HTTPException(503, "Authentication configuration invalid")
    if file_name:
        try:
            value = Path(file_name).read_text(encoding="utf-8").strip()
        except (OSError, UnicodeError) as error:
            raise HTTPException(503, "Authentication configuration unavailable") from error
    if not value and not required:
        return ""
    if len(value) < 43 or len(value) > 512 or any(ord(c) < 33 or ord(c) > 126 for c in value):
        raise HTTPException(503, "Authentication configuration invalid")
    return value


def _matches(candidate: str, expected: str) -> bool:
    return hmac.compare_digest(
        hashlib.sha256(candidate.encode("utf-8")).digest(),
        hashlib.sha256(expected.encode("utf-8")).digest(),
    )


def agent_headers() -> dict[str, str]:
    token = _secret("BOTKERNEL_AGENT_TOKEN", required=True)
    return {"Authorization": f"Bearer {token}"}


def operator_headers() -> dict[str, str]:
    token = _secret("BOTKERNEL_OPERATOR_TOKEN", required=True)
    return {"Authorization": f"Bearer {token}"}


def validate_configuration() -> tuple[str, str, str]:
    operator = _secret("BOTKERNEL_OPERATOR_TOKEN", required=True)
    agent = _secret("BOTKERNEL_AGENT_TOKEN", required=False)
    metrics = _secret("BOTKERNEL_METRICS_TOKEN", required=False)
    if ((agent and _matches(agent, operator)) or (metrics and _matches(metrics, operator))
            or (metrics and agent and _matches(metrics, agent))):
        raise HTTPException(503, "Authentication configuration invalid")
    return operator, agent, metrics


def authorize(request: Request) -> str:
    if request.url.path in ("/health", "/ready"):
        return "health"
    operator, agent, metrics = validate_configuration()
    scheme, _, candidate = request.headers.get("Authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not candidate or len(candidate) > 512:
        raise HTTPException(401, "Authentication required", headers={"WWW-Authenticate": "Bearer"})
    if _matches(candidate, operator):
        request.state.actor = "operator"
        return "operator"
    if metrics and _matches(candidate, metrics):
        if request.method != "GET" or request.url.path != "/metrics":
            raise HTTPException(403, "Operator authorization required")
        request.state.actor = "metrics"
        return "metrics"
    if agent and _matches(candidate, agent):
        path, method = request.url.path, request.method
        allowed = (method, path) in _AGENT_ROUTES
        if _AGENT_PATH.fullmatch(path):
            allowed = (method == "POST" and not path.endswith("/action-by-key")) or (
                method == "GET" and path.endswith("/action-by-key")
            )
        if not allowed:
            raise HTTPException(403, "Operator authorization required")
        request.state.actor = "agent"
        return "agent"
    raise HTTPException(401, "Invalid credentials", headers={"WWW-Authenticate": "Bearer"})
