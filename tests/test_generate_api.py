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
    PromptWildcardError,
)
from dts_util.generate_api import (
    GrpcClientOptions,
    ImageGenerationRequestOptions,
    build_image_generation_request,
    coerce_generations_json,
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


def test_build_image_generation_request_invalid_wildcard_prompt(monkeypatch, tmp_path):
    cfg = tmp_path / "c.fb"
    cfg.write_bytes(b"x")
    monkeypatch.setattr(
        "dts_util.generate_api.read_configuration_bytes",
        lambda **kwargs: b"resolved",
    )
    with pytest.raises(PromptWildcardError, match="Unresolved"):
        build_image_generation_request(
            ImageGenerationRequestOptions(prompt="{||}", configuration=cfg),
        )


def test_build_image_generation_request_invalid_wildcard_negative(monkeypatch, tmp_path):
    cfg = tmp_path / "c.fb"
    cfg.write_bytes(b"x")
    monkeypatch.setattr(
        "dts_util.generate_api.read_configuration_bytes",
        lambda **kwargs: b"resolved",
    )
    with pytest.raises(PromptWildcardError, match="Unresolved"):
        build_image_generation_request(
            ImageGenerationRequestOptions(prompt="ok", negative_prompt="{||}", configuration=cfg),
        )


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


def test_coerce_generations_json_defaults() -> None:
    assert coerce_generations_json(None) == 1


def test_coerce_generations_json_rejects_bool() -> None:
    with pytest.raises(ConfigurationError, match="integer"):
        coerce_generations_json(True)


def test_generate_png_bytes_invalid_generations(tmp_path: Path) -> None:
    cfg = tmp_path / "x.fb"
    cfg.write_bytes(b"c")
    with pytest.raises(ConfigurationError, match="at least"):
        generate_png_bytes(
            GrpcClientOptions(no_tls=True),
            ImageGenerationRequestOptions(prompt="p", configuration=cfg),
            generations=0,
        )


def test_generate_png_bytes_three_generations_rerolls_wildcards(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cfg = tmp_path / "c.fb"
    cfg.write_bytes(b"x")
    monkeypatch.setattr("dts_util.generate_api.read_configuration_bytes", lambda **k: b"x")
    prompts_seen: list[str] = []

    def fake_collect(_client: object, request: object) -> list[bytes]:
        prompts_seen.append(request.prompt)
        return [b"tensor"]

    monkeypatch.setattr("dts_util.generate_api.collect_raw_generation_tensors", fake_collect)
    monkeypatch.setattr("dts_util.generate_api.decode_dt_tensor_to_png", lambda _b: b"\x89PNG\r\n")

    pngs = generate_png_bytes(
        GrpcClientOptions(no_tls=True),
        ImageGenerationRequestOptions(prompt="{a|b|c}", configuration=cfg),
        generations=3,
    )
    assert len(pngs) == 3
    assert len(prompts_seen) == 3
    assert all(p in {"a", "b", "c"} for p in prompts_seen)


def test_generate_to_paths_two_generations(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
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
    monkeypatch.setattr("dts_util.generate_api.time.time_ns", lambda: 42_000_000_000_000)
    seq = iter(range(1_700_000_000_000_001, 1_700_000_000_000_099))
    monkeypatch.setattr("dts_util.image_output.time.time_ns", lambda: next(seq))

    out = tmp_path / "batch.png"
    paths = generate_to_paths(
        GrpcClientOptions(no_tls=True),
        ImageGenerationRequestOptions(prompt="hi", configuration=config_path),
        out,
        generations=2,
    )
    assert len(paths) == 2
    assert all(p.read_bytes().startswith(b"\x89PNG") for p in paths)
