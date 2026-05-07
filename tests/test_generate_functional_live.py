"""Full-stack functional tests against ephemeral ``gRPCServerCLI`` (no mocks).

Uses the same ``spawned_live_cli`` fixture as ``test_grpc_live_cli.py``; enable with
``DTS_GRPC_TEST_SPAWN_SERVER=1``. Cold model load can take tens of seconds on first run.

Generation uses the saved profile **`default`** (same resolution as ``--configuration default`` /
shorthand), via :func:`dts_utils.configs.ensure_default_generation_json_config`.
"""

from __future__ import annotations

import shutil
from importlib import import_module, reload
from pathlib import Path

import pytest

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
