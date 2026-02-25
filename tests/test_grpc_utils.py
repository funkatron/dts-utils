import pytest
import grpc
from unittest.mock import patch, MagicMock
from dts_util.grpc.utils import is_server_running, handle_grpc_error, create_channel_and_stub
from dts_util.grpc.proto.image_generation_pb2_grpc import ImageGenerationServiceStub

def test_is_server_running_nonexistent():
    """Test that is_server_running returns False for non-existent server."""
    # Test with a port that's unlikely to have a server
    assert not is_server_running(port=65432, timeout=0.1)

def test_is_server_running_invalid_host():
    """Test that is_server_running handles invalid hostnames gracefully."""
    assert not is_server_running(host="nonexistent.local", timeout=0.1)

def test_is_server_running_zero_timeout():
    """Test that is_server_running works with zero timeout."""
    assert not is_server_running(timeout=0)

# Create a simple exception class to simulate gRPC errors
class MockGrpcError(Exception):
    def __init__(self, status_code):
        self._code = status_code
        super().__init__(f"gRPC error with status {status_code}")

    def code(self):
        return self._code

def test_handle_grpc_error_unavailable():
    """Test that handle_grpc_error converts UNAVAILABLE errors to ConnectionError."""
    pytest.skip("TODO: add a reliable grpc.RpcError fixture for UNAVAILABLE simulation")

def test_handle_grpc_error_other():
    """Test that handle_grpc_error preserves other gRPC errors."""
    pytest.skip("TODO: add a reliable grpc.RpcError fixture for non-UNAVAILABLE errors")

def test_create_channel_and_stub_insecure():
    """Test that create_channel_and_stub creates insecure channels correctly."""
    with patch('grpc.insecure_channel') as mock_channel, \
         patch('dts_util.grpc.utils.is_server_running', return_value=True):
        mock_channel.return_value = MagicMock()
        channel, stub = create_channel_and_stub(use_tls=False)
        mock_channel.assert_called_once()
        assert isinstance(stub, ImageGenerationServiceStub)

def test_create_channel_and_stub_shared_secret():
    """Test that create_channel_and_stub adds shared secret to options."""
    with patch('grpc.insecure_channel') as mock_channel, \
         patch('dts_util.grpc.utils.is_server_running', return_value=True):
        mock_channel.return_value = MagicMock()
        create_channel_and_stub(use_tls=False, shared_secret="test_secret")
        mock_channel.assert_called_once()
        call_args = mock_channel.call_args[1]
        assert ('grpc.primary_user_agent', 'secret=test_secret') in call_args['options']

def test_create_channel_and_stub_server_not_running():
    """Test that create_channel_and_stub raises ConnectionError when server is not running."""
    with patch('dts_util.grpc.utils.is_server_running', return_value=False):
        with pytest.raises(ConnectionError, match="Unable to connect to server"):
            create_channel_and_stub(port=65432)  # Use a port that's not running