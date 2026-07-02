#!/usr/bin/env python3

import argparse
import os
import subprocess
import sys
from pathlib import Path
import shutil
import tempfile
import urllib.error
import urllib.request
import plistlib
import time
import socket
from subprocess import PIPE
import json
from ..grpc.utils import is_server_running
from ..cli_prog import cli_command_name

_DOWNLOAD_USER_AGENT = "dts-utils-server-installer"


class DTSServerInstaller:
    # Default server settings
    DEFAULT_PORT = 7859
    DEFAULT_HOST = '0.0.0.0'
    DEFAULT_GPU = 0  # Default GPU index

    @property
    def DEFAULT_NAME(self):
        """Get cleaned up hostname for server name"""
        hostname = socket.gethostname()
        # Remove .local suffix if present
        if hostname.endswith('.local'):
            hostname = hostname[:-6]
        # Convert to ASCII if possible, otherwise keep Unicode
        try:
            return hostname.encode('ascii').decode('ascii')
        except UnicodeEncodeError:
            return hostname

    # File and directory names
    BINARY_NAME = "gRPCServerCLI"
    SERVICE_NAME = "com.drawthings.grpcserver"

    # System paths
    PREFERRED_BIN_DIR = Path('/usr/local/bin')
    LOCAL_BIN_DIR = Path.home() / '.local/bin'
    AGENTS_DIR = Path.home() / "Library/LaunchAgents"

    # GitHub API
    GITHUB_API_URL = "https://api.github.com/repos/drawthingsai/draw-things-community/releases/latest"
    FALLBACK_VERSION = "v1.20250225.0"

    def __init__(self):
        self.default_model_path = Path.home() / "Library/Containers/com.liuliu.draw-things/Data/Documents/Models"
        self.model_path = None
        self.server_args = None
        self.quiet = False
        self.install_yes = False
        self.usage_text = f"""
Draw Things gRPCServerCLI Installer

This script installs the Draw Things gRPCServerCLI and sets it up as a LaunchAgent service.

Usage:
    dts-utils server install [-m MODEL_PATH] [gRPCServerCLI options]
    dts-utils server uninstall
    dts-utils server start
    dts-utils server stop
    dts-utils server restart [--no-model-browser]
    dts-utils server test|check [--port PORT]
    dts-utils server models [--json] [--category CATEGORY]
    dts-utils server tail [--last DURATION]
    dts-utils generate --prompt PROMPT --configuration CONFIG [...]
    dts-utils \"PROMPT\" [PROFILE] [...]   Shorthand: same as generate with --trust-server-cert --open; PROFILE optional — missing default.json is auto-created (legacy zit.json renamed if present; model guessed from Draw Things Models dir) and $DTS_UTILS_DEFAULT_CONFIGURATION is set
    dts-utils reflect [--host HOST] [--port PORT] [--json] [TLS options]
    dts-utils configs <path|list> [...]
    dts-utils tls <path|export> [...]
    dts-utils models <build|search|show|report> [...]

Lifecycle commands apply only after ``dts-utils server …`` — see Commands below.

The installer will:
1. Download the gRPCServerCLI binary
2. Install it to {self.PREFERRED_BIN_DIR} (or {self.LOCAL_BIN_DIR} if {self.PREFERRED_BIN_DIR} is not writable)
3. Create and start a LaunchAgent service

Commands:
    server install        Install or update LaunchAgent-managed gRPCServerCLI
    server uninstall      Stop service, remove plist + binary paths this tool manages
    server start          Bootstrap plist into your GUI ``launchd`` domain (start job)
    server stop           Boot job out of ``launchd`` (plist remains)
    server restart        Stop then start (optional ``--no-model-browser`` to disable browsing)
    server test|check     Probe localhost listener; ``check`` aliases ``test``
    server models         List model files exposed by the server (``Echo`` RPC / model browser)
    server tail           Follow ``gRPCServerCLI`` logs via macOS ``log show`` + ``log stream``
    generate …            Client RPC: image generation (see upstream ``GenerateImage``)
    reflect …             Client RPC: reflection
    configs …             Saved JSON configs for ``generate``
    tls …                  Export presented TLS PEM for ``--root-cert``
    models …              Local Draw Things metadata index tools

Installer Options:
    -m, --model-path     Custom path to store models (default: Draw Things app models directory)
    -h, --help          Show this help message
    -q, --quiet            Minimize output and assume default answers to prompts

Install PEM export (requires TLS-enabled server install):
    --export-tls-cert      After successful install, write presented server PEM for ``--root-cert``
    --export-tls-cert-path PATH   PEM destination (default: ``dts-utils tls path`` output)
    --export-tls-cert-force       Overwrite an existing PEM

gRPCServerCLI Options:
    -n, --name             Server name in local network (default: machine name)
    -p, --port             Server port (default: {self.DEFAULT_PORT})
    -a, --address          Network address (default: {self.DEFAULT_HOST})
    -g, --gpu              GPU device index (default: {self.DEFAULT_GPU})
    -d, --datadog-api-key  Monitoring API key
    -s, --shared-secret    Authentication key
    --no-tls               Disable encryption (not recommended)
    --no-response-compression  Disable compression
    --no-model-browser     Disable model browsing (enabled by default)
    --no-flash-attention   Disable Flash Attention
    --debug                Enable verbose logging
    --join                 JSON configuration for proxy setup (see below)

Advanced Options:
    The --join option accepts a JSON string for distributed configurations:
    Example: --join '{{"host":"proxy.example.com", "port":7859, "servers":[{{"address":"gpu1.local", "port":7859, "priority":1}}]}}'

    Required fields for --join:
    - host: The proxy server hostname
    - port: The proxy server port
    Optional fields:
    - servers: List of GPU servers with required fields:
      - address: Server hostname
      - port: Server port
      - priority: Server priority (1=high, 2=low)

Examples:
    # Install with default settings
    dts-utils server install

    # Install and save the presented TLS certificate for ``--root-cert``
    dts-utils server install --export-tls-cert

    # Install with custom model path
    dts-utils server install -m /path/to/models

    # Install with custom port and server name
    dts-utils server install -p 7860 -n "MyServer"

    # Install with security options (recommended for public networks)
    dts-utils server install -s "mysecret"

    # Install without model browsing (enabled by default)
    dts-utils server install --no-model-browser

    # Install with proxy configuration
    dts-utils server install --join '{{"host":"proxy.local", "port":7859}}'

    # Start / stop / restart (plist must exist — run ``server install`` first)
    dts-utils server start
    dts-utils server stop
    dts-utils server restart

    # Disable model browsing on an existing service and restart
    dts-utils server restart --no-model-browser

    # Probe server connection
    dts-utils server test

    # Same probe on specific port / alternate verb
    dts-utils server test --port 7859
    dts-utils server check

    # Tail server logs (macOS Unified Logging)
    dts-utils server tail
    dts-utils server tail --last 1h
    dts-utils server tail --last 0    # live stream only, no history

    # Generate an image using a saved JSON config
    dts-utils generate --prompt "a small robot painting clouds" --configuration portrait --trust-server-cert

    # List services exposed through gRPC reflection
    dts-utils reflect --trust-server-cert

    # Show where named JSON generation configs are stored
    dts-utils configs path

    # Pin the server's TLS certificate locally (PEM for ``--root-cert``):
    dts-utils tls export

    # Quiet install with defaults
    dts-utils server install -q
"""

    def validate_join_config(self, join_config_str):
        """Validate the join configuration string.

        Args:
            join_config_str: JSON string containing join configuration

        Returns:
            bool: True if configuration is valid

        Raises:
            ValueError: If configuration is invalid
        """
        try:
            join_config = json.loads(join_config_str)
            required_fields = ['host', 'port']
            if not all(field in join_config for field in required_fields):
                raise ValueError("Join configuration must include 'host' and 'port'")

            # Validate host is not empty
            if not join_config['host']:
                raise ValueError("Host cannot be empty")

            # Validate port is positive
            if join_config['port'] <= 0:
                raise ValueError("Port must be positive")

            if 'servers' in join_config:
                for server in join_config['servers']:
                    if not all(field in server for field in ['address', 'port']):
                        raise ValueError("Each server in join configuration must have 'address' and 'port'")
            return True
        except json.JSONDecodeError:
            raise ValueError("Join configuration must be valid JSON")

    def parse_args(self):
        prog = cli_command_name()
        epilog = self.usage_text
        parser = argparse.ArgumentParser(
            prog=prog,
            description='Install Draw Things gRPCServerCLI',
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog=epilog)

        # Add actions as positional arguments
        parser.add_argument(
            'action',
            nargs='?',
            choices=['install', 'uninstall', 'start', 'stop', 'restart', 'test', 'check', 'status', 'tail'],
            help=(
                'Action (install | uninstall | start | stop | restart | test | check | status | tail); '
                'test|check probes the listener; status prints LaunchAgent flags; tail follows logs (macOS)'
            ),
        )

        # Installer arguments
        parser.add_argument('-m', '--model-path',
                          default=os.environ.get('DRAW_THINGS_MODEL_PATH', None),
                          help='Model directory path')
        parser.add_argument('-q', '--quiet', action='store_true',
                          help='Minimize output and assume default answers to prompts')
        parser.add_argument(
            '-y', '--yes',
            action='store_true',
            help='Non-interactive install: overwrite an existing LaunchAgent plist without prompting',
        )

        # gRPCServerCLI arguments
        parser.add_argument('-n', '--name', default=None,
                          help=f'Server name in local network (default: machine name)')
        parser.add_argument('-p', '--port', type=int, default=self.DEFAULT_PORT,
                          help=f'Port to run the server on (default: {self.DEFAULT_PORT})')
        parser.add_argument('-a', '--address', default=self.DEFAULT_HOST,
                          help=f'Address to bind to (default: {self.DEFAULT_HOST})')
        parser.add_argument('-g', '--gpu', type=int, default=self.DEFAULT_GPU,
                          help=f'GPU index to use (default: {self.DEFAULT_GPU})')
        parser.add_argument('-d', '--datadog-api-key',
                          help='Datadog API key for logging backend')
        parser.add_argument('-s', '--shared-secret',
                          help='Shared secret for server security')
        parser.add_argument('--no-tls', action='store_true',
                          help='Disable TLS for connections')
        parser.add_argument('--no-response-compression', action='store_true',
                          help='Disable response compression')
        model_browser_group = parser.add_mutually_exclusive_group()
        model_browser_group.add_argument(
            '--model-browser',
            action='store_true',
            help='Enable model browsing (default unless --no-model-browser is set)',
        )
        model_browser_group.add_argument(
            '--no-model-browser',
            action='store_true',
            help='Disable model browsing on gRPCServerCLI (Echo file list)',
        )
        parser.add_argument('--no-flash-attention', action='store_true',
                          help='Disable Flash Attention')
        parser.add_argument('--debug', action='store_true',
                          help='Enable verbose model inference logging')
        parser.add_argument('--join',
                          help='JSON configuration for proxy setup')
        parser.add_argument(
            '--export-tls-cert',
            action='store_true',
            help=(
                'After a successful install with TLS, write the presented server certificate '
                f'to a PEM file (default path: run `{prog} tls path`).'
            ),
        )
        parser.add_argument(
            '--export-tls-cert-path',
            type=Path,
            default=None,
            metavar='PATH',
            help='Destination PEM when using --export-tls-cert (default: tls path).',
        )
        parser.add_argument(
            '--export-tls-cert-force',
            action='store_true',
            help='Overwrite an existing PEM when using --export-tls-cert.',
        )
        parser.add_argument(
            '--last',
            default='5m',
            metavar='DURATION',
            help=(
                'For server tail: history window before live stream (log show --last; default: 5m). '
                'Use 0 to skip history and stream only.'
            ),
        )
        parser.add_argument(
            '--log-style',
            dest='log_style',
            choices=['compact', 'syslog', 'default'],
            default='compact',
            help='For server tail: log(1) output style (default: compact).',
        )

        args = parser.parse_args()

        if args.action == "check":
            args.action = "test"

        # Handle start / stop / restart (LaunchAgent lifecycle)
        if args.action == 'start':
            self.start_service()
            sys.exit(0)
        if args.action == 'stop':
            self.stop_service()
            sys.exit(0)
        if args.action == 'restart':
            self.restart_service(ensure_model_browser=not args.no_model_browser)
            sys.exit(0)

        # Handle uninstall action
        if args.action == 'uninstall':
            self.uninstall()
            sys.exit(0)

        # Handle test action (moved from run method to here for consistency)
        if args.action == 'test':
            if is_server_running(port=args.port, prefer_plaintext=args.no_tls):
                print("Server is running and responding!")
                sys.exit(0)
            else:
                print("Could not connect to server")
                sys.exit(1)

        if args.action == 'tail':
            sys.exit(self.tail_server_logs(last=args.last, log_style=args.log_style))

        if args.action == 'status':
            sys.exit(self.show_service_status())

        self.quiet = args.quiet
        self.install_yes = args.yes
        self.model_path = Path(args.model_path) if args.model_path else self.get_default_model_path()

        # Validate join configuration if provided
        if args.join:
            try:
                self.validate_join_config(args.join)
            except ValueError as e:
                print(f"Error: {e}")
                sys.exit(1)

        # Security warning for no-tls
        if args.no_tls:
            if not self.quiet:
                print("\nWARNING: --no-tls disables encryption. Use only in trusted networks!")
                response = input("Are you sure you want to continue? (y/N): ")
                if response.lower() != 'y':
                    print("Installation cancelled.")
                    sys.exit(0)

        self.server_args = {
            'name': args.name if args.name is not None else self.DEFAULT_NAME,
            'port': args.port,
            'address': args.address,
            'gpu': args.gpu,
            'datadog_api_key': args.datadog_api_key,
            'shared_secret': args.shared_secret,
            'no_tls': args.no_tls,
            'no_response_compression': args.no_response_compression,
            'model_browser': not args.no_model_browser,
            'no_flash_attention': args.no_flash_attention,
            'debug': args.debug,
            'join': args.join
        }

        return args

    def get_default_model_path(self):
        """Return the default model path if it exists, otherwise prompt user"""
        if self.default_model_path.exists():
            return self.default_model_path

        print(f"Default model path not found: {self.default_model_path}")
        print("\nUsage tip: You can specify a custom model path with:")
        print(f"    {sys.argv[0]} -m /path/to/models\n")

        while True:
            path = input("Please enter path for models (or 'h' for help, 'q' to quit): ")
            if path.lower() == 'q':
                sys.exit(0)
            if path.lower() == 'h':
                print(self.usage_text)
                continue
            if Path(path).exists():
                return Path(path)
            print("Path does not exist. Please try again.")

    def get_latest_release_url(self):
        """Get the download URL for the latest macOS release"""
        print("Checking for latest release...")
        try:
            # Get the latest release
            req = urllib.request.Request(self.GITHUB_API_URL, headers={'Accept': 'application/json'})
            with urllib.request.urlopen(req) as response:
                release = json.loads(response.read().decode())
                if release and 'tag_name' in release:
                    latest_tag = release['tag_name']
                    print(f"Found latest version: {latest_tag}")
                    return f"https://github.com/drawthingsai/draw-things-community/releases/download/{latest_tag}/{self.BINARY_NAME}-macOS"
                raise ValueError("No release found")
        except Exception as e:
            print(f"Failed to get latest version: {e}")
            print("Falling back to hardcoded latest known version...")
            return f"https://github.com/drawthingsai/draw-things-community/releases/download/{self.FALLBACK_VERSION}/{self.BINARY_NAME}-macOS"

    def _http_request_headers(self) -> dict[str, str]:
        return {"User-Agent": _DOWNLOAD_USER_AGENT, "Accept": "*/*"}

    def _probe_download_size(self, url: str) -> int | None:
        """Best-effort Content-Length for progress (follows GitHub redirects)."""
        try:
            req = urllib.request.Request(url, method="HEAD", headers=self._http_request_headers())
            with urllib.request.urlopen(req, timeout=30) as response:
                length = response.headers.get("Content-Length")
                if length:
                    return int(length)
        except Exception:
            pass
        return None

    @staticmethod
    def _format_download_progress(downloaded: int, total_size: int, *, bar_width: int = 28) -> str:
        downloaded_mib = downloaded / (1024 * 1024)
        if total_size <= 0:
            return f"{downloaded_mib:.1f} MiB downloaded"
        pct = min(100, downloaded * 100 // total_size)
        filled = pct * bar_width // 100
        if pct >= 100:
            bar = "=" * bar_width
        else:
            arrow = filled < bar_width
            used = filled + (1 if arrow else 0)
            bar = ("=" * filled) + (">" if arrow else "") + (" " * (bar_width - used))
        total_mib = total_size / (1024 * 1024)
        return f"[{bar}] {pct:3d}%  {downloaded_mib:.1f}/{total_mib:.1f} MiB"

    def _download_url_to_path(self, url: str, dest_path: Path) -> None:
        """Download *url* to *dest_path* with an in-terminal progress meter."""
        total_size = self._probe_download_size(url)
        if total_size:
            print(
                f"Downloading gRPCServerCLI ({total_size / (1024 * 1024):.1f} MiB)\n"
                f"  {url}"
            )
        else:
            print(f"Downloading gRPCServerCLI from:\n  {url}")

        last_report = 0.0

        def reporthook(block_num: int, block_size: int, hook_total: int) -> None:
            nonlocal last_report
            if self.quiet:
                return
            now = time.monotonic()
            downloaded = block_num * block_size
            effective_total = hook_total if hook_total > 0 else (total_size or 0)
            if now - last_report < 0.2 and (effective_total <= 0 or downloaded < effective_total):
                return
            last_report = now
            line = self._format_download_progress(downloaded, effective_total)
            print(f"\r{line}", end="", flush=True)

        urllib.request.urlretrieve(url, dest_path, reporthook=reporthook)
        if not self.quiet:
            if total_size:
                print(f"\r{self._format_download_progress(total_size, total_size)}")
            else:
                print()

    def download_grpcserver(self):
        """Download and install the gRPCServerCLI binary"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            binary_path = Path(tmp_dir) / self.BINARY_NAME
            url = self.get_latest_release_url()

            try:
                self._download_url_to_path(url, binary_path)
            except urllib.error.URLError as e:
                print(f"Failed to download gRPCServerCLI: {e}")
                sys.exit(1)

            try:
                # Test if we can write to /usr/local/bin
                if not self.PREFERRED_BIN_DIR.exists():
                    self.PREFERRED_BIN_DIR.mkdir(parents=True)

                test_file = self.PREFERRED_BIN_DIR / '.write_test'
                test_file.touch()
                test_file.unlink()

                bin_dir = self.PREFERRED_BIN_DIR
            except (OSError, PermissionError):
                print(f"Cannot write to {self.PREFERRED_BIN_DIR}, using {self.LOCAL_BIN_DIR} instead")
                bin_dir = self.LOCAL_BIN_DIR
                bin_dir.mkdir(parents=True, exist_ok=True)

                # Check if ~/.local/bin is in PATH
                path = os.environ.get('PATH', '')
                if str(self.LOCAL_BIN_DIR) not in path:
                    print(f"\nNOTE: {self.LOCAL_BIN_DIR} is not in your PATH.")
                    response = input("Would you like to add it to your PATH? (y/N): ")
                    if response.lower() == 'y':
                        # Detect shell (zsh is default on modern macOS)
                        shell_path = os.environ.get('SHELL', '/bin/zsh')
                        if 'zsh' in shell_path:
                            rc_file = Path.home() / '.zshrc'
                        else:
                            rc_file = Path.home() / '.bash_profile'

                        path_line = f'\nexport PATH="$HOME/.local/bin:$PATH"  # Added by Draw Things installer\n'

                        try:
                            with open(rc_file, 'a') as f:
                                f.write(path_line)
                            print(f"Added {self.LOCAL_BIN_DIR} to PATH in {rc_file}")
                            print("Please restart your terminal or run:")
                            print(f"    source {rc_file}")
                        except Exception as e:
                            print(f"Failed to modify {rc_file}: {e}")
                            print("To add it manually, add this line to your shell configuration:")
                            print(f'    export PATH="{self.LOCAL_BIN_DIR}:$PATH"')
                    else:
                        print("\nTo add it manually later, add this line to your shell configuration:")
                        print(f'    export PATH="{self.LOCAL_BIN_DIR}:$PATH"')

            dest_path = bin_dir / self.BINARY_NAME

            # Check if binary already exists
            if dest_path.exists():
                print(f"\nFound existing gRPCServerCLI at {dest_path}")
                response = input("Would you like to overwrite it? (y/N): ")
                if response.lower() != 'y':
                    print("Installation cancelled.")
                    sys.exit(0)

                # Stop any running services before overwriting
                service_path = self.AGENTS_DIR / f'{self.SERVICE_NAME}.plist'
                if service_path.exists():
                    print("Stopping existing service before updating binary...")
                    try:
                        self._launchctl_stop_job(service_path)
                        time.sleep(1)  # Give the service time to stop
                    except Exception as e:
                        print(f"Warning: Failed to stop service: {e}")

                # Stop any running processes
                try:
                    subprocess.run(['pkill', '-f', 'gRPCServer'], check=False)
                    time.sleep(1)  # Give processes time to stop
                except Exception as e:
                    print(f"Warning: Failed to stop processes: {e}")

            shutil.move(str(binary_path), dest_path)
            os.chmod(dest_path, 0o755)

            return dest_path

    def create_launchd_service(self, binary_path):
        """Create and load the launchd service as a LaunchAgent"""
        self.AGENTS_DIR.mkdir(parents=True, exist_ok=True)
        service_path = self.AGENTS_DIR / f'{self.SERVICE_NAME}.plist'

        # Check if service already exists
        if service_path.exists():
            print(f"\nFound existing service at {service_path}")
            if not (self.install_yes or self.prompt_user("Would you like to update it? (y/N): ", default='n')):
                print("Service installation cancelled.")
                if self.server_args and self.server_args.get('model_browser'):
                    print(
                        "Tip: existing plist was left unchanged. Model browser is on by default — apply with:\n"
                        f"    uv run {cli_command_name()} server install -y\n"
                        f"    # or: uv run {cli_command_name()} server restart",
                    )
                return

            # Stop existing service
            print("Stopping existing service...")
            try:
                self._launchctl_stop_job(service_path)
                time.sleep(1)  # Give the service time to stop
            except Exception as e:
                print(f"Warning: Failed to stop service: {e}")

        # Build command line arguments list
        cmd_args = [str(binary_path), str(self.model_path)]

        # Add optional arguments
        if self.server_args['name'] != self.DEFAULT_NAME:
            cmd_args.extend(['--name', self.server_args['name']])
        if self.server_args['port'] != self.DEFAULT_PORT:
            cmd_args.extend(['--port', str(self.server_args['port'])])
        if self.server_args['address'] != self.DEFAULT_HOST:
            cmd_args.extend(['--address', self.server_args['address']])
        if self.server_args['gpu'] != self.DEFAULT_GPU:
            cmd_args.extend(['--gpu', str(self.server_args['gpu'])])
        if self.server_args['datadog_api_key']:
            cmd_args.extend(['--datadog-api-key', self.server_args['datadog_api_key']])
        if self.server_args['shared_secret']:
            cmd_args.extend(['--shared-secret', self.server_args['shared_secret']])
        if self.server_args['no_tls']:
            cmd_args.append('--no-tls')
        if self.server_args['no_response_compression']:
            cmd_args.append('--no-response-compression')
        if self.server_args['model_browser']:
            cmd_args.append('--model-browser')
        if self.server_args['no_flash_attention']:
            cmd_args.append('--no-flash-attention')
        if self.server_args['debug']:
            cmd_args.append('--debug')
        if self.server_args['join']:
            cmd_args.extend(['--join', self.server_args['join']])

        service_config = {
            'Label': self.SERVICE_NAME,
            'ProgramArguments': cmd_args,
            'RunAtLoad': True,
            'KeepAlive': True
        }

        try:
            with open(service_path, 'wb') as f:
                plistlib.dump(service_config, f)

            self._launchctl_start_job(service_path)
            print(f"Service installed and started at {service_path}")
            print("Server configuration:")
            # Only show non-default values
            defaults = {
                'name': self.DEFAULT_NAME,
                'port': self.DEFAULT_PORT,
                'address': self.DEFAULT_HOST,
                'gpu': self.DEFAULT_GPU,
                'datadog_api_key': None,
                'shared_secret': None,
                'no_tls': False,
                'no_response_compression': False,
                'model_browser': True,
                'no_flash_attention': False,
                'debug': False,
                'join': None
            }
            for key, value in self.server_args.items():
                if value != defaults[key]:
                    print(f"  {key}: {value}")
            if self.server_args.get('model_browser'):
                print("  model_browser: enabled (default)")
        except (OSError, subprocess.CalledProcessError) as e:
            print(f"Failed to create or load service: {e}")
            sys.exit(1)

    _LOG_PREDICATE = 'process == "gRPCServerCLI"'

    def tail_server_logs(self, *, last: str, log_style: str) -> int:
        """Print recent ``gRPCServerCLI`` unified logs, then follow live output (macOS only)."""
        prog = cli_command_name()
        if sys.platform != "darwin":
            print(f"{prog} server tail requires macOS (Unified Logging).", file=sys.stderr)
            return 1

        style_args: list[str] = []
        if log_style and log_style != "default":
            style_args = ["--style", log_style]

        show_history = last.strip() not in ("", "0")
        try:
            if show_history:
                print(f"--- gRPCServerCLI logs (last {last}) ---", file=sys.stderr, flush=True)
                show = subprocess.run(
                    ["log", "show", "--predicate", self._LOG_PREDICATE, "--last", last, *style_args],
                    check=False,
                )
                if show.returncode != 0:
                    print(
                        f"{prog} server tail: log show exited {show.returncode} "
                        "(history may be empty or unavailable).",
                        file=sys.stderr,
                    )
            print("--- following (Ctrl+C to stop) ---", file=sys.stderr, flush=True)
            stream = subprocess.run(
                ["log", "stream", "--predicate", self._LOG_PREDICATE, *style_args],
                check=False,
            )
            return stream.returncode if stream.returncode is not None else 0
        except KeyboardInterrupt:
            print("\nStopped.", file=sys.stderr)
            return 0

    def test_server_running(self):
        """Test if the gRPCServerCLI is running and accepting connections"""
        print("\nTesting gRPCServerCLI...")

        # Check if process is running
        try:
            result = subprocess.run(['pgrep', 'gRPCServerCLI'], stdout=PIPE, text=True)
            if not result.stdout.strip():
                print("ERROR: gRPCServerCLI process not found")
                return False

            pid = result.stdout.strip()
            print(f"Found gRPCServerCLI process (PID: {pid})")
        except subprocess.CalledProcessError as e:
            print(f"ERROR: Failed to check process: {e}")
            return False

        # Give the server a moment to start listening
        time.sleep(1)

        # Test port connection using lsof
        try:
            result = subprocess.run(['lsof', '-i', f':{self.server_args["port"]}'],
                                stdout=PIPE, stderr=PIPE, text=True)
            if result.returncode == 0 and 'gRPCServe' in result.stdout and 'LISTEN' in result.stdout:
                print(f"Server is listening on port {self.server_args['port']}")
                return True

            # If lsof fails or doesn't show the port, try a direct connection test
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            try:
                sock.connect(('localhost', self.server_args['port']))
                print(f"Server is accepting connections on port {self.server_args['port']}")
                return True
            except (socket.timeout, ConnectionRefusedError):
                print(f"ERROR: Server is not accepting connections on port {self.server_args['port']}")
                return False
            finally:
                sock.close()
        except Exception as e:
            print(f"ERROR: Failed to check port: {e}")
            return False

    def check_existing_service(self):
        """Check for any existing Draw Things gRPC services"""
        print("Checking for existing services...")

        has_existing = False

        # Check for existing service plist files
        service_patterns = [
            "com.drawthings.grpcserver*.plist",
            "com.draw-things.grpcserver*.plist",
            "*drawthings*grpc*.plist",
            "*draw-things*grpc*.plist"
        ]

        existing_services: list[Path] = []
        seen_services: set[Path] = set()
        for pattern in service_patterns:
            for service in self.AGENTS_DIR.glob(pattern):
                if service in seen_services:
                    continue
                seen_services.add(service)
                existing_services.append(service)

        if existing_services:
            has_existing = True
            print("\nFound existing service files:")
            for service in existing_services:
                print(f"  - {service}")

        # Check for running gRPC processes
        try:
            result = subprocess.run(['pgrep', '-fl', 'gRPCServer'], stdout=PIPE, text=True)
            if result.stdout.strip():
                has_existing = True
                print("\nFound running gRPC processes:")
                for line in result.stdout.strip().split('\n'):
                    print(f"  - {line}")
        except subprocess.CalledProcessError:
            pass

        # Check if default port is in use
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('localhost', self.DEFAULT_PORT))
            sock.close()

            if result == 0:
                has_existing = True
                print(f"\nPort {self.DEFAULT_PORT} is already in use!")
                try:
                    # Try to get more info about what's using the port
                    lsof = subprocess.run(['lsof', '-i', f':{self.DEFAULT_PORT}'],
                                       stdout=PIPE, text=True, check=True)
                    print("\nProcess using the port:")
                    print(lsof.stdout)
                except subprocess.CalledProcessError:
                    pass
        except Exception:
            pass

        if has_existing:
            print("\nFound existing Draw Things gRPC installation!")
            print("It's recommended to uninstall before proceeding.")
            response = input("Would you like to uninstall now? (Y/n): ")
            if response.lower() != 'n':
                self.uninstall()
                print("\nContinuing with fresh installation...\n")
            else:
                print("\nProceeding without uninstalling...")
                response = input("Are you sure you want to continue? This might cause issues. (y/N): ")
                if response.lower() != 'y':
                    print("Installation cancelled.")
                    sys.exit(1)
            print()  # Empty line for readability

    def enable_model_browser_for_service(self, service_path):
        """Ensure the installed LaunchAgent starts gRPCServerCLI with model browsing."""
        try:
            with open(service_path, 'rb') as f:
                service_config = plistlib.load(f)
        except (OSError, plistlib.InvalidFileException) as e:
            print(f"Failed to read service configuration: {e}")
            sys.exit(1)

        cmd_args = service_config.get('ProgramArguments')
        if not isinstance(cmd_args, list) or not cmd_args:
            print("Error: Service configuration is missing ProgramArguments")
            sys.exit(1)

        if '--model-browser' in cmd_args:
            return False

        cmd_args.append('--model-browser')
        try:
            with open(service_path, 'wb') as f:
                plistlib.dump(service_config, f)
        except OSError as e:
            print(f"Failed to update service configuration: {e}")
            sys.exit(1)

        print("Model browser enabled in service configuration")
        return True

    def disable_model_browser_for_service(self, service_path: Path) -> bool:
        """Remove ``--model-browser`` from the installed LaunchAgent when present."""
        try:
            with open(service_path, 'rb') as f:
                service_config = plistlib.load(f)
        except (OSError, plistlib.InvalidFileException) as e:
            print(f"Failed to read service configuration: {e}")
            sys.exit(1)

        cmd_args = service_config.get('ProgramArguments')
        if not isinstance(cmd_args, list) or not cmd_args:
            print("Error: Service configuration is missing ProgramArguments")
            sys.exit(1)

        if '--model-browser' not in cmd_args:
            return False

        service_config['ProgramArguments'] = [arg for arg in cmd_args if arg != '--model-browser']
        try:
            with open(service_path, 'wb') as f:
                plistlib.dump(service_config, f)
        except OSError as e:
            print(f"Failed to update service configuration: {e}")
            sys.exit(1)

        print("Model browser disabled in service configuration")
        return True

    @staticmethod
    def read_service_program_arguments(service_path: Path | None = None) -> list[str] | None:
        """Return ``ProgramArguments`` from the installed LaunchAgent plist."""
        path = service_path
        if path is None:
            path = Path.home() / "Library/LaunchAgents" / f"{DTSServerInstaller.SERVICE_NAME}.plist"
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
        return [str(x) for x in program_args]

    @staticmethod
    def parse_program_argument_flags(program_args: list[str]) -> dict[str, object]:
        """Extract a few settings from a gRPCServerCLI ``ProgramArguments`` list."""
        flags: dict[str, object] = {
            "model_browser": False,
            "no_tls": False,
            "port": DTSServerInstaller.DEFAULT_PORT,
            "shared_secret": None,
        }
        for index, token in enumerate(program_args):
            if token == "--model-browser":
                flags["model_browser"] = True
            elif token == "--no-tls":
                flags["no_tls"] = True
            elif token == "--port" and index + 1 < len(program_args):
                try:
                    flags["port"] = int(program_args[index + 1])
                except ValueError:
                    pass
            elif token == "--shared-secret" and index + 1 < len(program_args):
                flags["shared_secret"] = program_args[index + 1]
        return flags

    @staticmethod
    def echo_model_file_count(*, host: str, port: int, no_tls: bool, shared_secret: str | None = None) -> int | None:
        """Return Echo ``files`` count when the server exposes model browsing."""
        try:
            from dts_utils.grpc.connection import create_channel
            from dts_utils.grpc.proto.upstream import imageService_pb2 as pb
            from dts_utils.grpc.proto.upstream import imageService_pb2_grpc as stubs

            channel = create_channel(
                host,
                port,
                no_tls,
                trust_server_cert=not no_tls,
            )
            stub = stubs.ImageGenerationServiceStub(channel)
            request = pb.EchoRequest(name=cli_command_name())
            if shared_secret:
                request.sharedSecret = shared_secret
            reply = stub.Echo(request, timeout=5)
            channel.close()
            return len(reply.files)
        except Exception:
            return None

    def show_service_status(self) -> int:
        """Print installed LaunchAgent settings and whether model browsing is active."""
        prog = cli_command_name()
        service_path = self.AGENTS_DIR / f"{self.SERVICE_NAME}.plist"
        program_args = self.read_service_program_arguments(service_path)
        if program_args is None:
            print(f"{prog} server status: LaunchAgent not installed ({service_path})")
            print(f"Install with: uv run {prog} server install")
            return 1

        flags = self.parse_program_argument_flags(program_args)
        port = int(flags["port"])
        no_tls = bool(flags["no_tls"])
        model_browser = bool(flags["model_browser"])
        shared_secret = flags["shared_secret"]

        print(f"Plist: {service_path}")
        print(f"ProgramArguments: {' '.join(program_args)}")
        print(f"model-browser: {'enabled' if model_browser else 'disabled'}")
        if not model_browser:
            print(
                f"Enable with: uv run {prog} server restart "
                f"(or `server install -y`; model browser is on by default)"
            )

        listener_up = is_server_running(port=port, prefer_plaintext=no_tls)
        print(f"Listener ({port}, {'plaintext' if no_tls else 'TLS'}): {'up' if listener_up else 'down'}")

        if listener_up and model_browser:
            file_count = self.echo_model_file_count(
                host="localhost",
                port=port,
                no_tls=no_tls,
                shared_secret=str(shared_secret) if shared_secret else None,
            )
            if file_count is None:
                print("Echo model files: unavailable (RPC error)")
            elif file_count == 0:
                print("Echo model files: 0 (model browser flag set but server returned no files yet)")
            else:
                print(f"Echo model files: {file_count} (model browsing active)")
        elif listener_up and not model_browser:
            print("Echo model files: n/a until --model-browser is enabled and the job restarted")

        return 0 if listener_up else 2

    def _launchd_gui_domain(self) -> str:
        """launchd domain for per-user GUI agents (``gui/<uid>``)."""
        return f"gui/{os.getuid()}"

    def _launchctl_stop_job(self, service_path: Path) -> None:
        """Boot the LaunchAgent out of launchd; plist may remain on disk.

        Prefer ``launchctl bootout`` by service label, then by plist path. Avoid
        legacy ``unload`` — it prints noisy errors on modern macOS when the job
        was registered with ``bootstrap``.
        """
        domain = self._launchd_gui_domain()
        label_target = f"{domain}/{self.SERVICE_NAME}"
        for args in (
            ["launchctl", "bootout", label_target],
            ["launchctl", "bootout", domain, str(service_path)],
        ):
            out = subprocess.run(args, capture_output=True, text=True)
            if out.returncode == 0:
                return
        subprocess.run(
            ["launchctl", "remove", self.SERVICE_NAME],
            capture_output=True,
            text=True,
            check=False,
        )

    def _launchctl_kickstart_job(self, *, kill: bool = False) -> bool:
        """Restart a registered job in place (``kickstart -k`` when ``kill``)."""
        domain = self._launchd_gui_domain()
        cmd = ["launchctl", "kickstart"]
        if kill:
            cmd.append("-k")
        cmd.extend(["-p", f"{domain}/{self.SERVICE_NAME}"])
        out = subprocess.run(cmd, capture_output=True, text=True)
        return out.returncode == 0

    def _launchctl_start_job(self, service_path: Path) -> None:
        """Load plist into the user's GUI domain and ensure the job runs.

        Prefer ``launchctl bootstrap``. If the job is already registered, use
        ``kickstart``. Fall back to legacy ``load``.
        """
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

    def start_service(self) -> None:
        """Load the installed LaunchAgent plist and start gRPCServerCLI."""
        service_path = self.AGENTS_DIR / f"{self.SERVICE_NAME}.plist"
        if not service_path.exists():
            print("Error: Service not installed")
            sys.exit(1)
        print("Starting gRPCServerCLI LaunchAgent...")
        try:
            self._launchctl_start_job(service_path)
        except subprocess.CalledProcessError as e:
            print(f"Failed to start service: {e}")
            sys.exit(1)
        print("Service started successfully")

    def stop_service(self) -> None:
        """Stop and unload the LaunchAgent job; plist and binary remain."""
        service_path = self.AGENTS_DIR / f"{self.SERVICE_NAME}.plist"
        if not service_path.exists():
            print("Error: Service not installed")
            sys.exit(1)
        print("Stopping gRPCServerCLI LaunchAgent...")
        self._launchctl_stop_job(service_path)
        print("Service stopped successfully")

    def restart_service(self, *, ensure_model_browser: bool = True):
        """Restart the gRPCServerCLI service."""
        print("Restarting gRPCServerCLI service...")
        service_path = self.AGENTS_DIR / f'{self.SERVICE_NAME}.plist'
        if not service_path.exists():
            print("Error: Service not installed")
            sys.exit(1)

        if ensure_model_browser:
            plist_changed = self.enable_model_browser_for_service(service_path)
        else:
            plist_changed = self.disable_model_browser_for_service(service_path)

        try:
            if plist_changed:
                self._launchctl_stop_job(service_path)
                time.sleep(1)
                self._launchctl_start_job(service_path)
            elif not self._launchctl_kickstart_job(kill=True):
                self._launchctl_stop_job(service_path)
                time.sleep(1)
                self._launchctl_start_job(service_path)
            print("Service restarted successfully")
        except subprocess.CalledProcessError as e:
            print(f"Failed to restart service: {e}")
            sys.exit(1)

    def prompt_user(self, message, default='n'):
        """Handle user prompts with quiet mode support"""
        if self.quiet:
            return default.lower() == 'y'
        response = input(message)
        return response.lower() == 'y' if response else default.lower() == 'y'

    def check_port_available(self, port):
        """Check if a port is available"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        try:
            result = sock.connect_ex(('localhost', port))
            return result != 0
        finally:
            sock.close()

    def maybe_export_installed_tls_pem(self, args: argparse.Namespace) -> None:
        """Optionally fetch the presented server cert after a successful TLS install."""
        if not getattr(args, "export_tls_cert", False):
            return
        assert self.server_args is not None
        if self.server_args.get("no_tls"):
            print("\n(--export-tls-cert skipped: server was installed with --no-tls)")
            return
        from ..tls_export import default_server_pem_path, export_presented_certificate_with_retries

        dest = args.export_tls_cert_path if args.export_tls_cert_path else default_server_pem_path()
        try:
            resolved = export_presented_certificate_with_retries(
                "localhost",
                self.server_args["port"],
                dest,
                force=args.export_tls_cert_force,
                attempts=10,
            )
            print("\nPresented server TLS certificate saved (pin with client --root-cert):")
            print(f"    {resolved}")
            print(f"Example: uv run {cli_command_name()} generate --root-cert {resolved} ...")
        except Exception as exc:
            print(f"\nWARNING: Could not export TLS PEM: {exc}", file=sys.stderr)

    def run(self):
        args = self.parse_args()

        # If no arguments provided, show usage
        if len(sys.argv) == 1:
            print(self.usage_text)
            sys.exit(0)

        # At this point, only the 'install' action should reach here
        # All other actions (uninstall, start, stop, restart, test) are handled in parse_args()
        if args.action == 'install':
            try:
                # Validate port availability
                if not self.check_port_available(self.server_args['port']):
                    print(f"\nError: Port {self.server_args['port']} is already in use!")
                    try:
                        lsof = subprocess.run(['lsof', '-i', f":{self.server_args['port']}"],
                                           stdout=PIPE, text=True, check=True)
                        print("\nProcess using the port:")
                        print(lsof.stdout)
                    except subprocess.CalledProcessError:
                        pass
                    sys.exit(1)

                # Check for existing services before proceeding
                self.check_existing_service()

                binary_path = self.download_grpcserver()
                self.create_launchd_service(binary_path)

                # Wait a moment for the service to start
                print("\nWaiting for service to start...")
                time.sleep(2)

                # Test if server is running
                if self.test_server_running():
                    print("\nInstallation completed successfully!")
                    print(f"Models directory: {self.model_path}")
                    print(f"Binary location: {binary_path}")
                    print("\nThe gRPCServerCLI service is running and will start automatically on login.")
                    print("You can manage it with:")
                    uid = os.getuid()
                    p = cli_command_name()
                    print(f"    uv run {p} server stop   # or: launchctl bootout gui/{uid} ~/Library/LaunchAgents/{self.SERVICE_NAME}.plist")
                    print(f"    uv run {p} server start  # or: launchctl bootstrap gui/{uid} ~/Library/LaunchAgents/{self.SERVICE_NAME}.plist")
                    self.maybe_export_installed_tls_pem(args)
                else:
                    print("\nWARNING: Installation completed but server may not be running correctly.")
                    print("Try these troubleshooting steps:")
                    print("1. Check the system log for errors:")
                    print(f"    uv run {cli_command_name()} server tail")
                    print("2. Restart the service:")
                    uid = os.getuid()
                    print(f"    uv run {cli_command_name()} server restart")
                    print(f"    # launchctl bootout gui/{uid} ~/Library/LaunchAgents/{self.SERVICE_NAME}.plist")
                    print(f"    # launchctl bootstrap gui/{uid} ~/Library/LaunchAgents/{self.SERVICE_NAME}.plist")
                    print("3. Check if the models directory is accessible:")
                    print(f"    ls {self.model_path}")
            except Exception as e:
                print(f"Installation failed: {e}")
                print("\nFor usage information, run:")
                print(f"    {sys.argv[0]} --help")
                sys.exit(1)
        elif args.action is None:
            # No action specified
            print("No action specified.")
            print(self.usage_text)
            sys.exit(1)
        else:
            # This should never happen since parse_args() handles all actions
            print(f"Unknown action: {args.action}")
            print(self.usage_text)
            sys.exit(1)

    def uninstall(self):
        """Remove gRPCServerCLI, service files, and clean up"""
        print("Uninstalling gRPCServerCLI...")

        # Stop and remove LaunchAgent
        service_path = self.AGENTS_DIR / f'{self.SERVICE_NAME}.plist'
        if service_path.exists():
            try:
                print("Stopping and removing service...")
                self._launchctl_stop_job(service_path)
                service_path.unlink()
            except Exception as e:
                print(f"Warning: Failed to fully remove service: {e}")

        # Stop any running gRPCServer processes
        try:
            subprocess.run(['pkill', '-f', 'gRPCServer'], check=False)
            time.sleep(1)  # Give processes time to stop
        except Exception as e:
            print(f"Warning: Failed to stop processes: {e}")

        # Remove binary from potential locations
        binary_paths = [
            self.PREFERRED_BIN_DIR / self.BINARY_NAME,
            self.LOCAL_BIN_DIR / self.BINARY_NAME
        ]

        for binary_path in binary_paths:
            if binary_path.exists():
                try:
                    print(f"Removing binary from {binary_path}...")
                    binary_path.unlink()
                except Exception as e:
                    print(f"Warning: Failed to remove binary at {binary_path}: {e}")

        # Check if the port is still in use
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('localhost', self.DEFAULT_PORT))
            sock.close()

            if result == 0:
                print(f"\nWARNING: Port {self.DEFAULT_PORT} is still in use!")
                print("You may need to restart your computer or check for other services using this port.")
        except Exception:
            pass

        print("\nUninstall complete!")
        print("Note: Model directory was not removed.")
