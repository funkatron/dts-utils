"""MCP server entrypoint for coding agents (stdio and Streamable HTTP)."""

from __future__ import annotations

import argparse
import sys
from typing import Literal

from mcp.server.fastmcp import FastMCP

from dts_utils.mcp.env import (
    DEFAULT_MCP_HTTP_BIND,
    DEFAULT_MCP_HTTP_PATH,
    DEFAULT_MCP_HTTP_PORT,
    MCP_TOKEN_ENV,
    lifecycle_tools_enabled,
)
from dts_utils.mcp.http_auth import build_http_auth, read_mcp_token, warn_if_insecure_bind
from dts_utils.mcp.lifecycle import (
    tool_server_restart,
    tool_server_start,
    tool_server_status,
    tool_server_stop,
)
from dts_utils.mcp.resources import register_mcp_prompts, register_mcp_resources
from dts_utils.mcp.tools import (
    LIFECYCLE_TOOL_NAMES,
    MCP_TOOL_NAMES,
    tool_expand_prompt,
    tool_generate_cancel,
    tool_generate_image,
    tool_get_config,
    tool_list_configs,
    tool_list_installed_models,
    tool_models_doctor,
    tool_models_search,
    tool_pipeline_run,
    tool_pipeline_status,
    tool_server_check,
)

TransportMode = Literal["stdio", "http"]


def create_mcp_server(
    *,
    transport_mode: TransportMode = "stdio",
    host: str = DEFAULT_MCP_HTTP_BIND,
    port: int = DEFAULT_MCP_HTTP_PORT,
    streamable_http_path: str = DEFAULT_MCP_HTTP_PATH,
    token: str | None = None,
) -> FastMCP:
    """Build a FastMCP server with tools, resources, and prompts."""
    http_transport = transport_mode == "http"
    token_verifier, auth = build_http_auth(host, port, streamable_http_path, token)

    instructions = (
        "Draw Things gRPC helper tools. Default gRPC: localhost:7859 with trust_server_cert on loopback. "
        "Use dts_server_check before dts_generate_image or dts_pipeline_run. "
        "Use dts_generate_cancel to stop long generate batches cooperatively. "
        "Resources: dts://config/{stem}, dts://output/{relative_path}, "
        "dts://pipeline/{run_id}/{step_id}/{filename}. "
    )
    if http_transport:
        instructions += "Streamable HTTP transport: macOS lifecycle tools are not available over HTTP."
    else:
        instructions += "macOS server lifecycle tools require DTS_MCP_ALLOW_SERVER_LIFECYCLE=1."

    mcp = FastMCP(
        "dts-utils",
        instructions=instructions,
        json_response=True,
        host=host,
        port=port,
        streamable_http_path=streamable_http_path,
        token_verifier=token_verifier,
        auth=auth,
    )

    mcp.add_tool(tool_server_check, name="dts_server_check")
    mcp.add_tool(tool_list_configs, name="dts_list_configs")
    mcp.add_tool(tool_get_config, name="dts_get_config")
    mcp.add_tool(tool_expand_prompt, name="dts_expand_prompt")
    mcp.add_tool(tool_generate_image, name="dts_generate_image")
    mcp.add_tool(tool_list_installed_models, name="dts_list_installed_models")
    mcp.add_tool(tool_models_search, name="dts_models_search")
    mcp.add_tool(tool_models_doctor, name="dts_models_doctor")
    mcp.add_tool(tool_pipeline_run, name="dts_pipeline_run")
    mcp.add_tool(tool_pipeline_status, name="dts_pipeline_status")
    mcp.add_tool(tool_generate_cancel, name="dts_generate_cancel")

    if lifecycle_tools_enabled(http_transport=http_transport):
        mcp.add_tool(tool_server_status, name="dts_server_status")
        mcp.add_tool(tool_server_start, name="dts_server_start")
        mcp.add_tool(tool_server_stop, name="dts_server_stop")
        mcp.add_tool(tool_server_restart, name="dts_server_restart")

    expected_tools = set(MCP_TOOL_NAMES)
    if lifecycle_tools_enabled(http_transport=http_transport):
        expected_tools |= LIFECYCLE_TOOL_NAMES

    registered = {t.name for t in mcp._tool_manager.list_tools()}
    missing = expected_tools - registered
    if missing:
        raise RuntimeError(f"MCP tool registration incomplete: {sorted(missing)}")

    register_mcp_resources(mcp)
    register_mcp_prompts(mcp)

    return mcp


def _serve_parser(prog: str = "dts-utils-mcp") -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=prog, description="Draw Things MCP server for coding agents.")
    sub = parser.add_subparsers(dest="command")

    serve = sub.add_parser("serve", help="Run Streamable HTTP MCP listener on the Draw Things host.")
    serve.add_argument(
        "--bind",
        default=DEFAULT_MCP_HTTP_BIND,
        metavar="HOST",
        help=f"Listen address (default: {DEFAULT_MCP_HTTP_BIND}).",
    )
    serve.add_argument(
        "--port",
        type=int,
        default=DEFAULT_MCP_HTTP_PORT,
        metavar="PORT",
        help=f"Listen port (default: {DEFAULT_MCP_HTTP_PORT}).",
    )
    serve.add_argument(
        "--path",
        default=DEFAULT_MCP_HTTP_PATH,
        metavar="PATH",
        help=f"Streamable HTTP path (default: {DEFAULT_MCP_HTTP_PATH}).",
    )
    serve.add_argument(
        "--token-env",
        default=MCP_TOKEN_ENV,
        metavar="VAR",
        help=f"Env var for bearer token (default: {MCP_TOKEN_ENV}).",
    )
    return parser


def _run_http_serve(args: argparse.Namespace) -> None:
    token = read_mcp_token(args.token_env)
    warn_if_insecure_bind(args.bind, token_set=token is not None)

    path = args.path if args.path.startswith("/") else f"/{args.path}"
    print(
        f"dts-utils-mcp serve: http://{args.bind}:{args.port}{path}",
        file=sys.stderr,
    )
    if token:
        print(f"dts-utils-mcp serve: bearer auth via {args.token_env}", file=sys.stderr)
    else:
        print(
            f"dts-utils-mcp serve: no bearer token ({args.token_env} unset; loopback only recommended)",
            file=sys.stderr,
        )

    server = create_mcp_server(
        transport_mode="http",
        host=args.bind,
        port=args.port,
        streamable_http_path=path,
        token=token,
    )
    server.run(transport="streamable-http")


def main(argv: list[str] | None = None) -> None:
    """Console entrypoint: stdio MCP by default; ``serve`` for Streamable HTTP."""
    args = _serve_parser().parse_args(argv)
    if args.command == "serve":
        _run_http_serve(args)
        return
    create_mcp_server().run(transport="stdio")


if __name__ == "__main__":
    main()
