"""Typed programmatic API for Draw Things image generation."""

from __future__ import annotations

import base64
import dataclasses
import io
import time
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
import threading

import grpc

from dts_utils.configuration_build import read_configuration_bytes, read_configuration_json_dict
from dts_utils.exceptions import (
    ChannelSetupError,
    ConfigurationError,
    GenerationCancelledError,
    GenerationEmptyError,
    GenerationRpcError,
)
from dts_utils.prompt_wildcards import expand_prompt_wildcards
from dts_utils.generation_stream import collect_generated_images, iter_generate_image_stream
from dts_utils.grpc.connection import create_channel
from dts_utils.grpc.proto.upstream import imageService_pb2 as up_pb2
from dts_utils.grpc.proto.upstream import imageService_pb2_grpc as up_grpc
from dts_utils.image_output import unique_ms_timestamp_output_path, write_images
from dts_utils.input_image import normalize_input_image_path
from PIL import Image

from dts_utils.tensor_png import decode_dt_tensor_to_png, encode_png_to_dt_tensor

# Independent RPC runs per UI/API/CLI request (each run re-expands `{…}` wildcards).
MAX_BATCH_GENERATIONS = 25


def validate_batch_generations(n: int) -> int:
    if not isinstance(n, int) or isinstance(n, bool):
        raise ConfigurationError("generations must be an integer.")
    if n < 1:
        raise ConfigurationError("generations must be at least 1.")
    if n > MAX_BATCH_GENERATIONS:
        raise ConfigurationError(f"generations must be at most {MAX_BATCH_GENERATIONS}.")
    return n


def coerce_generations_json(value: object) -> int:
    """JSON body helper: missing or null → 1; otherwise validate integer."""
    if value is None:
        return 1
    if isinstance(value, bool):
        raise ConfigurationError("generations must be an integer.")
    if isinstance(value, int):
        return validate_batch_generations(value)
    raise ConfigurationError("generations must be an integer.")


def expand_prompt_templates_for_batch(
    prompt: str,
    negative_prompt: str,
    *,
    count: int,
) -> tuple[list[str], list[str]]:
    """Expand `{…}` templates *count* times—once per item—with independent random choices each time.

    Matches generation behavior: each call uses `expand_prompt_wildcards` exactly as when building
    a single image RPC (same brace rules and random picks per block). There is no shared random
    state across iterations; preview batches behave like *count* separate expansions."""
    n = validate_batch_generations(count)
    neg_in = negative_prompt.strip()
    prompts_out: list[str] = []
    negatives_out: list[str] = []
    for _ in range(n):
        prompts_out.append(expand_prompt_wildcards(prompt))
        negatives_out.append(expand_prompt_wildcards(neg_in) if neg_in else "")
    return prompts_out, negatives_out


@dataclass(frozen=True)
class GrpcClientOptions:
    host: str = "localhost"
    port: int = 7859
    no_tls: bool = False
    root_cert: Path | None = None
    trust_server_cert: bool = False
    force_trust_server_cert: bool = False
    max_message_mb: int = 64


@dataclass(frozen=True)
class ImageGenerationRequestOptions:
    prompt: str
    negative_prompt: str = ""
    configuration: str | Path | None = None
    configuration_json: str | Path | None = None
    user: str = "dts-utils"
    shared_secret: str | None = None
    config_dir: Path | None = None
    input_image_path: Path | None = None


@dataclass(frozen=True)
class GeneratePngBatchResult:
    """One multipart-capable generation round: PNG bytes plus prompts actually sent (after wildcard expansion)."""

    images: list[bytes]
    expanded_prompts: list[str]
    expanded_negative_prompts: list[str]


