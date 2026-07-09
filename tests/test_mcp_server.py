"""Tests for the stdio MCP server."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from dts_utils.generate_api import GeneratePngBatchResult
from dts_utils.generation_session import generation_cancel_event
from dts_utils.mcp.server import create_mcp_server
from dts_utils.mcp.tools import MCP_TOOL_NAMES


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


def test_all_mcp_tool_names_registered(mcp_server) -> None:
    names = asyncio.run(_tool_names(mcp_server))
    assert names == MCP_TOOL_NAMES


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

    def fake_batch(client, gen, *, generations=1, cancel_event=None, **kwargs):
        return GeneratePngBatchResult(
            images=[b"png-bytes"],
            expanded_prompts=["a red house"],
            expanded_negative_prompts=[""],
        )

    monkeypatch.setattr("dts_utils.mcp.tools.generate_png_batch", fake_batch)

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
    assert len(payload["paths"]) == 1
    assert Path(payload["paths"][0]).read_bytes() == b"png-bytes"
    assert "images_base64" not in payload


def test_generate_image_with_input_image_path(mcp_server, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    out = tmp_path / "out.png"
    src = tmp_path / "ref.png"
    src.write_bytes(b"\x89PNG\r\n\x1a\n")
    seen: dict[str, object] = {}

    def fake_batch(client, gen, *, generations=1, cancel_event=None, input_images_per_run=None, **kwargs):
        seen["input_images_per_run"] = input_images_per_run
        return GeneratePngBatchResult(
            images=[b"png-bytes"],
            expanded_prompts=["styled"],
            expanded_negative_prompts=[""],
        )

    monkeypatch.setattr("dts_utils.mcp.tools.generate_png_batch", fake_batch)

    payload = asyncio.run(
        _call_payload(
            mcp_server,
            "dts_generate_image",
            {
                "prompt": "styled",
                "output": str(out),
                "input_image_path": str(src),
            },
        )
    )
    assert len(payload["paths"]) == 1
    assert seen["input_images_per_run"] == [src]


def test_generate_image_includes_base64_when_asked(
    mcp_server, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    out = tmp_path / "out.png"
    png = b"\x89PNG\r\n\x1a\n"

    def fake_batch(client, gen, *, generations=1, cancel_event=None, **kwargs):
        return GeneratePngBatchResult(
            images=[png],
            expanded_prompts=["test"],
            expanded_negative_prompts=[""],
        )

    monkeypatch.setattr("dts_utils.mcp.tools.generate_png_batch", fake_batch)

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

    def fake_batch(client, gen, *, generations=1, cancel_event=None, **kwargs):
        return GeneratePngBatchResult(images=[b"x"], expanded_prompts=["remote"], expanded_negative_prompts=[""])

    monkeypatch.setattr("dts_utils.mcp.tools.generate_png_batch", fake_batch)

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


def test_models_search(mcp_server, tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "drawthings_uncurated_models.json").write_text(
        json.dumps(
            [
                {
                    "id": "flux-1-dev",
                    "name": "FLUX.1 [dev]",
                    "type": "model",
                    "model_family": "Flux",
                    "huggingface_repo_id": "black-forest-labs/FLUX.1-dev",
                    "author": "BFL",
                    "license": "other",
                    "tags": ["flux"],
                    "metadata_path": "models/flux/metadata.json",
                    "raw_metadata_json": {},
                }
            ]
        ),
        encoding="utf-8",
    )
    payload = asyncio.run(
        _call_payload(
            mcp_server,
            "dts_models_search",
            {"query": "flux", "data_dir": str(data_dir), "limit": 5},
        )
    )
    assert payload["count"] == 1
    assert payload["results"][0]["id"] == "flux-1-dev"


def test_models_doctor_partial_file(mcp_server, tmp_path: Path) -> None:
    models_dir = tmp_path / "Models"
    models_dir.mkdir()
    (models_dir / "weights.part").write_bytes(b"partial")
    payload = asyncio.run(
        _call_payload(
            mcp_server,
            "dts_models_doctor",
            {"models_dir": str(models_dir), "data_dir": str(tmp_path / "data")},
        )
    )
    assert any(f["kind"] == "partial-download" for f in payload["findings"])
    assert payload["counts"].get("partial-download", 0) >= 1


def test_pipeline_run_stub(mcp_server, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("dts_utils.mcp.tools.is_pipeline_profile", lambda name: name == "prompt-to-video")

    def fake_execute(request):
        return SimpleNamespace(
            run_id=request.run_id or "run-1",
            run_root=str(request.run_root),
            artifacts=[{"path": "/tmp/out.mp4", "kind": "video"}],
            steps=[{"step_id": "t2i", "status": "completed"}],
        )

    monkeypatch.setattr("dts_utils.mcp.tools.execute_pipeline_run", fake_execute)

    payload = asyncio.run(
        _call_payload(
            mcp_server,
            "dts_pipeline_run",
            {
                "profile": "prompt-to-video",
                "prompt": "a rainy street",
                "run_root": str(tmp_path / "runs"),
                "run_id": "demo-run",
            },
        )
    )
    assert payload["run_id"] == "demo-run"
    assert payload["artifacts"][0]["kind"] == "video"


def test_pipeline_run_with_input_image_path(
    mcp_server, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("dts_utils.mcp.tools.is_pipeline_profile", lambda name: name == "prompt-to-video")
    seen: dict[str, object] = {}
    src = tmp_path / "start.png"
    src.write_bytes(b"\x89PNG\r\n\x1a\n")

    def fake_execute(request):
        seen["image_path"] = request.image_path
        seen["prompt"] = request.prompt
        return SimpleNamespace(
            run_id=request.run_id or "run-1",
            run_root=str(request.run_root),
            artifacts=[{"path": "/tmp/out.mp4", "kind": "video"}],
            steps=[{"step_id": "i2v", "status": "completed"}],
        )

    monkeypatch.setattr("dts_utils.mcp.tools.execute_pipeline_run", fake_execute)

    payload = asyncio.run(
        _call_payload(
            mcp_server,
            "dts_pipeline_run",
            {
                "profile": "prompt-to-video",
                "prompt": "gentle camera pan",
                "input_image_path": str(src),
                "run_root": str(tmp_path / "runs"),
                "run_id": "i2v-run",
            },
        )
    )
    assert payload["run_id"] == "i2v-run"
    assert seen["image_path"] == src
    assert seen["prompt"] == "gentle camera pan"


def test_pipeline_status_reads_heartbeat(mcp_server, tmp_path: Path) -> None:
    run_root = tmp_path / "runs"
    run_dir = run_root / "demo"
    run_dir.mkdir(parents=True)
    (run_dir / "heartbeat.json").write_text(
        json.dumps({"run_id": "demo", "step_id": "t2i", "status": "running"}),
        encoding="utf-8",
    )
    payload = asyncio.run(
        _call_payload(
            mcp_server,
            "dts_pipeline_status",
            {"run_id": "demo", "run_root": str(run_root)},
        )
    )
    assert payload["heartbeat"]["step_id"] == "t2i"
    assert payload["status"] == "running_or_incomplete"


def test_generate_cancel_sets_event(mcp_server) -> None:
    generation_cancel_event.clear()
    payload = asyncio.run(_call_payload(mcp_server, "dts_generate_cancel", {}))
    assert payload["cancel_requested"] is True
    assert generation_cancel_event.is_set()
