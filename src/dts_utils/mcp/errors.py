"""Map ``dts_utils`` exceptions to MCP tool errors."""

from __future__ import annotations

from mcp.server.fastmcp.exceptions import ToolError

from dts_utils.exceptions import (
    ChannelSetupError,
    ConfigurationError,
    DTSUtilError,
    GenerationCancelledError,
    GenerationEmptyError,
    GenerationRpcError,
)


def exception_detail(exc: Exception) -> str:
    """Human-readable tool error text (no secrets)."""
    if isinstance(exc, DTSUtilError):
        return str(exc)
    return str(exc) or exc.__class__.__name__


def raise_tool_error(exc: Exception) -> None:
    """Raise :class:`ToolError` with a detail string aligned with web ``_map_exc`` semantics."""
    detail = exception_detail(exc)
    if isinstance(exc, ConfigurationError):
        raise ToolError(f"configuration: {detail}") from exc
    if isinstance(exc, ChannelSetupError):
        raise ToolError(f"channel: {detail}") from exc
    if isinstance(exc, GenerationRpcError):
        raise ToolError(f"generation_rpc: {detail}") from exc
    if isinstance(exc, GenerationEmptyError):
        raise ToolError(f"generation_empty: {detail}") from exc
    if isinstance(exc, GenerationCancelledError):
        raise ToolError(f"generation_cancelled: {detail}") from exc
    if isinstance(exc, DTSUtilError):
        raise ToolError(detail) from exc
    raise ToolError(detail) from exc
