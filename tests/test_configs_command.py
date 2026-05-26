"""Tests for saved configuration helpers and CLI dispatch."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from dts_utils import configs
from dts_utils import cli_router


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


def test_resolve_configuration_value_finds_dotted_stem_json_config(tmp_path):
    """Stems with dotted versions must resolve (pathlib ``suffix`` is not ``.json``)."""
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    saved_path = config_dir / "dreamshaper-v6.31.json"
    saved_path.write_text("{}", encoding="utf-8")

    assert configs.resolve_configuration_value("dreamshaper-v6.31", config_dir=config_dir) == saved_path


def test_resolve_configuration_value_rejects_missing_raw_path(tmp_path):
    """Verify missing non-JSON paths are treated as missing raw config files."""
    with pytest.raises(ValueError, match="Configuration file not found"):
        configs.resolve_configuration_value("missing.fb", config_dir=tmp_path)


def test_configs_path_creates_and_prints_directory(monkeypatch, tmp_path, capsys):
    """Verify dts-utils configs path creates the idiomatic directory."""
    config_root = tmp_path / "dts-utils" / "configurations"
    monkeypatch.setattr(configs, "configurations_dir", lambda: config_root)

    result = configs.main(["path"])

    captured = capsys.readouterr()
    assert result == 0
    assert captured.out.strip() == str(config_root)
    assert config_root.is_dir()


def test_configs_list_prints_saved_names(tmp_path, capsys):
    """Verify dts-utils configs list prints JSON config names."""
    (tmp_path / "portrait.json").write_text("{}", encoding="utf-8")
    (tmp_path / "raw.fb").write_bytes(b"flatbuffer")

    result = configs.main(["list", "--directory", str(tmp_path)])

    captured = capsys.readouterr()
    assert result == 0
    assert captured.out.splitlines() == ["portrait"]


def test_dts_util_main_dispatches_configs(monkeypatch):
    """Verify dts-utils configs is routed before installer argument parsing."""
    monkeypatch.setattr("sys.argv", ["dts-utils", "configs", "path"])
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


def test_ensure_default_generation_json_renames_legacy_zit_json(monkeypatch, tmp_path):
    monkeypatch.delenv(configs.DEFAULT_CONFIGURATION_ENV, raising=False)
    monkeypatch.setattr(configs, "configurations_dir", lambda: tmp_path)
    (tmp_path / "zit.json").write_text('{"migrated": true}', encoding="utf-8")
    path = configs.ensure_default_generation_json_config()
    assert path == tmp_path / "default.json"
    assert path.read_text().strip() == '{"migrated": true}'
    assert not (tmp_path / "zit.json").exists()


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
    monkeypatch.setattr("dts_utils.model_index.local.default_models_dir", lambda: models)
    assert configs.guess_default_model_basename() == "a.ckpt"


def test_user_config_dir_unix_defaults_to_dot_config(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    assert configs.user_config_dir() == tmp_path / ".config" / "dts-utils"


def test_list_configuration_names_merges_legacy_application_support(monkeypatch, tmp_path):
    """Profiles left under pre-XDG macOS paths still appear in default listings."""
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    primary = tmp_path / ".config" / "dts-utils" / "configurations"
    legacy = tmp_path / "Library" / "Application Support" / "dts-utils" / "configurations"
    primary.mkdir(parents=True)
    legacy.mkdir(parents=True)
    (primary / "default.json").write_text("{}", encoding="utf-8")
    (legacy / "legacyonly.json").write_text("{}", encoding="utf-8")

    assert configs.list_configuration_names() == ["default", "legacyonly"]


def test_resolve_configuration_value_finds_file_in_legacy_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    primary = tmp_path / ".config" / "dts-utils" / "configurations"
    legacy = tmp_path / "Library" / "Application Support" / "dts-utils" / "configurations"
    primary.mkdir(parents=True)
    legacy.mkdir(parents=True)
    (legacy / "portrait.json").write_text("{}", encoding="utf-8")

    assert configs.resolve_configuration_value("portrait") == legacy / "portrait.json"


def test_resolve_configuration_value_prefers_primary_over_legacy(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    primary = tmp_path / ".config" / "dts-utils" / "configurations"
    legacy = tmp_path / "Library" / "Application Support" / "dts-utils" / "configurations"
    primary.mkdir(parents=True)
    legacy.mkdir(parents=True)
    (primary / "dup.json").write_text('{"a": 1}', encoding="utf-8")
    (legacy / "dup.json").write_text('{"b": 2}', encoding="utf-8")

    assert configs.resolve_configuration_value("dup").read_text().strip().startswith('{"a"')


def test_list_configuration_names_explicit_directory_skips_legacy(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    legacy = tmp_path / "Library" / "Application Support" / "dts-utils" / "configurations"
    legacy.mkdir(parents=True)
    (legacy / "ghost.json").write_text("{}", encoding="utf-8")

    only = tmp_path / "solo"
    only.mkdir()
    (only / "here.json").write_text("{}", encoding="utf-8")

    assert configs.list_configuration_names(config_dir=only) == ["here"]


def test_user_config_dir_unix_respects_xdg_config_home(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("HOME", str(tmp_path))
    xdg = tmp_path / "xdg"
    xdg.mkdir()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
    assert configs.user_config_dir() == xdg / "dts-utils"


def test_scaffold_generation_json_from_community_metadata_local() -> None:
    payload = {
        "name": "Example",
        "file": "flux_2_klein_base_9b_q8p.ckpt",
        "note": (
            "Trained at 1024×1024 resolution using Flow Matching. "
            "Best with 30–50 sampling steps."
        ),
    }
    body = configs.scaffold_generation_json_from_community_metadata(payload)
    assert body["model"] == "flux_2_klein_base_9b_q8p.ckpt"
    assert body["width"] == 1024
    assert body["height"] == 1024
    assert body["steps"] == 40


def test_scaffold_generation_json_rejects_remote_api() -> None:
    payload = {"file": "x.ckpt", "remote_api_model_config": {"url": "https://example.com"}}
    with pytest.raises(ValueError, match="cloud/API"):
        configs.scaffold_generation_json_from_community_metadata(payload)


def test_configs_scaffold_from_metadata_cli_writes_file(tmp_path, monkeypatch):
    monkeypatch.delenv(configs.DEFAULT_MODEL_ENV, raising=False)
    monkeypatch.delenv("DRAW_THINGS_MODEL_PATH", raising=False)
    monkeypatch.setattr("dts_utils.model_index.local.default_models_dir", lambda: tmp_path / "nowhere")

    meta = tmp_path / "flux-2-klein-base-9b" / "metadata.json"
    meta.parent.mkdir(parents=True)
    meta.write_text(
        json.dumps(
            {
                "name": "FLUX.2 [klein] 9B Base",
                "file": "flux_2_klein_base_9b_q8p.ckpt",
                "note": "Trained at 768×768 resolution. Use 12 sampling steps.",
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "configs-out"
    rc = configs.main(
        [
            "scaffold-from-metadata",
            str(meta),
            "--directory",
            str(out),
        ]
    )
    assert rc == 0
    written = out / "flux-2-klein-base-9b.json"
    assert written.is_file()
    data = json.loads(written.read_text(encoding="utf-8"))
    assert data["model"] == "flux_2_klein_base_9b_q8p.ckpt"
    assert data["width"] == 768
    assert data["height"] == 768
    assert data["steps"] == 12


def test_configs_scaffold_limit_without_scan_errors(tmp_path: Path) -> None:
    m = tmp_path / "m.json"
    m.write_text(json.dumps({"file": "x.ckpt"}), encoding="utf-8")
    rc = configs.main(["scaffold-from-metadata", str(m), "--limit", "5"])
    assert rc == 2


def test_iter_scannable_skips_apis(tmp_path: Path) -> None:
    root = tmp_path / "community"
    m1 = root / "models" / "m1" / "metadata.json"
    m1.parent.mkdir(parents=True)
    m1.write_text(json.dumps({"file": "a.ckpt"}), encoding="utf-8")
    ax = root / "apis" / "x" / "metadata.json"
    ax.parent.mkdir(parents=True)
    ax.write_text(json.dumps({"file": "b.ckpt"}), encoding="utf-8")
    paths = configs.iter_scannable_community_metadata_files(root)
    assert len(paths) == 1


def test_configs_scaffold_scan_writes_multiple(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(configs.DEFAULT_MODEL_ENV, raising=False)
    monkeypatch.delenv("DRAW_THINGS_MODEL_PATH", raising=False)
    monkeypatch.setattr("dts_utils.model_index.local.default_models_dir", lambda: tmp_path / "nowhere")

    root = tmp_path / "cm" / "models"
    for slug, payload in (
        ("alpha", {"file": "alpha.ckpt"}),
        ("beta", {"file": "beta.ckpt"}),
        ("gamma", {"remote_api_model_config": {}}),
    ):
        p = root / slug / "metadata.json"
        p.parent.mkdir(parents=True)
        p.write_text(json.dumps(payload), encoding="utf-8")
    out = tmp_path / "out"
    rc = configs.main(["scaffold-from-metadata", "--scan", str(tmp_path / "cm"), "--directory", str(out)])
    assert rc == 0
    assert (out / "alpha.json").is_file()
    assert (out / "beta.json").is_file()
    assert not (out / "gamma.json").exists()


def test_configs_scaffold_scan_limit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(configs.DEFAULT_MODEL_ENV, raising=False)
    monkeypatch.delenv("DRAW_THINGS_MODEL_PATH", raising=False)
    monkeypatch.setattr("dts_utils.model_index.local.default_models_dir", lambda: tmp_path / "nowhere")

    root = tmp_path / "cm"
    for name in ("a", "b", "c"):
        p = root / "models" / name / "metadata.json"
        p.parent.mkdir(parents=True)
        p.write_text(
            json.dumps({"file": f"{name}.ckpt"}),
            encoding="utf-8",
        )
    out = tmp_path / "out"
    rc = configs.main(
        ["scaffold-from-metadata", "--scan", str(root), "--directory", str(out), "--limit", "2"],
    )
    assert rc == 0
    assert len(list(out.glob("*.json"))) == 2


def test_configs_scaffold_rejects_scan_and_metadata_together(tmp_path: Path) -> None:
    m = tmp_path / "m.json"
    m.write_text("{}", encoding="utf-8")
    rc = configs.main(
        ["scaffold-from-metadata", str(m), "--scan", str(tmp_path)],
    )
    assert rc == 2


def test_configs_import_draw_things_writes_profiles(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    src = tmp_path / "custom_configs.json"
    src.write_text(
        json.dumps(
            [
                {"name": "Alpha", "configuration": {"model": "a.ckpt", "width": 64}},
                {"name": "Same", "configuration": {"model": "b.ckpt"}},
                {"name": "Same", "configuration": {"model": "c.ckpt"}},
            ]
        ),
        encoding="utf-8",
    )
    out = tmp_path / "cfgs"
    rc = configs.main(["import-draw-things", "--source", str(src), "--directory", str(out)])
    captured = capsys.readouterr()
    assert rc == 0
    assert "Imported presets may not work immediately" in captured.err
    assert json.loads((out / "Alpha.json").read_text())["model"] == "a.ckpt"
    assert (out / "Same.json").is_file()
    assert (out / "Same-2.json").is_file()


def test_configs_import_draw_things_missing_file_returns_2(tmp_path: Path) -> None:
    rc = configs.main(
        ["import-draw-things", "--source", str(tmp_path / "missing.json"), "--directory", str(tmp_path / "out")],
    )
    assert rc == 2


def test_configs_import_draw_things_mirror_goes_to_subdir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    doc = tmp_path / "Documents"
    models = doc / "Models"
    models.mkdir(parents=True)
    src = models / "custom_configs.json"
    src.write_text(
        json.dumps([{"name": "Alpha", "configuration": {"model": "a.ckpt"}}]),
        encoding="utf-8",
    )
    (models / "custom_lora.json").write_text("[]", encoding="utf-8")
    monkeypatch.setattr(configs, "draw_things_container_documents", lambda: doc)
    out = tmp_path / "cfgs"
    rc = configs.main(
        ["import-draw-things", "--source", str(src), "--directory", str(out), "--mirror-app-json"],
    )
    assert rc == 0
    assert (out / "Alpha.json").is_file()
    assert (out / configs.DRAW_THINGS_APP_MIRROR_SUBDIR / "custom_lora.json").is_file()


def test_scaffold_pipeline_list() -> None:
    rc = configs.main(["scaffold-pipeline", "--list"])
    assert rc == 0


def test_scaffold_pipeline_writes_infomux(tmp_path: Path, capsys) -> None:
    rc = configs.main(["scaffold-pipeline", "infomux", "--directory", str(tmp_path)])
    assert rc == 0
    dest = tmp_path / "infomux.json"
    assert dest.is_file()
    payload = json.loads(dest.read_text(encoding="utf-8"))
    assert "_dts_utils_pipeline" in payload
    assert payload["_dts_utils_pipeline"]["t2i_configuration"] == "default"
    out = capsys.readouterr()
    assert str(dest) in out.out
    assert "pipeline run" in out.err


def test_scaffold_pipeline_refuses_overwrite(tmp_path: Path) -> None:
    dest = tmp_path / "infomux.json"
    dest.write_text("{}", encoding="utf-8")
    rc = configs.main(["scaffold-pipeline", "infomux", "--directory", str(tmp_path)])
    assert rc == 2
