"""Tests for ``dts-utils server status`` and plist flag parsing."""

from __future__ import annotations

import plistlib
from pathlib import Path
from unittest.mock import patch

import pytest

from dts_utils.installer.server_installer import DTSServerInstaller


def test_parse_program_argument_flags_reads_model_browser_and_port() -> None:
    args = [
        "/usr/local/bin/gRPCServerCLI",
        "/tmp/Models",
        "--port",
        "9999",
        "--model-browser",
        "--no-tls",
    ]
    flags = DTSServerInstaller.parse_program_argument_flags(args)
    assert flags["model_browser"] is True
    assert flags["no_tls"] is True
    assert flags["port"] == 9999


def test_show_service_status_reports_model_browser_disabled(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    agents = tmp_path / "LaunchAgents"
    agents.mkdir(parents=True)
    service_path = agents / "com.drawthings.grpcserver.plist"
    with service_path.open("wb") as handle:
        plistlib.dump(
            {
                "Label": "com.drawthings.grpcserver",
                "ProgramArguments": ["/bin/gRPCServerCLI", "/tmp/Models"],
                "RunAtLoad": True,
                "KeepAlive": True,
            },
            handle,
        )
    installer = DTSServerInstaller()
    installer.AGENTS_DIR = agents
    with patch("dts_utils.installer.server_installer.is_server_running", return_value=True):
        code = installer.show_service_status()
    assert code == 0


def test_install_yes_skips_update_prompt(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    installer = DTSServerInstaller()
    agents = tmp_path / "LaunchAgents"
    agents.mkdir(parents=True)
    installer.AGENTS_DIR = agents
    service_path = agents / f"{installer.SERVICE_NAME}.plist"
    service_path.write_text("old", encoding="utf-8")
    installer.model_path = tmp_path / "Models"
    installer.model_path.mkdir()
    installer.server_args = {
        "name": installer.DEFAULT_NAME,
        "port": installer.DEFAULT_PORT,
        "address": installer.DEFAULT_HOST,
        "gpu": installer.DEFAULT_GPU,
        "datadog_api_key": None,
        "shared_secret": None,
        "no_tls": False,
        "no_response_compression": False,
        "model_browser": True,
        "no_flash_attention": False,
        "debug": False,
        "join": None,
    }
    installer.install_yes = True
    prompts: list[str] = []

    def fake_input(message: str = "") -> str:
        prompts.append(message)
        return "n"

    monkeypatch.setattr("builtins.input", fake_input)
    monkeypatch.setattr(installer, "_launchctl_start_job", lambda _p: None)
    installer.create_launchd_service(tmp_path / "gRPCServerCLI")
    assert prompts == []
    with service_path.open("rb") as handle:
        payload = plistlib.load(handle)
    assert "--model-browser" in payload["ProgramArguments"]
