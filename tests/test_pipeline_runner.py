from __future__ import annotations

import json
from pathlib import Path

from dts_utils.pipeline.cache import step_cache_key
from dts_utils.pipeline.executors import PlaceholderImageToVideoExecutor, StubTextToImageExecutor
from dts_utils.pipeline.runner import PipelineRunner, PipelineStep


def test_runner_writes_step_and_pipeline_manifests(tmp_path: Path) -> None:
    runner = PipelineRunner(tmp_path)
    manifest = runner.run(
        run_id="run-a",
        steps=[
            PipelineStep(
                step_id="t2i",
                executor=StubTextToImageExecutor(),
                request={"width": 64, "height": 64, "seed": 1},
            ),
            PipelineStep(
                step_id="i2v",
                executor=PlaceholderImageToVideoExecutor(),
                input_from_step="t2i",
                request={"fps": 8, "seconds": 1.0},
            ),
        ],
    )
    assert manifest.run_id == "run-a"
    assert len(manifest.steps) == 2
    assert (tmp_path / "run-a" / "pipeline_run.json").exists()
    assert (tmp_path / "run-a" / "t2i" / "step_run.json").exists()
    assert (tmp_path / "run-a" / "i2v" / "step_run.json").exists()


def test_runner_cache_hit_marks_cached_status(tmp_path: Path) -> None:
    runner = PipelineRunner(tmp_path)
    steps = [
        PipelineStep(
            step_id="t2i",
            executor=StubTextToImageExecutor(),
            request={"width": 32, "height": 32, "seed": 42},
        )
    ]
    first = runner.run(run_id="run-one", steps=steps)
    assert first.steps[0]["status"] == "completed"
    second = runner.run(run_id="run-two", steps=steps)
    assert second.steps[0]["status"] == "cached"
    idx = json.loads((tmp_path / "cache_index.json").read_text(encoding="utf-8"))
    assert len(idx) == 1


def test_runner_oom_policy_downscales_for_placeholder_i2v(tmp_path: Path) -> None:
    runner = PipelineRunner(tmp_path, max_oom_retries=1)
    manifest = runner.run(
        run_id="run-oom",
        steps=[
            PipelineStep(step_id="t2i", executor=StubTextToImageExecutor(), request={"width": 2048, "height": 2048, "seed": 2}),
            PipelineStep(
                step_id="i2v",
                executor=PlaceholderImageToVideoExecutor(),
                input_from_step="t2i",
                request={"fps": 12, "seconds": 2.0, "width": 2048, "height": 2048, "simulate_oom": True},
            ),
        ],
    )
    i2v = manifest.steps[1]
    retries = i2v["metadata"].get("oom_retries", [])
    assert retries, "expected OOM retry metadata"
    assert retries[0]["width"] <= 1024
    image_path = manifest.artifacts[0]["path"]
    parent_id = manifest.artifacts[0]["artifact_id"]
    full_key = step_cache_key(
        cache_namespace="image_to_video_placeholder",
        executor_version=PlaceholderImageToVideoExecutor().executor_version,
        request_payload={
            "image_path": image_path,
            "fps": 12,
            "seconds": 2.0,
            "width": 2048,
            "height": 2048,
            "simulate_oom": True,
        },
        upstream_artifact_ids=[parent_id],
        model_fingerprint=PlaceholderImageToVideoExecutor().model_fingerprint(),
    )
    retry_key = step_cache_key(
        cache_namespace="image_to_video_placeholder",
        executor_version=PlaceholderImageToVideoExecutor().executor_version,
        request_payload={
            "image_path": image_path,
            "fps": 12,
            "seconds": retries[0]["seconds"],
            "width": retries[0]["width"],
            "height": retries[0]["height"],
        },
        upstream_artifact_ids=[parent_id],
        model_fingerprint=PlaceholderImageToVideoExecutor().model_fingerprint(),
    )
    assert full_key != retry_key
    assert i2v["cache_key"] == retry_key
