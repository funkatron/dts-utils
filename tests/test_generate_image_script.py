"""Functional tests for `dts_utils.generate` (`dts-utils generate`)."""

from __future__ import annotations

import json
import os
from importlib import import_module, reload
from pathlib import Path
import struct
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pytest

from dts_utils import cli_router
from dts_utils.configs import DEFAULT_CONFIGURATION_ENV, DEFAULT_PROFILE_NAME

_FIXED_MS = 1_735_123_456_789
_FIXED_NS = _FIXED_MS * 1_000_000


def load_generate_image_module():
    return reload(import_module("dts_utils.generate"))


class FakeChannel:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class FakeImageGenerationStub:
    def __init__(self, responses):
        self.responses = responses
        self.request = None

    def GenerateImage(self, request):
        self.request = request
        return iter(self.responses)


def make_uncompressed_dt_tensor(width=1, height=1, channels=3, values=None):
    header = [0] * 17
    header[1] = 1
    header[2] = 2
    header[3] = 131072
    header[5] = 1
    header[6] = height
    header[7] = width
    header[8] = channels
    if values is None:
        values = [0] * (width * height * channels)
    return struct.pack("<17I", *header) + np.array(values, dtype=np.float16).tobytes()


def _patch_generate_client(monkeypatch, channel, stub):
    """Route generate_api gRPC calls to fakes (implementation is no longer on dts_utils.generate)."""
    monkeypatch.setattr("dts_utils.generate_api.create_channel", lambda *args, **kwargs: channel)
    monkeypatch.setattr(
        "dts_utils.generate_api.up_grpc.ImageGenerationServiceStub",
        lambda created_channel: stub,
    )


def test_generate_image_script_writes_generated_images(monkeypatch, tmp_path):
    """Exercise the script from CLI args through streamed response image writes."""
    module = load_generate_image_module()
    monkeypatch.setattr("dts_utils.image_output.time.time_ns", lambda: _FIXED_NS)
    channel = FakeChannel()
    stub = FakeImageGenerationStub(
        [
            SimpleNamespace(generatedImages=[make_uncompressed_dt_tensor(values=[-1, 0, 1])]),
            SimpleNamespace(generatedImages=[make_uncompressed_dt_tensor(values=[1, 0, -1])]),
        ]
    )
    output_path = tmp_path / "result.png"
    config_path = tmp_path / "configuration.fb"
    config_path.write_bytes(b"flatbuffer-config")

    _patch_generate_client(monkeypatch, channel, stub)

    result = module.main(
        [
            "--prompt",
            "a small robot painting clouds",
            "--negative-prompt",
            "blurry",
            "--output",
            str(output_path),
            "--configuration",
            str(config_path),
            "--shared-secret",
            "secret",
            "--no-tls",
        ]
    )

    assert result == 0
    assert channel.closed is True
    stamped = tmp_path / f"result-{_FIXED_MS}.png"
    assert stamped.read_bytes().startswith(b"\x89PNG")
    assert (tmp_path / f"result-{_FIXED_MS}-2.png").read_bytes().startswith(b"\x89PNG")
    assert stub.request.prompt == "a small robot painting clouds"
    assert stub.request.negativePrompt == "blurry"
    assert stub.request.sharedSecret == "secret"
    assert stub.request.chunked is True


def test_generate_image_script_can_open_generated_images(monkeypatch, tmp_path):
    """Verify --open launches the default viewer after successful writes."""
    module = load_generate_image_module()
    monkeypatch.setattr("dts_utils.image_output.time.time_ns", lambda: _FIXED_NS)
    stub = FakeImageGenerationStub([SimpleNamespace(generatedImages=[make_uncompressed_dt_tensor()])])
    opened_paths = []
    output_path = tmp_path / "result.png"
    config_path = tmp_path / "configuration.fb"
    config_path.write_bytes(b"flatbuffer-config")

    _patch_generate_client(monkeypatch, FakeChannel(), stub)
    monkeypatch.setattr(module, "open_images", lambda paths: opened_paths.extend(paths))

    result = module.main(
        [
            "--prompt",
            "open this image",
            "--output",
            str(output_path),
            "--configuration",
            str(config_path),
            "--open",
        ]
    )

    assert result == 0
    stamped = tmp_path / f"result-{_FIXED_MS}.png"
    assert opened_paths == [stamped]
    assert stamped.read_bytes().startswith(b"\x89PNG")


