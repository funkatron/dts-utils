"""Load and normalize raster images for Draw Things input tensors."""

from __future__ import annotations

import base64
from collections.abc import Sequence
from pathlib import Path

from dts_utils.exceptions import ConfigurationError
from dts_utils.tensor_png import normalize_image_bytes_to_png

_MAX_INPUT_IMAGES = 25  # keep in sync with generate_api.MAX_BATCH_GENERATIONS


def normalize_input_image_bytes(raw: bytes) -> bytes:
    try:
        return normalize_image_bytes_to_png(raw)
    except (OSError, ValueError) as exc:
        raise ConfigurationError(f"Invalid input image: {exc}") from exc


def normalize_input_image_path(path: Path) -> bytes:
    if not path.is_file():
        raise ConfigurationError(f"Input image not found: {path}")
    return normalize_input_image_bytes(path.read_bytes())


def decode_input_image_base64(raw: object, *, field: str = "input_image") -> bytes:
    if not isinstance(raw, str) or not raw.strip():
        raise ConfigurationError(f"{field} must be a non-empty base64 string.")
    try:
        decoded = base64.b64decode(raw.strip(), validate=True)
    except ValueError as exc:
        raise ConfigurationError(f"{field} is not valid base64.") from exc
    return normalize_input_image_bytes(decoded)


def coerce_input_images_base64(raw: object) -> list[bytes]:
    if not isinstance(raw, list):
        raise ConfigurationError("input_images must be an array of base64 strings.")
    if len(raw) < 1:
        raise ConfigurationError("input_images must contain at least one image.")
    if len(raw) > _MAX_INPUT_IMAGES:
        raise ConfigurationError(f"input_images cannot contain more than {_MAX_INPUT_IMAGES} entries.")
    out: list[bytes] = []
    for i, item in enumerate(raw):
        out.append(decode_input_image_base64(item, field=f"input_images[{i}]"))
    return out


def validate_input_image_paths(paths: Sequence[Path]) -> None:
    if len(paths) < 1:
        raise ConfigurationError("input_images must contain at least one path.")
    if len(paths) > _MAX_INPUT_IMAGES:
        raise ConfigurationError(f"input_images cannot contain more than {_MAX_INPUT_IMAGES} entries.")
    for path in paths:
        if not path.is_file():
            raise ConfigurationError(f"Input image not found: {path}")


def resolve_generations_with_input_images(
    generations: int | None,
    input_image_count: int,
) -> int:
    if input_image_count < 1:
        raise ConfigurationError("input_images must contain at least one image.")
    if input_image_count > _MAX_INPUT_IMAGES:
        raise ConfigurationError(f"input_images cannot contain more than {_MAX_INPUT_IMAGES} entries.")
    if generations is None:
        return input_image_count
    if generations != input_image_count:
        raise ConfigurationError(
            f"'generations' ({generations}) must equal len(input_images) ({input_image_count}) "
            "or be omitted when input_images is set."
        )
    return generations


def materialize_input_images_to_dir(directory: Path, images_png: Sequence[bytes]) -> list[Path]:
    directory.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for i, png in enumerate(images_png):
        path = directory / f"input-{i}.png"
        path.write_bytes(png)
        paths.append(path)
    return paths
