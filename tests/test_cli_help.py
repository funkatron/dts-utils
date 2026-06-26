"""Focused tests for CLI help text and usage prefixes."""

from __future__ import annotations

from dts_utils import configs, generate, tls_export
from dts_utils.grpc import reflect


def test_subcommand_parser_usage_prefixes(monkeypatch) -> None:
    monkeypatch.setattr("sys.argv", ["dts-utils"])

    assert generate.build_parser().format_usage().startswith("usage: dts-utils generate ")
    assert configs.build_parser().format_usage().startswith("usage: dts-utils configs ")
    assert reflect.build_parser().format_usage().startswith("usage: dts-utils reflect ")
    assert tls_export.build_parser().format_usage().startswith("usage: dts-utils tls ")
