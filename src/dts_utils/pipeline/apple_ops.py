"""Apple-specific operational helpers for local media pipelines."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class AppleRuntimeChecks:
    ffmpeg_path: str | None
    run_root_writable: bool
    gatekeeper_note: str


def is_run_root_writable(run_root: Path) -> bool:
    try:
        run_root.mkdir(parents=True, exist_ok=True)
        probe = run_root / ".write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def collect_apple_runtime_checks(run_root: Path) -> AppleRuntimeChecks:
    ffmpeg_path = shutil.which("ffmpeg")
    return AppleRuntimeChecks(
        ffmpeg_path=ffmpeg_path,
        run_root_writable=is_run_root_writable(run_root),
        gatekeeper_note=(
            "If executables are quarantined on macOS, clear com.apple.quarantine "
            "or sign/notarize distributed binaries."
        ),
    )
