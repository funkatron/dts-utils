"""Tests for `dts_utils.generate_api` and stable package exports."""

from __future__ import annotations

import io
import json
import re
import shutil
import subprocess
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import grpc
import pytest
from PIL import Image

import dts_utils
from dts_utils.configuration_build import CONFIG_SCHEMA_PATH, read_configuration_bytes, resolve_flatc_path
from dts_utils.exceptions import (
    ChannelSetupError,
    ConfigurationError,
    DTSUtilError,
    GenerationCancelledError,
    GenerationEmptyError,
    GenerationRpcError,
    PromptWildcardError,
)
from dts_utils.generate_api import (
    GrpcClientOptions,
    ImageGenerationRequestOptions,
    build_image_generation_request,
    coerce_generations_json,
    collect_raw_generation_tensors,
    expand_prompt_templates_for_batch,
    generate_png_batch,
    generate_png_bytes,
    generate_to_paths,
    iter_generate_stream_dicts,
    prepare_image_generation_request,
)

from tests.test_configuration_build import _MINIMAL_DRAW_THINGS_STYLE


def _strength_from_configuration_flatbuffer(configuration: bytes, tmp_path: Path) -> float:
    """Decode ``strength`` from a Draw Things configuration FlatBuffer (requires flatc)."""
    bin_path = tmp_path / "cfg.bin"
    bin_path.write_bytes(configuration)
    out_dir = tmp_path / "flatc-out"
    out_dir.mkdir()
    subprocess.run(
        [
            resolve_flatc_path(),
            "--json",
            "--raw-binary",
            "-o",
            str(out_dir),
            str(CONFIG_SCHEMA_PATH),
            "--",
            str(bin_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    decoded = (out_dir / "cfg.json").read_text(encoding="utf-8")
    match = re.search(r"strength:\s*([0-9.]+)", decoded)
    assert match is not None, decoded
    return float(match.group(1))


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
        assert hasattr(dts_utils, name), f"missing dts_utils.{name}"
    assert set(expected).issubset(set(dts_utils.__all__))


def test_read_configuration_bytes_requires_source():
    with pytest.raises(ConfigurationError, match="Generation configuration is required"):
        read_configuration_bytes()


def test_prepare_image_generation_request_attaches_input_image(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "dts_utils.generate_api.read_configuration_bytes",
        lambda **kwargs: b"resolved",
    )
    monkeypatch.setattr(
        "dts_utils.generate_api.normalize_input_image_path",
        lambda _p: b"png-normalized",
    )
    monkeypatch.setattr(
        "dts_utils.generate_api.encode_png_to_dt_tensor",
        lambda _png: b"tensor-bytes",
    )
    image_path = tmp_path / "in.png"
    image_path.write_bytes(b"png")
    req, _, _ = prepare_image_generation_request(
        ImageGenerationRequestOptions(
            prompt="motion",
            configuration="default",
            input_image_path=image_path,
        )
    )
    assert req.image == b"tensor-bytes"


@pytest.mark.skipif(not shutil.which("flatc"), reason="flatc not on PATH")
def test_prepare_img2img_request_encodes_seventy_percent_strength(tmp_path: Path) -> None:
    """Existing input image + new prompt uses strength 0.7 from the saved JSON profile."""
    cfg_path = tmp_path / "img2img-70.json"
    cfg_path.write_text(json.dumps({**_MINIMAL_DRAW_THINGS_STYLE, "strength": 0.7}), encoding="utf-8")

    ref = Image.new("RGB", (64, 64), (120, 80, 200))
    buf = io.BytesIO()
    ref.save(buf, format="PNG")
    image_path = tmp_path / "ref.png"
    image_path.write_bytes(buf.getvalue())

    req, prompt, _ = prepare_image_generation_request(
        ImageGenerationRequestOptions(
            prompt="sunset watercolor over the scene",
            configuration_json=cfg_path,
            input_image_path=image_path,
        )
    )
    assert prompt == "sunset watercolor over the scene"
    assert req.image
    assert _strength_from_configuration_flatbuffer(req.configuration, tmp_path) == pytest.approx(0.7)


def test_build_image_generation_request(monkeypatch, tmp_path):
    config_path = tmp_path / "c.fb"
    config_path.write_bytes(b"fb-bytes")
    monkeypatch.setattr(
        "dts_utils.generate_api.read_configuration_bytes",
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


def test_prepare_image_generation_request_matches_proto_fields(monkeypatch, tmp_path):
    cfg = tmp_path / "c.fb"
    cfg.write_bytes(b"x")
    monkeypatch.setattr(
        "dts_utils.generate_api.read_configuration_bytes",
        lambda **kwargs: b"resolved",
    )
    req, ep, en = prepare_image_generation_request(
        ImageGenerationRequestOptions(
            prompt="{a|b}",
            negative_prompt="{x|y}",
            configuration=cfg,
        )
    )
    assert ep in {"a", "b"}
    assert en in {"x", "y"}
    assert req.prompt == ep
    assert req.negativePrompt == en


def test_prepare_image_generation_request_expands_wildcards_before_configuration_io(monkeypatch):
    calls: list[str] = []

    def track_read(**kwargs: object) -> bytes:
        calls.append("read_configuration_bytes")
        return b"x"

    monkeypatch.setattr("dts_utils.generate_api.read_configuration_bytes", track_read)
    with pytest.raises(PromptWildcardError, match="Unresolved"):
        prepare_image_generation_request(
            ImageGenerationRequestOptions(
                prompt="{||}",
                negative_prompt="",
                configuration="dummy-profile",
            ),
        )
    assert calls == []


def test_generate_png_batch_returns_expanded_prompts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cfg = tmp_path / "c.fb"
    cfg.write_bytes(b"x")
    monkeypatch.setattr("dts_utils.generate_api.read_configuration_bytes", lambda **k: b"x")
    seen: list[str] = []

    def fake_collect(_client: object, request: object) -> list[bytes]:
        seen.append(request.prompt)
        return [b"tensor"]

    monkeypatch.setattr("dts_utils.generate_api.collect_raw_generation_tensors", fake_collect)
    monkeypatch.setattr("dts_utils.generate_api.decode_dt_tensor_to_png", lambda _b: b"\x89PNG\r\n")

    batch = generate_png_batch(
        GrpcClientOptions(no_tls=True),
        ImageGenerationRequestOptions(prompt="{p|q}", configuration=cfg),
        generations=2,
    )
    assert len(batch.images) == 2
    assert batch.expanded_prompts == seen
    assert all(x in {"p", "q"} for x in batch.expanded_prompts)
    assert batch.expanded_negative_prompts == ["", ""]


def test_generate_png_batch_per_run_input_images(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cfg = tmp_path / "c.fb"
    cfg.write_bytes(b"x")
    in_a = tmp_path / "a.png"
    in_b = tmp_path / "b.png"
    in_a.write_bytes(b"a")
    in_b.write_bytes(b"b")
    seen_paths: list[Path | None] = []

    def fake_prepare(gen: ImageGenerationRequestOptions):
        seen_paths.append(gen.input_image_path)
        return SimpleNamespace(image=b"tensor"), gen.prompt, ""

    monkeypatch.setattr("dts_utils.generate_api.prepare_image_generation_request", fake_prepare)
    monkeypatch.setattr(
        "dts_utils.generate_api.collect_raw_generation_tensors",
        lambda _client, _request: [b"tensor"],
    )
    monkeypatch.setattr("dts_utils.generate_api.decode_dt_tensor_to_png", lambda _b: b"\x89PNG\r\n")

    batch = generate_png_batch(
        GrpcClientOptions(no_tls=True),
        ImageGenerationRequestOptions(prompt="edit", configuration=cfg),
        generations=2,
        input_images_per_run=[in_a, in_b],
    )
    assert len(batch.images) == 2
    assert seen_paths == [in_a, in_b]


def test_build_image_generation_request_invalid_wildcard_prompt(monkeypatch, tmp_path):
    cfg = tmp_path / "c.fb"
    cfg.write_bytes(b"x")
    monkeypatch.setattr(
        "dts_utils.generate_api.read_configuration_bytes",
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
        "dts_utils.generate_api.read_configuration_bytes",
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

    monkeypatch.setattr("dts_utils.generate_api.collect_generated_images", bad_collect)
    monkeypatch.setattr("dts_utils.generate_api._open_channel", lambda _c: FakeChannel())

    class PassStub:
        pass

    monkeypatch.setattr(
        "dts_utils.generate_api.up_grpc.ImageGenerationServiceStub",
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
        "dts_utils.generate_api.collect_raw_generation_tensors",
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
    monkeypatch.setattr("dts_utils.generate_api._open_channel", lambda _c: ch)
    monkeypatch.setattr(
        "dts_utils.generate_api.up_grpc.ImageGenerationServiceStub",
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
    monkeypatch.setattr("dts_utils.generate_api._open_channel", lambda _c: ch)
    monkeypatch.setattr(
        "dts_utils.generate_api.up_grpc.ImageGenerationServiceStub",
        lambda _c: stub,
    )
    config_path = tmp_path / "c.fb"
    config_path.write_bytes(b"x")
    monkeypatch.setattr("dts_utils.image_output.time.time_ns", lambda: 1_700_000_000_000_000)
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


def test_generate_png_bytes_cancel_between_batch_iterations(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg = tmp_path / "c.fb"
    cfg.write_bytes(b"x")
    cancel = threading.Event()

    def fake_collect(_client: object, request: object) -> list[bytes]:
        cancel.set()
        return [b"tensor"]

    monkeypatch.setattr("dts_utils.generate_api.collect_raw_generation_tensors", fake_collect)
    monkeypatch.setattr("dts_utils.generate_api.decode_dt_tensor_to_png", lambda _b: b"\x89PNG\r\n")

    with pytest.raises(GenerationCancelledError, match="cancelled"):
        generate_png_bytes(
            GrpcClientOptions(no_tls=True),
            ImageGenerationRequestOptions(prompt="p", configuration=cfg),
            generations=3,
            cancel_event=cancel,
        )


def test_generate_png_bytes_cancel_before_first_rpc(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cfg = tmp_path / "c.fb"
    cfg.write_bytes(b"x")
    cancel = threading.Event()
    cancel.set()
    calls: list[int] = []

    def fake_collect(_client: object, request: object) -> list[bytes]:
        calls.append(1)
        return [b"tensor"]

    monkeypatch.setattr("dts_utils.generate_api.collect_raw_generation_tensors", fake_collect)
    monkeypatch.setattr("dts_utils.generate_api.decode_dt_tensor_to_png", lambda _b: b"\x89PNG\r\n")

    with pytest.raises(GenerationCancelledError, match="cancelled"):
        generate_png_bytes(
            GrpcClientOptions(no_tls=True),
            ImageGenerationRequestOptions(prompt="p", configuration=cfg),
            generations=2,
            cancel_event=cancel,
        )
    assert calls == []


def test_generate_png_bytes_three_generations_rerolls_wildcards(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cfg = tmp_path / "c.fb"
    cfg.write_bytes(b"x")
    monkeypatch.setattr("dts_utils.generate_api.read_configuration_bytes", lambda **k: b"x")
    prompts_seen: list[str] = []

    def fake_collect(_client: object, request: object) -> list[bytes]:
        prompts_seen.append(request.prompt)
        return [b"tensor"]

    monkeypatch.setattr("dts_utils.generate_api.collect_raw_generation_tensors", fake_collect)
    monkeypatch.setattr("dts_utils.generate_api.decode_dt_tensor_to_png", lambda _b: b"\x89PNG\r\n")

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
    monkeypatch.setattr("dts_utils.generate_api._open_channel", lambda _c: ch)
    monkeypatch.setattr(
        "dts_utils.generate_api.up_grpc.ImageGenerationServiceStub",
        lambda _c: stub,
    )
    config_path = tmp_path / "c.fb"
    config_path.write_bytes(b"x")
    monkeypatch.setattr("dts_utils.generate_api.time.time_ns", lambda: 42_000_000_000_000)
    seq = iter(range(1_700_000_000_000_001, 1_700_000_000_000_099))
    monkeypatch.setattr("dts_utils.image_output.time.time_ns", lambda: next(seq))

    out = tmp_path / "batch.png"
    paths = generate_to_paths(
        GrpcClientOptions(no_tls=True),
        ImageGenerationRequestOptions(prompt="hi", configuration=config_path),
        out,
        generations=2,
    )
    assert len(paths) == 2
    assert all(p.read_bytes().startswith(b"\x89PNG") for p in paths)


def test_expand_prompt_templates_for_batch_draws_independently() -> None:
    prompts, negs = expand_prompt_templates_for_batch("{a|b}", "{x|y}", count=4)
    assert len(prompts) == len(negs) == 4
    assert all(p in {"a", "b"} for p in prompts)
    assert all(n in {"x", "y"} for n in negs)


def test_generate_png_batch_prompts_per_run(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cfg = tmp_path / "c.fb"
    cfg.write_bytes(b"x")
    monkeypatch.setattr("dts_utils.generate_api.read_configuration_bytes", lambda **k: b"x")
    prompts_seen: list[str] = []

    def fake_collect(_client: object, request: object) -> list[bytes]:
        prompts_seen.append(request.prompt)
        return [b"tensor"]

    monkeypatch.setattr("dts_utils.generate_api.collect_raw_generation_tensors", fake_collect)
    monkeypatch.setattr("dts_utils.generate_api.decode_dt_tensor_to_png", lambda _b: b"\x89PNG\r\n")

    gen = ImageGenerationRequestOptions(prompt="unused", configuration=cfg)
    batch = generate_png_batch(
        GrpcClientOptions(no_tls=True),
        gen,
        generations=2,
        prompts_per_run=["alpha", "beta"],
        negative_prompts_per_run=["", "neg"],
    )
    assert len(batch.images) == 2
    assert prompts_seen == ["alpha", "beta"]
    assert batch.expanded_prompts == prompts_seen


def test_iter_generate_stream_dicts_sequence(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cfg = tmp_path / "c.fb"
    cfg.write_bytes(b"x")
    monkeypatch.setattr("dts_utils.generate_api.read_configuration_bytes", lambda **k: b"x")

    def fake_run_stream(_client, _request, _cancel):
        yield ("preview", b"\x89PNG\r\n")
        yield ("image", b"\x89PNG\r\n")

    monkeypatch.setattr("dts_utils.generate_api._iter_generation_run_png_stream", fake_run_stream)

    gen = ImageGenerationRequestOptions(prompt="{a|b}", configuration=cfg)
    events = list(
        iter_generate_stream_dicts(GrpcClientOptions(no_tls=True), gen, generations=2),
    )
    types = [e["type"] for e in events]
    assert types[0] == "meta"
    assert types.count("progress") == 2
    assert types.count("preview") == 2
    assert types.count("image") == 2
    assert types[-1] == "done"
    for event in events:
        if event["type"] in {"progress", "preview", "image"}:
            assert event.get("total_runs") == 2
            assert event.get("run") in {1, 2}
    done = events[-1]
    assert done["type"] == "done"
    assert done["total_images"] == 2
    assert len(done["expanded_prompts"]) == 2


def test_generate_png_batch_prompts_per_run_length_mismatch(tmp_path: Path) -> None:
    cfg = tmp_path / "c.fb"
    cfg.write_bytes(b"x")
    gen = ImageGenerationRequestOptions(prompt="x", configuration=cfg)
    with pytest.raises(ConfigurationError, match="'prompts' length"):
        generate_png_batch(
            GrpcClientOptions(no_tls=True),
            gen,
            generations=2,
            prompts_per_run=["only_one"],
        )
