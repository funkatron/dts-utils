"""stdio MCP server entrypoint for coding agents."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from dts_utils.mcp.tools import (
    PHASE_1_TOOL_NAMES,
    tool_expand_prompt,
    tool_generate_image,
    tool_get_config,
    tool_list_configs,
    tool_list_installed_models,
    tool_server_check,
)


def create_mcp_server() -> FastMCP:
    """Build a FastMCP server with Phase 1 tools registered."""
    mcp = FastMCP(
        "dts-utils",
        instructions=(
            "Draw Things gRPC helper tools. Default gRPC: localhost:7859 with trust_server_cert on loopback. "
            "Use dts_server_check before dts_generate_image."
        ),
        json_response=True,
    )

    mcp.add_tool(tool_server_check, name="dts_server_check")
    mcp.add_tool(tool_list_configs, name="dts_list_configs")
    mcp.add_tool(tool_get_config, name="dts_get_config")
    mcp.add_tool(tool_expand_prompt, name="dts_expand_prompt")
    mcp.add_tool(tool_generate_image, name="dts_generate_image")
    mcp.add_tool(tool_list_installed_models, name="dts_list_installed_models")

    registered = {t.name for t in mcp._tool_manager.list_tools()}
    missing = PHASE_1_TOOL_NAMES - registered
    if missing:
        raise RuntimeError(f"MCP tool registration incomplete: {sorted(missing)}")
    return mcp


def main() -> None:
    """Console entrypoint: run stdio MCP server."""
    create_mcp_server().run(transport="stdio")


if __name__ == "__main__":
    main()
