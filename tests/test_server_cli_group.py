"""Tests for ``dts-util server …`` stripping and rejecting bare lifecycle verbs."""

from __future__ import annotations

from dts_util.installer.server_installer import SERVER_SUBCOMMAND_HELP, prepare_argv_for_installer_dispatch


def test_prepare_server_help_only():
    argv = ["dts-util", "server"]
    assert prepare_argv_for_installer_dispatch(argv) == 0
    assert argv == ["dts-util", "server"]


def test_prepare_server_install_rewrites_argv():
    argv = ["dts-util", "server", "install", "-q"]
    assert prepare_argv_for_installer_dispatch(argv) is None
    assert argv == ["dts-util", "install", "-q"]


def test_prepare_server_check_rewrites_to_inner_argv():
    argv = ["dts-util", "server", "check", "--port", "7860"]
    assert prepare_argv_for_installer_dispatch(argv) is None
    assert argv == ["dts-util", "check", "--port", "7860"]


def test_prepare_rejects_plain_install_without_server_prefix():
    argv = ["dts-util", "install"]
    assert prepare_argv_for_installer_dispatch(argv) == 2


def test_prepare_rejects_unknown_server_subcommand():
    argv = ["dts-util", "server", "nope"]
    assert prepare_argv_for_installer_dispatch(argv) == 2


def test_server_help_text_documents_prefix():
    assert "server install" in SERVER_SUBCOMMAND_HELP
    assert "check" in SERVER_SUBCOMMAND_HELP
