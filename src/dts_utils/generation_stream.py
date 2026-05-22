"""Collect streamed image tensors from Draw Things ImageGenerationService."""

from __future__ import annotations

import os
import sys

from dts_utils.grpc.proto.upstream import imageService_pb2 as up_pb2
from dts_utils.grpc.proto.upstream import imageService_pb2_grpc as up_grpc
from dts_utils.tensor_png import decode_dt_tensor_to_png

_DEBUG_ENV = "DTS_GRPC_GENERATE_DEBUG"
_DEBUG_PREFIX = "[dts-utils] GenerateImage stream:"


def _grpc_generate_debug_enabled() -> bool:
    return os.environ.get(_DEBUG_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


def _current_signpost_set(response: object) -> bool:
    hf = getattr(response, "HasField", None)
    if callable(hf):
        try:
            return bool(hf("currentSignpost"))
        except (ValueError, AttributeError):
            pass
    return getattr(response, "currentSignpost", None) is not None


def _debug_log_stream_message(seq: int, response: object) -> None:
    """One stderr line per streamed message (counts only; no tensor/preview bytes)."""
    gi = list(getattr(response, "generatedImages", None) or [])
    parts = [
        f"seq={seq}",
        f"generatedImages_count={len(gi)}",
    ]
    if gi:
        parts.append(f"first_generatedImage_bytes={len(gi[0])}")
    cs = getattr(response, "chunkState", up_pb2.LAST_CHUNK)
    try:
        cs_name = up_pb2.ChunkState.Name(cs)
    except ValueError:
        cs_name = str(int(cs))
    parts.append(f"chunkState={cs_name}")
    pv = getattr(response, "previewImage", b"") or b""
    parts.append(f"previewImage_bytes={len(pv)}")
    sp = getattr(response, "signposts", None) or []
    parts.append(f"signposts_count={len(sp)}")
    parts.append(f"currentSignpost_set={str(_current_signpost_set(response)).lower()}")
    tags = getattr(response, "tags", None) or []
    parts.append(f"tags_count={len(tags)}")
    rd = getattr(response, "remoteDownload", None)
    if rd is not None:
        parts.append(
            "remoteDownload="
            f"received={getattr(rd, 'bytesReceived', '?')}"
            f" expected={getattr(rd, 'bytesExpected', '?')}"
            f" item={getattr(rd, 'item', '?')}"
            f" itemsExpected={getattr(rd, 'itemsExpected', '?')}"
        )
    print(f"{_DEBUG_PREFIX} {' '.join(parts)}", file=sys.stderr, flush=True)


def _preview_payload_if_decodable_tensor(preview: bytes) -> bytes | None:
    """Return *preview* if it looks like Draw Things tensor bytes (same as ``generatedImages`` entries)."""
    if len(preview) < 68:
        return None
    try:
        decode_dt_tensor_to_png(preview)
    except Exception:
        return None
    return preview


def collect_generated_images(stub: up_grpc.ImageGenerationServiceStub, request: up_pb2.ImageGenerationRequest) -> list[bytes]:
    images = []
    pending_chunk = b""
    debug = _grpc_generate_debug_enabled()
    best_preview: bytes | None = None
    best_preview_len = 0
    for seq, response in enumerate(stub.GenerateImage(request)):
        if debug:
            _debug_log_stream_message(seq, response)
        pv = getattr(response, "previewImage", b"") or b""
        if pv:
            ok = _preview_payload_if_decodable_tensor(pv)
            if ok is not None and len(pv) > best_preview_len:
                best_preview_len = len(pv)
                best_preview = ok
        if not response.generatedImages:
            continue

        chunk_state = getattr(response, "chunkState", up_pb2.LAST_CHUNK)
        if chunk_state == up_pb2.MORE_CHUNKS:
            pending_chunk += response.generatedImages[0]
            continue

        response_images = list(response.generatedImages)
        if pending_chunk:
            response_images[0] = pending_chunk + response_images[0]
            pending_chunk = b""
        images.extend(response_images)
    if not images and best_preview is not None:
        images.append(best_preview)
    return images
