import pytest
import grpc
import os
import sys
from contextlib import contextmanager

# Add the src directory to the Python path
src_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src')
sys.path.insert(0, src_dir)

from dts_util.grpc.proto.image_generation_pb2 import (
    EchoRequest,
    EchoResponse,
    FilesExistRequest,
    FilesExistResponse,
    ImageGenerationRequest,
    ImageGenerationResponse,
    UploadFileRequest,
    UploadFileResponse,
)
from dts_util.grpc.proto.image_generation_pb2_grpc import ImageGenerationServiceStub

def is_server_running(host='localhost', port=7859, timeout=1):
    """Check if the gRPC server is running."""
    try:
        with grpc.insecure_channel(f'{host}:{port}') as channel:
            try:
                grpc.channel_ready_future(channel).result(timeout=timeout)
                return True
            except grpc.FutureTimeoutError:
                return False
    except Exception:
        return False

@pytest.fixture(scope="session")
def server_check():
    """Check if the server is running before running tests."""
    if not is_server_running():
        pytest.skip("gRPC server is not running. Please start the server first.")

@pytest.fixture
def grpc_channel(server_check):
    """Create a gRPC channel for testing; close cleanly to avoid background poll thread noise."""
    with grpc.insecure_channel("localhost:7859") as channel:
        yield channel

@pytest.fixture
def grpc_stub(grpc_channel):
    """Create a gRPC stub for testing."""
    return ImageGenerationServiceStub(grpc_channel)

@contextmanager
def handle_grpc_error():
    """Context manager to handle gRPC errors gracefully."""
    try:
        yield
    except grpc.RpcError as e:
        if isinstance(e, grpc._channel._InactiveRpcError):
            if e.code() == grpc.StatusCode.UNAVAILABLE:
                pytest.skip("Server became unavailable during test")
            else:
                raise
        else:
            raise

@pytest.mark.integration
def test_echo(grpc_stub):
    """Test the Echo endpoint."""
    with handle_grpc_error():
        request = EchoRequest()
        response = grpc_stub.Echo(request)
        assert response.message == "HELLO"

@pytest.mark.integration
def test_files_exist_empty(grpc_stub):
    """Test FilesExist endpoint with empty request."""
    with handle_grpc_error():
        request = FilesExistRequest(files=[])
        response = grpc_stub.FilesExist(request)
        assert len(response.files) == 0
        assert len(response.exists) == 0
        assert len(response.errors) == 0

@pytest.mark.integration
def test_files_exist_nonexistent(grpc_stub):
    """Test FilesExist endpoint with nonexistent files."""
    with handle_grpc_error():
        test_files = ["nonexistent1.safetensors", "nonexistent2.safetensors"]
        request = FilesExistRequest(files=test_files)
        response = grpc_stub.FilesExist(request)
        assert len(response.files) == len(test_files)
        assert len(response.exists) == len(test_files)
        assert all(not exists for exists in response.exists)
        assert len(response.errors) == len(test_files)

@pytest.mark.integration
@pytest.mark.skip(reason="Requires model files to be installed")
def test_files_exist_real(grpc_stub):
    """Test FilesExist endpoint with real model files (requires installation)."""
    with handle_grpc_error():
        test_files = [
            "models/Stable-diffusion/v1-5-pruned-emaonly.safetensors",
            "models/VAE/vae-ft-mse-840000-ema-pruned.safetensors"
        ]
        request = FilesExistRequest(files=test_files)
        response = grpc_stub.FilesExist(request)
        assert len(response.files) == len(test_files)
        assert len(response.exists) == len(test_files)
        assert len(response.errors) == len(test_files)

@pytest.mark.integration
@pytest.mark.skip(reason="Requires model files to be installed")
def test_generate_image(grpc_stub):
    """Test GenerateImage endpoint (requires model installation)."""
    with handle_grpc_error():
        request = ImageGenerationRequest(
            prompt="a beautiful landscape",
            negative_prompt="",
            width=512,
            height=512,
            steps=20,
            cfg_scale=7.0,
            seed=-1,
            sampler="Euler a",
            restore_faces=False,
            enable_hr=False,
            denoising_strength=0.7,
            batch_size=1,
            batch_count=1
        )
        response = grpc_stub.GenerateImage(request)
        assert len(response.images) > 0
        assert len(response.info) > 0
        assert len(response.events) > 0

@pytest.mark.integration
@pytest.mark.skip(reason="Implementation pending")
def test_upload_file(grpc_stub):
    """Test UploadFile endpoint."""
    # TODO: Implement file upload test
    pass

def test_connection_error():
    """Test connection to wrong port."""
    with pytest.raises(grpc.RpcError):
        with grpc.insecure_channel("localhost:12345") as channel:
            stub = ImageGenerationServiceStub(channel)
            request = EchoRequest()
            stub.Echo(request)