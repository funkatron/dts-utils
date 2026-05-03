"""Tests for saved configuration helpers and CLI dispatch."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from dts_util import configs
from dts_util import cli_router


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
    with patch.object(cli_router, "configs_main", return_value=0) as configs_main:
        with pytest.raises(SystemExit) as exc_info:
            cli_router.main()

    configs_main.assert_called_once_with(["path"])
    assert exc_info.value.code == 0


def test_ensure_default_generation_json_creates_file_and_sets_env(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv(configs.DEFAULT_CONFIGURATION_ENV, raising=False)
    monkeypatch.delenv(configs.DEFAULT_MODEL_ENV, raising=False)
    monkeypatch.setattr(configs, "configurations_dir", lambda: tmp_path)
    monkeypatch.setattr(configs, "guess_default_model_basename", lambda: "")
    path = configs.ensure_default_generation_json_config()
    assert path == tmp_path / f"{configs.DEFAULT_PROFILE_NAME}.json"
    assert path.is_file()
    assert os.environ[configs.DEFAULT_CONFIGURATION_ENV] == configs.DEFAULT_PROFILE_NAME
    assert "created default.json" in capsys.readouterr().err


def test_ensure_default_generation_json_idempotent(monkeypatch, tmp_path):
    monkeypatch.delenv(configs.DEFAULT_CONFIGURATION_ENV, raising=False)
    monkeypatch.setattr(configs, "configurations_dir", lambda: tmp_path)
    monkeypatch.setattr(configs, "guess_default_model_basename", lambda: "x.ckpt")
    configs.ensure_default_generation_json_config()
    first = (tmp_path / f"{configs.DEFAULT_PROFILE_NAME}.json").read_text()
    configs.ensure_default_generation_json_config()
    second = (tmp_path / f"{configs.DEFAULT_PROFILE_NAME}.json").read_text()
    assert first == second
    assert '"model": "x.ckpt"' in first


def test_ensure_default_does_not_override_existing_configuration_env(monkeypatch, tmp_path):
    monkeypatch.setenv(configs.DEFAULT_CONFIGURATION_ENV, "custom")
    monkeypatch.setattr(configs, "configurations_dir", lambda: tmp_path)
    monkeypatch.setattr(configs, "guess_default_model_basename", lambda: "")
    configs.ensure_default_generation_json_config()
    assert os.environ[configs.DEFAULT_CONFIGURATION_ENV] == "custom"


def test_guess_default_model_prefers_dts_util_env(monkeypatch):
    monkeypatch.setenv(configs.DEFAULT_MODEL_ENV, "my.ckpt")
    assert configs.guess_default_model_basename() == "my.ckpt"


def test_guess_default_model_first_ckpt_in_draw_things_models_dir(monkeypatch, tmp_path):
    monkeypatch.delenv(configs.DEFAULT_MODEL_ENV, raising=False)
    monkeypatch.delenv("DRAW_THINGS_MODEL_PATH", raising=False)
    models = tmp_path / "models"
    models.mkdir()
    (models / "b.ckpt").write_bytes(b"")
    (models / "a.ckpt").write_bytes(b"")
    monkeypatch.setattr("dts_util.model_index.local.default_models_dir", lambda: models)
    assert configs.guess_default_model_basename() == "a.ckpt"
