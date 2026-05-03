"""Tests for the Draw Things model indexing workflow."""

from __future__ import annotations

import json
from pathlib import Path

from dts_util.model_index.cli import main as models_main
from dts_util.model_index.export import write_html_report
from dts_util.model_index.huggingface import _cache_paths
from dts_util.model_index.local import compute_index_status, doctor_local_models, scan_local_models, summarize_installed_models
from dts_util.model_index.parse import ModelRecord, build_records, enrich_huggingface_records
from dts_util.model_index.search import filter_records, format_record_detail, format_summary, search_records


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _sample_repo(tmp_path: Path) -> Path:
    repo_dir = tmp_path / "community-models"
    repo_dir.mkdir()
    _write_text(repo_dir / "uncurated_models.txt", "flux-1-dev bad-model missing-model")
    _write_text(
        repo_dir / "uncurated_models_sha256.json",
        json.dumps({"flux_1_dev_q8p.ckpt": "abc123", "bad_model_q8p.ckpt": "def456"}),
    )
    _write_text(
        repo_dir / "models" / "flux-1-dev" / "metadata.json",
        json.dumps(
            {
                "name": "FLUX.1 [dev]",
                "version": "flux1",
                "file": "flux_1_dev_q8p.ckpt",
                "source": "https://huggingface.co/black-forest-labs/FLUX.1-dev",
                "author": "Black Forest Labs",
                "license": "other",
                "tags": ["flux", "text-to-image"],
            }
        ),
    )
    _write_text(repo_dir / "uncurated_models" / "bad-model" / "metadata.json", '{"name": ')
    return repo_dir


def _sample_repo_with_hf_note(tmp_path: Path) -> Path:
    repo_dir = tmp_path / "community-models"
    repo_dir.mkdir()
    _write_text(repo_dir / "uncurated_models.txt", "chroma-v42-detail-calibrated animagine-xl")
    _write_text(repo_dir / "uncurated_models_sha256.json", json.dumps({}))
    _write_text(
        repo_dir / "uncurated_models" / "chroma-v42-detail-calibrated" / "metadata.json",
        json.dumps(
            {
                "name": "Chroma v42 Detail Calibrated",
                "version": "flux1",
                "file": "chroma_v42_detail_calibrated_q8p.ckpt",
                "note": "See more about [Chroma](https://huggingface.co/lodestones/Chroma).",
            }
        ),
    )
    _write_text(
        repo_dir / "models" / "animagine-xl" / "metadata.json",
        json.dumps(
            {
                "name": "Animagine XL v3.1",
                "download": {
                    "file": "https://huggingface.co/cagliostrolab/animagine-xl-3.1/resolve/main/animagine-xl-3.1.safetensors"
                },
                "file": "animagine_xl_v3.1_f16.ckpt",
                "version": "sdxl_base_v0.9",
            }
        ),
    )
    return repo_dir


def test_build_records_tolerates_bad_metadata(tmp_path: Path) -> None:
    repo_dir = _sample_repo(tmp_path)

    records = build_records(repo_dir)
    by_id = {record.id: record for record in records}

    assert set(by_id) == {"flux-1-dev", "bad-model", "missing-model"}
    assert by_id["flux-1-dev"].name == "FLUX.1 [dev]"
    assert by_id["flux-1-dev"].model_family == "Flux"
    assert by_id["flux-1-dev"].huggingface_repo_id == "black-forest-labs/FLUX.1-dev"
    assert by_id["flux-1-dev"].sha256 == "abc123"
    assert "Malformed JSON" in by_id["bad-model"].warnings[0]
    assert by_id["missing-model"].warnings == ["No metadata.json file found"]


