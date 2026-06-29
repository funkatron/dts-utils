"""Shared execute lock and cooperative cancel for web UI and MCP."""

from __future__ import annotations

import threading

execute_lock = threading.Lock()
generation_cancel_event = threading.Event()


def request_generation_cancel() -> dict[str, bool]:
    """Signal cancel for in-flight generate / pipeline work (between batch iterations)."""
    generation_cancel_event.set()
    return {"ok": True, "cancel_requested": True}


def clear_generation_cancel() -> None:
    generation_cancel_event.clear()
