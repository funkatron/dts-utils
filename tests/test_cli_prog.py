"""Tests for ``dts_utils.cli_prog``."""

from __future__ import annotations

from dts_utils.cli_prog import cli_command_name


def test_cli_command_name_uses_argv0_basename():
    assert cli_command_name(["/x/y/dts-utils", "server"]) == "dts-utils"
    assert cli_command_name(["bin/my-cli", "install"]) == "my-cli"


def test_cli_command_name_fallback():
    assert cli_command_name([]) == "dts-utils"
    assert cli_command_name([""]) == "dts-utils"
