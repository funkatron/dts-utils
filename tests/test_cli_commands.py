#!/usr/bin/env python3
"""Functional tests for the dts-utils CLI commands."""
import os
import sys
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

# Add the src directory to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(project_root, "src"))

from dts_utils.cli_router import prepare_argv_for_installer_dispatch
from dts_utils.installer.server_installer import DTSServerInstaller


def _setup_server_argv(monkeypatch: pytest.MonkeyPatch, *tokens: str) -> None:
    monkeypatch.setattr("sys.argv", ["dts-utils", "server", *tokens])
    assert prepare_argv_for_installer_dispatch(sys.argv) is None


@pytest.fixture
def mock_subprocess():
    """Mock subprocess.run to test CLI command execution."""
    with patch('subprocess.run') as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout='', stderr='')
        yield mock_run


@pytest.fixture
def mock_exit():
    """Make ``sys.exit`` propagate :class:`SystemExit` so ``parse_args`` does not fall through after early exits."""

    def _exit(code: int | None = None) -> None:
        raise SystemExit(code)

    with patch("sys.exit", side_effect=_exit) as mock_exit:
        yield mock_exit


@pytest.fixture
def mock_installer_methods():
    """Mock installer methods to prevent real execution."""
    with patch.object(DTSServerInstaller, 'restart_service') as mock_restart, \
         patch.object(DTSServerInstaller, 'start_service') as mock_start, \
         patch.object(DTSServerInstaller, 'stop_service') as mock_stop, \
         patch.object(DTSServerInstaller, 'uninstall') as mock_uninstall, \
         patch('dts_utils.installer.server_installer.is_server_running') as mock_is_running:

        mock_is_running.return_value = True  # Default to server running
        yield {
            'restart': mock_restart,
            'start': mock_start,
            'stop': mock_stop,
            'uninstall': mock_uninstall,
            'is_running': mock_is_running
        }


