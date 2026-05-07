"""Output paths and writing PNG files from generated tensors."""

from __future__ import annotations

import time
from pathlib import Path

from dts_utils.tensor_png import decode_dt_tensor_to_png


def unique_ms_timestamp_output_path(output_path: Path) -> Path:
    """Insert Unix milliseconds before the suffix so repeated runs do not clobber prior files."""
    ms = time.time_ns() // 1_000_000
    return output_path.with_name(f"{output_path.stem}-{ms}{output_path.suffix}")


def indexed_output_path(output_path: Path, index: int) -> Path:
    if index == 0:
        return output_path
    return output_path.with_name(f"{output_path.stem}-{index + 1}{output_path.suffix}")


def write_images(images: list[bytes], output_path: Path) -> list[Path]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    written_paths = []
    for index, image in enumerate(images):
        image_path = indexed_output_path(output_path, index)
        image_path.write_bytes(decode_dt_tensor_to_png(image))
        written_paths.append(image_path)
    return written_paths
