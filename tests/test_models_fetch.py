"""Tests for bundled ``models fetch`` recipes and CLI wiring."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dts_utils.model_fetch.download import assert_https_url
from dts_utils.model_fetch.download import download_hf_file
from dts_utils.model_fetch.download import verify_sha_required
from dts_utils.model_fetch.errors import FetchRecipeError
from dts_utils.model_fetch.recipes import DEFAULT_FETCH_RECIPE_ENV
from dts_utils.model_fetch.recipes import resolve_default_recipe_id
from dts_utils.model_fetch.runner import _artifact_satisfied
from dts_utils.model_fetch.runner import _download_first_working_source
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


def test_resolve_default_recipe_id_registry_oserror(monkeypatch):
    monkeypatch.delenv(DEFAULT_FETCH_RECIPE_ENV, raising=False)

    def boom() -> dict[str, str]:
        raise OSError("simulated")

    monkeypatch.setattr("dts_utils.model_fetch.recipes.load_registry_dict", boom)
    with pytest.raises(FetchRecipeError, match="Could not read bundled registry"):
        resolve_default_recipe_id()


def test_models_fetch_broken_registry_exit_2(monkeypatch, capsys):
    monkeypatch.delenv(DEFAULT_FETCH_RECIPE_ENV, raising=False)

    def boom() -> dict[str, str]:
        raise OSError("simulated")

    monkeypatch.setattr("dts_utils.model_fetch.recipes.load_registry_dict", boom)
    rc = models_main(["fetch", "--dry-run"])
    assert rc == 2
    assert "registry" in capsys.readouterr().err.lower()


def test_models_fetch_empty_default_recipe_id_exit_2(monkeypatch):
    monkeypatch.delenv(DEFAULT_FETCH_RECIPE_ENV, raising=False)
    monkeypatch.setattr(
        "dts_utils.model_fetch.recipes.load_registry_dict",
        lambda: {"default_recipe_id": ""},
    )
    rc = models_main(["fetch", "--dry-run"])
    assert rc == 2


def test_manifest_requires_from_metadata():
    rc = models_main(["fetch", "--manifest"])
    assert rc == 2


def test_models_fetch_manifest_tsv_columns(tmp_path: Path, capsys):
    h = "6d90c3f0342410a747396ae7b7dedfb03caa4621ee426744793fc57e60766c52"
    meta = tmp_path / "metadata.json"
    meta.write_text(
        json.dumps(
            {
                "file": "m.ckpt",
                "converted": {"m.ckpt": h},
                "huggingface_repo_id": "org/hf",
                "download_url": "https://example.com/x",
            },
        ),
        encoding="utf-8",
    )
    rc = models_main(["fetch", "--from-metadata", str(meta), "--manifest"])
    assert rc == 0
    line = capsys.readouterr().out.strip().splitlines()[0]
    parts = line.split("\t")
    assert parts == ["m.ckpt", h, "org/hf", "https://example.com/x"]


def test_run_fetch_plan_dry_run_invokes_no_download_backends(monkeypatch):
    calls: list[str] = []

    monkeypatch.setattr(
        "dts_utils.model_fetch.runner.download_bytes_https",
        lambda url: calls.append(url) or b"",
    )

    def hf(**_: object) -> Path:
        calls.append("hf")
        return Path("/dev/null")

    monkeypatch.setattr("dts_utils.model_fetch.runner.download_hf_file", hf)
    rc = run_fetch_plan(
        recipe_id="z-image-turbo-1.0-exact",
        model_dir=Path("/nonexistent/models"),
        dry_run=True,
        yes=False,
        force=False,
    )
    assert rc == 0
    assert calls == []


def test_https_sources_try_next_on_failure(monkeypatch, tmp_path: Path):
    dest = tmp_path / "out.bin"
    art = {
        "filename": "out.bin",
        "sources": [
            {"type": "https", "url": "https://example.invalid/first"},
            {"type": "https", "url": "https://example.invalid/second"},
        ],
    }
    urls: list[str] = []

    def fake_download(url: str) -> bytes:
        urls.append(url)
        if len(urls) == 1:
            raise FetchRecipeError("404")
        return b"ok-bytes"

    monkeypatch.setattr(
        "dts_utils.model_fetch.runner.download_bytes_https",
        fake_download,
    )

    def atomic(dest_path: Path, data: bytes) -> None:
        dest_path.write_bytes(data)

    monkeypatch.setattr("dts_utils.model_fetch.runner.atomic_write_bytes", atomic)
    _download_first_working_source(art, dest)
    assert dest.read_bytes() == b"ok-bytes"
    assert len(urls) == 2


def test_artifact_satisfied_no_sha_skips_nonempty_file(tmp_path: Path):
    dest = tmp_path / "flux_1_vae_f16.ckpt"
    dest.write_bytes(b"x")
    assert _artifact_satisfied(dest, None, force=False) is True


@pytest.mark.integration
def test_optional_https_integration_skipped_by_default():
    import os

    if os.environ.get("DTS_UTILS_FETCH_INTEGRATION") != "1":
        pytest.skip("Set DTS_UTILS_FETCH_INTEGRATION=1 for optional live fetch smoke.")


def test_download_hf_file_with_stubbed_hub(monkeypatch, tmp_path: Path):
    pytest.importorskip("huggingface_hub")
    cached = tmp_path / "cached.safetensors"
    cached.write_bytes(b"hub-bytes")
    monkeypatch.setattr(
        "huggingface_hub.hf_hub_download",
        lambda **kw: str(cached),
    )
    got = download_hf_file(repo_id="org/repo", path_in_repo="weights.bin", revision=None)
    assert Path(got) == cached


def test_verify_sha_required_detects_mismatch(tmp_path: Path):
    p = tmp_path / "f.ckpt"
    p.write_bytes(b"abc")
    with pytest.raises(FetchRecipeError, match="SHA-256 mismatch"):
        verify_sha_required(p, "0" * 64)