def test_generate_image_script_sends_configuration_bytes(monkeypatch, tmp_path):
    """Verify a Draw Things FlatBuffer configuration file is sent as raw bytes."""
    module = load_generate_image_module()
    config_path = tmp_path / "configuration.fb"
    config_path.write_bytes(b"flatbuffer-config")
    stub = FakeImageGenerationStub([SimpleNamespace(generatedImages=[make_uncompressed_dt_tensor()])])

    _patch_generate_client(monkeypatch, FakeChannel(), stub)

    result = module.main(
        [
            "--prompt",
            "test prompt",
            "--configuration",
            str(config_path),
            "--output",
            str(tmp_path / "result.png"),
        ]
    )

    assert result == 0
    assert stub.request.configuration == b"flatbuffer-config"


def test_generate_image_script_auto_converts_json_configuration(monkeypatch, tmp_path):
    """Verify --configuration converts existing .json files to FlatBuffer bytes."""
    module = load_generate_image_module()
    config_path = tmp_path / "configuration.json"
    config_path.write_text('{"steps": 8, "model": "model.ckpt"}', encoding="utf-8")
    stub = FakeImageGenerationStub([SimpleNamespace(generatedImages=[make_uncompressed_dt_tensor()])])
    captured_config = {}

    _patch_generate_client(monkeypatch, FakeChannel(), stub)

    def fake_json_configuration_to_flatbuffer(config):
        captured_config["config"] = config
        return b"flatbuffer-json"

    monkeypatch.setattr(
        "dts_utils.configuration_build.json_configuration_to_flatbuffer",
        fake_json_configuration_to_flatbuffer,
    )

    result = module.main(
        [
            "--prompt",
            "test prompt",
            "--configuration",
            str(config_path),
            "--output",
            str(tmp_path / "result.png"),
        ]
    )

    assert result == 0
    assert captured_config["config"] == {"steps": 8, "model": "model.ckpt"}
    assert stub.request.configuration == b"flatbuffer-json"


def test_generate_image_script_resolves_named_json_configuration(monkeypatch, tmp_path):
    """Verify --configuration can resolve a saved config name."""
    module = load_generate_image_module()
    saved_dir = tmp_path / "configs"
    saved_dir.mkdir()
    (saved_dir / "portrait.json").write_text('{"steps": 12}', encoding="utf-8")
    stub = FakeImageGenerationStub([SimpleNamespace(generatedImages=[make_uncompressed_dt_tensor()])])

    _patch_generate_client(monkeypatch, FakeChannel(), stub)
    monkeypatch.setattr(
        "dts_utils.configuration_build.resolve_configuration_value",
        lambda value, config_dir=None: saved_dir / f"{value}.json",
    )
    monkeypatch.setattr(
        "dts_utils.configuration_build.json_configuration_to_flatbuffer",
        lambda config: b"named-config",
    )

    result = module.main(
        [
            "--prompt",
            "test prompt",
            "--configuration",
            "portrait",
            "--output",
            str(tmp_path / "result.png"),
        ]
    )

    assert result == 0
    assert stub.request.configuration == b"named-config"


