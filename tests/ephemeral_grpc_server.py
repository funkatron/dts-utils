"""Spawn Draw Things ``gRPCServerCLI`` for opt-in live tests (no LaunchAgent).

See ``tests/README.md`` § Ephemeral server and ``PROTOBUF.md`` § gRPC integration tests.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Tuple

from dts_utils.grpc.utils import is_server_running

_BINARY_NAME = "gRPCServerCLI"


def env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def resolve_grpc_server_cli_binary() -> Path | None:
    """Locate ``gRPCServerCLI``: ``DTS_GRPC_TEST_SERVER_BINARY``, ``PATH``, then usual install dirs."""
    raw = os.environ.get("DTS_GRPC_TEST_SERVER_BINARY", "").strip()
    if raw:
        p = Path(raw).expanduser()
        return p if p.is_file() else None
    found = shutil.which(_BINARY_NAME)
    if found:
        return Path(found)
    for candidate in (
        Path("/usr/local/bin") / _BINARY_NAME,
        Path.home() / ".local/bin" / _BINARY_NAME,
    ):
        if candidate.is_file():
            return candidate
    return None


def resolve_models_directory() -> Path | None:
    """Directory passed as the server's model root (first positional argument)."""
    raw = os.environ.get("DTS_GRPC_TEST_MODEL_PATH", "").strip()
    if raw:
        p = Path(raw).expanduser()
        return p if p.is_dir() else None
    default = (
        Path.home()
        / "Library/Containers/com.liuliu.draw-things/Data/Documents/Models"
    )
    return default if default.is_dir() else None


def pick_free_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@contextmanager
def ephemeral_grpc_server_cli(
    *,
    models_dir: Path,
    binary: Path,
    startup_timeout: float = 120.0,
) -> Iterator[Tuple[str, int]]:
    """Run ``gRPCServerCLI MODEL_DIR ...`` on an ephemeral loopback port with ``--no-tls``.

    Yields ``("127.0.0.1", port)``. Terminates the process on exit.
    """
    port = pick_free_loopback_port()
    cmd = [
        str(binary),
        str(models_dir),
        "--port",
        str(port),
        "--address",
        "127.0.0.1",
        "--no-tls",
    ]
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    deadline = time.monotonic() + startup_timeout
    try:
        while time.monotonic() < deadline:
            code = proc.poll()
            if code is not None:
                err = proc.stderr.read() if proc.stderr else ""
                raise RuntimeError(
                    f"gRPCServerCLI exited with code {code} before listening.\n"
                    f"cmd: {' '.join(cmd)}\nstderr:\n{err}"
                )
            if is_server_running(
                "127.0.0.1",
                port,
                timeout=1.5,
                prefer_plaintext=True,
            ):
                yield "127.0.0.1", port
                return
            time.sleep(0.35)
        err = ""
        if proc.stderr:
            proc.stderr.flush()
            err = proc.stderr.read()
        proc.terminate()
        raise TimeoutError(
            f"gRPCServerCLI did not accept connections on 127.0.0.1:{port} within "
            f"{startup_timeout}s.\nstderr:\n{err}"
        )
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
