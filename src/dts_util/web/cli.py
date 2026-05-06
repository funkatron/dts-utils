"""CLI entry for ``dts-utils web`` / ``dts-util web``."""

from __future__ import annotations

import argparse
import os
import sys
import threading
import webbrowser

import uvicorn

from dts_util.cli_prog import cli_command_name
from dts_util.web.app import create_app


def main(argv: list[str] | None = None) -> int:
    prog_root = cli_command_name()
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
    parser.add_argument("--port", type=int, default=8765, metavar="N", help="HTTP port (default: 8765).")
    parser.add_argument(
        "--open",
        action="store_true",
        help="Open the default browser after the server starts.",
    )
    args = parser.parse_args(argv)

    loopback_hosts = {"127.0.0.1", "::1", "localhost"}
    if args.bind not in loopback_hosts and not os.environ.get("DTS_WEB_TOKEN", "").strip():
        print(
            f"{prog_root} web: warning — non-loopback bind without DTS_WEB_TOKEN exposes "
            "mutating APIs. Set DTS_WEB_TOKEN (Authorization: Bearer).",
            file=sys.stderr,
        )

    config = uvicorn.Config(
        create_app,
        host=args.bind,
        port=args.port,
        factory=True,
        log_level="info",
    )
    server = uvicorn.Server(config)

    if args.open:
        open_host = "127.0.0.1" if args.bind in {"0.0.0.0", "::"} else args.bind
        url = f"http://{open_host}:{args.port}/"
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()

    server.run()
    return 0
