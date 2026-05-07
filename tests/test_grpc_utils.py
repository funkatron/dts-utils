import pytest
import grpc
from unittest.mock import patch, MagicMock
from dts_utils.grpc.utils import is_server_running, handle_grpc_error, create_channel_and_stub
from dts_utils.grpc.proto.image_generation_pb2_grpc import ImageGenerationServiceStub


class _FakeRpcError(grpc.RpcError):
    """Minimal grpc.RpcError for testing handle_grpc_error."""

    def __init__(self, code: grpc.StatusCode) -> None:
        self._code = code

    def code(self) -> grpc.StatusCode:
        return self._code


def test_is_server_running_nonexistent():
    """Test that is_server_running returns False for non-existent server."""
    assert not is_server_running(port=65432, timeout=0.1)


def test_is_server_running_invalid_host():
    """Test that is_server_running handles invalid hostnames gracefully."""
    assert not is_server_running(host="nonexistent.local", timeout=0.1)


def test_is_server_running_zero_timeout():
    """Test that is_server_running works with zero timeout."""
    assert not is_server_running(timeout=0)


def test_handle_grpc_error_unavailable():
    """UNAVAILABLE RpcError maps to ConnectionError."""
    err = _FakeRpcError(grpc.StatusCode.UNAVAILABLE)
    with pytest.raises(ConnectionError, match="Server is unavailable"):
        with handle_grpc_error():
            raise err


def test_handle_grpc_error_other():
    """Non-UNAVAILABLE gRPC errors propagate unchanged."""
    err = _FakeRpcError(grpc.StatusCode.INVALID_ARGUMENT)
    with pytest.raises(_FakeRpcError) as excinfo:
        with handle_grpc_error():
            raise err
    assert excinfo.value is err


def test_create_channel_and_stub_insecure():
    """Test that create_channel_and_stub creates insecure channels correctly."""
    with patch("grpc.insecure_channel") as mock_channel, patch(
        "dts_utils.grpc.utils.is_server_running", return_value=True
    ):
        mock_channel.return_value = MagicMock()
        channel, stub = create_channel_and_stub(use_tls=False)
        mock_channel.assert_called_once()
        assert isinstance(stub, ImageGenerationServiceStub)


def test_create_channel_and_stub_shared_secret():
    """Test that create_channel_and_stub adds shared secret to options."""
    with patch("grpc.insecure_channel") as mock_channel, patch(
        "dts_utils.grpc.utils.is_server_running", return_value=True
    ):
        mock_channel.return_value = MagicMock()
        create_channel_and_stub(use_tls=False, shared_secret="test_secret")
        mock_channel.assert_called_once()
        call_args = mock_channel.call_args[1]
        assert ("grpc.primary_user_agent", "secret=test_secret") in call_args["options"]


def test_create_channel_and_stub_server_not_running():
    """Test that create_channel_and_stub raises ConnectionError when server is not running."""
    with patch("dts_utils.grpc.utils.is_server_running", return_value=False):
        with pytest.raises(ConnectionError, match="Unable to connect to server"):
            create_channel_and_stub(port=65432)  # Use a port that's not running
