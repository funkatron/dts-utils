"""Tests for input image normalization helpers."""

from __future__ import annotations

import base64
import io

import pytest
from PIL import Image

from dts_utils.exceptions import ConfigurationError
from dts_utils.input_image import (
    coerce_input_images_base64,
    decode_input_image_base64,
    normalize_input_image_bytes,
    resolve_generations_with_input_images,
)
from dts_utils.tensor_png import normalize_image_bytes_to_png


def _jpeg_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), color=(128, 64, 32)).save(buf, format="JPEG")
    return buf.getvalue()


def test_normalize_image_bytes_jpeg_to_png() -> None:
    png = normalize_image_bytes_to_png(_jpeg_bytes())
    assert png.startswith(b"\x89PNG\r\n\x1a\n")


def test_decode_input_image_base64_accepts_jpeg() -> None:
    raw = base64.standard_b64encode(_jpeg_bytes()).decode("ascii")
    png = decode_input_image_base64(raw)
    assert png.startswith(b"\x89PNG\r\n\x1a\n")


def test_coerce_input_images_base64_rejects_empty() -> None:
    with pytest.raises(ConfigurationError, match="at least one"):
        coerce_input_images_base64([])


def test_resolve_generations_with_input_images_defaults_to_count() -> None:
    assert resolve_generations_with_input_images(None, 3) == 3


def test_resolve_generations_with_input_images_requires_match() -> None:
    with pytest.raises(ConfigurationError, match="must equal"):
        resolve_generations_with_input_images(2, 3)
