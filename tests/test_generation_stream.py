"""Tests for Draw Things ``GenerateImage`` stream collection."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from dts_utils.generation_stream import (
    collect_generated_images,
    iter_generate_image_stream,
    preview_payload_to_png_bytes,
)
from dts_utils.grpc.proto.upstream import imageService_pb2 as up_pb2
from tests.test_generate_image_script import make_uncompressed_dt_tensor


class _FakeStub:
    def __init__(self, responses: list[object]) -> None:
        self.responses = responses

    def GenerateImage(self, request: object):
        return iter(self.responses)


def test_collect_generated_images_debug_stderr_off_by_default(capsys, monkeypatch):
    monkeypatch.delenv("DTS_GRPC_GENERATE_DEBUG", raising=False)
    stub = _FakeStub(
        [
            SimpleNamespace(
                generatedImages=[],
                chunkState=up_pb2.LAST_CHUNK,
                previewImage=b"preview-bytes",
            ),
        ]
    )
    assert collect_generated_images(stub, SimpleNamespace()) == []
    err = capsys.readouterr().err
    assert "[dts-utils] GenerateImage stream:" not in err


@pytest.mark.parametrize("truthy", ["1", "true", "yes", "on"])
def test_collect_generated_images_debug_stderr_on(capsys, monkeypatch, truthy):
    monkeypatch.setenv("DTS_GRPC_GENERATE_DEBUG", truthy)
    stub = _FakeStub(
        [
            SimpleNamespace(
                generatedImages=[],
                chunkState=up_pb2.LAST_CHUNK,
                previewImage=b"x" * 12,
                signposts=[],
                tags=[],
            ),
        ]
    )
    assert collect_generated_images(stub, SimpleNamespace()) == []
    err = capsys.readouterr().err
    assert "[dts-utils] GenerateImage stream:" in err
    assert "seq=0" in err
    assert "generatedImages_count=0" in err
    assert "previewImage_bytes=12" in err
    assert "chunkState=LAST_CHUNK" in err


def test_collect_generated_images_preview_fallback_when_generated_images_empty():
    tensor = make_uncompressed_dt_tensor()
    stub = _FakeStub(
        [
            SimpleNamespace(
                generatedImages=[],
                chunkState=up_pb2.LAST_CHUNK,
                previewImage=b"",
            ),
            SimpleNamespace(
                generatedImages=[],
                chunkState=up_pb2.LAST_CHUNK,
                previewImage=tensor,
            ),
        ]
    )
    out = collect_generated_images(stub, SimpleNamespace())
    assert len(out) == 1
    assert out[0] == tensor


def test_collect_generated_images_prefers_generated_images_over_preview():
    tensor = make_uncompressed_dt_tensor()
    other = make_uncompressed_dt_tensor(values=[0.5, 0.5, 0.5])
    stub = _FakeStub(
        [
            SimpleNamespace(
                generatedImages=[tensor],
                chunkState=up_pb2.LAST_CHUNK,
                previewImage=other,
            ),
        ]
    )
    out = collect_generated_images(stub, SimpleNamespace())
    assert out == [tensor]


def test_collect_generated_images_preview_fallback_picks_largest_decodable():
    small = make_uncompressed_dt_tensor(width=1, height=1)
    large = make_uncompressed_dt_tensor(width=4, height=4)
    assert len(large) > len(small)
    stub = _FakeStub(
        [
            SimpleNamespace(
                generatedImages=[],
                chunkState=up_pb2.LAST_CHUNK,
                previewImage=small,
            ),
            SimpleNamespace(
                generatedImages=[],
                chunkState=up_pb2.LAST_CHUNK,
                previewImage=large,
            ),
        ]
    )
    out = collect_generated_images(stub, SimpleNamespace())
    assert len(out) == 1
    assert out[0] == large


def test_preview_payload_to_png_bytes_accepts_raw_png():
    png = b"\x89PNG\r\n\x1a\n" + b"x" * 32
    assert preview_payload_to_png_bytes(png) == png


def test_iter_generate_image_stream_yields_preview_before_image():
    tensor = make_uncompressed_dt_tensor()
    stub = _FakeStub(
        [
            SimpleNamespace(
                generatedImages=[],
                chunkState=up_pb2.LAST_CHUNK,
                previewImage=tensor,
            ),
            SimpleNamespace(
                generatedImages=[tensor],
                chunkState=up_pb2.LAST_CHUNK,
                previewImage=b"",
            ),
        ]
    )
    events = list(iter_generate_image_stream(stub, SimpleNamespace()))
    assert [kind for kind, _payload in events] == ["preview", "image"]
    assert events[0][1].startswith(b"\x89PNG\r\n\x1a\n")
    assert events[1][1] == tensor
