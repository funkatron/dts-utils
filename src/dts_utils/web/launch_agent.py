"""macOS LaunchAgent lifecycle for ``dts-utils web``."""

from __future__ import annotations

import argparse
import os
import plistlib
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from dts_utils.cli_prog import cli_command_name
from dts_utils.web.defaults import DEFAULT_WEB_PORT
from dts_utils.web.log_io import default_web_log_path, resolve_web_log_path

WEB_LIFECYCLE_SUBCOMMANDS = frozenset({"install", "uninstall", "start", "stop", "restart", "status"})


class DTSWebLaunchAgent:
    """Install and manage a user LaunchAgent that runs ``dts-utils web``."""

    SERVICE_NAME = "com.dts-utils.web"
    DEFAULT_PORT = DEFAULT_WEB_PORT
    DEFAULT_BIND = "127.0.0.1"

    def __init__(self, *, agents_dir: Path | None = None) -> None:
        self.agents_dir = agents_dir or (Path.home() / "Library/LaunchAgents")

    @property
    def service_path(self) -> Path:
        return self.agents_dir / f"{self.SERVICE_NAME}.plist"

    def _require_darwin(self) -> None:
        prog = cli_command_name()
        if sys.platform != "darwin":
            print(f"{prog} web install requires macOS (LaunchAgent).", file=sys.stderr)
            sys.exit(1)

    def _launchd_gui_domain(self) -> str:
        return f"gui/{os.getuid()}"

    def _launchctl_stop_job(self, service_path: Path) -> None:
        domain = self._launchd_gui_domain()
        out = subprocess.run(
            ["launchctl", "bootout", domain, str(service_path)],
            capture_output=True,
            text=True,
        )
        if out.returncode == 0:
            return
        subprocess.run(["launchctl", "unload", str(service_path)], check=False)
        subprocess.run(["launchctl", "remove", self.SERVICE_NAME], check=False)

    def _launchctl_start_job(self, service_path: Path) -> None:
        domain = self._launchd_gui_domain()
        boot = subprocess.run(
            ["launchctl", "bootstrap", domain, str(service_path)],
            capture_output=True,
            text=True,
        )
        if boot.returncode == 0:
            return
        kick = subprocess.run(
            ["launchctl", "kickstart", "-p", f"{domain}/{self.SERVICE_NAME}"],
            capture_output=True,
            text=True,
        )
        if kick.returncode == 0:
            return
        subprocess.run(["launchctl", "load", str(service_path)], check=True)

    @staticmethod
    def resolve_web_cli_executable(*, argv0: str | None = None) -> Path:
        name = cli_command_name()
        found = shutil.which(name)
        if found:
            return Path(found).resolve()
        if argv0:
            candidate = Path(argv0).resolve()
            if candidate.is_file():
                return candidate
        raise RuntimeError(
            f"Could not find {name!r} on PATH. Install the package or run from a venv with the console script.",
        )

    @staticmethod
    def build_program_arguments(*, executable: Path, args: argparse.Namespace) -> list[str]:
        cmd = [str(executable), "web", "--bind", args.bind, "--port", str(args.port), "--log-level", args.log_level]
        if args.no_access_log:
            cmd.append("--no-access-log")
        if args.no_log_file:
            cmd.append("--no-log-file")
        elif args.log_file is not None:
            cmd.extend(["--log-file", str(args.log_file.expanduser())])
        return cmd

    def read_installed_web_args(self) -> tuple[str, int] | None:
        """Return ``(bind, port)`` from an installed plist, or ``None`` if missing."""
        path = self.service_path
        if not path.is_file():
            return None
        try:
            with path.open("rb") as handle:
                payload = plistlib.load(handle)
        except (OSError, plistlib.InvalidFileException):
            return None
        program_args = payload.get("ProgramArguments")
        if not isinstance(program_args, list):
            return None
        bind = self.DEFAULT_BIND
        port = self.DEFAULT_PORT
        tokens = [str(x) for x in program_args]
        for index, token in enumerate(tokens):
            if token == "--bind" and index + 1 < len(tokens):
                bind = tokens[index + 1]
            if token == "--port" and index + 1 < len(tokens):
                try:
                    port = int(tokens[index + 1])
                except ValueError:
                    pass
        return bind, port

    def install(self, args: argparse.Namespace) -> int:
        self._require_darwin()
        prog = cli_command_name()
        if args.executable:
            executable = Path(args.executable).expanduser().resolve()
            if not executable.is_file():
                print(f"{prog} web install: executable not found: {executable}", file=sys.stderr)
                return 1
        else:
            try:
                executable = self.resolve_web_cli_executable(argv0=sys.argv[0])
            except RuntimeError as exc:
                print(f"{prog} web install: {exc}", file=sys.stderr)
                return 1

        service_path = self.service_path
        self.agents_dir.mkdir(parents=True, exist_ok=True)
        if service_path.exists() and not args.yes:
            response = input(f"Update existing LaunchAgent at {service_path}? (y/N): ")
            if response.strip().lower() != "y":
                print("LaunchAgent install cancelled.")
                return 0
            self._launchctl_stop_job(service_path)

        program_args = self.build_program_arguments(executable=executable, args=args)
        service_config = {
            "Label": self.SERVICE_NAME,
            "ProgramArguments": program_args,
            "RunAtLoad": True,
            "KeepAlive": True,
        }
        try:
            with service_path.open("wb") as handle:
                plistlib.dump(service_config, handle)
            self._launchctl_start_job(service_path)
        except (OSError, subprocess.CalledProcessError) as exc:
            print(f"{prog} web install: failed to create or load service: {exc}", file=sys.stderr)
            return 1

        log_path = resolve_web_log_path(args.log_file if not args.no_log_file else None)
        open_host = "127.0.0.1" if args.bind in {"0.0.0.0", "::"} else args.bind
        url = f"http://{open_host}:{args.port}/"
        print(f"Web UI LaunchAgent installed at {service_path}")
        print(f"  URL: {url}")
        if log_path is not None:
            print(f"  Log: {log_path.resolve()}")
        print(f"  Follow logs: uv run {prog} web tail")
        return 0

    def uninstall(self) -> int:
        self._require_darwin()
        prog = cli_command_name()
        service_path = self.service_path
        if not service_path.exists():
            print(f"{prog} web uninstall: service not installed", file=sys.stderr)
            return 1
        print("Stopping web UI LaunchAgent...")
        self._launchctl_stop_job(service_path)
        service_path.unlink(missing_ok=True)
        print("Web UI LaunchAgent removed.")
        return 0

    def start(self) -> int:
        self._require_darwin()
        prog = cli_command_name()
        service_path = self.service_path
        if not service_path.exists():
            print(f"{prog} web start: service not installed (run `{prog} web install` first)", file=sys.stderr)
            return 1
        print("Starting web UI LaunchAgent...")
        try:
            self._launchctl_start_job(service_path)
        except subprocess.CalledProcessError as exc:
            print(f"{prog} web start: failed: {exc}", file=sys.stderr)
            return 1
        print("Web UI LaunchAgent started.")
        return 0

    def stop(self) -> int:
        self._require_darwin()
        prog = cli_command_name()
        service_path = self.service_path
        if not service_path.exists():
            print(f"{prog} web stop: service not installed", file=sys.stderr)
            return 1
        print("Stopping web UI LaunchAgent...")
        self._launchctl_stop_job(service_path)
        print("Web UI LaunchAgent stopped.")
        return 0

    def restart(self) -> int:
        self._require_darwin()
        prog = cli_command_name()
        service_path = self.service_path
        if not service_path.exists():
            print(f"{prog} web restart: service not installed", file=sys.stderr)
            return 1
        print("Restarting web UI LaunchAgent...")
        try:
            self._launchctl_stop_job(service_path)
            time.sleep(1)
            self._launchctl_start_job(service_path)
        except subprocess.CalledProcessError as exc:
            print(f"{prog} web restart: failed: {exc}", file=sys.stderr)
            return 1
        print("Web UI LaunchAgent restarted.")
        return 0

    def status(self) -> int:
        prog = cli_command_name()
        service_path = self.service_path
        if not service_path.exists():
            print(f"{prog} web status: LaunchAgent not installed")
            return 1

        installed = self.read_installed_web_args()
        bind = installed[0] if installed else self.DEFAULT_BIND
        port = installed[1] if installed else self.DEFAULT_PORT
        health_host = "127.0.0.1" if bind in {"0.0.0.0", "::"} else bind
        url = f"http://{health_host}:{port}/api/health"

        listener = self._port_is_open(health_host, port)
        health_ok = False
        if listener:
            health_ok = self._health_check(url)

        print(f"Plist: {service_path}")
        print(f"URL: http://{health_host}:{port}/")
        print(f"Listener: {'up' if listener else 'down'}")
        print(f"Health: {'ok' if health_ok else 'not ready' if listener else 'n/a'}")
        return 0 if listener and health_ok else 2

    @staticmethod
    def _port_is_open(host: str, port: int) -> bool:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        try:
            return sock.connect_ex((host, port)) == 0
        finally:
            sock.close()

    @staticmethod
    def _health_check(url: str) -> bool:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                return 200 <= response.status < 300
        except (urllib.error.URLError, TimeoutError, ValueError):
            return False