def prepare_image_generation_request(
    gen: ImageGenerationRequestOptions,
) -> tuple[up_pb2.ImageGenerationRequest, str, str]:
    """Build the gRPC request and return expanded prompt strings (same values set on *request*)."""
    # Expand `{…}` templates before configuration I/O so invalid templates fail fast (e.g. HTTP 400)
    # even when `flatc` or saved JSON is unavailable — matches `/api/prompt/expand` semantics.
    prompt_expanded = expand_prompt_wildcards(gen.prompt)
    neg_raw = gen.negative_prompt or ""
    negative_expanded = expand_prompt_wildcards(neg_raw) if neg_raw.strip() else ""
    configuration = read_configuration_bytes(
        configuration=gen.configuration,
        configuration_json=gen.configuration_json,
        config_dir=gen.config_dir,
    )
    request = up_pb2.ImageGenerationRequest(
        prompt=prompt_expanded,
        negativePrompt=negative_expanded,
        scaleFactor=1,
        configuration=configuration,
        chunked=True,
        user=gen.user,
        device=up_pb2.LAPTOP,
    )
    if gen.shared_secret:
        request.sharedSecret = gen.shared_secret
    if gen.input_image_path is not None:
        png_bytes = normalize_input_image_path(gen.input_image_path)
        request.image = encode_png_to_dt_tensor(png_bytes)
    return request, prompt_expanded, negative_expanded


def configuration_output_fps(gen: ImageGenerationRequestOptions, *, default: int = 24) -> int:
    """Best-effort FPS from a saved JSON profile (mux fallback when the server omits timing)."""
    try:
        cfg = read_configuration_json_dict(
            configuration=gen.configuration,
            configuration_json=gen.configuration_json,
            config_dir=gen.config_dir,
        )
    except ConfigurationError:
        return default
    for key in ("frames_per_second", "fps", "fps_id"):
        value = cfg.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            fps = int(value)
            if fps > 0:
                return fps
    return default


def build_image_generation_request(gen: ImageGenerationRequestOptions) -> up_pb2.ImageGenerationRequest:
    req, _, _ = prepare_image_generation_request(gen)
    return req


def _open_channel(client: GrpcClientOptions) -> grpc.Channel:
    try:
        return create_channel(
            client.host,
            client.port,
            client.no_tls,
            root_cert=client.root_cert,
            trust_server_cert=client.trust_server_cert,
            force_trust_server_cert=client.force_trust_server_cert,
            max_message_mb=client.max_message_mb,
        )
    except (OSError, ValueError) as e:
        raise ChannelSetupError(str(e)) from e


def collect_raw_generation_tensors(
    client: GrpcClientOptions,
    request: up_pb2.ImageGenerationRequest,
) -> list[bytes]:
    channel = _open_channel(client)
    try:
        stub = up_grpc.ImageGenerationServiceStub(channel)
        try:
            return collect_generated_images(stub, request)
        except grpc.RpcError as e:
            raise GenerationRpcError.from_rpc_error(e) from e
    finally:
        close = getattr(channel, "close", None)
        if close:
            close()


def _iter_generation_run_png_stream(
    client: GrpcClientOptions,
    request: up_pb2.ImageGenerationRequest,
    cancel_event: threading.Event | None,
) -> Iterator[tuple[str, bytes]]:
    """Yield ``(kind, payload)`` where *kind* is ``preview`` (PNG bytes) or ``image`` (PNG bytes)."""
    channel = _open_channel(client)
    try:
        stub = up_grpc.ImageGenerationServiceStub(channel)
        try:
            for kind, payload in iter_generate_image_stream(stub, request):
                if cancel_event is not None and cancel_event.is_set():
                    raise GenerationCancelledError("Generation cancelled.")
                if kind == "preview":
                    yield ("preview", payload)
                else:
                    yield ("image", decode_dt_tensor_to_png(payload))
        except grpc.RpcError as e:
            raise GenerationRpcError.from_rpc_error(e) from e
    finally:
        close = getattr(channel, "close", None)
        if close:
            close()


def _validate_per_run_prompt_lengths(
    n: int,
    prompts_per_run: Sequence[str] | None,
    negative_prompts_per_run: Sequence[str] | None,
) -> None:
    if prompts_per_run is not None and len(prompts_per_run) != n:
        raise ConfigurationError("'prompts' length must equal generations.")
    if negative_prompts_per_run is not None and len(negative_prompts_per_run) != n:
        raise ConfigurationError("'negative_prompts' length must equal generations.")


def _validate_input_images_per_run(
    n: int,
    input_images_per_run: Sequence[Path | None] | None,
) -> None:
    if input_images_per_run is not None and len(input_images_per_run) != n:
        raise ConfigurationError("'input_images' length must equal generations.")


