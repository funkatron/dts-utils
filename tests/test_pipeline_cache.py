from __future__ import annotations

from pathlib import Path

import pytest

from dts_utils.pipeline.cache import cache_request_payload, step_cache_key
from dts_utils.pipeline.worker import _render_ffmpeg_loop


def test_cache_key_includes_image_file_content(tmp_path: Path) -> None:
    image = tmp_path / "input.png"
    image.write_bytes(b"version-a")
    key_a = step_cache_key(
        cache_namespace="image_to_video_ltx",
        executor_version="0.1.0",
        request_payload={"image_path": str(image), "fps": 12, "seconds": 2.0},
        upstream_artifact_ids=[],
        model_fingerprint="ltx",
    )
    image.write_bytes(b"version-b")
    key_b = step_cache_key(
        cache_namespace="image_to_video_ltx",
        executor_version="0.1.0",
        request_payload={"image_path": str(image), "fps": 12, "seconds": 2.0},
        upstream_artifact_ids=[],
        model_fingerprint="ltx",
    )
    assert key_a != key_b


def test_cache_request_payload_hashes_existing_image_path(tmp_path: Path) -> None:
    image = tmp_path / "frame.png"
    image.write_bytes(b"\x89PNG")
    payload = cache_request_payload({"image_path": str(image), "seed": 1})
    assert payload["image_path"]["content_sha256"]
    assert payload["image_path"]["path"].endswith("frame.png")


def test_ffmpeg_missing_raises_without_stub_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DTS_PIPELINE_ALLOW_FFMPEG_STUB", raising=False)

    def _missing(*_args, **_kwargs):
        raise FileNotFoundError("ffmpeg")

    monkeypatch.setattr("dts_utils.pipeline.worker.subprocess.run", _missing)
    image = tmp_path / "in.png"
    image.write_bytes(b"\x00")
    out = tmp_path / "out.mp4"
    with pytest.raises(RuntimeError, match="ffmpeg not found"):
        _render_ffmpeg_loop(image, out, fps=12, seconds=1.0, width=64, height=64, motion=False)


def test_ffmpeg_missing_writes_stub_when_env_set(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DTS_PIPELINE_ALLOW_FFMPEG_STUB", "1")

    def _missing(*_args, **_kwargs):
        raise FileNotFoundError("ffmpeg")

    monkeypatch.setattr("dts_utils.pipeline.worker.subprocess.run", _missing)
    image = tmp_path / "in.png"
    image.write_bytes(b"\x00")
    out = tmp_path / "out.mp4"
    _render_ffmpeg_loop(image, out, fps=12, seconds=1.0, width=64, height=64, motion=False)
    assert out.read_bytes() == b"INFOMUX-STUB-MP4"
