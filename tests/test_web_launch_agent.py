"""Tests for ``dts-utils web`` LaunchAgent lifecycle."""

from __future__ import annotations

import os
import plistlib
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from dts_utils.web import cli as web_cli
from dts_utils.web.launch_agent import DTSWebLaunchAgent, _lifecycle_parser, run_web_lifecycle


@pytest.fixture
def mock_home_dir():
    temp_dir = tempfile.mkdtemp()
    original_home = os.environ.get("HOME")
    os.environ["HOME"] = temp_dir
    yield Path(temp_dir)
    os.environ["HOME"] = original_home
    shutil.rmtree(temp_dir)


@pytest.fixture
def agent(mock_home_dir: Path) -> DTSWebLaunchAgent:
    return DTSWebLaunchAgent(agents_dir=mock_home_dir / "Library/LaunchAgents")


def test_build_program_arguments_defaults(tmp_path: Path) -> None:
    exe = tmp_path / "dts-utils"
    exe.write_text("", encoding="utf-8")
    args = web_cli._serve_parser("dts-utils").parse_args([])
    assert DTSWebLaunchAgent.build_program_arguments(executable=exe, args=args) == [
        str(exe),
        "web",
        "--bind",
        "127.0.0.1",
        "--port",
        "8765",
        "--log-level",
        "info",
    ]


def test_web_help_documents_foreground_tail_and_launch_agent(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setattr("sys.argv", ["dts-utils", "web", "--help"])
    assert web_cli.main(["--help"]) == 0
    out = capsys.readouterr().out
    assert "dts-utils web [serve options]" in out
    assert "dts-utils web tail" in out
    assert "dts-utils web install --yes" in out
    assert "dts-utils web start" in out
    assert "dts-utils web uninstall" in out
    assert "http://127.0.0.1:8765/" in out


def test_web_install_help_explains_service_options() -> None:
    help_text = _lifecycle_parser("dts-utils", "install").format_help()
    assert "Bind address for the web UI" in help_text
    assert "HTTP port for the web UI" in help_text
    assert "Uvicorn log level for the LaunchAgent process" in help_text
    assert "Disable HTTP access logs" in help_text
    assert "Do not append LaunchAgent logs to a file" in help_text


def test_install_writes_plist_and_bootstraps(agent: DTSWebLaunchAgent, mock_subprocess, tmp_path: Path) -> None:
    exe = tmp_path / "dts-utils"
    exe.write_text("", encoding="utf-8")
    args = _lifecycle_parser("dts-utils", "install").parse_args(["--port", "9999", "--yes", "--executable", str(exe)])

    with patch.object(DTSWebLaunchAgent, "_require_darwin", return_value=None):
        code = agent.install(args)

    assert code == 0
    service_path = agent.service_path
    assert service_path.is_file()
    with service_path.open("rb") as handle:
        payload = plistlib.load(handle)
    assert payload["Label"] == agent.SERVICE_NAME
    assert payload["ProgramArguments"] == [
        str(exe),
        "web",
        "--bind",
        "127.0.0.1",
        "--port",
        "9999",
        "--log-level",
        "info",
    ]
    uid = os.getuid()
    mock_subprocess.assert_called_once()
    cmd = list(mock_subprocess.call_args.args[0])
    assert cmd == ["launchctl", "bootstrap", f"gui/{uid}", str(service_path)]


def test_start_and_stop_use_launchctl(agent: DTSWebLaunchAgent, mock_subprocess) -> None:
    service_path = agent.service_path
    service_path.parent.mkdir(parents=True, exist_ok=True)
    service_path.write_text("plist", encoding="utf-8")
    uid = os.getuid()
    domain = f"gui/{uid}"

    with patch.object(DTSWebLaunchAgent, "_require_darwin", return_value=None):
        assert agent.start() == 0
        assert agent.stop() == 0
    assert mock_subprocess.call_count == 2
    assert list(mock_subprocess.call_args_list[0].args[0]) == [
        "launchctl",
        "bootstrap",
        domain,
        str(service_path),
    ]
    assert list(mock_subprocess.call_args_list[1].args[0]) == [
        "launchctl",
        "bootout",
        domain,
        str(service_path),
    ]


def test_status_reports_not_installed(agent: DTSWebLaunchAgent) -> None:
    assert agent.status() == 1


def test_web_main_dispatches_install(monkeypatch: pytest.MonkeyPatch) -> None:
    called: dict[str, object] = {}

    def fake_lifecycle(action: str, argv: list[str] | None) -> int:
        called["action"] = action
        called["argv"] = list(argv or [])
        return 0

    monkeypatch.setattr("dts_utils.web.launch_agent.run_web_lifecycle", fake_lifecycle)
    assert web_cli.main(["install", "--yes"]) == 0
    assert called == {"action": "install", "argv": ["--yes"]}


def test_run_web_lifecycle_unknown_action() -> None:
    assert run_web_lifecycle("nope", []) == 2