def _generation_runs_iter(
    client: GrpcClientOptions,
    gen: ImageGenerationRequestOptions,
    n: int,
    cancel_event: threading.Event | None,
    prompts_per_run: Sequence[str] | None,
    negative_prompts_per_run: Sequence[str] | None,
    input_images_per_run: Sequence[Path | None] | None = None,
) -> Iterator[tuple[int, str, str, list[bytes]]]:
    """Yield ``(run_index_zero_based, expanded_prompt, expanded_negative, png_bytes_for_run)`` per generation RPC."""
    for i in range(n):
        if cancel_event is not None and cancel_event.is_set():
            raise GenerationCancelledError("Generation cancelled.")
        g = gen
        if prompts_per_run is not None:
            g = dataclasses.replace(g, prompt=prompts_per_run[i])
        if negative_prompts_per_run is not None:
            g = dataclasses.replace(g, negative_prompt=negative_prompts_per_run[i])
        if input_images_per_run is not None:
            image_path = input_images_per_run[i]
            g = dataclasses.replace(g, input_image_path=image_path)
        request, ep, en = prepare_image_generation_request(g)
        tensors = collect_raw_generation_tensors(client, request)
        if not tensors:
            raise GenerationEmptyError("No generated images returned by the server.")
        pngs = [decode_dt_tensor_to_png(tensor) for tensor in tensors]
        yield i, ep, en, pngs


def generate_png_batch(
    client: GrpcClientOptions,
    gen: ImageGenerationRequestOptions,
    *,
    generations: int = 1,
    cancel_event: threading.Event | None = None,
    prompts_per_run: Sequence[str] | None = None,
    negative_prompts_per_run: Sequence[str] | None = None,
    input_images_per_run: Sequence[Path | None] | None = None,
) -> GeneratePngBatchResult:
    n = validate_batch_generations(generations)
    _validate_per_run_prompt_lengths(n, prompts_per_run, negative_prompts_per_run)
    _validate_input_images_per_run(n, input_images_per_run)
    pngs: list[bytes] = []
    expanded_prompts: list[str] = []
    expanded_negatives: list[str] = []
    for _i, ep, en, run_pngs in _generation_runs_iter(
        client,
        gen,
        n,
        cancel_event,
        prompts_per_run,
        negative_prompts_per_run,
        input_images_per_run,
    ):
        expanded_prompts.append(ep)
        expanded_negatives.append(en)
        pngs.extend(run_pngs)
    return GeneratePngBatchResult(
        images=pngs,
        expanded_prompts=expanded_prompts,
        expanded_negative_prompts=expanded_negatives,
    )


def iter_generate_stream_dicts(
    client: GrpcClientOptions,
    gen: ImageGenerationRequestOptions,
    *,
    generations: int = 1,
    cancel_event: threading.Event | None = None,
    prompts_per_run: Sequence[str] | None = None,
    negative_prompts_per_run: Sequence[str] | None = None,
    input_images_per_run: Sequence[Path | None] | None = None,
) -> Iterator[dict[str, object]]:
    """Yield serializable dicts for SSE: meta, progress, preview (live frames), image, done."""
    n = validate_batch_generations(generations)
    _validate_per_run_prompt_lengths(n, prompts_per_run, negative_prompts_per_run)
    _validate_input_images_per_run(n, input_images_per_run)
    yield {"type": "meta", "total_runs": n}
    global_idx = 0
    expanded_prompts: list[str] = []
    expanded_negatives: list[str] = []
    for i in range(n):
        if cancel_event is not None and cancel_event.is_set():
            raise GenerationCancelledError("Generation cancelled.")
        g = gen
        if prompts_per_run is not None:
            g = dataclasses.replace(g, prompt=prompts_per_run[i])
        if negative_prompts_per_run is not None:
            g = dataclasses.replace(g, negative_prompt=negative_prompts_per_run[i])
        if input_images_per_run is not None:
            g = dataclasses.replace(g, input_image_path=input_images_per_run[i])
        request, ep, en = prepare_image_generation_request(g)
        expanded_prompts.append(ep)
        expanded_negatives.append(en)
        yield {"type": "progress", "run": i + 1, "total_runs": n}
        preview_seq = 0
        run_pngs: list[bytes] = []
        for kind, png in _iter_generation_run_png_stream(client, request, cancel_event):
            if kind == "preview":
                preview_seq += 1
                yield {
                    "type": "preview",
                    "run": i + 1,
                    "total_runs": n,
                    "seq": preview_seq,
                    "png_b64": base64.standard_b64encode(png).decode("ascii"),
                }
            else:
                run_pngs.append(png)
                global_idx += 1
                yield {
                    "type": "image",
                    "run": i + 1,
                    "total_runs": n,
                    "index": global_idx,
                    "png_b64": base64.standard_b64encode(png).decode("ascii"),
                }
        if not run_pngs and preview_seq == 0:
            raise GenerationEmptyError("No generated images returned by the server.")
    yield {
        "type": "done",
        "expanded_prompts": expanded_prompts,
        "expanded_negative_prompts": expanded_negatives,
        "total_images": global_idx,
    }


