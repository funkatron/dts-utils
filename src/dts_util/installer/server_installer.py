#!/usr/bin/env python3

import argparse
import os
import subprocess
import sys
from pathlib import Path
import shutil
import tempfile
import urllib.request
import plistlib
import time
import socket
from subprocess import PIPE
import json
from ..configs import main as configs_main
from ..generate import main as generate_main
from ..grpc.utils import is_server_running, handle_grpc_error
from ..grpc.reflect import main as reflect_main
from dt_model_index.cli import main as models_main

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
        self.usage_text = f"""
Draw Things gRPCServerCLI Installer

This script installs the Draw Things gRPCServerCLI and sets it up as a LaunchAgent service.

Usage:
    dts-util install [-m MODEL_PATH] [gRPCServerCLI options]
    dts-util uninstall
    dts-util restart [--model-browser]
    dts-util test [--port PORT]
    dts-util generate --prompt PROMPT --configuration CONFIG [...]
    dts-util reflect [--host HOST] [--port PORT] [--json] [TLS options]
    dts-util configs <path|list> [...]
    dts-util models <build|search|show|report> [...]

The installer will:
1. Download the gRPCServerCLI binary
2. Install it to {self.PREFERRED_BIN_DIR} (or {self.LOCAL_BIN_DIR} if {self.PREFERRED_BIN_DIR} is not writable)
3. Create and start a LaunchAgent service

Commands:
    install               Install the gRPCServerCLI
    uninstall            Uninstall gRPCServerCLI and remove all related files
    restart             Restart the gRPCServerCLI service
    test                Test if the server is running and responding
    generate            Generate an image through the Draw Things gRPC API
    reflect             List gRPC reflection services and methods
    configs             Show and list saved JSON generation configurations
    models              Build and inspect a local Draw Things model index

Installer Options:
    -m, --model-path     Custom path to store models (default: Draw Things app models directory)
    -h, --help          Show this help message
    -q, --quiet        Minimize output and assume default answers to prompts

gRPCServerCLI Options:
    -n, --name             Server name in local network (default: machine name)
    -p, --port             Server port (default: {self.DEFAULT_PORT})
    -a, --address          Network address (default: {self.DEFAULT_HOST})
    -g, --gpu              GPU device index (default: {self.DEFAULT_GPU})
    -d, --datadog-api-key  Monitoring API key
    -s, --shared-secret    Authentication key
    --no-tls               Disable encryption (not recommended)
    --no-response-compression  Disable compression
    --model-browser        Enable model browser
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
    # Install using default settings
    dts-util install

    # Install with custom model path
    dts-util install -m /path/to/models

    # Install with custom port and server name
    dts-util install -p 7860 -n "MyServer"

    # Install with security options (recommended for public networks)
    dts-util install -s "mysecret"

    # Install with model browser enabled
    dts-util install --model-browser

    # Install with proxy configuration
    dts-util install --join '{{"host":"proxy.local", "port":7859}}'

    # Restart the service
    dts-util restart

    # Enable model browser for an existing service and restart
    dts-util restart --model-browser

    # Test server connection
    dts-util test

    # Test server connection on specific port
    dts-util test --port 7859

    # Generate an image using a saved JSON config
    dts-util generate --prompt "a small robot painting clouds" --configuration portrait --trust-server-cert

    # List services exposed through gRPC reflection
    dts-util reflect --trust-server-cert

    # Show where named JSON generation configs are stored
    dts-util configs path

    # Quiet install with defaults
    dts-util install -q
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
        parser = argparse.ArgumentParser(
            description='Install Draw Things gRPCServerCLI',
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog=self.usage_text)

        # Add actions as positional arguments
        parser.add_argument('action', nargs='?', choices=['install', 'uninstall', 'restart', 'test'],
                          help='Action to perform (install: install server, uninstall: remove server, restart: restart server, test: check if server is running)')

        # Installer arguments
        parser.add_argument('-m', '--model-path',
                          default=os.environ.get('DRAW_THINGS_MODEL_PATH', None),
                          help='Model directory path')
        parser.add_argument('-q', '--quiet', action='store_true',
                          help='Minimize output and assume default answers to prompts')

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
        parser.add_argument('--model-browser', action='store_true',
                          help='Enable model browsing')
        parser.add_argument('--no-flash-attention', action='store_true',
                          help='Disable Flash Attention')
        parser.add_argument('--debug', action='store_true',
                          help='Enable verbose model inference logging')
        parser.add_argument('--join',
                          help='JSON configuration for proxy setup')

        args = parser.parse_args()

        # Handle restart action
        if args.action == 'restart':
            self.restart_service(enable_model_browser=args.model_browser)
            sys.exit(0)

        # Handle uninstall action
        if args.action == 'uninstall':
            self.uninstall()
            sys.exit(0)

        # Handle test action (moved from run method to here for consistency)
        if args.action == 'test':
            if is_server_running(port=args.port):
                print("Server is running and responding!")
                sys.exit(0)
            else:
                print("Could not connect to server")
                sys.exit(1)

        self.quiet = args.quiet
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
            'model_browser': args.model_browser,
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

    def download_grpcserver(self):
        """Download and install the gRPCServerCLI binary"""
        print("Downloading gRPCServerCLI...")
        with tempfile.TemporaryDirectory() as tmp_dir:
            binary_path = Path(tmp_dir) / self.BINARY_NAME
            url = self.get_latest_release_url()

            try:
                urllib.request.urlretrieve(url, binary_path)
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
                        subprocess.run(['launchctl', 'unload', service_path], check=False)
                        subprocess.run(['launchctl', 'remove', self.SERVICE_NAME], check=False)
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
            response = input("Would you like to update it? (y/N): ")
            if response.lower() != 'y':
                print("Service installation cancelled.")
                return

            # Stop existing service
            print("Stopping existing service...")
            try:
                subprocess.run(['launchctl', 'unload', service_path], check=False)
                subprocess.run(['launchctl', 'remove', self.SERVICE_NAME], check=False)
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

            subprocess.run(['launchctl', 'load', service_path], check=True)
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
                'model_browser': False,
                'no_flash_attention': False,
                'debug': False,
                'join': None
            }
            for key, value in self.server_args.items():
                if value != defaults[key]:
                    print(f"  {key}: {value}")
        except (OSError, subprocess.CalledProcessError) as e:
            print(f"Failed to create or load service: {e}")
            sys.exit(1)

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

        existing_services = []
        for pattern in service_patterns:
            existing_services.extend(list(self.AGENTS_DIR.glob(pattern)))

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
            print("Model browser is already enabled")
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

    def restart_service(self, enable_model_browser=False):
        """Restart the gRPCServerCLI service"""
        print("Restarting gRPCServerCLI service...")
        service_path = self.AGENTS_DIR / f'{self.SERVICE_NAME}.plist'
        if not service_path.exists():
            print("Error: Service not installed")
            sys.exit(1)

        if enable_model_browser:
            self.enable_model_browser_for_service(service_path)

        try:
            subprocess.run(['launchctl', 'unload', service_path], check=True)
            time.sleep(1)  # Give the service time to stop
            subprocess.run(['launchctl', 'load', service_path], check=True)
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

    def run(self):
        args = self.parse_args()

        # If no arguments provided, show usage
        if len(sys.argv) == 1:
            print(self.usage_text)
            sys.exit(0)

        # At this point, only the 'install' action should reach here
        # All other actions (uninstall, restart, test) are handled in parse_args()
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
                    print("You can manage it with these commands:")
                    print(f"    launchctl unload ~/Library/LaunchAgents/{self.SERVICE_NAME}.plist")
                    print(f"    launchctl load ~/Library/LaunchAgents/{self.SERVICE_NAME}.plist")
                else:
                    print("\nWARNING: Installation completed but server may not be running correctly.")
                    print("Try these troubleshooting steps:")
                    print("1. Check the system log for errors:")
                    print("    log show --predicate 'process == \"gRPCServerCLI\"' --last 5m")
                    print("2. Restart the service:")
                    print(f"    launchctl unload ~/Library/LaunchAgents/{self.SERVICE_NAME}.plist")
                    print(f"    launchctl load ~/Library/LaunchAgents/{self.SERVICE_NAME}.plist")
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
                subprocess.run(['launchctl', 'unload', service_path], check=False)
                subprocess.run(['launchctl', 'remove', self.SERVICE_NAME], check=False)
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

def main():
    """Main entry point for the CLI."""
    if len(sys.argv) > 1 and sys.argv[1] == "generate":
        sys.exit(generate_main(sys.argv[2:]))
    if len(sys.argv) > 1 and sys.argv[1] == "configs":
        sys.exit(configs_main(sys.argv[2:]))
    if len(sys.argv) > 1 and sys.argv[1] == "reflect":
        sys.exit(reflect_main(sys.argv[2:]))
    if len(sys.argv) > 1 and sys.argv[1] == "models":
        sys.exit(models_main(sys.argv[2:]))
    installer = DTSServerInstaller()
    installer.run()

if __name__ == "__main__":
    main()
