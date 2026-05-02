"""Common test fixtures for dts-utils tests."""
import os
import sys

import pytest
from unittest.mock import patch, MagicMock

# Add the project root directory to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)


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
