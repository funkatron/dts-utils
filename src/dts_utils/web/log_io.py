"""Web UI log file path, uvicorn file logging, and ``web tail`` follower."""

from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

from uvicorn.config import LOG_LEVELS

from dts_utils.cli_prog import cli_command_name
from dts_utils.configs import user_config_dir

WEB_LOG_ENV = "DTS_WEB_LOG_FILE"
WEB_LOG_FILENAME = "web.log"


def default_web_log_path() -> Path:
    """Default append-only log for ``dts-utils web`` (under :func:`user_config_dir`)."""
    override = os.environ.get(WEB_LOG_ENV, "").strip()
    if override:
        return Path(override).expanduser()
    return user_config_dir() / WEB_LOG_FILENAME


def web_log_info() -> dict[str, str]:
    """Paths and CLI hints for the web log file (health JSON, UI)."""
    path = default_web_log_path().resolve()
    prog = cli_command_name()
    return {
        "log_file": str(path),
        "tail_cli": f"uv run {prog} web tail",
    }


def resolve_web_log_path(cli_path: Path | None) -> Path | None:
    """Return the log file path, or ``None`` when file logging is disabled."""
    if cli_path is not None:
        return cli_path.expanduser()
    return default_web_log_path()


def build_uvicorn_log_config(*, log_level: str, log_path: Path, access_log: bool) -> dict[str, Any]:
    """Uvicorn logging dict with stderr and an append-only file handler."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    level = LOG_LEVELS.get(log_level, logging.INFO)
    access_handlers: list[str] = ["access", "file"] if access_log else []
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "()": "uvicorn.logging.DefaultFormatter",
                "fmt": "%(levelprefix)s %(message)s",
                "use_colors": None,
            },
            "access": {
                "()": "uvicorn.logging.AccessFormatter",
                "fmt": '%(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s',
            },
            "file": {
                "format": "%(asctime)s %(levelname)s [%(name)s] %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "default": {
                "formatter": "default",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stderr",
            },
            "access": {
                "formatter": "access",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
            },
            "file": {
                "formatter": "file",
                "class": "logging.FileHandler",
                "filename": str(log_path),
                "encoding": "utf-8",
                "mode": "a",
            },
        },
        "loggers": {
            "uvicorn": {"handlers": ["default", "file"], "level": level, "propagate": False},
            "uvicorn.error": {"handlers": ["default", "file"], "level": level, "propagate": False},
            "uvicorn.access": {
                "handlers": access_handlers,
                "level": level,
                "propagate": False,
            },
        },
    }


def _read_last_lines(path: Path, count: int) -> list[str]:
    if count <= 0:
        return []
    with path.open("rb") as handle:
        handle.seek(0, os.SEEK_END)
        end = handle.tell()
        if end == 0:
            return []
        block = 8192
        data = b""
        pos = end
        newlines = 0
        while pos > 0 and newlines <= count:
            read_size = min(block, pos)
            pos -= read_size
            handle.seek(pos)
            data = handle.read(read_size) + data
            newlines = data.count(b"\n")
        text = data.decode("utf-8", errors="replace")
        lines = text.splitlines()
        return lines[-count:] if len(lines) > count else lines


def tail_web_log_file(*, log_path: Path, lines: int, follow: bool) -> int:
    """Print recent lines from the web log file; optionally follow new output."""
    prog = cli_command_name()
    if not log_path.is_file():
        print(f"{prog} web tail: no log file at {log_path}", file=sys.stderr)
        print(f"Start the UI first (it writes logs by default): uv run {prog} web", file=sys.stderr)
        return 1

    print(f"Log file: {log_path.resolve()}", file=sys.stderr, flush=True)

    for line in _read_last_lines(log_path, lines):
        print(line)

    if not follow:
        return 0

    print(f"--- following {log_path} (Ctrl+C to stop) ---", file=sys.stderr, flush=True)
    try:
        with log_path.open("r", encoding="utf-8", errors="replace") as handle:
            handle.seek(0, os.SEEK_END)
            while True:
                chunk = handle.readline()
                if chunk:
                    sys.stdout.write(chunk if chunk.endswith("\n") else chunk + "\n")
                    sys.stdout.flush()
                else:
                    time.sleep(0.25)
    except KeyboardInterrupt:
        print("\nStopped.", file=sys.stderr)
        return 0