def _lifecycle_parser(prog_root: str, action: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=f"{prog_root} web {action}",
        description="Manage a macOS LaunchAgent for the dts-utils web UI.",
    )
    if action == "install":
        parser.add_argument(
            "--bind",
            default=DTSWebLaunchAgent.DEFAULT_BIND,
            metavar="ADDR",
            help=f"Bind address for the web UI (default: {DTSWebLaunchAgent.DEFAULT_BIND}).",
        )
        parser.add_argument(
            "--port",
            type=int,
            default=DTSWebLaunchAgent.DEFAULT_PORT,
            metavar="N",
            help=f"HTTP port for the web UI (default: {DTSWebLaunchAgent.DEFAULT_PORT}).",
        )
        parser.add_argument(
            "--log-level",
            default="info",
            choices=["critical", "error", "warning", "info", "debug", "trace"],
            help="Uvicorn log level for the LaunchAgent process (default: info).",
        )
        parser.add_argument(
            "--no-access-log",
            action="store_true",
            help="Disable HTTP access logs on stdout and in the web log file.",
        )
        parser.add_argument(
            "--log-file",
            type=Path,
            default=None,
            metavar="PATH",
            help=f"Append uvicorn logs here (default: {default_web_log_path()}).",
        )
        parser.add_argument(
            "--no-log-file",
            action="store_true",
            help="Do not append LaunchAgent logs to a file.",
        )
        parser.add_argument(
            "--executable",
            default=None,
            metavar="PATH",
            help="Console script path for the LaunchAgent (default: resolve dts-utils on PATH).",
        )
        parser.add_argument(
            "-y",
            "--yes",
            action="store_true",
            help="Overwrite an existing LaunchAgent without prompting.",
        )
    return parser


def run_web_lifecycle(action: str, argv: list[str] | None) -> int:
    """Dispatch ``dts-utils web install|uninstall|start|stop|restart|status``."""
    if action not in WEB_LIFECYCLE_SUBCOMMANDS:
        prog = cli_command_name()
        subs = ", ".join(sorted(WEB_LIFECYCLE_SUBCOMMANDS))
        print(f"{prog}: unknown web subcommand {action!r}. Expected: {subs}.", file=sys.stderr)
        return 2

    agent = DTSWebLaunchAgent()
    if action == "install":
        prog_root = cli_command_name()
        args = _lifecycle_parser(prog_root, action).parse_args(argv)
        return agent.install(args)
    if action == "uninstall":
        return agent.uninstall()
    if action == "start":
        return agent.start()
    if action == "stop":
        return agent.stop()
    if action == "restart":
        return agent.restart()
    if action == "status":
        return agent.status()
    return 2
