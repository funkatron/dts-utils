from __future__ import annotations

from pathlib import Path

from dts_utils.pipeline.executors import (
    LtxImageToVideoExecutor,
    SdxlTextToImageExecutor,
    ZImageTurboTextToImageExecutor,
)
from dts_utils.pipeline.runner import PipelineRunner, PipelineStep


def test_sdxl_executor_records_runtime_metadata(tmp_path: Path) -> None:
    runner = PipelineRunner(tmp_path)
    manifest = runner.run(
        run_id="run-sdxl",
        steps=[
            PipelineStep(
                step_id="t2i",
                executor=SdxlTextToImageExecutor(runtime="pytorch-mps", model_sha256="abc123"),
                request={"width": 48, "height": 48, "seed": 7},
            )
        ],
    )
    model = manifest.steps[0]["model"]
    assert model["id"] == "sdxl-turbo"
    assert model["sha256"] == "abc123"
    assert model["runtime_package"] == "torch"


def test_z_image_uses_distinct_cache_namespace(tmp_path: Path) -> None:
    runner = PipelineRunner(tmp_path)
    step = PipelineStep(
        step_id="z",
        executor=ZImageTurboTextToImageExecutor(model_sha256="zsha"),
        request={"width": 40, "height": 40, "seed": 9},
    )
    manifest = runner.run(run_id="run-z", steps=[step])
    assert manifest.steps[0]["cache_namespace"] == "text_to_image_z_image_turbo"


def test_ltx_executor_emits_video_artifact(tmp_path: Path) -> None:
    runner = PipelineRunner(tmp_path)
    manifest = runner.run(
        run_id="run-ltx",
        steps=[
            PipelineStep(
                step_id="img",
                executor=SdxlTextToImageExecutor(runtime="mlx"),
                request={"width": 64, "height": 64, "seed": 4},
            ),
            PipelineStep(
                step_id="vid",
                executor=LtxImageToVideoExecutor(model_sha256="ltxsha"),
                input_from_step="img",
                request={"fps": 10, "seconds": 1.0},
            ),
        ],
    )
    out = manifest.steps[1]["outputs"][0]
    assert out["kind"] == "video"
    assert Path(out["path"]).suffix == ".mp4"
