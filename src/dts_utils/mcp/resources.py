"""MCP resource templates and prompts."""

from __future__ import annotations

from pathlib import Path

from mcp.server.fastmcp import FastMCP

from dts_utils.mcp.errors import raise_tool_error
from dts_utils.mcp.paths import (
    mime_type_for_path,
    resolve_config_resource_path,
    resolve_output_resource_path,
    resolve_pipeline_resource_path,
)

RESOURCE_URI_TEMPLATES: frozenset[str] = frozenset(
    {
        "dts://config/{stem}",
        "dts://output/{relative_path}",
        "dts://pipeline/{run_id}/{step_id}/{filename}",
    }
)

MCP_PROMPT_NAMES: frozenset[str] = frozenset({"generate_image"})


def register_mcp_resources(mcp: FastMCP) -> None:
    """Register MCP resource templates on a FastMCP server."""

    @mcp.resource("dts://config/{stem}", mime_type="application/json", name="dts_config")
    def resource_config(stem: str) -> str:
        """Saved Draw Things generation profile JSON."""
        try:
            path = resolve_config_resource_path(stem)
            return path.read_text(encoding="utf-8")
        except Exception as exc:
            raise_tool_error(exc)
            raise AssertionError("raise_tool_error always raises")

    @mcp.resource("dts://output/{relative_path}", mime_type="application/octet-stream", name="dts_output_file")
    def resource_output(relative_path: str) -> bytes:
        """PNG or other file under allowed output directories (default: ./output)."""
        try:
            path = resolve_output_resource_path(relative_path)
            # FastMCP picks mime from decorator default; set per-read via bytes return.
            return path.read_bytes()
        except Exception as exc:
            raise_tool_error(exc)
            raise AssertionError("raise_tool_error always raises")

    @mcp.resource(
        "dts://pipeline/{run_id}/{step_id}/{filename}",
        mime_type="application/octet-stream",
        name="dts_pipeline_artifact",
    )
    def resource_pipeline(run_id: str, step_id: str, filename: str) -> bytes:
        """Pipeline step artifact (image or video) under the pipeline run root."""
        try:
            path = resolve_pipeline_resource_path(run_id, step_id, filename)
            return path.read_bytes()
        except Exception as exc:
            raise_tool_error(exc)
            raise AssertionError("raise_tool_error always raises")


def register_mcp_prompts(mcp: FastMCP) -> None:
    """Register MCP prompts for agent onboarding."""

    @mcp.prompt(name="generate_image", description="How to generate images with dts-utils MCP tools.")
    def prompt_generate_image() -> str:
        text = (
            "Use dts-utils MCP to generate Draw Things images:\n"
            "1. Call dts_server_check to confirm gRPCServerCLI is listening (default localhost:7859).\n"
            "2. Call dts_list_configs or read resource dts://config/{stem} to pick a profile (default: default).\n"
            "3. Call dts_generate_image with prompt and configuration; paths are returned (set include_image_data only if needed).\n"
            "For prompt-to-video, use dts_pipeline_run with a pipeline profile (e.g. prompt-to-video), then dts_pipeline_status.\n"
            "Call dts_generate_cancel to stop a long generate batch cooperatively.\n"
            "Resources: dts://config/{stem}, dts://output/{relative_path}, dts://pipeline/{run_id}/{step_id}/{filename}."
        )
        return text
