from __future__ import annotations

import io
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
