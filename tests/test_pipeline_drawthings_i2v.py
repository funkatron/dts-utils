from __future__ import annotations

import io
import json
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from dts_utils.pipeline.executors import DrawThingsGrpcImageToVideoExecutor


def test_drawthings_i2v_executor_writes_mp4(tmp_path: Path) -> None:
    image_path = tmp_path / "in.png"
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), color=(10, 20, 30)).save(buf, format="PNG")
    image_path.write_bytes(buf.getvalue())
    fake_mp4 = b"\x00\x00\x00\x18ftypmp42"
    fake_meta = {
        "width": 64,
        "height": 36,
        "fps": 12,
        "seconds": 1.0,
        "frame_count": 12,
        "source": "drawthings_grpc",
        "motion": "drawthings_frames",
    }

    executor = DrawThingsGrpcImageToVideoExecutor(
        video_configuration="ltx-profile",
    )
    with patch(
        "dts_utils.pipeline.executors.generate_video_mp4_bytes",
        return_value=(fake_mp4, fake_meta),
    ):
        result = executor.execute(
            run_root=tmp_path / "runs",
            run_id="run-dt",
            step_id="i2v",
            cache_key="cache1234567890",
            request={
                "image_path": str(image_path),
                "prompt": "gentle motion",
                "configuration": "ltx-profile",
                "fps": 12,
            },
            parent_artifact_ids=["parent-1"],
        )

    assert result.artifact.kind == "video"
    assert Path(result.artifact.path).read_bytes() == fake_mp4
    assert result.metadata["output_meta"]["motion"] == "drawthings_frames"


def test_drawthings_i2v_executor_rejects_single_frame_when_duration_requested(tmp_path: Path) -> None:
    image_path = tmp_path / "in.png"
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), color=(10, 20, 30)).save(buf, format="PNG")
    image_path.write_bytes(buf.getvalue())
    fake_mp4 = b"\x00\x00\x00\x18ftypmp42"
    fake_meta = {
        "width": 64,
        "height": 36,
        "fps": 12,
        "seconds": 0.08333333333333333,
        "frame_count": 1,
        "source": "drawthings_grpc",
        "motion": "drawthings_frames",
    }

    executor = DrawThingsGrpcImageToVideoExecutor(video_configuration="ltx-profile")
    with patch(
        "dts_utils.pipeline.executors.generate_video_mp4_bytes",
        return_value=(fake_mp4, fake_meta),
    ):
        try:
            executor.execute(
                run_root=tmp_path / "runs",
                run_id="run-dt",
                step_id="i2v",
                cache_key="cache1234567890",
                request={
                    "image_path": str(image_path),
                    "prompt": "gentle motion",
                    "configuration": "ltx-profile",
                    "fps": 12,
                    "seconds": 1.0,
                },
                parent_artifact_ids=["parent-1"],
            )
        except RuntimeError as exc:
            assert "single frame" in str(exc)
        else:
            raise AssertionError("expected RuntimeError for single-frame i2v output")


def test_drawthings_i2v_executor_seeds_ltx_video_profile_when_missing_numframes(tmp_path: Path) -> None:
    image_path = tmp_path / "in.png"
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), color=(10, 20, 30)).save(buf, format="PNG")
    image_path.write_bytes(buf.getvalue())
    fake_mp4 = b"\x00\x00\x00\x18ftypmp42"
    fake_meta = {
        "width": 64,
        "height": 36,
        "fps": 12,
        "seconds": 1.0,
        "frame_count": 12,
        "source": "drawthings_grpc",
        "motion": "drawthings_frames",
    }
    minimal_cfg = {
        "model": "ltx_2.3_22b_distilled_f16.ckpt",
        "width": 512,
        "height": 512,
        "steps": 8,
    }
    seed_cfg = {
        "model": "ltx_2.3_22b_distilled_q6p.ckpt",
        "numFrames": 121,
        "fps": 5,
        "startFrameGuidance": 1,
    }

    def _fake_read_configuration_json_dict(*, configuration=None, configuration_json=None, config_dir=None):
        if configuration == "ltx-2.3-portrait":
            return dict(seed_cfg)
        return dict(minimal_cfg)

    executor = DrawThingsGrpcImageToVideoExecutor(video_configuration="ltx-profile")
    with patch(
        "dts_utils.pipeline.executors.read_configuration_json_dict",
        side_effect=_fake_read_configuration_json_dict,
    ), patch(
        "dts_utils.pipeline.executors.generate_video_mp4_bytes",
        return_value=(fake_mp4, fake_meta),
    ) as mocked_video:
        result = executor.execute(
            run_root=tmp_path / "runs",
            run_id="run-dt",
            step_id="i2v",
            cache_key="cache1234567890",
            request={
                "image_path": str(image_path),
                "prompt": "gentle motion",
                "configuration": "ltx-profile",
                "fps": 12,
                "seconds": 1.0,
            },
            parent_artifact_ids=["parent-1"],
        )

    _, gen = mocked_video.call_args.args[:2]
    assert gen.configuration is None
    assert gen.configuration_json is not None
    override_cfg = json.loads(Path(str(gen.configuration_json)).read_text(encoding="utf-8"))
    assert override_cfg["model"] == "ltx_2.3_22b_distilled_f16.ckpt"
    assert override_cfg["startFrameGuidance"] == 1
    assert override_cfg["numFrames"] == 12
    assert override_cfg["fps"] == 12
    assert result.metadata["output_meta"]["frame_count"] == 12
