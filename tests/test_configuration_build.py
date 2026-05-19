"""Tests for JSON configuration normalization and FlatBuffer conversion."""

from __future__ import annotations

import shutil

import pytest

from dts_utils.configuration_build import (
    configurations_equivalent_for_flatbuffer,
    json_configuration_to_flatbuffer,
    normalize_configuration_for_flatc,
)

# Enough fields that normalize → flatc succeeds when flatc is installed (see integration test).
_MINIMAL_DRAW_THINGS_STYLE = {
    "width": 512,
    "height": 512,
    "batchCount": 1,
    "steps": 8,
    "guidanceScale": 7.5,
    "model": "x.ckpt",
    "controls": [],
    "strength": 1.0,
    "seed": 0,
}


@pytest.mark.parametrize(
    ("incoming_key", "value"),
    [
        ("fps", 12),
        ("fps_id", 12),
        ("fpsId", 12),
    ],
)
def test_fps_field_aliases_normalize_to_fps_id(incoming_key: str, value: int) -> None:
    """Draw Things JSON uses ``fps`` / ``fpsId``; schema field is ``fps_id``."""
    out = normalize_configuration_for_flatc({"model": "m.ckpt", incoming_key: value})
    assert out["fps_id"] == value
    assert "fps" not in out


def test_fps_and_fps_id_last_occurrence_wins() -> None:
    """Both keys map to ``fps_id``; insertion order picks the winner."""
    newer_fps = normalize_configuration_for_flatc({"model": "x", "fps_id": 10, "fps": 20})
    assert newer_fps["fps_id"] == 20

    newer_fps_id = normalize_configuration_for_flatc({"model": "x", "fps": 20, "fps_id": 10})
    assert newer_fps_id["fps_id"] == 10


def test_configurations_equivalent_fps_aliases() -> None:
    eq = configurations_equivalent_for_flatbuffer
    base = {
        **_MINIMAL_DRAW_THINGS_STYLE,
        "fps": 7,
    }
    assert eq(base, {**_MINIMAL_DRAW_THINGS_STYLE, "fps_id": 7}) is True
    assert eq(base, {**_MINIMAL_DRAW_THINGS_STYLE, "fpsId": 7}) is True
    assert eq(base, {**_MINIMAL_DRAW_THINGS_STYLE, "fps": 99}) is False


@pytest.mark.skipif(not shutil.which("flatc"), reason="flatc not on PATH")
def test_flatc_accepts_json_with_fps_alias() -> None:
    """Regression: flatc rejects unknown field ``fps`` without normalization."""
    cfg = {**_MINIMAL_DRAW_THINGS_STYLE, "fps": 8}
    blob = json_configuration_to_flatbuffer(cfg)
    assert isinstance(blob, bytes)
    assert len(blob) >= 32


@pytest.mark.skipif(not shutil.which("flatc"), reason="flatc not on PATH")
def test_flatc_accepts_guiding_frame_noise_from_draw_things_camel_case() -> None:
    """Regression: Draw Things exports ``guidingFrameNoise``; schema field is ``guiding_frame_noise``."""
    cfg = {**_MINIMAL_DRAW_THINGS_STYLE, "guidingFrameNoise": 0.05}
    blob = json_configuration_to_flatbuffer(cfg)
    assert isinstance(blob, bytes)
    assert len(blob) >= 32


@pytest.mark.skipif(not shutil.which("flatc"), reason="flatc not on PATH")
def test_flatc_accepts_motion_scale_from_draw_things_camel_case() -> None:
    """Regression: Draw Things exports ``motionScale``; schema field is ``motion_scale``."""
    cfg = {**_MINIMAL_DRAW_THINGS_STYLE, "motionScale": 1.5}
    blob = json_configuration_to_flatbuffer(cfg)
    assert isinstance(blob, bytes)
    assert len(blob) >= 32


@pytest.mark.skipif(not shutil.which("flatc"), reason="flatc not on PATH")
def test_flatc_accepts_stage2_guidance_from_draw_things_camel_case() -> None:
    """Regression: Draw Things exports ``stage2Guidance``; schema field is ``stage_2_guidance``."""
    cfg = {**_MINIMAL_DRAW_THINGS_STYLE, "stage2Guidance": 3.0}
    blob = json_configuration_to_flatbuffer(cfg)
    assert isinstance(blob, bytes)
    assert len(blob) >= 32
