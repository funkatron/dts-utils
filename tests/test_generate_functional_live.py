"""Full-stack functional tests against ephemeral ``gRPCServerCLI`` (no mocks).

Uses the same ``spawned_live_cli`` / ``live_upstream_stub`` fixtures as ``tests/test_grpc_server.py``; enable with
``DTS_GRPC_TEST_SPAWN_SERVER=1``. Cold model load can take tens of seconds on first run.

Generation uses the saved profile **`default`** (same resolution as ``--configuration default`` /
shorthand), via :func:`dts_utils.configs.ensure_default_generation_json_config`.
"""

from __future__ import annotations

import shutil
from importlib import import_module, reload
from pathlib import Path

import pytest
from PIL import Image

from dts_utils.configs import DEFAULT_PROFILE_NAME, ensure_default_generation_json_config


def load_generate_module():
    return reload(import_module("dts_utils.generate"))


@pytest.mark.integration
@pytest.mark.live_grpc_cli
def test_generate_cli_writes_png(spawned_live_cli, tmp_path: Path) -> None:
    """``dts_utils.generate.main`` reaches the server and writes a PNG (real RPC + decode)."""
    host, port = spawned_live_cli
    if not shutil.which("flatc"):
        pytest.skip("flatc not on PATH (JSON configuration conversion)")

    ensure_default_generation_json_config()
    out = tmp_path / "live-out.png"

    mod = load_generate_module()
    rc = mod.main(
        [
            "--prompt",
            "functional live test gray square",
            "--configuration",
            DEFAULT_PROFILE_NAME,
            "--output",
            str(out),
            "--host",
            host,
            "--port",
            str(port),
            "--no-tls",
            "--generations",
            "1",
        ]
    )
    assert rc == 0
    written = sorted(tmp_path.glob("live-out*.png"))
    assert len(written) >= 1
    assert written[0].stat().st_size > 500


@pytest.mark.integration
@pytest.mark.live_grpc_cli
def test_generate_img2img_at_seventy_percent_strength(spawned_live_cli, tmp_path: Path) -> None:
    """Img2img: existing PNG + new prompt with ``strength`` 0.7 in the JSON profile."""
    import json

    host, port = spawned_live_cli
    if not shutil.which("flatc"):
        pytest.skip("flatc not on PATH (JSON configuration conversion)")

    default_path = ensure_default_generation_json_config()
    cfg = json.loads(default_path.read_text(encoding="utf-8"))
    cfg["strength"] = 0.7
    cfg_path = tmp_path / "img2img-70.json"
    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")

    ref = Image.new("RGB", (512, 512), (30, 60, 120))
    ref_path = tmp_path / "ref.png"
    ref.save(ref_path)

    out = tmp_path / "img2img-out.png"
    mod = load_generate_module()
    rc = mod.main(
        [
            "--prompt",
            "functional img2img live test warm sunset painting",
            "--configuration-json",
            str(cfg_path),
            "--image",
            str(ref_path),
            "--output",
            str(out),
            "--host",
            host,
            "--port",
            str(port),
            "--no-tls",
            "--generations",
            "1",
        ]
    )
    assert rc == 0
    written = sorted(tmp_path.glob("img2img-out*.png"))
    assert len(written) >= 1
    assert written[0].stat().st_size > 500
