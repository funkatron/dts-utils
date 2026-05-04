"""Typed programmatic API for Draw Things image generation."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
import threading

import grpc

from dts_util.configuration_build import read_configuration_bytes
from dts_util.exceptions import (
    ChannelSetupError,
    ConfigurationError,
    GenerationCancelledError,
    GenerationEmptyError,
    GenerationRpcError,
)
from dts_util.prompt_wildcards import expand_prompt_wildcards
from dts_util.generation_stream import collect_generated_images
from dts_util.grpc.connection import create_channel
from dts_util.grpc.proto.upstream import imageService_pb2 as up_pb2
from dts_util.grpc.proto.upstream import imageService_pb2_grpc as up_grpc
from dts_util.image_output import unique_ms_timestamp_output_path, write_images
from dts_util.tensor_png import decode_dt_tensor_to_png

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
    user: str = "dts-util"
    shared_secret: str | None = None
    config_dir: Path | None = None


def build_image_generation_request(gen: ImageGenerationRequestOptions) -> up_pb2.ImageGenerationRequest:
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
    return request


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


def generate_png_bytes(
    client: GrpcClientOptions,
    gen: ImageGenerationRequestOptions,
    *,
    generations: int = 1,
    cancel_event: threading.Event | None = None,
) -> list[bytes]:
    n = validate_batch_generations(generations)
    pngs: list[bytes] = []
    for _ in range(n):
        if cancel_event is not None and cancel_event.is_set():
            raise GenerationCancelledError("Generation cancelled.")
        request = build_image_generation_request(gen)
        tensors = collect_raw_generation_tensors(client, request)
        if not tensors:
            raise GenerationEmptyError("No generated images returned by the server.")
        pngs.extend(decode_dt_tensor_to_png(tensor) for tensor in tensors)
    return pngs


def generate_to_paths(
    client: GrpcClientOptions,
    gen: ImageGenerationRequestOptions,
    output_base: Path,
    *,
    generations: int = 1,
) -> list[Path]:
    n = validate_batch_generations(generations)
    if n == 1:
        request = build_image_generation_request(gen)
        tensors = collect_raw_generation_tensors(client, request)
        if not tensors:
            raise GenerationEmptyError("No generated images returned by the server.")
        return write_images(tensors, unique_ms_timestamp_output_path(output_base))
    stamp = time.time_ns()
    paths_out: list[Path] = []
    for i in range(n):
        batch_base = output_base.with_name(f"{output_base.stem}-{stamp}-{i}{output_base.suffix}")
        request = build_image_generation_request(gen)
        tensors = collect_raw_generation_tensors(client, request)
        if not tensors:
            raise GenerationEmptyError("No generated images returned by the server.")
        paths_out.extend(write_images(tensors, unique_ms_timestamp_output_path(batch_base)))
    return paths_out
