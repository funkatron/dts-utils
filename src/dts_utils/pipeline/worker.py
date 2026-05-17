"""Subprocess worker for pipeline step execution."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image


def _write_stub_png(path: Path, width: int, height: int, seed: int) -> None:
    width = max(1, width)
    height = max(1, height)
    color = (seed % 255, (seed * 7) % 255, (seed * 13) % 255)
    img = Image.new("RGB", (width, height), color)
    img.save(path, format="PNG")


def _render_ffmpeg_loop(image_path: Path, video_path: Path, fps: int, seconds: float, width: int, height: int) -> None:
    cmd = [
        "ffmpeg",
        "-y",
        "-loop",
        "1",
        "-i",
        str(image_path),
        "-vf",
        f"fps={fps},scale={width}:{height}",
        "-t",
        f"{seconds:.3f}",
        "-pix_fmt",
        "yuv420p",
        str(video_path),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError:
        # Test/dev fallback when ffmpeg is unavailable: write placeholder bytes.
        video_path.write_bytes(b"INFOMUX-STUB-MP4")
        return
    if proc.returncode != 0:
        stderr = proc.stderr or "ffmpeg failed"
        raise RuntimeError(stderr.strip())


def _mode_text_to_image_stub(request: dict[str, object], artifact_path: Path) -> dict[str, object]:
    width = int(request.get("width", 1024))
    height = int(request.get("height", 1024))
    seed = int(request.get("seed", 0))
    _write_stub_png(artifact_path, width, height, seed)
    return {"width": width, "height": height}


def _mode_image_to_video_ffmpeg_stub(request: dict[str, object], artifact_path: Path) -> dict[str, object]:
    image_path = Path(str(request["image_path"]))
    fps = int(request.get("fps", 12))
    seconds = float(request.get("seconds", 1.0))
    width = int(request.get("width", 1024))
    height = int(request.get("height", 1024))
    _render_ffmpeg_loop(image_path, artifact_path, fps, seconds, width, height)
    return {"width": width, "height": height, "fps": fps, "seconds": seconds}


def _mode_image_to_video_ltx(request: dict[str, object], artifact_path: Path) -> dict[str, object]:
    # Placeholder LTX adapter: looped still-image render with OOM guard simulation.
    width = int(request.get("width", 1024))
    height = int(request.get("height", 576))
    if bool(request.get("simulate_oom")) and (width * height) > (1024 * 576):
        raise RuntimeError("out of memory while allocating video latent tensors")
    return _mode_image_to_video_ffmpeg_stub(request, artifact_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pipeline worker subprocess.")
    parser.add_argument("--mode", required=True)
    parser.add_argument("--request-json", type=Path, required=True)
    parser.add_argument("--artifact-path", type=Path, required=True)
    parser.add_argument("--metadata-path", type=Path, required=True)
    args = parser.parse_args(argv)

    request = json.loads(args.request_json.read_text(encoding="utf-8"))
    args.artifact_path.parent.mkdir(parents=True, exist_ok=True)
    args.metadata_path.parent.mkdir(parents=True, exist_ok=True)

    if args.mode in {"text_to_image_stub", "text_to_image_sdxl", "text_to_image_z_image_turbo"}:
        metadata = _mode_text_to_image_stub(request, args.artifact_path)
    elif args.mode == "image_to_video_ffmpeg_stub":
        metadata = _mode_image_to_video_ffmpeg_stub(request, args.artifact_path)
    elif args.mode == "image_to_video_ltx":
        metadata = _mode_image_to_video_ltx(request, args.artifact_path)
    else:
        raise ValueError(f"Unsupported worker mode: {args.mode}")

    args.metadata_path.write_text(json.dumps(metadata, sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