class TestCLICommands:
    """Test the CLI commands."""

    @pytest.fixture(autouse=True)
    def _draw_things_default_models_dir(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """CI/Linux has no Draw Things container path; mirror macOS layout under a fake HOME."""
        monkeypatch.setenv("HOME", str(tmp_path))
        models = tmp_path / "Library/Containers/com.liuliu.draw-things/Data/Documents/Models"
        models.mkdir(parents=True, exist_ok=True)

    def test_install_command(self, mock_installer_methods, monkeypatch, mock_exit):
        """Test the install command."""
        # Set up command line arguments
        _setup_server_argv(monkeypatch, 'install')

        # Create instance but patch run to prevent installation
        with patch.object(DTSServerInstaller, "run") as mock_run:
            installer = DTSServerInstaller()
            args = installer.parse_args()

            assert args.action == "install"
            mock_run.assert_not_called()

        mock_exit.assert_not_called()

    def test_uninstall_command(self, mock_installer_methods, monkeypatch, mock_exit):
        """Test the uninstall command."""
        _setup_server_argv(monkeypatch, "uninstall")

        installer = DTSServerInstaller()
        with pytest.raises(SystemExit) as exc_info:
            installer.parse_args()

        assert exc_info.value.code == 0
        mock_installer_methods["uninstall"].assert_called_once()

    def test_start_command(self, mock_installer_methods, monkeypatch, mock_exit):
        """``server start`` loads the LaunchAgent job."""
        _setup_server_argv(monkeypatch, "start")

        installer = DTSServerInstaller()
        with pytest.raises(SystemExit) as exc_info:
            installer.parse_args()

        assert exc_info.value.code == 0
        mock_installer_methods["start"].assert_called_once_with()

    def test_stop_command(self, mock_installer_methods, monkeypatch, mock_exit):
        """``server stop`` boots the job out of launchd."""
        _setup_server_argv(monkeypatch, "stop")

        installer = DTSServerInstaller()
        with pytest.raises(SystemExit) as exc_info:
            installer.parse_args()

        assert exc_info.value.code == 0
        mock_installer_methods["stop"].assert_called_once_with()

    def test_restart_command(self, mock_installer_methods, monkeypatch, mock_exit):
        """Test the restart command."""
        _setup_server_argv(monkeypatch, "restart")

        installer = DTSServerInstaller()
        with pytest.raises(SystemExit) as exc_info:
            installer.parse_args()

        assert exc_info.value.code == 0
        mock_installer_methods["restart"].assert_called_once_with(ensure_model_browser=True)

    def test_restart_command_can_disable_model_browser(self, mock_installer_methods, monkeypatch, mock_exit):
        """Test restarting while disabling model browser."""
        _setup_server_argv(monkeypatch, "restart", "--no-model-browser")

        installer = DTSServerInstaller()
        with pytest.raises(SystemExit) as exc_info:
            installer.parse_args()

        assert exc_info.value.code == 0
        mock_installer_methods["restart"].assert_called_once_with(ensure_model_browser=False)

    def test_test_command_server_running(self, mock_installer_methods, monkeypatch, mock_exit):
        """Test the test command when server is running."""
        _setup_server_argv(monkeypatch, "test")

        mock_installer_methods["is_running"].return_value = True

        installer = DTSServerInstaller()
        with pytest.raises(SystemExit) as exc_info:
            installer.parse_args()

        assert exc_info.value.code == 0
        mock_installer_methods["is_running"].assert_called_once_with(port=7859, prefer_plaintext=False)

    def test_test_command_server_not_running(self, mock_installer_methods, monkeypatch, mock_exit):
        """Test the test command when server is not running."""
        _setup_server_argv(monkeypatch, "test")

        mock_installer_methods["is_running"].return_value = False

        installer = DTSServerInstaller()
        with pytest.raises(SystemExit) as exc_info:
            installer.parse_args()

        assert exc_info.value.code == 1
        mock_installer_methods["is_running"].assert_called_once_with(port=7859, prefer_plaintext=False)

    def test_check_alias_invokes_listener_probe(self, mock_installer_methods, monkeypatch, mock_exit):
        """``check`` is synonymous with ``test`` (listener probe, not pytest)."""
        _setup_server_argv(monkeypatch, "check")

        mock_installer_methods["is_running"].return_value = True

        installer = DTSServerInstaller()
        with pytest.raises(SystemExit) as exc_info:
            installer.parse_args()

        assert exc_info.value.code == 0
        mock_installer_methods["is_running"].assert_called_once_with(port=7859, prefer_plaintext=False)

    def test_no_arguments_shows_usage(self, monkeypatch, mock_exit):
        """Test that running with no arguments shows usage."""
        monkeypatch.setattr("sys.argv", ["dts-utils"])

        with patch("builtins.print") as mock_print:
            installer = DTSServerInstaller()
            with pytest.raises(SystemExit) as exc_info:
                installer.run()

        assert exc_info.value.code == 0
        mock_print.assert_called()

    def test_command_with_custom_port(self, mock_installer_methods, monkeypatch, mock_exit):
        """Test using a command with a custom port."""
        _setup_server_argv(monkeypatch, "test", "--port", "7860")

        mock_installer_methods["is_running"].return_value = True

        installer = DTSServerInstaller()
        with pytest.raises(SystemExit) as exc_info:
            installer.parse_args()

        assert exc_info.value.code == 0
        mock_installer_methods["is_running"].assert_called_once_with(port=7860, prefer_plaintext=False)

    def test_test_command_no_tls_uses_plaintext_probe(self, mock_installer_methods, monkeypatch, mock_exit):
        """``server test --no-tls`` probes plaintext gRPC (matches no-TLS installs)."""
        _setup_server_argv(monkeypatch, "test", "--no-tls")

        mock_installer_methods["is_running"].return_value = True

        installer = DTSServerInstaller()
        with pytest.raises(SystemExit) as exc_info:
            installer.parse_args()

        assert exc_info.value.code == 0
        mock_installer_methods["is_running"].assert_called_once_with(port=7859, prefer_plaintext=True)

    def test_tail_command_invokes_log_tools(self, monkeypatch, mock_exit):
        """``server tail`` runs log show (history) then log stream on macOS."""
        _setup_server_argv(monkeypatch, "tail", "--last", "10m")

        calls: list[list[str]] = []

        def fake_run(cmd, check=False):
            calls.append(list(cmd))
            return MagicMock(returncode=0)

        monkeypatch.setattr(sys, "platform", "darwin")
        with patch("subprocess.run", side_effect=fake_run):
            installer = DTSServerInstaller()
            with pytest.raises(SystemExit) as exc_info:
                installer.parse_args()

        assert exc_info.value.code == 0
        assert len(calls) == 2
        assert calls[0][:3] == ["log", "show", "--predicate"]
        assert calls[0][3] == 'process == "gRPCServerCLI"'
        assert calls[0][4:6] == ["--last", "10m"]
        assert calls[1][:3] == ["log", "stream", "--predicate"]

    def test_tail_command_skips_history_when_last_zero(self, monkeypatch, mock_exit):
        """``server tail --last 0`` streams only (no log show)."""
        _setup_server_argv(monkeypatch, "tail", "--last", "0")

        calls: list[list[str]] = []

        def fake_run(cmd, check=False):
            calls.append(list(cmd))
            return MagicMock(returncode=0)

        monkeypatch.setattr(sys, "platform", "darwin")
        with patch("subprocess.run", side_effect=fake_run):
            installer = DTSServerInstaller()
            with pytest.raises(SystemExit) as exc_info:
                installer.parse_args()

        assert exc_info.value.code == 0
        assert len(calls) == 1
        assert calls[0][0:2] == ["log", "stream"]

    def test_tail_command_non_macos_exits_one(self, monkeypatch, mock_exit):
        """``server tail`` refuses to run off macOS."""
        _setup_server_argv(monkeypatch, "tail")

        monkeypatch.setattr(sys, "platform", "linux")
        installer = DTSServerInstaller()
        with pytest.raises(SystemExit) as exc_info:
            installer.parse_args()

        assert exc_info.value.code == 1


if __name__ == "__main__":
    pytest.main(["-v", __file__])