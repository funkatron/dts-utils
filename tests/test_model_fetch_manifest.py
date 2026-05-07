"""Community metadata manifest parity tests."""

from __future__ import annotations

import pytest

from dts_utils.model_index.local import _expected_file_names
from dts_utils.model_index.local import expected_filenames_from_community_metadata
from dts_utils.model_index.parse import ModelRecord


def _minimal_meta(**extras: object) -> dict[str, object]:
    base: dict[str, object] = {
        "file": "model.ckpt",
        "autoencoder": "path/to/vae_f16.ckpt",
        "text_encoder": "enc.ckpt",
    }
    base.update(extras)
    return base


def test_expected_filenames_matches_legacy_expected_names_via_model_record():
    payload = _minimal_meta(
        converted={
            "model.ckpt": "aaa",
            "extra.ckpt": "bbb",
        },
        additional_clip_encoders=["sub/extra_clip.ckpt"],
    )
    record = ModelRecord(
        id="x",
        name="",
        type=None,
        model_family="x",
        source_url=None,
        huggingface_repo_id=None,
        download_url=None,
        author=None,
        license=None,
        tags=[],
        sha256=None,
        metadata_path=None,
        raw_metadata_json=dict(payload),
        likes=None,
        downloads=None,
        last_modified=None,
        sibling_file_names=[],
        readme_excerpt=None,
        suggested_config={},
        warnings=[],
    )
    direct = expected_filenames_from_community_metadata(dict(payload))
    via_record = _expected_file_names(record)
    assert direct == via_record == [
        "model.ckpt",
        "vae_f16.ckpt",
        "enc.ckpt",
        "extra_clip.ckpt",
        "extra.ckpt",
    ]


def test_expected_filenames_skips_remote_api_style_unused_here():
    # Manifest helper ignores unknown keys; remote_api presets handled elsewhere.
    meta = _minimal_meta()
    meta["remote_api_model_config"] = {"x": 1}
    names = expected_filenames_from_community_metadata(meta)
    assert "model.ckpt" in names


def test_expected_filenames_remote_only_payload():
    meta: dict[str, object] = {"remote_api_model_config": {"x": 1}}
    assert expected_filenames_from_community_metadata(meta) == []
