"""Tests for MCP resources and prompts (Phase 3)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from dts_utils.exceptions import ConfigurationError
from dts_utils.mcp.paths import resolve_output_resource_path
from dts_utils.mcp.resources import MCP_PROMPT_NAMES, RESOURCE_URI_TEMPLATES
from dts_utils.mcp.server import create_mcp_server


@pytest.fixture
def mcp_server():
    return create_mcp_server()


async def _resource_templates(server) -> set[str]:
    templates = await server.list_resource_templates()
    return {template.uriTemplate for template in templates}


async def _read_resource_text(server, uri: str) -> str:
    contents = await server.read_resource(uri)
    assert len(contents) == 1
    return contents[0].content


async def _read_resource_bytes(server, uri: str) -> bytes:
    contents = await server.read_resource(uri)
    assert len(contents) == 1
    raw = contents[0].content
    return raw.encode("latin-1") if isinstance(raw, str) else raw


def test_resource_templates_registered(mcp_server) -> None:
    templates = asyncio.run(_resource_templates(mcp_server))
    assert RESOURCE_URI_TEMPLATES <= templates


def test_prompts_registered(mcp_server) -> None:
    prompts = asyncio.run(mcp_server.list_prompts())
    names = {prompt.name for prompt in prompts}
    assert MCP_PROMPT_NAMES <= names


def test_read_config_resource(mcp_server, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg_dir = tmp_path / "configurations"
    cfg_dir.mkdir()
    (cfg_dir / "portrait.json").write_text(
        json.dumps({"model": "test.ckpt"}),
        encoding="utf-8",
    )
    monkeypatch.setattr("dts_utils.configs.configurations_dir", lambda: cfg_dir)
    monkeypatch.setattr("dts_utils.configs.configuration_search_directories", lambda config_dir=None: (cfg_dir,))

    text = asyncio.run(_read_resource_text(mcp_server, "dts://config/portrait"))
    payload = json.loads(text)
    assert payload["model"] == "test.ckpt"


def test_read_output_resource(mcp_server, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    out_dir = tmp_path / "output"
    out_dir.mkdir()
    png = out_dir / "demo.png"
    png.write_bytes(b"\x89PNG\r\n")
    monkeypatch.chdir(tmp_path)
    data = asyncio.run(_read_resource_bytes(mcp_server, "dts://output/demo.png"))
    assert data.startswith(b"\x89PNG")


def test_output_path_traversal_rejected() -> None:
    with pytest.raises(ConfigurationError):
        resolve_output_resource_path("../secret.png")


def test_read_pipeline_resource(mcp_server, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run_root = tmp_path / "runs"
    artifact = run_root / "demo-run" / "t2i" / "image.png"
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b"png-data")
    monkeypatch.setenv("DTS_MCP_PIPELINE_RUN_ROOT", str(run_root))

    data = asyncio.run(
        _read_resource_bytes(mcp_server, "dts://pipeline/demo-run/t2i/image.png")
    )
    assert data == b"png-data"


def test_config_resource_missing_file(mcp_server, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg_dir = tmp_path / "configurations"
    cfg_dir.mkdir()
    monkeypatch.setattr("dts_utils.configs.configurations_dir", lambda: cfg_dir)
    monkeypatch.setattr("dts_utils.configs.configuration_search_directories", lambda config_dir=None: (cfg_dir,))

    with pytest.raises((ToolError, ValueError)):
        asyncio.run(_read_resource_text(mcp_server, "dts://config/missing"))
