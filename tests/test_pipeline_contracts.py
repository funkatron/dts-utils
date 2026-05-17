from __future__ import annotations

from pathlib import Path

from dts_utils.pipeline.contracts import (
    image_ref_schema,
    pipeline_run_manifest_schema,
    run_layout_paths,
    step_run_schema,
    video_ref_schema,
)


def test_run_layout_paths_uses_run_step_tree(tmp_path: Path) -> None:
    out = run_layout_paths(tmp_path, "run-123", "text_to_image", "image.png")
    assert out["step_dir"] == tmp_path / "run-123" / "text_to_image"
    assert out["artifact_path"] == tmp_path / "run-123" / "text_to_image" / "image.png"
    assert out["artifact_metadata_path"].name == "image.png.json"
    assert out["step_run_path"].name == "step_run.json"


def test_schemas_require_core_fields() -> None:
    img = image_ref_schema()
    vid = video_ref_schema()
    step = step_run_schema()
    run = pipeline_run_manifest_schema()
    assert "required" in img and "artifact_id" in img["required"]
    assert "required" in vid and "fps" in vid["required"]
    assert "required" in step and "cache_key" in step["required"]
    assert "required" in run and run["required"] == ["run_id", "run_root", "steps", "artifacts"]
