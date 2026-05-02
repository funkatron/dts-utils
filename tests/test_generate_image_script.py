"""Functional tests for the prompt-to-image helper script."""

from __future__ import annotations

from importlib import util
from pathlib import Path
import struct
from types import SimpleNamespace

import numpy as np


def load_generate_image_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "generate_image.py"
    spec = util.spec_from_file_location("generate_image_script", script_path)
    module = util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


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


def test_generate_image_script_writes_generated_images(monkeypatch, tmp_path):
    """Exercise the script from CLI args through streamed response image writes."""
    module = load_generate_image_module()
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

    monkeypatch.setattr(module, "create_channel", lambda *args, **kwargs: channel)
    monkeypatch.setattr(module.up_grpc, "ImageGenerationServiceStub", lambda created_channel: stub)

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
    assert output_path.read_bytes().startswith(b"\x89PNG")
    assert (tmp_path / "result-2.png").read_bytes().startswith(b"\x89PNG")
    assert stub.request.prompt == "a small robot painting clouds"
    assert stub.request.negativePrompt == "blurry"
    assert stub.request.sharedSecret == "secret"
    assert stub.request.chunked is True


def test_generate_image_script_can_open_generated_images(monkeypatch, tmp_path):
    """Verify --open launches the default viewer after successful writes."""
    module = load_generate_image_module()
    stub = FakeImageGenerationStub([SimpleNamespace(generatedImages=[make_uncompressed_dt_tensor()])])
    opened_paths = []
    output_path = tmp_path / "result.png"
    config_path = tmp_path / "configuration.fb"
    config_path.write_bytes(b"flatbuffer-config")

    monkeypatch.setattr(module, "create_channel", lambda *args, **kwargs: FakeChannel())
    monkeypatch.setattr(module.up_grpc, "ImageGenerationServiceStub", lambda created_channel: stub)
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
    assert opened_paths == [output_path]
    assert output_path.read_bytes().startswith(b"\x89PNG")


def test_generate_image_script_sends_configuration_bytes(monkeypatch, tmp_path):
    """Verify a Draw Things FlatBuffer configuration file is sent as raw bytes."""
    module = load_generate_image_module()
    config_path = tmp_path / "configuration.fb"
    config_path.write_bytes(b"flatbuffer-config")
    stub = FakeImageGenerationStub([SimpleNamespace(generatedImages=[make_uncompressed_dt_tensor()])])

    monkeypatch.setattr(module, "create_channel", lambda *args, **kwargs: FakeChannel())
    monkeypatch.setattr(module.up_grpc, "ImageGenerationServiceStub", lambda created_channel: stub)

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

    monkeypatch.setattr(module, "create_channel", lambda *args, **kwargs: FakeChannel())
    monkeypatch.setattr(module.up_grpc, "ImageGenerationServiceStub", lambda created_channel: stub)
    def fake_json_configuration_to_flatbuffer(config):
        captured_config["config"] = config
        return b"flatbuffer-json"

    monkeypatch.setattr(module, "json_configuration_to_flatbuffer", fake_json_configuration_to_flatbuffer)

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

    monkeypatch.setattr(module, "create_channel", lambda *args, **kwargs: FakeChannel())
    monkeypatch.setattr(module.up_grpc, "ImageGenerationServiceStub", lambda created_channel: stub)
    monkeypatch.setattr(module, "json_configuration_to_flatbuffer", lambda config: b"named-config")
    monkeypatch.setattr(module, "resolve_configuration_value", lambda value: saved_dir / f"{value}.json")

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

    monkeypatch.setattr(module, "create_channel", lambda *args, **kwargs: FakeChannel())
    monkeypatch.setattr(module.up_grpc, "ImageGenerationServiceStub", lambda created_channel: stub)
    def fake_json_configuration_to_flatbuffer(config):
        captured_config["config"] = config
        return b"flatbuffer-json"

    monkeypatch.setattr(
        module,
        "json_configuration_to_flatbuffer",
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

    monkeypatch.setattr(module, "create_channel", lambda *args, **kwargs: FakeChannel())
    monkeypatch.setattr(module.up_grpc, "ImageGenerationServiceStub", lambda created_channel: stub)

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
    assert not (tmp_path / "result.png").exists()


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
    assert "dts-util configs path" in captured.err


def test_create_channel_can_trust_presented_server_certificate(monkeypatch):
    """Verify TLS credentials can be built from the server's presented certificate."""
    from dts_util.grpc import connection as grpc_connection

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
    from dts_util.grpc import connection as grpc_connection

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
    from dts_util.grpc import connection as grpc_connection

    try:
        grpc_connection.create_channel("drawthings.example.com", 7859, insecure=False, trust_server_cert=True)
    except ValueError as exc:
        assert "only allowed for localhost or loopback" in str(exc)
        assert "--force-trust-server-cert" in str(exc)
    else:
        raise AssertionError("Expected remote trust-on-first-use to fail")


def test_create_channel_can_force_trust_remote_presented_certificate(monkeypatch):
    """Verify the explicit unsafe escape hatch trusts remote presented certificates."""
    from dts_util.grpc import connection as grpc_connection

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
        ) or "channel",
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
    module = load_generate_image_module()
    stub = FakeImageGenerationStub(
        [
            SimpleNamespace(generatedImages=[b"first-"], chunkState=module.up_pb2.MORE_CHUNKS),
            SimpleNamespace(generatedImages=[b"image"], chunkState=module.up_pb2.LAST_CHUNK),
        ]
    )

    images = module.collect_generated_images(stub, object())

    assert images == [b"first-image"]
