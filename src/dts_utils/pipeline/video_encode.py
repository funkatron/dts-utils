"""ffmpeg helpers for pipeline video artifacts."""

from __future__ import annotations

import io
import os
import subprocess
import tempfile
from collections.abc import Sequence
from pathlib import Path

from PIL import Image


def ffmpeg_missing_message() -> str:
    return (
        "ffmpeg is required for pipeline video steps. Install ffmpeg or run "
        "`dts-utils pipeline check`. For tests only, set DTS_PIPELINE_ALLOW_FFMPEG_STUB=1."
    )


def raise_ffmpeg_missing(exc: FileNotFoundError | None = None) -> None:
    if os.environ.get("DTS_PIPELINE_ALLOW_FFMPEG_STUB") == "1":
        return
    msg = ffmpeg_missing_message()
    if exc is not None:
        raise RuntimeError(msg) from exc
    raise RuntimeError(msg)


def png_frames_to_mp4(
    png_frames: Sequence[bytes],
    *,
    fps: int,
    width: int | None = None,
    height: int | None = None,
) -> bytes:
    """Mux decoded frame PNGs into an H.264 MP4 (returns file bytes)."""
    if not png_frames:
        raise ValueError("At least one frame is required to build a video.")
    fps = max(1, int(fps))

    with tempfile.TemporaryDirectory(prefix="dts-pipeline-frames-") as tmp:
        frames_dir = Path(tmp)
        for i, png in enumerate(png_frames):
            frame_path = frames_dir / f"frame_{i:06d}.png"
            if width and height:
                with Image.open(io.BytesIO(png)) as img:
                    img = img.convert("RGB")
                    img = img.resize((width, height), Image.Resampling.LANCZOS)
                    img.save(frame_path, format="PNG")
            else:
                frame_path.write_bytes(png)

        out_path = frames_dir / "output.mp4"
        cmd = [
            "ffmpeg",
            "-y",
            "-framerate",
            str(fps),
            "-i",
            str(frames_dir / "frame_%06d.png"),
            "-frames:v",
            str(len(png_frames)),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(out_path),
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True)
        except FileNotFoundError as exc:
            raise_ffmpeg_missing(exc)
            return b"INFOMUX-STUB-MP4"
        if proc.returncode != 0:
            stderr = proc.stderr or "ffmpeg failed"
            raise RuntimeError(stderr.strip())
        return out_path.read_bytes()
