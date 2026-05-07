"""Typed programmatic API for Draw Things image generation."""

from __future__ import annotations

import base64
import dataclasses
import time
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
import threading

import grpc

from dts_utils.configuration_build import read_configuration_bytes
from dts_utils.exceptions import (
    ChannelSetupError,
    ConfigurationError,
    GenerationCancelledError,
    GenerationEmptyError,
    GenerationRpcError,
)
from dts_utils.prompt_wildcards import expand_prompt_wildcards
from dts_utils.generation_stream import collect_generated_images
from dts_utils.grpc.connection import create_channel
from dts_utils.grpc.proto.upstream import imageService_pb2 as up_pb2
from dts_utils.grpc.proto.upstream import imageService_pb2_grpc as up_grpc
from dts_utils.image_output import unique_ms_timestamp_output_path, write_images
from dts_utils.tensor_png import decode_dt_tensor_to_png

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
    configuration = read_configuration_bytes(
        configuration=gen.configuration,
        configuration_json=gen.configuration_json,
        config_dir=gen.config_dir,
    )
    prompt_expanded = expand_prompt_wildcards(gen.prompt)
    neg_raw = gen.negative_prompt or ""
    negative_expanded = expand_prompt_wildcards(neg_raw) if neg_raw.strip() else ""
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
    return request, prompt_expanded, negative_expanded


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


def _validate_per_run_prompt_lengths(
    n: int,
    prompts_per_run: Sequence[str] | None,
    negative_prompts_per_run: Sequence[str] | None,
) -> None:
    if prompts_per_run is not None and len(prompts_per_run) != n:
        raise ConfigurationError("'prompts' length must equal generations.")
    if negative_prompts_per_run is not None and len(negative_prompts_per_run) != n:
        raise ConfigurationError("'negative_prompts' length must equal generations.")


def _generation_runs_iter(
    client: GrpcClientOptions,
    gen: ImageGenerationRequestOptions,
    n: int,
    cancel_event: threading.Event | None,
    prompts_per_run: Sequence[str] | None,
    negative_prompts_per_run: Sequence[str] | None,
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
) -> GeneratePngBatchResult:
    n = validate_batch_generations(generations)
    _validate_per_run_prompt_lengths(n, prompts_per_run, negative_prompts_per_run)
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
) -> Iterator[dict[str, object]]:
    """Yield serializable dicts for SSE: meta, progress (once per generation run), image (per PNG; multiple per run if the server returns several tensors), done."""
    n = validate_batch_generations(generations)
    _validate_per_run_prompt_lengths(n, prompts_per_run, negative_prompts_per_run)
    yield {"type": "meta", "total_runs": n}
    global_idx = 0
    expanded_prompts: list[str] = []
    expanded_negatives: list[str] = []
    for i, ep, en, run_pngs in _generation_runs_iter(
        client,
        gen,
        n,
        cancel_event,
        prompts_per_run,
        negative_prompts_per_run,
    ):
        expanded_prompts.append(ep)
        expanded_negatives.append(en)
        yield {"type": "progress", "run": i + 1, "total_runs": n}
        for png in run_pngs:
            global_idx += 1
            yield {
                "type": "image",
                "run": i + 1,
                "index": global_idx,
                "png_b64": base64.standard_b64encode(png).decode("ascii"),
            }
    yield {
        "type": "done",
        "expanded_prompts": expanded_prompts,
        "expanded_negative_prompts": expanded_negatives,
        "total_images": global_idx,
    }


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
) -> list[Path]:
    n = validate_batch_generations(generations)
    if n == 1:
        request, _, _ = prepare_image_generation_request(gen)
        tensors = collect_raw_generation_tensors(client, request)
        if not tensors:
            raise GenerationEmptyError("No generated images returned by the server.")
        return write_images(tensors, unique_ms_timestamp_output_path(output_base))
    stamp = time.time_ns()
    paths_out: list[Path] = []
    for i in range(n):
        batch_base = output_base.with_name(f"{output_base.stem}-{stamp}-{i}{output_base.suffix}")
        request, _, _ = prepare_image_generation_request(gen)
        tensors = collect_raw_generation_tensors(client, request)
        if not tensors:
            raise GenerationEmptyError("No generated images returned by the server.")
        paths_out.extend(write_images(tensors, unique_ms_timestamp_output_path(batch_base)))
    return paths_out
