"""Resolved CLI program name (matches ``sys.argv[0]`` basename when sensible)."""

from __future__ import annotations

import sys
from pathlib import Path


def cli_command_name(argv: list[str] | None = None) -> str:
    """Basename of the invoked executable (e.g. ``dts-utils`` or ``dts-util``)."""
    a = argv if argv is not None else sys.argv
    if not a or not a[0]:
        return "dts-utils"
    name = Path(a[0]).name
    return name if name else "dts-utils"
