"""Subprocess worker for pipeline step execution."""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from pathlib import Path

from PIL import Image


def _write_stub_png(path: Path, width: int, height: int, seed: int) -> None:
    width = max(1, width)
    height = max(1, height)
    # Deterministic pseudo-random art so local pipeline demos are visibly non-trivial.
    base_r = seed % 255
    base_g = (seed * 7) % 255
    base_b = (seed * 13) % 255
    img = Image.new("RGB", (width, height))
    px = img.load()
    assert px is not None

    # Background gradient with subtle wave interference.
    for y in range(height):
        yf = y / max(1, height - 1)
        for x in range(width):
            xf = x / max(1, width - 1)
            wave = 0.5 + 0.5 * math.sin((xf * 9.0 + yf * 7.0 + seed * 0.01) * math.pi)
            r = int((base_r * (1.0 - xf) + 220 * xf) * (0.70 + 0.30 * wave)) % 256
            g = int((base_g * (1.0 - yf) + 210 * yf) * (0.70 + 0.30 * (1.0 - wave))) % 256
            b = int((base_b * (1.0 - xf * yf) + 235 * xf * yf) * (0.72 + 0.28 * wave)) % 256
            px[x, y] = (r, g, b)

    # Overlay deterministic sparkles and diagonal accents.
    sparkle_count = max(32, (width * height) // 1800)
    state = (seed ^ 0xA5A5A5A5) & 0xFFFFFFFF
    for _ in range(sparkle_count):
        state = (1664525 * state + 1013904223) & 0xFFFFFFFF
        x = state % width
        state = (1664525 * state + 1013904223) & 0xFFFFFFFF
        y = state % height
        state = (1664525 * state + 1013904223) & 0xFFFFFFFF
        val = 180 + (state % 76)
        px[x, y] = (val, min(255, val + 20), min(255, val + 35))

    for i in range(0, width + height, max(8, min(width, height) // 20 or 8)):
        x = min(width - 1, i % width)
        y = min(height - 1, i % height)
        px[x, y] = (255, 255, 255)

    img.save(path, format="PNG")


def _render_ffmpeg_loop(
    image_path: Path,
    video_path: Path,
    fps: int,
    seconds: float,
    width: int,
    height: int,
    *,
    motion: bool = False,
) -> None:
    if motion:
        # Add clearly visible Ken Burns motion so output never looks static.
        frame_count = max(1, int(round(max(seconds, 0.1) * max(fps, 1))))
        vf = (
            f"scale={width}:{height},"
            f"zoompan="
            f"z='if(eq(on,1),1.0,min(zoom+0.0035,1.28))':"
            f"x='iw/2-(iw/zoom/2)+sin(on/10)*48':"
            f"y='ih/2-(ih/zoom/2)+cos(on/14)*32':"
            f"d=1:s={width}x{height}:fps={fps},"
            f"trim=end_frame={frame_count}"
        )
    else:
        vf = f"fps={fps},scale={width}:{height}"

    cmd = [
        "ffmpeg",
        "-y",
        "-loop",
        "1",
        "-i",
        str(image_path),
        "-vf",
        vf,
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
    _render_ffmpeg_loop(image_path, artifact_path, fps, seconds, width, height, motion=False)
    return {"width": width, "height": height, "fps": fps, "seconds": seconds, "motion": "none"}


def _mode_image_to_video_ltx(request: dict[str, object], artifact_path: Path) -> dict[str, object]:
    # Placeholder LTX adapter: looped still-image render with OOM guard simulation.
    width = int(request.get("width", 1024))
    height = int(request.get("height", 576))
    if bool(request.get("simulate_oom")) and (width * height) > (1024 * 576):
        raise RuntimeError("out of memory while allocating video latent tensors")
    image_path = Path(str(request["image_path"]))
    fps = int(request.get("fps", 12))
    seconds = float(request.get("seconds", 1.0))
    _render_ffmpeg_loop(image_path, artifact_path, fps, seconds, width, height, motion=True)
    return {
        "width": width,
        "height": height,
        "fps": fps,
        "seconds": seconds,
        "motion": "ken_burns",
    }


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
