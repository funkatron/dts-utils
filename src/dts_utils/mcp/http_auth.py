"""Bearer auth and bind warnings for MCP Streamable HTTP."""

from __future__ import annotations

import os
import secrets
import sys
from typing import TYPE_CHECKING

from mcp.server.auth.provider import AccessToken
from mcp.server.auth.settings import AuthSettings
from pydantic import AnyHttpUrl

from dts_utils.mcp.env import MCP_TOKEN_ENV

if TYPE_CHECKING:
    from mcp.server.auth.provider import TokenVerifier

LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})


def read_mcp_token(env_name: str = MCP_TOKEN_ENV) -> str | None:
    """Return bearer token from env, or None when unset."""
    value = os.environ.get(env_name, "").strip()
    return value or None


class StaticBearerTokenVerifier:
    """Validate Authorization: Bearer tokens against a shared secret."""

    def __init__(self, expected_token: str) -> None:
        self._expected_token = expected_token

    async def verify_token(self, token: str) -> AccessToken | None:
        if not secrets.compare_digest(token, self._expected_token):
            return None
        return AccessToken(token=token, client_id="dts-utils-mcp", scopes=[])


def build_auth_settings(host: str, port: int, path: str) -> AuthSettings:
    """OAuth resource-server metadata for FastMCP bearer middleware."""
    base = f"http://{host}:{port}"
    resource_path = path if path.startswith("/") else f"/{path}"
    return AuthSettings(
        issuer_url=AnyHttpUrl(base),
        resource_server_url=AnyHttpUrl(f"{base}{resource_path}"),
    )


def build_http_auth(host: str, port: int, path: str, token: str | None) -> tuple[TokenVerifier | None, AuthSettings | None]:
    """Return token_verifier and auth settings for Streamable HTTP."""
    if not token:
        return None, None
    return StaticBearerTokenVerifier(token), build_auth_settings(host, port, path)


def warn_if_insecure_bind(bind: str, token_set: bool, *, prog: str = "dts-utils-mcp") -> None:
    """Warn when listening on a non-loopback address without bearer auth."""
    if bind in LOOPBACK_HOSTS or token_set:
        return
    print(
        f"{prog} serve: warning — non-loopback bind without {MCP_TOKEN_ENV} exposes "
        "MCP tools over the network. Set DTS_MCP_TOKEN (Authorization: Bearer).",
        file=sys.stderr,
    )
