"""Tests for ``dts-utils server …`` stripping and rejecting bare lifecycle verbs."""

from __future__ import annotations

import pytest

from dts_utils import cli_router
from dts_utils.cli_router import (
    prepare_argv_for_installer_dispatch,
    server_subcommand_help_text,
    should_show_top_level_help,
    top_level_help_text,
)


def test_prepare_server_help_only():
    argv = ["dts-utils", "server"]
    assert prepare_argv_for_installer_dispatch(argv) == 0
    assert argv == ["dts-utils", "server"]


def test_prepare_server_help_flag(capsys):
    argv = ["dts-utils", "server", "--help"]
    assert prepare_argv_for_installer_dispatch(argv) == 0
    assert argv == ["dts-utils", "server", "--help"]
    out = capsys.readouterr().out
    assert "Draw Things gRPC server" in out
    assert "server install" in out


def test_top_level_help_documents_command_tree(monkeypatch):
    monkeypatch.setattr("sys.argv", ["dts-utils"])
    text = top_level_help_text()
    assert 'dts-utils "PROMPT" [PROFILE]' in text
    assert "dts-utils generate --prompt PROMPT" in text
    assert "dts-utils server <install|start|stop|restart|check|status|list-models|tail>" in text
    assert "dts-utils web <install|start|stop|restart|status|uninstall|tail>" in text
    assert "dts-utils configs" in text
    assert "dts-utils models" in text


def test_top_level_help_triggered_by_no_args_and_help_flags():
    assert should_show_top_level_help(["dts-utils"]) is True
    assert should_show_top_level_help(["dts-utils", "--help"]) is True
    assert should_show_top_level_help(["dts-utils", "-h"]) is True
    assert should_show_top_level_help(["dts-utils", "server"]) is False
    assert should_show_top_level_help(["dts-utils", "a prompt"]) is False


def test_main_prints_top_level_help_for_no_args(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["dts-utils"])
    with pytest.raises(SystemExit) as exc_info:
        cli_router.main()
    assert exc_info.value.code == 0
    out = capsys.readouterr().out
    assert "Usage:" in out
    assert "dts-utils web" in out
    assert "dts-utils server --help" in out


def test_prepare_server_install_rewrites_argv():
    argv = ["dts-utils", "server", "install", "-q"]
    assert prepare_argv_for_installer_dispatch(argv) is None
    assert argv == ["dts-utils", "install", "-q"]


def test_prepare_server_check_rewrites_to_inner_argv():
    argv = ["dts-utils", "server", "check", "--port", "7860"]
    assert prepare_argv_for_installer_dispatch(argv) is None
    assert argv == ["dts-utils", "check", "--port", "7860"]


def test_prepare_server_stop_rewrites_argv():
    argv = ["dts-utils", "server", "stop"]
    assert prepare_argv_for_installer_dispatch(argv) is None
    assert argv == ["dts-utils", "stop"]


def test_prepare_server_tail_rewrites_argv():
    argv = ["dts-utils", "server", "tail", "--last", "1h"]
    assert prepare_argv_for_installer_dispatch(argv) is None
    assert argv == ["dts-utils", "tail", "--last", "1h"]


def test_prepare_rejects_plain_install_without_server_prefix():
    argv = ["dts-utils", "install"]
    assert prepare_argv_for_installer_dispatch(argv) == 2


def test_prepare_rejects_unknown_server_subcommand():
    argv = ["dts-utils", "server", "nope"]
    assert prepare_argv_for_installer_dispatch(argv) == 2


def test_prepare_server_status_rewrites_argv():
    argv = ["dts-utils", "server", "status"]
    assert prepare_argv_for_installer_dispatch(argv) is None
    assert argv == ["dts-utils", "status"]


def test_server_help_text_documents_prefix():
    text = server_subcommand_help_text()
    assert "server install" in text
    assert "server start" in text
    assert "server stop" in text
    assert "check" in text
    assert "server tail" in text
    assert "server status" in text
    assert "server list-models" in text
