"""Tests for ``dts-utils server list-models`` (gRPC Echo catalog)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import grpc
import pytest

from dts_utils.grpc import server_catalog as sc
from dts_utils.grpc.proto.upstream import imageService_pb2 as pb


def _echo_reply(*, message: str = "HELLO dts-utils", files: list[str] | None = None, override: bool = True) -> pb.EchoReply:
    reply = pb.EchoReply(message=message)
    if files:
        reply.files.extend(files)
    if override:
        reply.override.models = b"\x01\x02"
        reply.override.loras = b"\x03"
    return reply


def test_fetch_server_catalog_returns_sorted_files() -> None:
    reply = _echo_reply(files=["b.ckpt", "a.ckpt"])
    channel = MagicMock()
    stub = MagicMock()
    stub.Echo.return_value = reply

    with (
        patch("dts_utils.grpc.server_catalog.create_channel", return_value=channel),
        patch("dts_utils.grpc.server_catalog.grpc_stub.ImageGenerationServiceStub", return_value=stub),
        patch("dts_utils.grpc.server_catalog.grpc.channel_ready_future") as ready_future,
    ):
        ready_future.return_value.result.return_value = None
        catalog = sc.fetch_server_catalog(trust_server_cert=True)

    assert catalog.message == "HELLO dts-utils"
    assert catalog.files == ["a.ckpt", "b.ckpt"]
    assert catalog.override_bytes["models"] == 2
    assert catalog.model_browser_enabled is True
    stub.Echo.assert_called_once()
    channel.close.assert_called_once()


def test_format_server_catalog_filters_category() -> None:
    catalog = sc.ServerCatalog(
        message="HELLO",
        files=["real.ckpt", "tiny_lora_f16.ckpt"],
        override_bytes={"models": 10},
    )
    text = sc.format_server_catalog(catalog, category="model")
    assert "real.ckpt" in text
    assert "tiny_lora_f16.ckpt" not in text


def test_format_server_catalog_clips_long_filenames() -> None:
    long_name = ("x" * 60) + ".ckpt"
    assert len(long_name) > sc._FILE_COLUMN_WIDTH
    catalog = sc.ServerCatalog(message="HELLO", files=[long_name, "short.ckpt"])
    text = sc.format_server_catalog(catalog)
    long_line = next(line for line in text.splitlines() if "…" in line)
    short_line = next(line for line in text.splitlines() if line.startswith("short.ckpt"))
    assert long_name not in text
    assert long_line[sc._FILE_COLUMN_WIDTH] == " "
    assert short_line[sc._FILE_COLUMN_WIDTH] == " "
    assert long_line[sc._FILE_COLUMN_WIDTH + 1 :].lstrip().startswith("model")
    assert short_line[sc._FILE_COLUMN_WIDTH + 1 :].lstrip().startswith("model")


def test_format_server_catalog_includes_human_size(tmp_path: Path) -> None:
    models_dir = tmp_path / "Models"
    models_dir.mkdir()
    big = models_dir / "big.ckpt"
    big.write_bytes(b"x" * (2 * 1024 * 1024 + 512 * 1024))  # 2.5 MiB
    catalog = sc.ServerCatalog(message="HELLO", files=["big.ckpt", "missing.ckpt"])
    sizes = sc.local_model_file_sizes(models_dir)
    text = sc.format_server_catalog(
        catalog,
        file_sizes=sizes,
        models_dir=models_dir,
    )
    assert "SIZE" in text
    assert "SIZE_MB" not in text
    assert "Local sizes from:" in text
    assert "2.5 MB" in text
    missing_line = next(line for line in text.splitlines() if "missing.ckpt" in line)
    assert missing_line.rstrip().endswith("-")


def test_catalog_to_json_includes_size_fields(tmp_path: Path) -> None:
    models_dir = tmp_path / "Models"
    models_dir.mkdir()
    (models_dir / "a.ckpt").write_bytes(b"y" * (1024 * 1024))
    catalog = sc.ServerCatalog(message="HELLO", files=["a.ckpt", "b_lora_f16.ckpt"])
    payload = sc.catalog_to_json(
        catalog,
        file_sizes=sc.local_model_file_sizes(models_dir),
        models_dir=models_dir,
    )
    assert payload["file_count"] == 2
    assert payload["models_dir"] == str(models_dir)
    by_name = {entry["name"]: entry for entry in payload["files"]}
    assert by_name["a.ckpt"]["size_bytes"] == 1024 * 1024
    assert by_name["a.ckpt"]["size_mb"] == 1.0
    assert by_name["a.ckpt"]["size"] == "1.0 MB"
    assert by_name["b_lora_f16.ckpt"]["size_bytes"] is None
    assert by_name["b_lora_f16.ckpt"]["size_mb"] is None
    assert by_name["b_lora_f16.ckpt"]["size"] is None
    assert "model" in payload["files_by_category"]
    assert "lora" in payload["files_by_category"]


def test_catalog_to_json_groups_by_category() -> None:
    catalog = sc.ServerCatalog(message="HELLO", files=["a.ckpt", "b_lora_f16.ckpt"])
    payload = sc.catalog_to_json(catalog)
    assert payload["file_count"] == 2
    assert "model" in payload["files_by_category"]
    assert "lora" in payload["files_by_category"]


def test_list_server_catalog_empty_catalog_exits_nonzero(capsys: pytest.CaptureFixture[str]) -> None:
    catalog = sc.ServerCatalog(message="HELLO", files=[], override_bytes={})
    args = argparse.Namespace(
        host="localhost",
        port=7859,
        timeout=2.0,
        no_tls=False,
        root_cert=None,
        trust_server_cert=False,
        force_trust_server_cert=False,
        shared_secret=None,
        json=False,
        category=None,
        limit=0,
        model_dir=None,
    )
    with patch("dts_utils.grpc.server_catalog.fetch_server_catalog", return_value=catalog):
        code = sc.list_server_catalog(args)
    assert code == 1
    err = capsys.readouterr().err
    assert "model browsing" in err


def test_list_server_catalog_remote_without_trust_exits_2(capsys: pytest.CaptureFixture[str]) -> None:
    args = argparse.Namespace(
        host="gpu.local",
        port=7859,
        timeout=2.0,
        no_tls=False,
        root_cert=None,
        trust_server_cert=False,
        force_trust_server_cert=False,
        shared_secret=None,
        json=False,
        category=None,
        limit=0,
        model_dir=None,
    )
    code = sc.list_server_catalog(args)
    assert code == 2
    assert "TLS requires" in capsys.readouterr().err


def test_list_server_catalog_grpc_error_exits_1(capsys: pytest.CaptureFixture[str]) -> None:
    args = argparse.Namespace(
        host="localhost",
        port=7859,
        timeout=2.0,
        no_tls=False,
        root_cert=None,
        trust_server_cert=True,
        force_trust_server_cert=False,
        shared_secret=None,
        json=False,
        category=None,
        limit=0,
        model_dir=None,
    )
    error = grpc.RpcError()
    error.code = lambda: grpc.StatusCode.UNAVAILABLE
    error.details = lambda: "connection refused"
    with patch("dts_utils.grpc.server_catalog.fetch_server_catalog", side_effect=error):
        code = sc.list_server_catalog(args)
    assert code == 1
    assert "UNAVAILABLE" in capsys.readouterr().err


def test_server_list_models_command_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["dts-utils", "server", "list-models", "--json"])

    with patch("dts_utils.grpc.server_catalog.main", return_value=0) as mock_main:
        from dts_utils.cli_router import main

        with pytest.raises(SystemExit) as exc_info:
            main()

    assert exc_info.value.code == 0
    mock_main.assert_called_once_with(["--json"])
