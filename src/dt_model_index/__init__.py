"""Compatibility shim. Prefer ``from dts_util.model_index import main`` or ``dts_util.model_index``."""

from dts_util.model_index.cli import main

__all__ = ["main"]
