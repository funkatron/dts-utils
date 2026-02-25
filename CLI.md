# dts-util CLI Reference

This document provides a comprehensive reference for the `dts-util` command-line interface tool.

## Command Structure

All commands follow this structure:

```
uv run dts-util <command> [options]
```

## Available Commands

### install

Installs and configures the Draw Things gRPC server.

```bash
uv run dts-util install [options]
```

Options:
- `-m, --model-path PATH`: Custom path to store models (default: Draw Things app models directory)
- `-q, --quiet`: Minimize output and assume default answers to prompts
- `-n, --name NAME`: Server name in local network (default: machine name)
- `-p, --port PORT`: Port to run the server on (default: 7859)
- `-a, --address ADDR`: Address to bind to (default: 0.0.0.0)
- `-g, --gpu INDEX`: GPU index to use (default: 0)
- `-d, --datadog-api-key KEY`: Datadog API key for monitoring
- `-s, --shared-secret SECRET`: Authentication key for secure connections
- `--no-tls`: Disable encryption (not recommended)
- `--no-response-compression`: Disable compression
- `--model-browser`: Enable model browser
- `--no-flash-attention`: Disable Flash Attention
- `--debug`: Enable verbose logging
- `--join JSON`: JSON configuration for proxy setup

### uninstall

Removes the Draw Things gRPC server and all related files.

```bash
uv run dts-util uninstall
```

### restart

Restarts the Draw Things gRPC server service.

```bash
uv run dts-util restart
```

### test

Tests if the server is running and responding.

```bash
uv run dts-util test [options]
```

Options:
- `--port PORT`: Port to test connection on (default: 7859)

## Examples

### Basic Installation

```bash
# Install with default settings
uv run dts-util install

# Install with custom model path
uv run dts-util install -m /path/to/models
```

### Advanced Installation

```bash
# Install with custom port, name, and model path
uv run dts-util install -p 7860 -n "MyServer" -m /path/to/models

# Install with security settings
uv run dts-util install -s "your-secret-here"

# Install with advanced settings
uv run dts-util install --model-browser --debug --no-flash-attention
```

### Server Management

```bash
# Check if server is running
uv run dts-util test

# Test connection on a specific port
uv run dts-util test --port 7860

# Restart the server
uv run dts-util restart

# Uninstall the server
uv run dts-util uninstall
```

## Environment Variables

- `DRAW_THINGS_MODEL_PATH`: Sets the default model path where the server looks for and stores model files. This is useful when:
  - You regularly use a custom model location different from the default Draw Things app location
  - You're running commands in scripts or automation where you don't want to specify the path each time
  - You're deploying on systems where the Draw Things app isn't installed

  Example:
  ```bash
  # Set the environment variable
  export DRAW_THINGS_MODEL_PATH=/path/to/your/models

  # Now you can run commands without specifying --model-path
  uv run dts-util install
  ```

  Note: If you use both the environment variable and the `--model-path` option, the command line option takes precedence.

## Development Workflow with uv

```bash
# Install project and dev dependencies from pyproject.toml
uv sync --dev

# Run tests in the uv-managed environment
uv run pytest
```

## Exit Codes

- `0`: Success
- `1`: Error occurred during command execution

## See Also

- [API Documentation](API.md): Documentation for package utilities and functions
- [Protocol Buffer Specifications](PROTOBUF.md): Documentation of the gRPC server's API
- [README.md](README.md): General package information and usage