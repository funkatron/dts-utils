"""Full-stack functional tests against ephemeral ``gRPCServerCLI`` (no mocks).

Uses the same ``spawned_live_cli`` fixture as ``test_grpc_live_cli.py``; enable with
``DTS_GRPC_TEST_SPAWN_SERVER=1``. Cold model load can take tens of seconds on first run.
"""

from __future__ import annotations

import json
import shutil
from importlib import import_module, reload
from pathlib import Path

import pytest

from ephemeral_grpc_server import (
    first_model_checkpoint_basename,
    resolve_models_directory,
)


def load_generate_module():
    return reload(import_module("dts_utils.generate"))


@pytest.mark.integration
@pytest.mark.live_grpc_cli
def test_generate_cli_writes_png(spawned_live_cli, tmp_path: Path) -> None:
    """``dts_utils.generate.main`` reaches the server and writes a PNG (real RPC + decode)."""
    host, port = spawned_live_cli
    if not shutil.which("flatc"):
        pytest.skip("flatc not on PATH (JSON configuration conversion)")

    models = resolve_models_directory()
    assert models is not None  # prerequisite enforced by fixture
    model_name = first_model_checkpoint_basename(models)
    if not model_name:
        pytest.skip("No .safetensors / .ckpt under models directory")

    cfg = {
        "width": 512,
        "height": 512,
        "batchCount": 1,
        "steps": 4,
        "guidanceScale": 7.5,
        "strength": 1.0,
        "model": model_name,
        "controls": [],
        "hiresFix": False,
        "seed": 42,
    }
    config_path = tmp_path / "live-gen.json"
    config_path.write_text(json.dumps(cfg), encoding="utf-8")
    out = tmp_path / "live-out.png"

    mod = load_generate_module()
    rc = mod.main(
        [
            "--prompt",
            "functional live test gray square",
            "--configuration-json",
            str(config_path),
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
