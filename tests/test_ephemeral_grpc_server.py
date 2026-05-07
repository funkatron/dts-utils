"""Unit tests for ``tests/ephemeral_grpc_server.py`` helpers."""

from __future__ import annotations

from pathlib import Path

from ephemeral_grpc_server import first_model_checkpoint_basename


def test_first_model_checkpoint_prefers_safetensors_over_ckpt(tmp_path: Path) -> None:
    (tmp_path / "z.ckpt").write_bytes(b"x")
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "a.safetensors").write_bytes(b"x")
    assert first_model_checkpoint_basename(tmp_path) == "a.safetensors"


def test_first_model_checkpoint_returns_none_when_empty(tmp_path: Path) -> None:
    assert first_model_checkpoint_basename(tmp_path) is None
