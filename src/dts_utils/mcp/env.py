"""Environment gates and defaults for optional MCP tools."""

from __future__ import annotations

import os

DEFAULT_MCP_HTTP_PORT = 1976
DEFAULT_MCP_HTTP_BIND = "127.0.0.1"
DEFAULT_MCP_HTTP_PATH = "/mcp"
MCP_TOKEN_ENV = "DTS_MCP_TOKEN"


def _truthy_env(name: str) -> bool:
    value = os.environ.get(name, "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def lifecycle_tools_enabled() -> bool:
    """When true, register macOS server lifecycle MCP tools."""
    return _truthy_env("DTS_MCP_ALLOW_SERVER_LIFECYCLE")


def server_install_tools_enabled() -> bool:
    """When true, allow install/uninstall lifecycle tools (not registered by default)."""
    return _truthy_env("DTS_MCP_ALLOW_SERVER_INSTALL")