def test_enrich_huggingface_records_uses_cache(tmp_path: Path) -> None:
    cache_dir = tmp_path / ".cache" / "huggingface"
    cache_dir.mkdir(parents=True)
    cache_path, readme_cache = _cache_paths(cache_dir, "black-forest-labs/FLUX.1-dev")
    cache_path.write_text(
        json.dumps(
            {
                "likes": 12,
                "downloads": 345,
                "lastModified": "2026-04-01T00:00:00.000Z",
                "tags": ["diffusers", "flux"],
                "siblings": [{"rfilename": "README.md"}, {"rfilename": "model.safetensors"}],
                "readme_excerpt": "A strong FLUX checkpoint.",
            }
        ),
        encoding="utf-8",
    )
    readme_cache.write_text("# FLUX\nA strong FLUX checkpoint.", encoding="utf-8")

    record = ModelRecord(
        id="flux-1-dev",
        name="FLUX.1 [dev]",
        type="model",
        model_family="Flux",
        source_url="https://huggingface.co/black-forest-labs/FLUX.1-dev",
        huggingface_repo_id="black-forest-labs/FLUX.1-dev",
        download_url=None,
        author=None,
        license=None,
        tags=[],
        sha256=None,
        metadata_path=None,
        raw_metadata_json={},
    )

    enrich_huggingface_records([record], cache_dir=cache_dir, refresh=False)

    assert record.likes == 12
    assert record.downloads == 345
    assert record.last_modified == "2026-04-01T00:00:00.000Z"
    assert "model.safetensors" in record.sibling_file_names
    assert "diffusers" in record.tags
    assert record.readme_excerpt == "A strong FLUX checkpoint."


def test_build_records_extracts_huggingface_from_note_and_nested_download(tmp_path: Path) -> None:
    repo_dir = _sample_repo_with_hf_note(tmp_path)

    records = build_records(repo_dir)
    by_id = {record.id: record for record in records}

    assert by_id["chroma-v42-detail-calibrated"].source_url == "https://huggingface.co/lodestones/Chroma"
    assert by_id["chroma-v42-detail-calibrated"].huggingface_repo_id == "lodestones/Chroma"
    assert by_id["animagine-xl"].source_url == (
        "https://huggingface.co/cagliostrolab/animagine-xl-3.1/resolve/main/animagine-xl-3.1.safetensors"
    )
    assert by_id["animagine-xl"].huggingface_repo_id == "cagliostrolab/animagine-xl-3.1"


def test_search_and_show_helpers() -> None:
    records = [
        ModelRecord(
            id="flux-1-dev",
            name="FLUX.1 [dev]",
            type="model",
            model_family="Flux",
            source_url=None,
            huggingface_repo_id=None,
            download_url=None,
            author="Black Forest Labs",
            license="other",
            tags=["flux"],
            sha256=None,
            metadata_path="models/flux-1-dev/metadata.json",
            raw_metadata_json={"name": "FLUX.1 [dev]"},
            downloads=10,
            suggested_config={
                "baseline_config": {"default_scale": 16},
                "recommended_tuning": {"steps": "20-30"},
            },
        ),
        ModelRecord(
            id="anime-xl",
            name="Anime XL",
            type="model",
            model_family="SDXL",
            source_url=None,
            huggingface_repo_id=None,
            download_url=None,
            author="Example Author",
            license="cc-by",
            tags=["anime", "sdxl"],
            sha256=None,
            metadata_path="models/anime-xl/metadata.json",
            raw_metadata_json={"name": "Anime XL"},
            downloads=20,
        ),
    ]

    matches = search_records(records, ["flux"])
    assert [record.id for record in matches] == ["flux-1-dev"]
    filtered = filter_records(records, family="Flux", has_license=True)
    assert [record.id for record in filtered] == ["flux-1-dev"]

    detail = format_record_detail(records[0])
    assert "FLUX.1 [dev]" in detail
    assert "Baseline Config:" in detail
    assert "Recommended Tuning:" in detail
    assert "Raw Metadata JSON" in detail
    summary = format_summary(records)
    assert "Coverage:" in summary
    assert "Top model families:" in summary
    assert "With suggested config" in summary