def test_generate_image_script_sends_flatbuffer_from_json_configuration(monkeypatch, tmp_path):
    """Verify JSON config files are converted to FlatBuffer configuration bytes."""
    module = load_generate_image_module()
    config_path = tmp_path / "configuration.json"
    config_path.write_text(
        """
        {
          "steps": 8,
          "model": "pikon_realism_v2_alt_q6p_q8p.ckpt",
          "controls": []
        }
        """,
        encoding="utf-8",
    )
    stub = FakeImageGenerationStub([SimpleNamespace(generatedImages=[make_uncompressed_dt_tensor()])])
    captured_config = {}

    _patch_generate_client(monkeypatch, FakeChannel(), stub)

    def fake_json_configuration_to_flatbuffer(config):
        captured_config["config"] = config
        return b"flatbuffer-json"

    monkeypatch.setattr(
        "dts_utils.configuration_build.json_configuration_to_flatbuffer",
        fake_json_configuration_to_flatbuffer,
    )

    result = module.main(
        [
            "--prompt",
            "test prompt",
            "--configuration-json",
            str(config_path),
            "--output",
            str(tmp_path / "result.png"),
        ]
    )

    assert result == 0
    assert captured_config["config"] == {
        "steps": 8,
        "model": "pikon_realism_v2_alt_q6p_q8p.ckpt",
        "controls": [],
    }
    assert stub.request.configuration == b"flatbuffer-json"


def test_normalize_configuration_for_flatc_maps_draw_things_json():
    """Verify Draw Things camelCase JSON is transformed for config.fbs."""
    module = load_generate_image_module()

    normalized = module.normalize_configuration_for_flatc(
        {
            "width": 768,
            "height": 1024,
            "batchCount": 1,
            "guidanceScale": 3,
            "hiresFix": False,
            "model": "pikon_realism_v2_alt_q6p_q8p.ckpt",
            "controls": [],
            "faceRestoration": "",
        }
    )

    assert normalized == {
        "start_width": 12,
        "start_height": 16,
        "batch_count": 1,
        "guidance_scale": 3,
        "hires_fix": False,
        "model": "pikon_realism_v2_alt_q6p_q8p.ckpt",
    }


def test_normalize_compression_artifacts_enum_lowercase():
    """Draw Things exports compressionArtifacts as lowercase; flatc expects CompressionMethod labels."""
    module = load_generate_image_module()
    out = module.normalize_configuration_for_flatc(
        {"model": "x.ckpt", "compressionArtifacts": "disabled"},
    )
    assert out["compression_artifacts"] == "Disabled"
    out2 = module.normalize_configuration_for_flatc(
        {"compression_artifacts": "h265"},
    )
    assert out2["compression_artifacts"] == "H265"


def test_configurations_equivalent_for_flatbuffer_aliases_and_metadata():
    """Same flatc input after normalization → equivalent; real differences → not."""
    module = load_generate_image_module()
    eq = module.configurations_equivalent_for_flatbuffer

    # Dimension keys are always divided by 64 (pixel counts), same as width/height aliases.
    base_snake = {
        "start_width": 768,
        "start_height": 1024,
        "batch_count": 1,
        "guidance_scale": 3,
        "hires_fix": False,
        "model": "pikon_realism_v2_alt_q6p_q8p.ckpt",
    }
    base_camel = {
        "width": 768,
        "height": 1024,
        "batchCount": 1,
        "guidanceScale": 3,
        "hiresFix": False,
        "model": "pikon_realism_v2_alt_q6p_q8p.ckpt",
        "controls": [],
        "faceRestoration": "",
    }
    assert eq(base_snake, base_camel) is True

    low_ca = {"model": "x.ckpt", "compressionArtifacts": "disabled"}
    pascal_ca = {"model": "x.ckpt", "compression_artifacts": "Disabled"}
    assert eq(low_ca, pascal_ca) is True

    with_meta = {**base_camel, "_dts_utils_saved_from": "web"}
    assert eq(base_camel, with_meta) is True

    tweaked = {**base_camel, "guidanceScale": 4}
    assert eq(base_camel, tweaked) is False


