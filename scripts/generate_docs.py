#!/usr/bin/env python3
"""Regenerate machine-derived docs under docs/generated/."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dts_utils.doc_inventory import GENERATED_MCP_TOOLS, write_mcp_tools_doc_sync


def main() -> int:
    path = write_mcp_tools_doc_sync()
    print(f"Wrote {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
