# Draw Things gRPC Server Utilities

A Python package providing utilities for interacting with the Draw Things gRPC server. This package includes tools for server installation, management, and client communication.

## What This Package Provides

- **Server Management Tools**:
  - Installation and configuration of the Draw Things gRPC server
  - Server lifecycle management (start, stop, restart)
  - Health monitoring and status checks
  - Log file management

- **Client Utilities**:
  - Python helper functions for connecting to the gRPC server
  - Error handling utilities for gRPC calls
  - Connection management tools

- **Security Features**:
  - TLS configuration management
  - Authentication setup
  - Certificate management

### What This Package Does _Not_ Provide

- **Image Generation Logic**: The actual image generation is handled by the Draw Things gRPC server
- **Model Management**: Model loading and management is handled by the server
- **GPU Management**: GPU configuration is handled by the server
- **Web Interface**: This is a command-line and programmatic interface only
- **Endpoint Management**: The gRPC server's endpoints are fixed and cannot be modified through this tool

## Features

- **Server Management**: One-command installation and configuration of the Draw Things gRPC server
- **gRPC Client Utilities**: Python library for easy integration with the image generation service
- **File Management**: Tools for handling server files and configurations
- **Health Monitoring**: Built-in health check endpoints for server status verification
- **Security Features**:
  - TLS encryption support for secure communication
  - Authentication via shared secrets
  - Certificate chain verification
  - Client certificate validation

## Installation

```bash
# Clone the repository
git clone https://github.com/funkatron/draw-things-grpcservercli-installer.git
cd draw-things-grpcservercli-installer

# Create a virtual environment and install dependencies with uv
uv sync

# Run the CLI
uv run dts-util --help
```

## Getting Started

### Quick Start Guide

If you're new to the Draw Things gRPC server, here's a simple guide to get you started:

1. **Install the Server**:
```bash
# This will install the server with default settings
uv run dts-util install
```

2. **Verify the Server is Running**:
```bash
uv run dts-util test
```

3. **Generate Your First Image**:
```python
from dts_util.grpc.utils import create_channel_and_stub, handle_grpc_error
from dts_util.grpc.proto.image_generation_pb2 import GenerateImageRequest

# Connect to the server (defaults to localhost:7859 with TLS enabled)
channel, stub = create_channel_and_stub(port=7859)

# Generate an image
with handle_grpc_error():
    response = stub.GenerateImage(GenerateImageRequest(
        prompt="a beautiful sunset over mountains",  # Describe what you want to generate
        negative_prompt="",                          # What you don't want in the image
        width=512,                                   # Image width in pixels
        height=512                                   # Image height in pixels
    ))
```

### Common Tasks

#### Custom Server Settings

```bash
# Change port and model path
dts-util install --port 7860 --model-path /path/to/model

# Enable advanced features
dts-util install --model-browser --debug
```

#### Secure Setup

```bash
# Enable TLS and set a shared secret
dts-util install --shared-secret "your-secret-here"
```

#### Server Management

```bash
# Check server status
uv run dts-util test

# Restart the server
uv run dts-util restart

# Uninstall the server
uv run dts-util uninstall
```

## Troubleshooting

### Server Not Starting

1. Check server status:
```bash
uv run dts-util test
```

2. Check server logs:
```bash
cat ~/.config/draw-things/server.log
```

### Connection Issues

1. Verify server is running:
```bash
uv run dts-util test
```

2. Check port availability:
```bash
uv run dts-util test --port 7860
```

3. Check TLS configuration:
```bash
# If using TLS, ensure your client is configured correctly
# You can verify server configuration in ~/.config/draw-things/server.conf
```

## Advanced Usage

### Package Structure

The package is organized into several modules:

```
src/
├── dts_util/
│   ├── installer/               # Server installation and management
│   ├── grpc/                    # Client communication tools
│   └── utils/                   # Shared utilities
```

### Complete Installation Options

For advanced users, here are all available installation options:

```bash
# Basic settings
uv run dts-util install --port 7860 --model-path /path/to/model

# Security settings
uv run dts-util install --shared-secret "your-secret-here"

# Advanced settings
uv run dts-util install --model-browser --debug --no-flash-attention
```

### Python Client Examples

#### Basic Image Generation

```python
from dts_util.grpc.utils import create_channel_and_stub, handle_grpc_error
from dts_util.grpc.proto.image_generation_pb2 import GenerateImageRequest

# Connect to server
channel, stub = create_channel_and_stub(port=7859)

# Generate image
with handle_grpc_error():
    response = stub.GenerateImage(GenerateImageRequest(
        prompt="a beautiful landscape",
        negative_prompt="blurry, low quality",
        width=512,
        height=512
    ))
```

#### Error Handling

```python
from dts_util.grpc.utils import handle_grpc_error

try:
    with handle_grpc_error():
        # Your code here
        pass
except Exception as e:
    print(f"Error occurred: {e}")
```

## Documentation

### Package Documentation
- [API Documentation](API.md): Documentation for this package's utilities and functions
- [CLI Reference](CLI.md): Complete reference for the `dts-util` command-line tool

### Draw Things gRPC Server Documentation
- [Protocol Buffer Specifications](PROTOBUF.md): Documentation of the gRPC server's API and message definitions
- For complete server documentation, please refer to the [Draw Things documentation](https://drawthings.ai/docs)

## Development

### Requirements

- Python 3.13.x
- gRPC tools
- Protocol Buffers compiler

### Setting Up Development

```bash
# Install development dependencies
uv sync --dev

# Run tests
uv run pytest
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.