"""Tests for the installed-models programmatic API."""

from __future__ import annotations

import json
from pathlib import Path

from dts_utils.model_index.cli import main as models_main
from dts_utils.model_index.export import write_json
from dts_utils.model_index.parse import build_records
from dts_utils.models_api import (
    InstalledModelsOptions,
    list_installed_model_filenames,
    list_installed_models,
    resolve_draw_things_models_dir,
)


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _sample_repo(tmp_path: Path) -> Path:
    repo_dir = tmp_path / "community-models"
    repo_dir.mkdir()
    _write_text(repo_dir / "uncurated_models.txt", "flux-1-dev")
    _write_text(repo_dir / "uncurated_models_sha256.json", "{}")
    _write_text(
        repo_dir / "models" / "flux-1-dev" / "metadata.json",
        '{"name": "FLUX.1 [dev]", "file": "flux_1_dev_q8p.ckpt", "version": "flux1"}',
    )
    return repo_dir


def test_list_installed_models_without_index(tmp_path: Path) -> None:
    model_dir = tmp_path / "models"
    model_dir.mkdir()
    _write_text(model_dir / "alpha_q8p.ckpt", "alpha")
    _write_text(model_dir / "alpha_q8p.ckpt-tensordata", "tensor")

    result = list_installed_models(
        InstalledModelsOptions(models_dir=model_dir, use_index=False, limit=10)
    )

    assert result.models_dir == model_dir
    assert result.local_file_count == 2
    assert len(result.summaries) == 1
    assert result.summaries[0].base_name == "alpha_q8p.ckpt"
    assert result.summaries[0].matched_record_ids == []


def test_list_installed_models_with_index_match(tmp_path: Path) -> None:
    repo_dir = _sample_repo(tmp_path)
    records = build_records(repo_dir)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    write_json(records, data_dir / "drawthings_uncurated_models.json")

    model_dir = tmp_path / "models"
    model_dir.mkdir()
    _write_text(model_dir / "flux_1_dev_q8p.ckpt", "flux")

    result = list_installed_models(
        InstalledModelsOptions(models_dir=model_dir, data_dir=data_dir, use_index=True)
    )

    assert result.summaries[0].matched_record_ids == ["flux-1-dev"]


def test_list_installed_model_filenames(tmp_path: Path) -> None:
    model_dir = tmp_path / "models"
    model_dir.mkdir()
    _write_text(model_dir / "one.ckpt", "1")
    _write_text(model_dir / "two.ckpt", "2")

    names = list_installed_model_filenames(model_dir)

    assert names == ["one.ckpt", "two.ckpt"]


def test_resolve_draw_things_models_dir_env(tmp_path: Path, monkeypatch) -> None:
    custom = tmp_path / "custom-models"
    custom.mkdir()
    monkeypatch.setenv("DRAW_THINGS_MODEL_PATH", str(custom))
    assert resolve_draw_things_models_dir() == custom


def test_cli_installed_without_build(tmp_path: Path, capsys) -> None:
    model_dir = tmp_path / "models"
    model_dir.mkdir()
    _write_text(model_dir / "solo_q8p.ckpt", "solo")

    exit_code = models_main(["installed", "--model-dir", str(model_dir), "--no-index"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "solo_q8p.ckpt" in captured.out
    assert "Local Files: 1" in captured.out


def test_cli_installed_json(tmp_path: Path, capsys) -> None:
    model_dir = tmp_path / "models"
    model_dir.mkdir()
    _write_text(model_dir / "solo_q8p.ckpt", "solo")

    exit_code = models_main(
        ["installed", "--model-dir", str(model_dir), "--no-index", "--json", "--limit", "5"]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    payload = json.loads(captured.out)
    assert payload["local_file_count"] == 1
    assert payload["models"][0]["base_name"] == "solo_q8p.ckpt"