def test_generate_image_script_rejects_non_object_json_configuration(tmp_path, capsys):
    """Verify JSON config files must contain an object."""
    module = load_generate_image_module()
    config_path = tmp_path / "configuration.json"
    config_path.write_text("[]", encoding="utf-8")

    result = module.main(
        [
            "--prompt",
            "test prompt",
            "--configuration-json",
            str(config_path),
            "--output",
            str(tmp_path / "result.png"),
        ]
    )

    captured = capsys.readouterr()
    assert result == 1
    assert "JSON configuration must be an object" in captured.err


def test_generate_image_script_fails_when_no_images_returned(monkeypatch, tmp_path, capsys):
    """Verify the script reports a failed generation when the stream has no images."""
    module = load_generate_image_module()
    stub = FakeImageGenerationStub([SimpleNamespace(generatedImages=[])])
    config_path = tmp_path / "configuration.fb"
    config_path.write_bytes(b"flatbuffer-config")

    _patch_generate_client(monkeypatch, FakeChannel(), stub)

    result = module.main(
        [
            "--prompt",
            "empty response",
            "--configuration",
            str(config_path),
            "--output",
            str(tmp_path / "result.png"),
        ]
    )

    captured = capsys.readouterr()
    assert result == 1
    assert "No generated images returned" in captured.err
    assert list(tmp_path.glob("result*.png")) == []


def test_unique_ms_timestamp_output_path(monkeypatch):
    """Unix milliseconds are inserted before the extension."""
    module = load_generate_image_module()
    monkeypatch.setattr("dts_utils.image_output.time.time_ns", lambda: _FIXED_NS)
    assert module.unique_ms_timestamp_output_path(Path("generated.png")) == Path(f"generated-{_FIXED_MS}.png")
    assert module.unique_ms_timestamp_output_path(Path("out/foo.bar.webp")) == Path(f"out/foo.bar-{_FIXED_MS}.webp")


def test_generate_image_script_requires_configuration(capsys):
    """Verify prompt-only calls fail before opening a gRPC stream."""
    module = load_generate_image_module()

    result = module.main(["--prompt", "missing config"])

    captured = capsys.readouterr()
    assert result == 1
    assert "Generation configuration is required" in captured.err


def test_generate_image_script_reports_missing_named_configuration(capsys):
    """Verify missing config names produce an actionable configuration error."""
    module = load_generate_image_module()

    result = module.main(["--prompt", "missing config", "--configuration", "does-not-exist"])

    captured = capsys.readouterr()
    assert result == 1
    assert "Could not resolve generation configuration" in captured.err
    assert "uv run dts-utils configs path" in captured.err


def test_dts_util_main_dispatches_generate(monkeypatch):
    """Verify dts-utils generate is routed before installer argument parsing."""
    monkeypatch.setattr("sys.argv", ["dts-utils", "generate", "--prompt", "test", "--configuration", "portrait"])
    with patch.object(cli_router, "generate_main", return_value=0) as generate_main:
        with pytest.raises(SystemExit) as exc_info:
            cli_router.main()

    generate_main.assert_called_once_with(["--prompt", "test", "--configuration", "portrait"])
    assert exc_info.value.code == 0


def test_dts_util_main_generate_shorthand_prompt_and_profile(monkeypatch):
    """``dts-utils PROMPT PROFILE`` expands to generate with trust + open defaults."""
    monkeypatch.setattr("sys.argv", ["dts-utils", "hello", "portrait"])
    with patch.object(cli_router, "generate_main", return_value=0) as generate_main:
        with pytest.raises(SystemExit) as exc_info:
            cli_router.main()

    generate_main.assert_called_once_with(
        ["--prompt", "hello", "--configuration", "portrait", "--trust-server-cert", "--open"]
    )
    assert exc_info.value.code == 0


