"""Collect streamed image tensors from Draw Things ImageGenerationService."""

from __future__ import annotations

from dts_util.grpc.proto.upstream import imageService_pb2 as up_pb2
from dts_util.grpc.proto.upstream import imageService_pb2_grpc as up_grpc


def collect_generated_images(stub: up_grpc.ImageGenerationServiceStub, request: up_pb2.ImageGenerationRequest) -> list[bytes]:
    images = []
    pending_chunk = b""
    for response in stub.GenerateImage(request):
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
    return images
