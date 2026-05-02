"""Tests for `dts_util.generate_api` and stable package exports."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import grpc
import pytest

import dts_util
from dts_util.configuration_build import read_configuration_bytes
from dts_util.exceptions import (
    ChannelSetupError,
    ConfigurationError,
    DTSUtilError,
    GenerationEmptyError,
    GenerationRpcError,
)
from dts_util.generate_api import (
    GrpcClientOptions,
    ImageGenerationRequestOptions,
    build_image_generation_request,
    collect_raw_generation_tensors,
    generate_png_bytes,
    generate_to_paths,
)


def test_generation_rpc_error_from_rpc_error_mock():
    exc = Mock()
    exc.code = Mock(return_value=grpc.StatusCode.UNAVAILABLE)
    exc.details = Mock(return_value="upstream down")
    err = GenerationRpcError.from_rpc_error(exc)
    assert err.code is grpc.StatusCode.UNAVAILABLE
    assert err.details == "upstream down"
    assert "UNAVAILABLE" in str(err)


def test_dts_util_public_exports():
    expected = (
        "ChannelSetupError",
        "ConfigurationError",
        "DTSUtilError",
        "GenerationEmptyError",
        "GenerationRpcError",
        "GrpcClientOptions",
        "ImageGenerationRequestOptions",
        "generate_png_bytes",
        "generate_to_paths",
    )
    for name in expected:
        assert hasattr(dts_util, name), f"missing dts_util.{name}"
    assert set(expected).issubset(set(dts_util.__all__))


def test_read_configuration_bytes_requires_source():
    with pytest.raises(ConfigurationError, match="Generation configuration is required"):
        read_configuration_bytes()


def test_build_image_generation_request(monkeypatch, tmp_path):
    config_path = tmp_path / "c.fb"
    config_path.write_bytes(b"fb-bytes")
    monkeypatch.setattr(
        "dts_util.generate_api.read_configuration_bytes",
        lambda **kwargs: b"resolved",
    )
    req = build_image_generation_request(
        ImageGenerationRequestOptions(
            prompt="hello",
            negative_prompt="no",
            configuration=config_path,
            shared_secret="s",
        )
    )
    assert req.prompt == "hello"
    assert req.negativePrompt == "no"
    assert req.configuration == b"resolved"
    assert req.sharedSecret == "s"
    assert req.chunked is True


def test_collect_raw_generation_tensors_rpc_error(monkeypatch):
    from tests.test_generate_image_script import FakeChannel

    class FakeRpc(grpc.RpcError):
        def code(self):
            return grpc.StatusCode.UNAVAILABLE

        def details(self):
            return "boom"

    def bad_collect(*_a, **_k):
        raise FakeRpc()

    monkeypatch.setattr("dts_util.generate_api.collect_generated_images", bad_collect)
    monkeypatch.setattr("dts_util.generate_api._open_channel", lambda _c: FakeChannel())

    class PassStub:
        pass

    monkeypatch.setattr(
        "dts_util.generate_api.up_grpc.ImageGenerationServiceStub",
        lambda _ch: PassStub(),
    )

    with pytest.raises(GenerationRpcError, match="RPC error"):
        collect_raw_generation_tensors(
            GrpcClientOptions(no_tls=True),
            SimpleNamespace(),
        )


def test_channel_setup_error_from_bad_tls_options(tmp_path):
    root = tmp_path / "root.pem"
    root.write_bytes(b"root")
    with pytest.raises(ChannelSetupError, match="either --root-cert"):
        collect_raw_generation_tensors(
            GrpcClientOptions(
                no_tls=False,
                root_cert=root,
                trust_server_cert=True,
            ),
            SimpleNamespace(),
        )


def test_generate_png_bytes_empty_raises(monkeypatch, tmp_path):
    (tmp_path / "x.fb").write_bytes(b"cfg")
    monkeypatch.setattr(
        "dts_util.generate_api.collect_raw_generation_tensors",
        lambda *_a, **_k: [],
    )
    with pytest.raises(GenerationEmptyError, match="No generated images"):
        generate_png_bytes(
            GrpcClientOptions(no_tls=True),
            ImageGenerationRequestOptions(prompt="p", configuration=tmp_path / "x.fb"),
        )


def test_generate_png_bytes_returns_png_magic(monkeypatch, tmp_path):
    from tests.test_generate_image_script import FakeChannel, FakeImageGenerationStub, make_uncompressed_dt_tensor

    stub = FakeImageGenerationStub([SimpleNamespace(generatedImages=[make_uncompressed_dt_tensor()])])
    ch = FakeChannel()
    monkeypatch.setattr("dts_util.generate_api._open_channel", lambda _c: ch)
    monkeypatch.setattr(
        "dts_util.generate_api.up_grpc.ImageGenerationServiceStub",
        lambda _c: stub,
    )
    config_path = tmp_path / "c.fb"
    config_path.write_bytes(b"x")
    pngs = generate_png_bytes(
        GrpcClientOptions(no_tls=True),
        ImageGenerationRequestOptions(prompt="hi", configuration=config_path),
    )
    assert len(pngs) == 1
    assert pngs[0].startswith(b"\x89PNG")
    assert ch.closed is True


def test_generate_to_paths_writes_files(monkeypatch, tmp_path):
    from tests.test_generate_image_script import FakeChannel, FakeImageGenerationStub, make_uncompressed_dt_tensor

    stub = FakeImageGenerationStub([SimpleNamespace(generatedImages=[make_uncompressed_dt_tensor()])])
    ch = FakeChannel()
    monkeypatch.setattr("dts_util.generate_api._open_channel", lambda _c: ch)
    monkeypatch.setattr(
        "dts_util.generate_api.up_grpc.ImageGenerationServiceStub",
        lambda _c: stub,
    )
    config_path = tmp_path / "c.fb"
    config_path.write_bytes(b"x")
    monkeypatch.setattr("dts_util.image_output.time.time_ns", lambda: 1_700_000_000_000_000)
    out = tmp_path / "out.png"
    paths = generate_to_paths(
        GrpcClientOptions(no_tls=True),
        ImageGenerationRequestOptions(prompt="hi", configuration=config_path),
        out,
    )
    assert len(paths) == 1
    assert paths[0].read_bytes().startswith(b"\x89PNG")
    assert paths[0].name.startswith("out-")
