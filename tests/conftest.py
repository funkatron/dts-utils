"""Common test fixtures for dts-utils tests."""
import os
import sys

import pytest
from unittest.mock import patch, MagicMock

from ephemeral_grpc_server import (
    ephemeral_grpc_server_cli,
    env_truthy,
    resolve_grpc_server_cli_binary,
    resolve_models_directory,
)

# Add the project root directory to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)


@pytest.fixture(scope="session")
def spawned_live_cli():
    """Ephemeral ``gRPCServerCLI`` on loopback (opt-in via ``DTS_GRPC_TEST_SPAWN_SERVER``).

    Shared across modules so functional + RPC smoke tests reuse one subprocess per pytest run.
    """
    if not env_truthy("DTS_GRPC_TEST_SPAWN_SERVER"):
        pytest.skip(
            "Set DTS_GRPC_TEST_SPAWN_SERVER=1 to spawn gRPCServerCLI (see tests/README.md)."
        )
    binary = resolve_grpc_server_cli_binary()
    if binary is None:
        pytest.skip(
            "gRPCServerCLI not found; install via `dts-utils server install` or set "
            "DTS_GRPC_TEST_SERVER_BINARY to the binary path."
        )
    models = resolve_models_directory()
    if models is None:
        pytest.skip(
            "No Draw Things Models directory found; set DTS_GRPC_TEST_MODEL_PATH to "
            "an existing directory (server requires a model root argument)."
        )
    with ephemeral_grpc_server_cli(models_dir=models, binary=binary) as hp:
        yield hp


@pytest.fixture
def mock_subprocess():
    """Mock subprocess.run for testing."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        yield mock_run


@pytest.fixture
def mock_socket():
    """Mock socket for testing port availability."""
    with patch("socket.socket") as mock_socket:
        mock_sock = MagicMock()
        mock_sock.connect_ex.return_value = 1  # Port is available by default
        mock_socket.return_value = mock_sock
        yield mock_sock


@pytest.fixture
def temp_model_path(tmp_path):
    """Create a temporary model path for testing."""
    model_path = tmp_path / "Models"
    model_path.mkdir()
    return model_path


@pytest.fixture
def mock_home_dir(tmp_path, monkeypatch):
    """Mock home directory for testing."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    return home
