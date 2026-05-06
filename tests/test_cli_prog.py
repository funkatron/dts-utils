"""Tests for ``dts_util.cli_prog``."""

from __future__ import annotations

from dts_util.cli_prog import cli_command_name


def test_cli_command_name_uses_argv0_basename():
    assert cli_command_name(["/x/y/dts-utils", "server"]) == "dts-utils"
    assert cli_command_name(["bin/dts-util", "install"]) == "dts-util"


def test_cli_command_name_fallback():
    assert cli_command_name([]) == "dts-utils"
    assert cli_command_name([""]) == "dts-utils"
