"""Live ``gRPCServerCLI`` tests using the **upstream** proto (same stack as ``generate``).

Opt-in: does not run in CI unless you set ``DTS_GRPC_TEST_SPAWN_SERVER=1`` and satisfy
``tests/README.md`` prerequisites. See ``PROTOBUF.md`` § gRPC integration tests.

``tests/test_grpc_server.py`` still targets the legacy ``image_generation.proto`` and a fixed
port — keep new assertions here so assumptions stay aligned with production clients.

Uses the shared ``spawned_live_cli`` session fixture from ``conftest.py``.
"""

from __future__ import annotations

import pytest

from dts_utils.grpc.connection import create_channel
from dts_utils.grpc.proto.upstream import imageService_pb2 as up_pb2
from dts_utils.grpc.proto.upstream import imageService_pb2_grpc as up_grpc


@pytest.mark.integration
@pytest.mark.live_grpc_cli
def test_upstream_echo(spawned_live_cli):
    host, port = spawned_live_cli
    channel = create_channel(host, port, insecure=True)
    try:
        stub = up_grpc.ImageGenerationServiceStub(channel)
        reply = stub.Echo(up_pb2.EchoRequest(name="dts-utils-ephemeral-test"))
        assert isinstance(reply.message, str)
    finally:
        channel.close()


@pytest.mark.integration
@pytest.mark.live_grpc_cli
def test_upstream_files_exist_empty(spawned_live_cli):
    host, port = spawned_live_cli
    channel = create_channel(host, port, insecure=True)
    try:
        stub = up_grpc.ImageGenerationServiceStub(channel)
        reply = stub.FilesExist(up_pb2.FileListRequest())
        assert list(reply.files) == []
        assert list(reply.existences) == []
    finally:
        channel.close()