def test_dts_util_main_generate_shorthand_default_from_env(monkeypatch):
    monkeypatch.setenv(DEFAULT_CONFIGURATION_ENV, "landscape")
    monkeypatch.setattr("sys.argv", ["dts-utils", "hello"])
    with patch.object(cli_router, "generate_main", return_value=0) as generate_main:
        with pytest.raises(SystemExit) as exc_info:
            cli_router.main()

    generate_main.assert_called_once_with(
        ["--prompt", "hello", "--configuration", "landscape", "--trust-server-cert", "--open"]
    )
    assert exc_info.value.code == 0


def test_dts_util_main_generate_shorthand_default_json(monkeypatch, tmp_path):
    monkeypatch.delenv(DEFAULT_CONFIGURATION_ENV, raising=False)
    monkeypatch.setattr("dts_utils.configs.configurations_dir", lambda: tmp_path)
    (tmp_path / "default.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["dts-utils", "hello"])
    with patch.object(cli_router, "generate_main", return_value=0) as generate_main:
        with pytest.raises(SystemExit) as exc_info:
            cli_router.main()

    generate_main.assert_called_once_with(
        [
            "--prompt",
            "hello",
            "--configuration",
            DEFAULT_PROFILE_NAME,
            "--trust-server-cert",
            "--open",
        ]
    )
    assert exc_info.value.code == 0


def test_dts_util_main_generate_shorthand_auto_creates_default_json(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv(DEFAULT_CONFIGURATION_ENV, raising=False)
    monkeypatch.delenv("DTS_UTILS_DEFAULT_MODEL", raising=False)
    monkeypatch.delenv("DRAW_THINGS_MODEL_PATH", raising=False)
    monkeypatch.setattr("dts_utils.configs.configurations_dir", lambda: tmp_path)
    monkeypatch.setattr("dts_utils.configs.guess_default_model_basename", lambda: "")
    monkeypatch.setattr("sys.argv", ["dts-utils", "hello"])
    with patch.object(cli_router, "generate_main", return_value=0) as generate_main:
        with pytest.raises(SystemExit) as exc_info:
            cli_router.main()

    assert exc_info.value.code == 0
    default_path = tmp_path / f"{DEFAULT_PROFILE_NAME}.json"
    assert default_path.is_file()
    data = json.loads(default_path.read_text())
    assert data["width"] == 512
    assert "model" in data
    generate_main.assert_called_once_with(
        [
            "--prompt",
            "hello",
            "--configuration",
            DEFAULT_PROFILE_NAME,
            "--trust-server-cert",
            "--open",
        ]
    )
    assert os.environ.get(DEFAULT_CONFIGURATION_ENV) == DEFAULT_PROFILE_NAME
    err = capsys.readouterr().err
    assert "created default.json" in err


def test_dts_util_main_generate_shorthand_too_many_positionals(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["dts-utils", "a", "b", "c"])
    with patch.object(cli_router, "generate_main") as generate_main:
        with pytest.raises(SystemExit) as exc_info:
            cli_router.main()

    generate_main.assert_not_called()
    assert exc_info.value.code == 2
    assert "too many positional arguments" in capsys.readouterr().err


def test_dts_util_main_generate_shorthand_passes_trailing_flags(monkeypatch):
    monkeypatch.setattr("sys.argv", ["dts-utils", "hello", "portrait", "--negative-prompt", "blur"])
    with patch.object(cli_router, "generate_main", return_value=0) as generate_main:
        with pytest.raises(SystemExit) as exc_info:
            cli_router.main()

    generate_main.assert_called_once_with(
        [
            "--prompt",
            "hello",
            "--configuration",
            "portrait",
            "--trust-server-cert",
            "--open",
            "--negative-prompt",
            "blur",
        ]
    )
    assert exc_info.value.code == 0


def test_create_channel_can_trust_presented_server_certificate(monkeypatch):
    """Verify TLS credentials can be built from the server's presented certificate."""
    from dts_utils.grpc import connection as grpc_connection

    calls = {}

    monkeypatch.setattr(grpc_connection, "fetch_server_certificate", lambda host, port: b"server-cert")

    def fake_ssl_channel_credentials(root_certificates=None):
        calls["root_certificates"] = root_certificates
        return "credentials"

    def fake_secure_channel(target, credentials, options=None):
        calls["target"] = target
        calls["credentials"] = credentials
        calls["options"] = options
        return "channel"

    monkeypatch.setattr(grpc_connection.grpc, "ssl_channel_credentials", fake_ssl_channel_credentials)
    monkeypatch.setattr(grpc_connection.grpc, "secure_channel", fake_secure_channel)

    channel = grpc_connection.create_channel("localhost", 7859, insecure=False, trust_server_cert=True)

    assert channel == "channel"
    assert calls == {
        "root_certificates": b"server-cert",
        "target": "localhost:7859",
        "credentials": "credentials",
        "options": [
            ("grpc.max_send_message_length", 64 * 1024 * 1024),
            ("grpc.max_receive_message_length", 64 * 1024 * 1024),
        ],
    }


def test_create_channel_rejects_conflicting_cert_options(tmp_path):
    """Verify callers cannot combine trust-on-first-use and a pinned root certificate."""
    from dts_utils.grpc import connection as grpc_connection

    root_cert = tmp_path / "root.pem"
    root_cert.write_bytes(b"root")

    try:
        grpc_connection.create_channel("localhost", 7859, insecure=False, root_cert=root_cert, trust_server_cert=True)
    except ValueError as exc:
        assert "either --root-cert or a trust-server-cert option" in str(exc)
    else:
        raise AssertionError("Expected conflicting certificate options to fail")


def test_create_channel_rejects_trusting_remote_presented_certificate():
    """Verify trust-on-first-use is restricted to explicit loopback hosts."""
    from dts_utils.grpc import connection as grpc_connection

    try:
        grpc_connection.create_channel("drawthings.example.com", 7859, insecure=False, trust_server_cert=True)
    except ValueError as exc:
        assert "only allowed for localhost or loopback" in str(exc)
        assert "--force-trust-server-cert" in str(exc)
    else:
        raise AssertionError("Expected remote trust-on-first-use to fail")


def test_create_channel_can_force_trust_remote_presented_certificate(monkeypatch):
    """Verify the explicit unsafe escape hatch trusts remote presented certificates."""
    from dts_utils.grpc import connection as grpc_connection

    calls = {}
    monkeypatch.setattr(grpc_connection, "fetch_server_certificate", lambda host, port: b"remote-cert")
    monkeypatch.setattr(
        grpc_connection.grpc,
        "ssl_channel_credentials",
        lambda root_certificates=None: calls.setdefault("root_certificates", root_certificates) or "credentials",
    )
    monkeypatch.setattr(
        grpc_connection.grpc,
        "secure_channel",
        lambda target, credentials, options=None: calls.update(
            {"target": target, "credentials": credentials, "options": options}
        )
        or "channel",
    )

    channel = grpc_connection.create_channel(
        "drawthings.example.com",
        7859,
        insecure=False,
        force_trust_server_cert=True,
    )

    assert channel == "channel"
    assert calls["root_certificates"] == b"remote-cert"
    assert calls["target"] == "drawthings.example.com:7859"


def test_collect_generated_images_reassembles_chunks():
    """Verify chunked Draw Things image responses are reassembled."""
    from dts_utils.grpc.proto.upstream import imageService_pb2 as up_pb2

    from dts_utils.generation_stream import collect_generated_images

    stub = FakeImageGenerationStub(
        [
            SimpleNamespace(generatedImages=[b"first-"], chunkState=up_pb2.MORE_CHUNKS),
            SimpleNamespace(generatedImages=[b"image"], chunkState=up_pb2.LAST_CHUNK),
        ]
    )

    images = collect_generated_images(stub, object())

    assert images == [b"first-image"]
