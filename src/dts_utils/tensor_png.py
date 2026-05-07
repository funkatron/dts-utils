"""Decode Draw Things generated image tensors to PNG file bytes."""

from __future__ import annotations

import io
import struct

import fpzip
import numpy as np
from PIL import Image


def decode_dt_tensor_to_png(image_data: bytes) -> bytes:
    if len(image_data) < 68:
        raise ValueError("Generated image tensor is too small to contain a Draw Things header.")

    header = struct.unpack("<17I", image_data[:68])
    height, width, channels = header[6], header[7], header[8]
    if channels not in (1, 3, 4):
        raise ValueError(f"Unsupported generated image channel count: {channels}")

    is_compressed = header[0] == 1012247
    if is_compressed:
        tensor = fpzip.decompress(image_data[68:], order="C")
        tensor = np.asarray(tensor)
        if tensor.ndim == 4 and tensor.shape[0] == 1:
            tensor = tensor[0]
    else:
        tensor = np.frombuffer(image_data, dtype=np.float16, offset=68)
        tensor = tensor.reshape((height, width, channels))

    pixels = np.clip((tensor + 1) * 127, 0, 255).astype(np.uint8)
    if pixels.shape != (height, width, channels):
        pixels = pixels.reshape((height, width, channels))

    mode = {1: "L", 3: "RGB", 4: "RGBA"}[channels]
    output = io.BytesIO()
    Image.fromarray(pixels, mode=mode).save(output, format="PNG")
    return output.getvalue()
