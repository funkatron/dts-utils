from __future__ import annotations

import io
import struct

import numpy as np
from PIL import Image

from dts_utils.tensor_png import decode_dt_tensor_to_png, encode_png_to_dt_tensor
from tests.test_generate_image_script import make_uncompressed_dt_tensor


def test_encode_png_roundtrip() -> None:
    img = Image.new("RGB", (8,  6), color=(200, 100, 50))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    png = buf.getvalue()
    tensor = encode_png_to_dt_tensor(png)
    out = decode_dt_tensor_to_png(tensor)
    with Image.open(io.BytesIO(out)) as decoded:
        assert decoded.size == (8, 6)


def test_encode_matches_uncompressed_tensor_layout() -> None:
    tensor = make_uncompressed_dt_tensor(width=2, height=2, values=[0.0] * 12)
    header = struct.unpack("<17I", tensor[:68])
    assert header[6] == 2
    assert header[7] == 2
    png = decode_dt_tensor_to_png(tensor)
    reencoded = encode_png_to_dt_tensor(png)
    header2 = struct.unpack("<17I", reencoded[:68])
    assert header2[6:9] == header[6:9]
    raw = np.frombuffer(reencoded, dtype=np.float16, offset=68)
    assert raw.shape[0] == 2 * 2 * 3