def test_build_records_uses_filename_sha_map_and_version_family(tmp_path: Path) -> None:
    repo_dir = tmp_path / "community-models"
    repo_dir.mkdir()
    _write_text(repo_dir / "uncurated_models.txt", "2DN")
    _write_text(repo_dir / "uncurated_models_sha256.json", json.dumps({"2dn_f16.ckpt": "hash-2dn"}))
    _write_text(
        repo_dir / "uncurated_models" / "2DN" / "metadata.json",
        json.dumps(
            {
                "name": "2DN",
                "file": "2dn_f16.ckpt",
                "version": "sdxl_base_v0.9",
            }
        ),
    )

    records = build_records(repo_dir)
    assert records[0].sha256 == "hash-2dn"
    assert records[0].model_family == "SDXL"


def test_build_records_extracts_suggested_config_from_note(tmp_path: Path) -> None:
    repo_dir = tmp_path / "community-models"
    repo_dir.mkdir()
    _write_text(repo_dir / "uncurated_models.txt", "hidream-e1-full-exact")
    _write_text(repo_dir / "uncurated_models_sha256.json", json.dumps({}))
    _write_text(
        repo_dir / "models" / "hidream-e1-full-exact" / "metadata.json",
        json.dumps(
            {
                "name": "HiDream E1 [full] (Exact)",
                "version": "hidream_i1",
                "default_scale": 16,
                "hires_fix_scale": 24,
                "padded_text_encoding_length": 128,
                "high_precision_autoencoder": True,
                "note": "[HiDream-E1 [full]](https://huggingface.co/HiDream-ai/HiDream-E1-Full) is an image editing model built on HiDream-I1. It is MIT-licensed and commercially friendly. Trained at 768×768 resolution using a Flow Matching objective, the model performs best with trailing samplers and 30–50 sampling steps. For optimal results, ensure the width is set to 768 and use the following prompt format: Editing Instruction: {}. Target Image Description: {}.",
            }
        ),
    )

    records = build_records(repo_dir)
    config = records[0].suggested_config
    assert records[0].license == "MIT"
    assert config["baseline_config"]["default_scale"] == 16
    assert config["recommended_tuning"]["resolution"] == "768×768"
    assert config["recommended_tuning"]["sampler"] == "trailing"
    assert config["recommended_tuning"]["steps"] == "30–50"
    assert "Editing Instruction:" in config["recommended_tuning"]["prompt_format"]


def test_cli_build_search_show_and_report(tmp_path: Path) -> None:
    repo_dir = _sample_repo(tmp_path)
    data_dir = tmp_path / "data"
    cache_dir = tmp_path / ".cache" / "huggingface"

    exit_code = models_main(
        [
            "build",
            "--repo-dir",
            str(repo_dir),
            "--data-dir",
            str(data_dir),
            "--cache-dir",
            str(cache_dir),
            "--skip-hf",
        ]
    )
    assert exit_code == 0
    assert (data_dir / "drawthings_uncurated_models.json").exists()
    assert (data_dir / "drawthings_uncurated_models.csv").exists()
    assert (data_dir / "drawthings_models.sqlite").exists()
    assert (data_dir / "report.html").exists()

    assert models_main(["search", "flux", "--data-dir", str(data_dir)]) == 0
    assert models_main(["search", "--family", "Flux", "--data-dir", str(data_dir)]) == 0
    assert models_main(["show", "flux-1-dev", "--data-dir", str(data_dir)]) == 0
    assert models_main(["show", "flux-1-dev", "--local", "--model-dir", str(tmp_path / "models"), "--data-dir", str(data_dir)]) == 0
    assert models_main(["report", "--data-dir", str(data_dir)]) == 0
    assert models_main(["report", "--summary-only", "--data-dir", str(data_dir)]) == 0


