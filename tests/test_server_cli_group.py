"""Tests for ``dts-utils server …`` stripping and rejecting bare lifecycle verbs."""

from __future__ import annotations

from dts_utils.cli_router import server_subcommand_help_text, prepare_argv_for_installer_dispatch


def test_prepare_server_help_only():
    argv = ["dts-utils", "server"]
    assert prepare_argv_for_installer_dispatch(argv) == 0
    assert argv == ["dts-utils", "server"]


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
