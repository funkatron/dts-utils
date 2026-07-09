"""Drift tests: user docs mention every shipped route/tool section."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from dts_utils.doc_inventory import (
    GENERATED_MCP_TOOLS,
    cli_sections_missing_from_cli_md,
    mcp_tools_for_docgen,
    mcp_tools_missing_from_agents_doc,
    render_mcp_tools_markdown,
    web_routes_missing_from_doc,
)


def test_web_api_doc_covers_all_app_routes() -> None:
    missing = web_routes_missing_from_doc()
    if missing:
        lines = [
            f"  {sorted(route.methods)} {route.normalized_path}"
            for route, _methods in missing
        ]
        pytest.fail(
            "web-api.md is missing route documentation for:\n" + "\n".join(lines)
        )


def test_mcp_for_agents_doc_mentions_all_tools() -> None:
    missing = mcp_tools_missing_from_agents_doc(include_lifecycle=True)
    assert not missing, f"mcp-for-agents.md missing tool names: {sorted(missing)}"


def test_cli_md_has_core_command_sections() -> None:
    missing = cli_sections_missing_from_cli_md()
    assert not missing, f"CLI.md missing ### sections for: {missing}"


def test_generated_mcp_tools_up_to_date() -> None:
    if not GENERATED_MCP_TOOLS.is_file():
        pytest.fail(
            f"Missing {GENERATED_MCP_TOOLS.relative_to(Path(__file__).resolve().parents[1])}; "
            "run: uv run python scripts/generate_docs.py"
        )
    tools = asyncio.run(mcp_tools_for_docgen())
    expected = render_mcp_tools_markdown(tools)
    actual = GENERATED_MCP_TOOLS.read_text(encoding="utf-8")
    assert actual == expected, (
        "docs/generated/mcp-tools.md is stale; run: uv run python scripts/generate_docs.py"
    )
