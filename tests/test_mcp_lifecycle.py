"""Tests for gated MCP server lifecycle tools (Phase 4)."""

from __future__ import annotations

import asyncio

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from dts_utils.mcp.env import lifecycle_tools_enabled
from dts_utils.mcp.lifecycle import collect_server_status_dict
from dts_utils.mcp.server import create_mcp_server
from dts_utils.mcp.tools import LIFECYCLE_TOOL_NAMES, MCP_TOOL_NAMES
from dts_utils.installer.server_installer import DTSServerInstaller


@pytest.fixture
def mcp_server():
    return create_mcp_server()


async def _tool_names(server) -> set[str]:
    tools = await server.list_tools()
    return {tool.name for tool in tools}


def test_lifecycle_tools_absent_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DTS_MCP_ALLOW_SERVER_LIFECYCLE", raising=False)
    names = asyncio.run(_tool_names(create_mcp_server()))
    assert names == MCP_TOOL_NAMES
    assert not LIFECYCLE_TOOL_NAMES & names


def test_lifecycle_tools_registered_when_gated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DTS_MCP_ALLOW_SERVER_LIFECYCLE", "1")
    names = asyncio.run(_tool_names(create_mcp_server()))
    assert LIFECYCLE_TOOL_NAMES <= names


def test_lifecycle_tool_requires_macos(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DTS_MCP_ALLOW_SERVER_LIFECYCLE", "1")
    server = create_mcp_server()
    monkeypatch.setattr("dts_utils.mcp.lifecycle.sys.platform", "linux")
    with pytest.raises(ToolError, match="configuration"):
        asyncio.run(server.call_tool("dts_server_status", {}))


def test_collect_server_status_not_installed(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    installer = DTSServerInstaller()
    installer.AGENTS_DIR = tmp_path
    payload = collect_server_status_dict(installer)
    assert payload["installed"] is False
    assert payload["listener_up"] is False


def test_collect_server_status_installed(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    installer = DTSServerInstaller()
    installer.AGENTS_DIR = tmp_path
    plist = tmp_path / f"{installer.SERVICE_NAME}.plist"
    plist.write_text("plist", encoding="utf-8")
    monkeypatch.setattr(
        installer,
        "read_service_program_arguments",
        lambda path: ["gRPCServerCLI", "--port", "7859"],
    )
    monkeypatch.setattr(
        installer,
        "parse_program_argument_flags",
        lambda args: {
            "port": 7859,
            "no_tls": False,
            "model_browser": True,
            "shared_secret": None,
        },
    )
    monkeypatch.setattr("dts_utils.mcp.lifecycle.is_server_running", lambda **kwargs: True)
    monkeypatch.setattr(installer, "echo_model_file_count", lambda **kwargs: 3)

    payload = collect_server_status_dict(installer)
    assert payload["installed"] is True
    assert payload["listener_up"] is True
    assert payload["echo_model_files"] == 3


def test_collect_server_status_redacts_shared_secret(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    installer = DTSServerInstaller()
    installer.AGENTS_DIR = tmp_path
    plist = tmp_path / f"{installer.SERVICE_NAME}.plist"
    plist.write_text("plist", encoding="utf-8")
    monkeypatch.setattr(
        installer,
        "read_service_program_arguments",
        lambda path: [
            "gRPCServerCLI",
            "--port",
            "7859",
            "--shared-secret",
            "super-secret",
        ],
    )
    monkeypatch.setattr(
        installer,
        "parse_program_argument_flags",
        lambda args: {
            "port": 7859,
            "no_tls": False,
            "model_browser": False,
            "shared_secret": "super-secret",
        },
    )
    monkeypatch.setattr("dts_utils.mcp.lifecycle.is_server_running", lambda **kwargs: False)

    payload = collect_server_status_dict(installer)
    assert payload["program_arguments"] == [
        "gRPCServerCLI",
        "--port",
        "7859",
        "--shared-secret",
        "<redacted>",
    ]


def test_server_start_calls_launchctl(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("DTS_MCP_ALLOW_SERVER_LIFECYCLE", "1")
    monkeypatch.setattr("dts_utils.mcp.lifecycle.sys.platform", "darwin")
    server = create_mcp_server()
    installer = DTSServerInstaller()
    installer.AGENTS_DIR = tmp_path
    plist = tmp_path / f"{installer.SERVICE_NAME}.plist"
    plist.write_text("x", encoding="utf-8")

    started = False

    def fake_start(path):
        nonlocal started
        started = True

    monkeypatch.setattr(
        "dts_utils.mcp.lifecycle._installer",
        lambda: installer,
    )
    monkeypatch.setattr(installer, "_launchctl_start_job", fake_start)
    monkeypatch.setattr(
        "dts_utils.mcp.lifecycle.collect_server_status_dict",
        lambda inst: {"installed": True, "listener_up": True},
    )

    _content, payload = asyncio.run(server.call_tool("dts_server_start", {}))
    assert started
    assert payload["ok"] is True
    assert payload["action"] == "start"


def test_lifecycle_tools_enabled_truthy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DTS_MCP_ALLOW_SERVER_LIFECYCLE", "yes")
    assert lifecycle_tools_enabled()


def test_server_restart_surfaces_bad_plist_as_tool_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("DTS_MCP_ALLOW_SERVER_LIFECYCLE", "1")
    monkeypatch.setattr("dts_utils.mcp.lifecycle.sys.platform", "darwin")
    server = create_mcp_server()
    installer = DTSServerInstaller()
    installer.AGENTS_DIR = tmp_path
    plist = tmp_path / f"{installer.SERVICE_NAME}.plist"
    plist.write_text("x", encoding="utf-8")

    def raise_exit(*args, **kwargs):
        raise SystemExit(1)

    monkeypatch.setattr(
        "dts_utils.mcp.lifecycle._installer",
        lambda: installer,
    )
    monkeypatch.setattr(installer, "enable_model_browser_for_service", raise_exit)

    with pytest.raises(ToolError, match="model browser"):
        asyncio.run(server.call_tool("dts_server_restart", {}))