def test_local_scan_status_and_doctor(tmp_path: Path) -> None:
    repo_dir = _sample_repo(tmp_path)
    records = build_records(repo_dir)

    model_dir = tmp_path / "models"
    model_dir.mkdir()
    _write_text(model_dir / "flux_1_dev_q8p.ckpt", "base")
    _write_text(model_dir / "flux_1_dev_q8p.ckpt-tensordata", "tensor")
    _write_text(model_dir / "dangling.ckpt-tensordata", "orphan")
    _write_text(model_dir / "broken_download.ckpt.part", "partial")
    _write_text(model_dir / "mystery_model_q8p.ckpt", "mystery")

    local_files = scan_local_models(model_dir)
    summaries = summarize_installed_models(local_files, indexed_records=records)
    assert any(summary.base_name == "flux_1_dev_q8p.ckpt" for summary in summaries)

    statuses = compute_index_status(records, local_files)
    by_id = {status.model_id: status for status in statuses}
    assert by_id["flux-1-dev"].status == "installed"
    assert by_id["missing-model"].status == "unknown"

    findings = doctor_local_models(local_files, indexed_records=records)
    kinds = {finding.kind for finding in findings}
    assert "partial-download" in kinds
    assert "orphan-tensordata" in kinds
    assert "local-untracked" in kinds


def test_cli_installed_status_and_doctor(tmp_path: Path) -> None:
    repo_dir = _sample_repo(tmp_path)
    data_dir = tmp_path / "data"
    cache_dir = tmp_path / ".cache" / "huggingface"
    model_dir = tmp_path / "models"
    model_dir.mkdir()
    _write_text(model_dir / "flux_1_dev_q8p.ckpt", "base")
    _write_text(model_dir / "flux_1_dev_q8p.ckpt-tensordata", "tensor")
    _write_text(model_dir / "broken_download.ckpt.part", "partial")

    assert models_main(
        [
            "build",
            "--repo-dir",
            str(repo_dir),
            "--data-dir",
            str(data_dir),
            "--cache-dir",
            str(cache_dir),
            "--skip-hf",
        ]
    ) == 0
    assert models_main(["installed", "--model-dir", str(model_dir), "--data-dir", str(data_dir), "--limit", "5"]) == 0
    assert models_main(["status", "--model-dir", str(model_dir), "--data-dir", str(data_dir), "--limit", "5"]) == 0
    assert models_main(["doctor", "--model-dir", str(model_dir), "--data-dir", str(data_dir)]) == 0
    assert models_main(["doctor", "--model-dir", str(model_dir), "--data-dir", str(data_dir), "--severity", "all", "--limit", "5"]) == 0


def test_doctor_severity_filtering(tmp_path: Path) -> None:
    repo_dir = _sample_repo(tmp_path)
    records = build_records(repo_dir)
    model_dir = tmp_path / "models"
    model_dir.mkdir()
    _write_text(model_dir / "broken_download.ckpt.part", "partial")
    _write_text(model_dir / "mystery_model_q8p.ckpt", "mystery")

    findings = doctor_local_models(scan_local_models(model_dir), indexed_records=records)
    severities = {finding.severity for finding in findings}
    assert severities == {"warning", "info"}


def test_write_html_report_includes_sortable_table(tmp_path: Path) -> None:
    report_path = tmp_path / "report.html"
    write_html_report(
        [
            ModelRecord(
                id="flux-1-dev",
                name="FLUX.1 [dev]",
                type="model",
                model_family="Flux",
                source_url=None,
                huggingface_repo_id=None,
                download_url=None,
                author="Black Forest Labs",
                license="other",
                tags=[],
                sha256=None,
                metadata_path=None,
                raw_metadata_json={},
                downloads=100,
            )
        ],
        report_path,
    )
    html_text = report_path.read_text(encoding="utf-8")
    assert "Draw Things Uncurated Model Report" in html_text
    assert "models-table" in html_text
