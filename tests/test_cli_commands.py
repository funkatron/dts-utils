#!/usr/bin/env python3
"""Functional tests for the dts-util CLI commands."""
import os
import sys
import pytest
import subprocess
from unittest.mock import patch, MagicMock
from pathlib import Path

# Add the src directory to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(project_root, "src"))

from dts_util.installer.server_installer import DTSServerInstaller, prepare_argv_for_installer_dispatch


def _setup_server_argv(monkeypatch: pytest.MonkeyPatch, *tokens: str) -> None:
    monkeypatch.setattr("sys.argv", ["dts-util", "server", *tokens])
    assert prepare_argv_for_installer_dispatch(sys.argv) is None


@pytest.fixture
def mock_subprocess():
    """Mock subprocess.run to test CLI command execution."""
    with patch('subprocess.run') as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout='', stderr='')
        yield mock_run


@pytest.fixture
def mock_exit():
    """Mock sys.exit to prevent test termination."""
    with patch('sys.exit') as mock_exit:
        yield mock_exit


@pytest.fixture
def mock_installer_methods():
    """Mock installer methods to prevent real execution."""
    with patch.object(DTSServerInstaller, 'restart_service') as mock_restart, \
         patch.object(DTSServerInstaller, 'uninstall') as mock_uninstall, \
         patch('dts_util.installer.server_installer.is_server_running') as mock_is_running:

        mock_is_running.return_value = True  # Default to server running
        yield {
            'restart': mock_restart,
            'uninstall': mock_uninstall,
            'is_running': mock_is_running
        }


class TestCLICommands:
    """Test the CLI commands."""

    def test_install_command(self, mock_installer_methods, monkeypatch, mock_exit):
        """Test the install command."""
        # Set up command line arguments
        _setup_server_argv(monkeypatch, 'install')

        # Create instance but patch run to prevent installation
        with patch.object(DTSServerInstaller, 'run') as mock_run:
            installer = DTSServerInstaller()
            args = installer.parse_args()

            # Verify args are correct
            assert args.action == 'install'

            # Run should not have been called yet
            mock_run.assert_not_called()

            # sys.exit should not have been called
            mock_exit.assert_not_called()

    def test_uninstall_command(self, mock_installer_methods, monkeypatch, mock_exit):
        """Test the uninstall command."""
        # Set up command line arguments
        _setup_server_argv(monkeypatch, 'uninstall')

        # Create instance and parse args
        installer = DTSServerInstaller()
        installer.parse_args()

        # Verify uninstall was called
        mock_installer_methods['uninstall'].assert_called_once()

        # Verify sys.exit was called with 0
        mock_exit.assert_called_once_with(0)

    def test_restart_command(self, mock_installer_methods, monkeypatch, mock_exit):
        """Test the restart command."""
        # Set up command line arguments
        _setup_server_argv(monkeypatch, 'restart')

        # Create instance and parse args
        installer = DTSServerInstaller()
        installer.parse_args()

        # Verify restart_service was called
        mock_installer_methods['restart'].assert_called_once_with(enable_model_browser=False)

        # Verify sys.exit was called with 0
        mock_exit.assert_called_once_with(0)

    def test_restart_command_can_enable_model_browser(self, mock_installer_methods, monkeypatch, mock_exit):
        """Test restarting while enabling model browser."""
        _setup_server_argv(monkeypatch, 'restart', '--model-browser')

        installer = DTSServerInstaller()
        installer.parse_args()

        mock_installer_methods['restart'].assert_called_once_with(enable_model_browser=True)
        mock_exit.assert_called_once_with(0)

    def test_test_command_server_running(self, mock_installer_methods, monkeypatch, mock_exit):
        """Test the test command when server is running."""
        # Set up command line arguments
        _setup_server_argv(monkeypatch, 'test')

        # Mock server as running
        mock_installer_methods['is_running'].return_value = True

        # Create instance and parse args
        installer = DTSServerInstaller()
        installer.parse_args()

        # Verify is_server_running was called with default port
        mock_installer_methods['is_running'].assert_called_once_with(port=7859)

        # Verify sys.exit was called with 0 (success)
        mock_exit.assert_called_once_with(0)

    def test_test_command_server_not_running(self, mock_installer_methods, monkeypatch, mock_exit):
        """Test the test command when server is not running."""
        # Set up command line arguments
        _setup_server_argv(monkeypatch, 'test')

        # Mock server as not running
        mock_installer_methods['is_running'].return_value = False

        # Create instance and parse args
        installer = DTSServerInstaller()
        installer.parse_args()

        # Verify is_server_running was called with default port
        mock_installer_methods['is_running'].assert_called_once_with(port=7859)

        # Verify sys.exit was called with 1 (failure)
        mock_exit.assert_called_once_with(1)

    def test_check_alias_invokes_listener_probe(self, mock_installer_methods, monkeypatch, mock_exit):
        """``check`` is synonymous with ``test`` (listener probe, not pytest)."""
        _setup_server_argv(monkeypatch, 'check')

        mock_installer_methods["is_running"].return_value = True

        installer = DTSServerInstaller()
        installer.parse_args()

        mock_installer_methods["is_running"].assert_called_once_with(port=7859)
        mock_exit.assert_called_once_with(0)

    def test_no_arguments_shows_usage(self, monkeypatch, mock_exit):
        """Test that running with no arguments shows usage."""
        # Set up command line arguments
        monkeypatch.setattr('sys.argv', ['dts-util'])

        # Patch print to capture output
        with patch('builtins.print') as mock_print:
            installer = DTSServerInstaller()
            installer.run()

        # Verify print was called (to show usage)
        mock_print.assert_called()

        # Verify sys.exit was called at least once
        assert mock_exit.call_count >= 1
        # Verify at least one call was with 0 (success)
        mock_exit.assert_any_call(0)

    def test_command_with_custom_port(self, mock_installer_methods, monkeypatch, mock_exit):
        """Test using a command with a custom port."""
        # Set up command line arguments
        _setup_server_argv(monkeypatch, 'test', '--port', '7860')

        # Mock server as running
        mock_installer_methods['is_running'].return_value = True

        # Create instance and parse args
        installer = DTSServerInstaller()
        installer.parse_args()

        # Verify is_server_running was called with the custom port
        mock_installer_methods['is_running'].assert_called_once_with(port=7860)

        # Verify sys.exit was called with 0 (success)
        mock_exit.assert_called_once_with(0)


if __name__ == '__main__':
    pytest.main(['-v', __file__])