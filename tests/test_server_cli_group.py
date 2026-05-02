"""Tests for ``dts-util server …`` grouping and ``check`` alias."""

from __future__ import annotations

from dts_util.installer.server_installer import SERVER_SUBCOMMAND_HELP, consume_server_cli_prefix


def test_consume_server_prints_help():
    argv = ["dts-util", "server"]
    assert consume_server_cli_prefix(argv) == 0
    assert argv == ["dts-util", "server"]


def test_consume_server_install_rewrites_argv():
    argv = ["dts-util", "server", "install", "-q"]
    assert consume_server_cli_prefix(argv) is None
    assert argv == ["dts-util", "install", "-q"]


def test_consume_server_check_rewrites_to_top_level():
    argv = ["dts-util", "server", "check", "--port", "7860"]
    assert consume_server_cli_prefix(argv) is None
    assert argv == ["dts-util", "check", "--port", "7860"]


def test_server_help_text_documents_prefix():
    assert "server install" in SERVER_SUBCOMMAND_HELP
    assert "check" in SERVER_SUBCOMMAND_HELP
