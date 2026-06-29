"""Gated macOS LaunchAgent lifecycle tools for MCP."""

from __future__ import annotations

import sys
import time
from typing import Any

from dts_utils.exceptions import ConfigurationError
from dts_utils.grpc.utils import is_server_running
from dts_utils.installer.server_installer import DTSServerInstaller
from dts_utils.mcp.errors import raise_tool_error


def _require_macos() -> None:
    if sys.platform != "darwin":
        raise ConfigurationError("Draw Things server lifecycle MCP tools require macOS.")


def _installer() -> DTSServerInstaller:
    _require_macos()
    return DTSServerInstaller()


def _redact_program_arguments(program_args: list[str]) -> list[str]:
    """Return a copy of LaunchAgent argv with shared-secret values redacted."""
    redacted: list[str] = []
    skip_next = False
    for arg in program_args:
        if skip_next:
            redacted.append("<redacted>")
            skip_next = False
            continue
        redacted.append(arg)
        if arg in ("--shared-secret", "-s"):
            skip_next = True
    return redacted


def _sync_model_browser_plist(
    installer: DTSServerInstaller,
    service_path,
    *,
    enable: bool,
) -> bool:
    """Enable or disable model browser in the plist without terminating the MCP process."""
    try:
        if enable:
            return installer.enable_model_browser_for_service(service_path)
        return installer.disable_model_browser_for_service(service_path)
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
        action = "enable" if enable else "disable"
        raise ConfigurationError(
            f"Failed to {action} model browser in LaunchAgent plist (exit {code})."
        ) from exc


def collect_server_status_dict(installer: DTSServerInstaller) -> dict[str, Any]:
    service_path = installer.AGENTS_DIR / f"{installer.SERVICE_NAME}.plist"
    program_args = installer.read_service_program_arguments(service_path)
    if program_args is None:
        return {
            "installed": False,
            "plist": str(service_path),
            "listener_up": False,
            "platform": sys.platform,
        }

    flags = installer.parse_program_argument_flags(program_args)
    port = int(flags["port"])
    no_tls = bool(flags["no_tls"])
    model_browser = bool(flags["model_browser"])
    shared_secret = flags["shared_secret"]
    listener_up = is_server_running(port=port, prefer_plaintext=no_tls)

    echo_model_files: int | None = None
    if listener_up and model_browser:
        echo_model_files = installer.echo_model_file_count(
            host="localhost",
            port=port,
            no_tls=no_tls,
            shared_secret=str(shared_secret) if shared_secret else None,
        )

    return {
        "installed": True,
        "plist": str(service_path),
        "program_arguments": _redact_program_arguments(program_args),
        "port": port,
        "no_tls": no_tls,
        "model_browser": model_browser,
        "listener_up": listener_up,
        "echo_model_files": echo_model_files,
        "platform": sys.platform,
    }


def tool_server_status() -> dict[str, Any]:
    """Return LaunchAgent install state, listener probe, and model-browser Echo summary."""
    try:
        installer = _installer()
        return collect_server_status_dict(installer)
    except Exception as exc:
        raise_tool_error(exc)
        raise AssertionError("raise_tool_error always raises")


def tool_server_start() -> dict[str, Any]:
    """Load the installed LaunchAgent plist and start gRPCServerCLI."""
    try:
        installer = _installer()
        service_path = installer.AGENTS_DIR / f"{installer.SERVICE_NAME}.plist"
        if not service_path.exists():
            raise ConfigurationError(f"LaunchAgent not installed ({service_path}).")
        installer._launchctl_start_job(service_path)
        status = collect_server_status_dict(installer)
        return {"ok": True, "action": "start", **status}
    except Exception as exc:
        raise_tool_error(exc)
        raise AssertionError("raise_tool_error always raises")


def tool_server_stop() -> dict[str, Any]:
    """Boot out the LaunchAgent job (plist remains on disk)."""
    try:
        installer = _installer()
        service_path = installer.AGENTS_DIR / f"{installer.SERVICE_NAME}.plist"
        if not service_path.exists():
            raise ConfigurationError(f"LaunchAgent not installed ({service_path}).")
        installer._launchctl_stop_job(service_path)
        status = collect_server_status_dict(installer)
        return {"ok": True, "action": "stop", **status}
    except Exception as exc:
        raise_tool_error(exc)
        raise AssertionError("raise_tool_error always raises")


def tool_server_restart(ensure_model_browser: bool = True) -> dict[str, Any]:
    """Restart gRPCServerCLI via launchd (optional model-browser plist sync)."""
    try:
        installer = _installer()
        service_path = installer.AGENTS_DIR / f"{installer.SERVICE_NAME}.plist"
        if not service_path.exists():
            raise ConfigurationError(f"LaunchAgent not installed ({service_path}).")

        plist_changed = _sync_model_browser_plist(
            installer,
            service_path,
            enable=ensure_model_browser,
        )

        if plist_changed:
            installer._launchctl_stop_job(service_path)
            time.sleep(1)
            installer._launchctl_start_job(service_path)
        elif not installer._launchctl_kickstart_job(kill=True):
            installer._launchctl_stop_job(service_path)
            time.sleep(1)
            installer._launchctl_start_job(service_path)

        status = collect_server_status_dict(installer)
        return {
            "ok": True,
            "action": "restart",
            "ensure_model_browser": ensure_model_browser,
            "plist_changed": plist_changed,
            **status,
        }
    except Exception as exc:
        raise_tool_error(exc)
        raise AssertionError("raise_tool_error always raises")
