"""gRPC integration tests against Draw Things (upstream ``imageService.proto``).

Opt-in subprocess server: set ``DTS_GRPC_TEST_SPAWN_SERVER=1`` — see ``tests/README.md``
§ Ephemeral server. Uses :fixture:`live_upstream_stub` (plaintext to ephemeral port).

Legacy ``image_generation.proto`` coverage was removed here; unary ``GenerateImage`` in that
proto does not match the live server. Full-stack generation is in
``tests/test_generate_functional_live.py``.
"""

from __future__ import annotations

from contextlib import contextmanager

import grpc
import pytest

from dts_utils.grpc.proto.upstream import imageService_pb2 as up_pb2
from dts_utils.grpc.proto.upstream import imageService_pb2_grpc as up_grpc

from ephemeral_grpc_server import resolve_models_directory


@contextmanager
def handle_grpc_error():
    try:
        yield
    except grpc.RpcError as e:
        if isinstance(e, grpc._channel._InactiveRpcError):
            if e.code() == grpc.StatusCode.UNAVAILABLE:
                pytest.skip("Server became unavailable during test")
            raise
        raise


@pytest.mark.integration
@pytest.mark.live_grpc_cli
def test_upstream_echo(live_upstream_stub):
    with handle_grpc_error():
        reply = live_upstream_stub.Echo(up_pb2.EchoRequest(name="dts-utils-integration"))
        assert isinstance(reply.message, str)


@pytest.mark.integration
@pytest.mark.live_grpc_cli
def test_upstream_files_exist_empty(live_upstream_stub):
    with handle_grpc_error():
        reply = live_upstream_stub.FilesExist(up_pb2.FileListRequest())
        assert list(reply.files) == []
        assert list(reply.existences) == []


@pytest.mark.integration
@pytest.mark.live_grpc_cli
def test_upstream_files_exist_nonexistent(live_upstream_stub):
    with handle_grpc_error():
        names = ["nonexistent1.safetensors", "nonexistent2.safetensors"]
        reply = live_upstream_stub.FilesExist(up_pb2.FileListRequest(files=names))
        assert list(reply.files) == names
        assert len(reply.existences) == len(names)
        assert all(not x for x in reply.existences)


@pytest.mark.integration
@pytest.mark.live_grpc_cli
def test_upstream_files_exist_local_checkpoint(live_upstream_stub):
    """Resolve at least one real checkpoint path under the spawned server's models root."""
    models = resolve_models_directory()
    assert models is not None
    found = sorted(models.glob("**/*.safetensors")) + sorted(models.glob("**/*.ckpt"))
    if not found:
        pytest.skip("No checkpoints under models directory")

    rel = found[0].relative_to(models).as_posix()
    with handle_grpc_error():
        reply = live_upstream_stub.FilesExist(up_pb2.FileListRequest(files=[rel]))
    assert list(reply.files) == [rel]
    assert list(reply.existences) == [True]


@pytest.mark.integration
@pytest.mark.live_grpc_cli
@pytest.mark.skip(reason="UploadFile streaming test not implemented")
def test_upload_file():
    """Placeholder — implement against upstream ``UploadFile`` when needed."""
    pass  # pragma: no cover


def test_connection_error():
    """Wrong port should fail fast (no ephemeral server)."""
    with pytest.raises(grpc.RpcError):
        with grpc.insecure_channel("localhost:12345") as channel:
            stub = up_grpc.ImageGenerationServiceStub(channel)
            stub.Echo(up_pb2.EchoRequest())
