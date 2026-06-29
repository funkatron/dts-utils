"""Tests for the stdio MCP server (Phase 1 tools)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from dts_utils.exceptions import ConfigurationError
from dts_utils.mcp.server import create_mcp_server
from dts_utils.mcp.tools import PHASE_1_TOOL_NAMES


@pytest.fixture
def mcp_server():
    return create_mcp_server()


async def _tool_names(server) -> set[str]:
    tools = await server.list_tools()
    return {tool.name for tool in tools}


async def _call_payload(server, name: str, arguments: dict | None = None) -> dict:
    _content, structured = await server.call_tool(name, arguments or {})
    assert isinstance(structured, dict)
    return structured


def test_phase_1_tool_names_registered(mcp_server) -> None:
    names = asyncio.run(_tool_names(mcp_server))
    assert names == PHASE_1_TOOL_NAMES


def test_server_check_monkeypatch(mcp_server, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("dts_utils.mcp.tools.is_server_running", lambda **kwargs: True)
    payload = asyncio.run(_call_payload(mcp_server, "dts_server_check", {"host": "127.0.0.1"}))
    assert payload["running"] is True
    assert payload["host"] == "127.0.0.1"


def test_list_and_get_config(mcp_server, tmp_path: Path) -> None:
    cfg_dir = tmp_path / "configs"
    cfg_dir.mkdir()
    (cfg_dir / "portrait.json").write_text(
        json.dumps({"model": "test.ckpt", "width": 512, "height": 512}),
        encoding="utf-8",
    )
    list_payload = asyncio.run(
        _call_payload(mcp_server, "dts_list_configs", {"config_dir": str(cfg_dir)})
    )
    assert "portrait" in list_payload["configs"]

    got_payload = asyncio.run(
        _call_payload(
            mcp_server,
            "dts_get_config",
            {"configuration": "portrait", "config_dir": str(cfg_dir)},
        )
    )
    assert got_payload["stem"] == "portrait"
    assert got_payload["json"]["model"] == "test.ckpt"


def test_expand_prompt_wildcards(mcp_server) -> None:
    payload = asyncio.run(
        _call_payload(
            mcp_server,
            "dts_expand_prompt",
            {"prompt": "fixed", "negative_prompt": "", "count": 2},
        )
    )
    assert payload["prompts"] == ["fixed", "fixed"]
    assert len(payload["negative_prompts"]) == 2


def test_expand_prompt_rejects_high_count(mcp_server) -> None:
    with pytest.raises(ToolError, match="configuration"):
        asyncio.run(
            _call_payload(mcp_server, "dts_expand_prompt", {"prompt": "x", "count": 26})
        )


def test_generate_image_stub(mcp_server, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    out = tmp_path / "out.png"

    def fake_generate_to_paths(client, gen, output_base, *, generations=1):
        out.write_bytes(b"png-bytes")
        return [out]

    monkeypatch.setattr("dts_utils.mcp.tools.generate_to_paths", fake_generate_to_paths)

    payload = asyncio.run(
        _call_payload(
            mcp_server,
            "dts_generate_image",
            {
                "prompt": "a red house",
                "output": str(out),
                "include_image_data": False,
            },
        )
    )
    assert payload["paths"] == [str(out)]
    assert "images_base64" not in payload


def test_generate_image_includes_base64_when_asked(
    mcp_server, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    out = tmp_path / "out.png"
    png = b"\x89PNG\r\n\x1a\n"

    def fake_generate_to_paths(client, gen, output_base, *, generations=1):
        out.write_bytes(png)
        return [out]

    monkeypatch.setattr("dts_utils.mcp.tools.generate_to_paths", fake_generate_to_paths)

    payload = asyncio.run(
        _call_payload(
            mcp_server,
            "dts_generate_image",
            {
                "prompt": "test",
                "output": str(out),
                "include_image_data": True,
            },
        )
    )
    assert len(payload["images_base64"]) == 1


def test_generate_image_maps_configuration_error(mcp_server) -> None:
    with pytest.raises(ToolError, match="configuration"):
        asyncio.run(
            _call_payload(
                mcp_server,
                "dts_generate_image",
                {"prompt": "x", "generations": 26},
            )
        )


def test_list_installed_models_empty_dir(mcp_server, tmp_path: Path) -> None:
    models_dir = tmp_path / "Models"
    models_dir.mkdir()
    payload = asyncio.run(
        _call_payload(
            mcp_server,
            "dts_list_installed_models",
            {"models_dir": str(models_dir), "use_index": False},
        )
    )
    assert payload["local_file_count"] == 0
    assert payload["summaries"] == []


def test_non_loopback_warning_on_generate(mcp_server, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    out = tmp_path / "out.png"

    def fake_generate_to_paths(client, gen, output_base, *, generations=1):
        out.write_bytes(b"x")
        return [out]

    monkeypatch.setattr("dts_utils.mcp.tools.generate_to_paths", fake_generate_to_paths)

    payload = asyncio.run(
        _call_payload(
            mcp_server,
            "dts_generate_image",
            {
                "prompt": "remote",
                "host": "192.168.1.10",
                "no_tls": True,
                "output": str(out),
            },
        )
    )
    assert "warning" in payload
