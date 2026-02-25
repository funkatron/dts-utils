"""Utility functions for working with the Draw Things gRPC server.

This module provides helper functions for interacting with the Draw Things gRPC server.
It can be used both by the dts-util tool and by client applications.
"""

import grpc
from contextlib import contextmanager
from typing import Optional, Tuple

def is_server_running(host: str = 'localhost', port: int = 7859, timeout: float = 1) -> bool:
    """Check if the gRPC server is running.

    Args:
        host: Server hostname (default: localhost)
        port: Server port (default: 7859)
        timeout: Connection timeout in seconds (default: 1)

    Returns:
        bool: True if server is running and accepting connections

    Example:
        >>> from dts_util.grpc.utils import is_server_running
        >>> is_server_running(port=7859)
        True
    """
    try:
        with grpc.insecure_channel(f'{host}:{port}') as channel:
            try:
                grpc.channel_ready_future(channel).result(timeout=timeout)
                return True
            except grpc.FutureTimeoutError:
                return False
    except Exception:
        return False

@contextmanager
def handle_grpc_error():
    """Context manager to handle gRPC errors gracefully.

    This context manager converts gRPC connection errors into more user-friendly
    ConnectionError exceptions, while preserving other gRPC errors.

    Raises:
        ConnectionError: If the server is unavailable
        grpc.RpcError: If any other gRPC error occurs

    Example:
        >>> from dts_util.grpc.utils import handle_grpc_error
        >>> with handle_grpc_error():
        ...     response = stub.GenerateImage(request)
    """
    try:
        yield
    except grpc.RpcError as e:
        if hasattr(e, 'code') and e.code() == grpc.StatusCode.UNAVAILABLE:
            raise ConnectionError("Server is unavailable")
        raise

# Only import these if you need to create a channel with the specific service stub
try:
    from .proto.image_generation_pb2_grpc import ImageGenerationServiceStub

    def create_channel_and_stub(
        host: str = 'localhost',
        port: int = 7859,
        use_tls: bool = True,
        shared_secret: Optional[str] = None
    ) -> Tuple[grpc.Channel, ImageGenerationServiceStub]:
        """Create a gRPC channel and stub for communicating with the server.

        This function creates a gRPC channel with the appropriate security settings
        and returns both the channel and a stub for making RPC calls.

        Args:
            host: Server hostname (default: localhost)
            port: Server port (default: 7859)
            use_tls: Whether to use TLS encryption (default: True)
            shared_secret: Optional shared secret for authentication

        Returns:
            Tuple containing:
            - grpc.Channel: The created channel
            - ImageGenerationServiceStub: Stub for making RPC calls

        Raises:
            ConnectionError: If server is not running

        Example:
            >>> from dts_util.grpc.utils import create_channel_and_stub
            >>> channel, stub = create_channel_and_stub(port=7859)
            >>> response = stub.Echo(EchoRequest())
        """
        # Build channel options
        options = []
        if shared_secret:
            options.append(('grpc.primary_user_agent', f'secret={shared_secret}'))

        target = f'{host}:{port}'

        # Verify connection before opening channel threads.
        if not is_server_running(host, port):
            raise ConnectionError(f"Unable to connect to server at {target}")

        # Create appropriate channel
        if use_tls:
            channel = grpc.secure_channel(target, grpc.ssl_channel_credentials(), options=options)
        else:
            channel = grpc.insecure_channel(target, options=options)

        return channel, ImageGenerationServiceStub(channel)
except ImportError:
    # The ImageGenerationServiceStub is not available
    pass