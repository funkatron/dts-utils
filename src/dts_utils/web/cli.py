"""CLI entry for ``dts-utils web`` and ``dts-utils web tail``."""

from __future__ import annotations

import argparse
import os
import sys
import threading
import webbrowser
from pathlib import Path

import uvicorn
from uvicorn.config import LOG_LEVELS

from dts_utils.cli_prog import cli_command_name
from dts_utils.web.app import create_app
from dts_utils.web.defaults import DEFAULT_WEB_PORT
from dts_utils.web.log_io import (
    build_uvicorn_log_config,
    default_web_log_path,
    resolve_web_log_path,
    tail_web_log_file,
)


HELP_FLAGS = frozenset({"-h", "--help"})


def web_help_text(prog_root: str | None = None) -> str:
    prog = prog_root or cli_command_name()
    return f"""
Usage:
    {prog} web [serve options]
    {prog} web tail [options]
    {prog} web <install|start|stop|restart|status|uninstall> [...]

Run a loopback web UI for Draw Things image generation.

Modes:
    {prog} web                  Run the web UI in the foreground (default: http://127.0.0.1:{DEFAULT_WEB_PORT}/).
    {prog} web --open           Run in the foreground and open a browser.
    {prog} web tail             Follow the web UI log file.
    {prog} web install --yes    Install or update the macOS LaunchAgent.
    {prog} web start            Start the installed LaunchAgent.
    {prog} web stop             Stop the installed LaunchAgent.
    {prog} web restart          Restart the installed LaunchAgent.
    {prog} web status           Show installed LaunchAgent status.
    {prog} web uninstall        Remove the installed LaunchAgent.

Serve options:
    --bind ADDR        Bind address (default: 127.0.0.1). Use DTS_WEB_TOKEN when not loopback-only.
    --port N           HTTP port (default: {DEFAULT_WEB_PORT}).
    --log-level LEVEL  Uvicorn log level.
    --no-access-log    Disable HTTP access logs.
    --log-file PATH    Append uvicorn logs to PATH.
    --no-log-file      Do not append logs to a file.
    --open             Open the default browser after the server starts.

More:
    {prog} web install --help
    {prog} web tail --help
""".strip()


def _serve_parser(prog_root: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=f"{prog_root} web",
        description="Run a loopback web UI for Draw Things image generation.",
    )
    parser.add_argument(
        "--bind",
        default="127.0.0.1",
        metavar="ADDR",
        help="Bind address (default: 127.0.0.1). Use DTS_WEB_TOKEN when not loopback-only.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_WEB_PORT,
        metavar="N",
        help=f"HTTP port (default: {DEFAULT_WEB_PORT}).",
    )
    parser.add_argument(
        "--log-level",
        default="info",
        choices=sorted(LOG_LEVELS.keys()),
        metavar="LEVEL",
        help=f"Uvicorn log level (default: info). Choices: {', '.join(sorted(LOG_LEVELS.keys()))}.",
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
        help="Do not append logs to a file (stderr/stdout only).",
    )
    parser.add_argument(
        "--open",
        action="store_true",
        help="Open the default browser after the server starts.",
    )
    return parser


def _tail_parser(prog_root: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=f"{prog_root} web tail",
        description="Follow the dts-utils web UI log file (written by ``dts-utils web``).",
    )
    parser.add_argument(
        "--file",
        type=Path,
        default=None,
        metavar="PATH",
        help=f"Log file to read (default: {default_web_log_path()}).",
    )
    parser.add_argument(
        "-n",
        "--lines",
        type=int,
        default=50,
        metavar="N",
        help="Number of recent lines to print before following (default: 50).",
    )
    parser.add_argument(
        "--no-follow",
        action="store_true",
        help="Print recent lines only; do not wait for new log output.",
    )
    return parser


def run_web_server(argv: list[str] | None = None) -> int:
    prog_root = cli_command_name()
    args = _serve_parser(prog_root).parse_args(argv)

    loopback_hosts = {"127.0.0.1", "::1", "localhost"}
    if args.bind not in loopback_hosts and not os.environ.get("DTS_WEB_TOKEN", "").strip():
        print(
            f"{prog_root} web: warning — non-loopback bind without DTS_WEB_TOKEN exposes "
            "mutating APIs. Set DTS_WEB_TOKEN (Authorization: Bearer).",
            file=sys.stderr,
        )

    log_path = None if args.no_log_file else resolve_web_log_path(args.log_file)
    log_config = None
    if log_path is not None:
        log_config = build_uvicorn_log_config(
            log_level=args.log_level,
            log_path=log_path,
            access_log=not args.no_access_log,
        )
        resolved = log_path.resolve()
        print(f"{prog_root} web: logging to {resolved}", file=sys.stderr)
        print(str(resolved))

    config = uvicorn.Config(
        create_app,
        host=args.bind,
        port=args.port,
        factory=True,
        log_level=args.log_level,
        access_log=not args.no_access_log,
        log_config=log_config,
    )
    server = uvicorn.Server(config)

    if args.open:
        open_host = "127.0.0.1" if args.bind in {"0.0.0.0", "::"} else args.bind
        url = f"http://{open_host}:{args.port}/"
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()

    server.run()
    return 0


def run_web_tail(argv: list[str] | None = None) -> int:
    prog_root = cli_command_name()
    args = _tail_parser(prog_root).parse_args(argv)
    log_path = resolve_web_log_path(args.file)
    if log_path is None:
        print(f"{prog_root} web tail: no log file path (set --file or unset --no-log-file on web).", file=sys.stderr)
        return 1
    return tail_web_log_file(log_path=log_path, lines=args.lines, follow=not args.no_follow)


def main(argv: list[str] | None = None) -> int:
    """Entry for ``dts-utils web`` — serve UI by default; ``tail`` follows the web log file."""
    from dts_utils.web.launch_agent import WEB_LIFECYCLE_SUBCOMMANDS, run_web_lifecycle

    tokens = list(argv if argv is not None else sys.argv[1:])
    if tokens and tokens[0] in HELP_FLAGS:
        print(web_help_text(cli_command_name()))
        return 0
    if tokens and tokens[0] == "tail":
        return run_web_tail(tokens[1:])
    if tokens and tokens[0] in WEB_LIFECYCLE_SUBCOMMANDS:
        return run_web_lifecycle(tokens[0], tokens[1:])
    return run_web_server(tokens)
