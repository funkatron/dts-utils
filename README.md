# Draw Things gRPC Server Utilities

A Python package providing utilities for interacting with the Draw Things gRPC server. This package includes tools for server installation, management, and client communication.

It also includes a local model-indexing workflow for inspecting Draw Things uncurated community models.

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

### What This Package Does *Not* Provide

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

# Model inspector help
uv run dts-util models --help
```

## Getting Started

### Uncurated Model Inspector

Build the local model index:

```bash
uv run dts-util models build
```

Search the generated index:

```bash
uv run dts-util models search flux
uv run dts-util models search sdxl anime
uv run dts-util models search --family Flux --has-hf
uv run dts-util models search --family SDXL --has-license
```

Show one record in detail:

```bash
uv run dts-util models show MODEL_ID
```

`show` includes a `Suggested Config` block when the metadata provides usable hints, such as:

- `default_scale`
- `hires_fix_scale`
- `upcast_attention`
- `guidance_embed`
- `frames_per_second`
- recommended steps, text guidance, shift, resolution, sampler, and prompt format when these can be inferred from model notes

Generate the HTML report:

```bash
uv run dts-util models report
uv run dts-util models report --summary-only
```

Useful search filters:

- `--family Flux`
- `--type model`
- `--author NAME`
- `--license apache-2.0`
- `--has-source`
- `--has-hf`
- `--has-license`
- `--has-downloads`
- `--has-warnings`

Generated files:

- `data/drawthings_uncurated_models.json`
- `data/drawthings_uncurated_models.csv`
- `data/drawthings_models.sqlite`
- `data/report.html`

Cache directories:

- `.cache/community-models/` for the cloned upstream repository
- `.cache/huggingface/` for cached Hugging Face API responses

The `build` command clones or updates `drawthingsai/community-models`, parses `uncurated_models.txt`, `uncurated_models_sha256.json`, and matching `metadata.json` files under `uncurated_models/`, `models/`, and `loras/`. Hugging Face-backed models are enriched from the public API when possible, and malformed metadata is recorded as warnings instead of crashing the build.

### Quick Start Guide

If you're new to the Draw Things gRPC server, here's a simple guide to get you started:

1. **Install the Server**:

```bash
# This will install the server with default settings
uv run dts-util install
```

1. **Verify the Server is Running**:

```bash
uv run dts-util test
```

1. **Generate Your First Image**:

```bash
uv run python scripts/generate_image.py \
  --prompt "a beautiful sunset over mountains" \
  --configuration-json config.json \
  --output generated.png \
  --trust-server-cert \
  --open
```

`config.json` must contain a Draw Things generation configuration. The script converts that JSON to the FlatBuffer bytes required by `gRPCServerCLI`.

### Common Tasks

#### Custom Server Settings

```bash
# Change port and model path
uv run dts-util install --port 7860 --model-path /path/to/model

# Enable advanced features
uv run dts-util install --model-browser --debug

# Enable model browser for an existing service
uv run dts-util restart --model-browser
```

#### Secure Setup

```bash
# Enable TLS and set a shared secret
uv run dts-util install --shared-secret "your-secret-here"
```

#### Server Management

```bash
# Check server status
uv run dts-util test

# Restart the server
uv run dts-util restart

# Enable model browser and restart the server
uv run dts-util restart --model-browser

# Uninstall the server
uv run dts-util uninstall
```

## Troubleshooting

### Server Not Starting

1. Check server status:

```bash
uv run dts-util test
```

1. Check server logs:

```bash
cat ~/.config/draw-things/server.log
```

### Connection Issues

1. Verify server is running:

```bash
uv run dts-util test
```

1. Check port availability:

```bash
uv run dts-util test --port 7860
```

1. Inspect reflected gRPC services and methods:

```bash
uv run dts-util reflect --trust-server-cert
uv run dts-util reflect --json --trust-server-cert
```

1. Check TLS configuration:

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

#### Prompt-to-Image Script

If you only run one command, run this:

```bash
uv run python scripts/generate_image.py \
  --prompt "a small robot painting clouds" \
  --output generated.png \
  --configuration-json config.json \
  --trust-server-cert \
  --open
```

Draw Things gRPCServerCLI commonly uses a local certificate issued by its own root CA. For local development, `--trust-server-cert` fetches and trusts the presented server certificate for this localhost connection. For remote or LAN servers, use `--root-cert PATH` with a pinned PEM certificate when possible. If you cannot pin a certificate and accept the man-in-the-middle risk for one diagnostic connection, use `--force-trust-server-cert`. A generation configuration is required: use `--configuration-json` to pass a Draw Things generation configuration as JSON. This requires `flatc` on `PATH` so the script can convert JSON to the FlatBuffer bytes expected by gRPC. If the server was installed with `--no-tls`, use `--insecure` instead. If the server requires authentication, add `--shared-secret`.

The script writes PNG files. Draw Things returns generated image tensors over gRPC; the script reassembles chunked responses and decodes those tensors before writing the output file.

Common prompt-to-image tasks:


| Goal                           | Command                                                                                                                                                               | What you get                                      |
| ------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------- |
| Generate and open one image    | `uv run python scripts/generate_image.py --prompt "a small robot painting clouds" --configuration-json config.json --output generated.png --trust-server-cert --open` | A decoded PNG opened in the default viewer.       |
| Use a pinned local certificate | `uv run python scripts/generate_image.py --prompt "..." --configuration-json config.json --output generated.png --root-cert cert.pem`                                 | TLS verification against a known PEM file.        |
| Connect to a non-TLS server    | `uv run python scripts/generate_image.py --prompt "..." --configuration-json config.json --output generated.png --insecure`                                           | Plain gRPC for servers installed with `--no-tls`. |
| Send prebuilt config bytes     | `uv run python scripts/generate_image.py --prompt "..." --configuration config.bin --output generated.png --trust-server-cert`                                        | No `flatc` conversion step.                       |
| Force trust for diagnostics    | `uv run python scripts/generate_image.py --host gpu.local --prompt "..." --configuration-json config.json --output generated.png --force-trust-server-cert`            | Remote trust-on-first-use with MITM risk.         |


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

- [API Documentation](API.md): Notes on the upstream Draw Things gRPC API used by this repository
- [CLI Reference](CLI.md): Complete reference for the `dts-util` command-line tool

### Draw Things gRPC Server Documentation

- [Protocol and Schema Reference](PROTOBUF.md): Practical reference for the upstream protobuf and FlatBuffer schemas
- For complete server documentation, please refer to the [Draw Things documentation](https://drawthings.ai/docs)

## Development

### Requirements

- Python 3.12+
- `uv`
- `flatc` for `scripts/generate_image.py --configuration-json`
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