"""Tests for saved configuration helpers and CLI dispatch."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from dts_util import configs
from dts_util.installer import server_installer


def test_resolve_configuration_value_prefers_existing_file(tmp_path):
    """Verify explicit paths are used before named config lookup."""
    config_path = tmp_path / "custom.fb"
    config_path.write_bytes(b"flatbuffer")

    assert configs.resolve_configuration_value(config_path) == config_path


def test_resolve_configuration_value_finds_named_json_config(tmp_path):
    """Verify simple names resolve to NAME.json in the saved config directory."""
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    saved_path = config_dir / "portrait.json"
    saved_path.write_text("{}", encoding="utf-8")

    assert configs.resolve_configuration_value("portrait", config_dir=config_dir) == saved_path
    assert configs.resolve_configuration_value("portrait.json", config_dir=config_dir) == saved_path


def test_resolve_configuration_value_rejects_missing_raw_path(tmp_path):
    """Verify missing non-JSON paths are treated as missing raw config files."""
    with pytest.raises(ValueError, match="Configuration file not found"):
        configs.resolve_configuration_value("missing.fb", config_dir=tmp_path)


def test_configs_path_creates_and_prints_directory(monkeypatch, tmp_path, capsys):
    """Verify dts-util configs path creates the idiomatic directory."""
    config_root = tmp_path / "dts-util" / "configurations"
    monkeypatch.setattr(configs, "configurations_dir", lambda: config_root)

    result = configs.main(["path"])

    captured = capsys.readouterr()
    assert result == 0
    assert captured.out.strip() == str(config_root)
    assert config_root.is_dir()


def test_configs_list_prints_saved_names(tmp_path, capsys):
    """Verify dts-util configs list prints JSON config names."""
    (tmp_path / "portrait.json").write_text("{}", encoding="utf-8")
    (tmp_path / "raw.fb").write_bytes(b"flatbuffer")

    result = configs.main(["list", "--directory", str(tmp_path)])

    captured = capsys.readouterr()
    assert result == 0
    assert captured.out.splitlines() == ["portrait"]


def test_dts_util_main_dispatches_configs(monkeypatch):
    """Verify dts-util configs is routed before installer argument parsing."""
    monkeypatch.setattr("sys.argv", ["dts-util", "configs", "path"])
    with patch.object(server_installer, "configs_main", return_value=0) as configs_main:
        with pytest.raises(SystemExit) as exc_info:
            server_installer.main()

    configs_main.assert_called_once_with(["path"])
    assert exc_info.value.code == 0