def generate_video_mp4_bytes(
    client: GrpcClientOptions,
    gen: ImageGenerationRequestOptions,
    *,
    input_image_path: Path,
    output_fps: int | None = None,
    scale_width: int | None = None,
    scale_height: int | None = None,
) -> tuple[bytes, dict[str, object]]:
    """Run Draw Things ``GenerateImage`` with an input image tensor and mux returned frames to MP4."""
    from dts_utils.pipeline.video_encode import png_frames_to_mp4

    gen_with_image = dataclasses.replace(gen, input_image_path=input_image_path)
    request, prompt_expanded, negative_expanded = prepare_image_generation_request(gen_with_image)
    tensors = collect_raw_generation_tensors(client, request)
    if not tensors:
        raise GenerationEmptyError("No generated frames returned by the server.")
    frame_pngs = [decode_dt_tensor_to_png(tensor) for tensor in tensors]
    fps = output_fps if output_fps is not None else configuration_output_fps(gen_with_image)
    mp4 = png_frames_to_mp4(
        frame_pngs,
        fps=fps,
        width=scale_width,
        height=scale_height,
    )
    seconds = len(frame_pngs) / float(fps)
    meta: dict[str, object] = {
        "frame_count": len(frame_pngs),
        "fps": fps,
        "seconds": seconds,
        "source": "drawthings_grpc",
        "motion": "drawthings_frames",
        "expanded_prompt": prompt_expanded,
        "expanded_negative_prompt": negative_expanded,
    }
    width = scale_width
    height = scale_height
    if width is None or height is None:
        with Image.open(io.BytesIO(frame_pngs[0])) as img:
            width = width or img.size[0]
            height = height or img.size[1]
    meta["width"] = int(width)
    meta["height"] = int(height)
    return mp4, meta


def generate_png_bytes(
    client: GrpcClientOptions,
    gen: ImageGenerationRequestOptions,
    *,
    generations: int = 1,
    cancel_event: threading.Event | None = None,
) -> list[bytes]:
    return generate_png_batch(client, gen, generations=generations, cancel_event=cancel_event).images


def generate_to_paths(
    client: GrpcClientOptions,
    gen: ImageGenerationRequestOptions,
    output_base: Path,
    *,
    generations: int = 1,
    input_images_per_run: Sequence[Path | None] | None = None,
) -> list[Path]:
    n = validate_batch_generations(generations)
    _validate_input_images_per_run(n, input_images_per_run)
    if n == 1 and input_images_per_run is None:
        request, _, _ = prepare_image_generation_request(gen)
        tensors = collect_raw_generation_tensors(client, request)
        if not tensors:
            raise GenerationEmptyError("No generated images returned by the server.")
        return write_images(tensors, unique_ms_timestamp_output_path(output_base))
    stamp = time.time_ns()
    paths_out: list[Path] = []
    for i in range(n):
        batch_base = output_base.with_name(f"{output_base.stem}-{stamp}-{i}{output_base.suffix}")
        g = gen
        if input_images_per_run is not None:
            g = dataclasses.replace(g, input_image_path=input_images_per_run[i])
        request, _, _ = prepare_image_generation_request(g)
        tensors = collect_raw_generation_tensors(client, request)
        if not tensors:
            raise GenerationEmptyError("No generated images returned by the server.")
        paths_out.extend(write_images(tensors, unique_ms_timestamp_output_path(batch_base)))
    return paths_out
