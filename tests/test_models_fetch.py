"""Tests for bundled ``models fetch`` recipes and CLI wiring."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dts_utils.model_fetch.download import assert_https_url
from dts_utils.model_fetch.errors import FetchRecipeError
from dts_utils.model_fetch.recipes import DEFAULT_FETCH_RECIPE_ENV
from dts_utils.model_fetch.recipes import resolve_default_recipe_id
from dts_utils.model_fetch.runner import run_fetch_plan
from dts_utils.model_index.cli import main as models_main


def test_resolve_default_recipe_id_reads_registry_when_env_unset(monkeypatch):
    monkeypatch.delenv(DEFAULT_FETCH_RECIPE_ENV, raising=False)
    assert resolve_default_recipe_id() == "z-image-turbo-1.0-exact"


def test_resolve_default_recipe_id_env_overrides_registry(monkeypatch):
    monkeypatch.setenv(DEFAULT_FETCH_RECIPE_ENV, "z-image-turbo-1.0-exact")
    assert resolve_default_recipe_id() == "z-image-turbo-1.0-exact"


def test_assert_https_url_rejects_non_https():
    with pytest.raises(FetchRecipeError, match="Only https://"):
        assert_https_url("http://example.com/file.bin")


def test_run_fetch_plan_dry_run_zero_exit():
    rc = run_fetch_plan(
        recipe_id="z-image-turbo-1.0-exact",
        model_dir=Path("/nonexistent/models"),
        dry_run=True,
        yes=False,
        force=False,
    )
    assert rc == 0


def test_run_fetch_plan_requires_yes_when_not_dry_run():
    rc = run_fetch_plan(
        recipe_id="z-image-turbo-1.0-exact",
        model_dir=Path("/nonexistent/models"),
        dry_run=False,
        yes=False,
        force=False,
    )
    assert rc == 2


def test_models_fetch_cli_dry_run(capsys):
    rc = models_main(["fetch", "--dry-run", "z-image-turbo-1.0-exact"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "recipe=" in out
    assert "[dry-run]" in out


def test_models_fetch_cli_default_recipe_dry_run(monkeypatch, capsys):
    monkeypatch.delenv(DEFAULT_FETCH_RECIPE_ENV, raising=False)
    rc = models_main(["fetch", "--dry-run"])
    assert rc == 0
    assert "z-image-turbo-1.0-exact" in capsys.readouterr().out


def test_models_fetch_cli_without_yes_exit_2():
    rc = models_main(["fetch", "z-image-turbo-1.0-exact"])
    assert rc == 2


def test_models_fetch_from_metadata_prints_basenames(tmp_path: Path, capsys):
    meta = tmp_path / "metadata.json"
    meta.write_text(
        json.dumps(
            {
                "file": "m.ckpt",
                "autoencoder": "models/vae_f16.ckpt",
                "text_encoder": "te.ckpt",
            },
        ),
        encoding="utf-8",
    )
    rc = models_main(["fetch", "--from-metadata", str(meta)])
    assert rc == 0
    lines = [ln for ln in capsys.readouterr().out.splitlines() if ln.strip()]
    assert lines == ["m.ckpt", "vae_f16.ckpt", "te.ckpt"]


def test_models_fetch_recipe_and_from_metadata_mutually_exclusive():
    rc = models_main(["fetch", "z-image-turbo-1.0-exact", "--from-metadata", "/dev/null"])
    assert rc == 2
