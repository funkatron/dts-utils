"""Typed programmatic API for Draw Things image generation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import grpc

from dts_util.configuration_build import read_configuration_bytes
from dts_util.exceptions import ChannelSetupError, GenerationEmptyError, GenerationRpcError
from dts_util.prompt_wildcards import expand_prompt_wildcards
from dts_util.generation_stream import collect_generated_images
from dts_util.grpc.connection import create_channel
from dts_util.grpc.proto.upstream import imageService_pb2 as up_pb2
from dts_util.grpc.proto.upstream import imageService_pb2_grpc as up_grpc
from dts_util.image_output import unique_ms_timestamp_output_path, write_images
from dts_util.tensor_png import decode_dt_tensor_to_png


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


def generate_png_bytes(client: GrpcClientOptions, gen: ImageGenerationRequestOptions) -> list[bytes]:
    request = build_image_generation_request(gen)
    tensors = collect_raw_generation_tensors(client, request)
    if not tensors:
        raise GenerationEmptyError("No generated images returned by the server.")
    return [decode_dt_tensor_to_png(tensor) for tensor in tensors]


def generate_to_paths(
    client: GrpcClientOptions,
    gen: ImageGenerationRequestOptions,
    output_base: Path,
) -> list[Path]:
    request = build_image_generation_request(gen)
    tensors = collect_raw_generation_tensors(client, request)
    if not tensors:
        raise GenerationEmptyError("No generated images returned by the server.")
    return write_images(tensors, unique_ms_timestamp_output_path(output_base))
