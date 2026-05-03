# dts-util CLI Reference

This document provides a comprehensive reference for the `dts-util` command-line interface tool.

## Command Structure

All commands follow this structure:

```
uv run dts-util <command> [options]
```

## Server lifecycle (LaunchAgent)

These commands manage **macOS LaunchAgent + `gRPCServerCLI`** (not pytest, not Docker).

**Required spelling:** **`dts-util server <subcommand>`** for install, uninstall, restart, **`test`**, and **`check`**. Omitting **`server`** (e.g. `dts-util install`) is rejected (**stderr + exit code `2`**).

Bare **`dts-util server`** prints this summary.

## Available Commands

### install (`dts-util server install`)

Installs and configures the Draw Things gRPC server via the macOS LaunchAgent workflow.

```bash
uv run dts-util server install [options]
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
- `--export-tls-cert`: After a successful install with TLS, write the server's presented PEM (see **tls export** below)
- `--export-tls-cert-path PATH`: Destination PEM for `--export-tls-cert` (default: `dts-util tls path`)
- `--export-tls-cert-force`: Overwrite an existing PEM during `--export-tls-cert`

### uninstall

Removes the Draw Things gRPC server and all related files.

```bash
uv run dts-util server uninstall
```

### restart

Restarts the Draw Things gRPC server service.

```bash
uv run dts-util server restart [--model-browser]
```

Options:
- `--model-browser`: Enable model browser in the installed service before restarting

### test

Probes localhost for a reachable gRPC listener (installer workflow; not **`pytest`**).

```bash
uv run dts-util server test [--port PORT]
uv run dts-util server check [--port PORT]
```

Options:

- `--port PORT`: Port to probe (default: 7859)

**`check`** is a synonym for **`test`** (same flags). Both require the **`server`** prefix alongside **`install`**, **`uninstall`**, and **`restart`**.

### reflect

Lists gRPC services and methods exposed through server reflection.

If you only run one command, run this:

```bash
uv run dts-util reflect --trust-server-cert
```

Options:
- `--host HOST`: gRPC server host (default: `localhost`)
- `--port PORT`: gRPC server port (default: `7859`)
- `--timeout SECONDS`: Connection timeout (default: `2`)
- `--json`: Print machine-readable JSON
- `--trust-server-cert`: Trust the presented certificate for this localhost connection only
- `--force-trust-server-cert`: Trust the presented certificate for any host, with MITM risk
- `--root-cert PATH`: Use a pinned PEM root/server certificate
- `--no-tls`: Connect without TLS when the server was installed with `--no-tls`

Use `--root-cert` for remote or LAN servers when possible. `--trust-server-cert` is restricted to `localhost` and loopback addresses. `--force-trust-server-cert` is available for remote diagnostics, but it trusts whatever certificate is presented on that connection and can be vulnerable to man-in-the-middle attacks.

### configs

Shows and lists saved Draw Things JSON generation configurations.

If you only run one command, run this:

```bash
uv run dts-util configs path
```

Options:
- `configs path`: Print the directory for saved JSON configurations, creating it if needed.
- `configs path --no-create`: Print the directory without creating it.
- `configs list`: List saved JSON configuration names from the default directory.
- `configs list --directory PATH`: List saved JSON configuration names from another directory.

Save files like `portrait.json` in this directory, then use `--configuration portrait` with `dts-util generate`.

### tls

Writes the server's **presented** TLS certificate to a PEM file for **`dts-util generate --root-cert …`** / **`reflect --root-cert …`** (trust-on-fetch; same bytes Python's `ssl.get_server_certificate` returns). **`gRPCServerCLI`** keystores are not modified.

```bash
uv run dts-util tls path
uv run dts-util tls export
```

Subcommands:
- **`tls path`**: Print default PEM destination (usually under your `dts-util` config hierarchy / `trusted/`), creating parents unless `--no-create`.
- **`tls export`**: Connect with TLS, capture the presented PEM, `--output`/`-o` path (defaults to **`tls path`**), **`--force`** to replace, **`--host`** / **`--port`**, **`--retries`** for post-install backoff.

Combined with **`server install`** (macOS LaunchAgent workflow): `uv run dts-util server install --export-tls-cert` runs **`export`** to the default PEM after **`server test`** passes (skipped when **`--no-tls`** is set).

### generate

Generates an image through the upstream Draw Things streaming gRPC API.

If you only run one command, run this:

```bash
uv run dts-util generate \
  --prompt "a small robot painting clouds" \
  --configuration portrait \
  --trust-server-cert \
  --open
```

Important options:

- `--output PATH`: Base path for output files. **Default:** `output/generated.png` (files land under `./output`). The CLI inserts `-<unix_ms>` before the extension on disk (for example `output/generated.png` → `output/generated-1735123456789.png`) so successive runs do not overwrite earlier outputs. Multiple images use `-2`, `-3`, … before the extension on the same stem. Successful writes are printed as `Wrote …` lines on stdout.
- `--configuration VALUE`: Read a Draw Things configuration. Existing `.json` files are converted to FlatBuffer bytes, other existing files are sent as raw FlatBuffer bytes, and simple names resolve to saved JSON configs.
- `--configuration-json VALUE`: Read a Draw Things JSON configuration file or saved config name.
- `--trust-server-cert`: Trust the certificate presented by a localhost server for this connection.
- `--force-trust-server-cert`: Trust the certificate presented by any server for this connection, with MITM risk.
- `--root-cert PATH`: Use a pinned PEM root/server certificate.
- `--no-tls`: Connect without TLS when the server was installed with `--no-tls`.
- `--max-message-mb N`: Set gRPC send and receive message limits.
- `--open`: Open written image files with the platform default viewer.

## Examples

### Basic Installation

```bash
# Install with default settings
uv run dts-util server install

# Install with custom model path
uv run dts-util server install -m /path/to/models
```

### Advanced Installation

```bash
# Install with custom port, name, and model path
uv run dts-util server install -p 7860 -n "MyServer" -m /path/to/models

# Install with security settings
uv run dts-util server install -s "your-secret-here"

# Install with advanced settings
uv run dts-util server install --model-browser --debug --no-flash-attention
```

### Server Management

```bash
# Check if server is listening locally
uv run dts-util server test

# Probe a specific port
uv run dts-util server test --port 7860

# List reflected gRPC services and methods
uv run dts-util reflect --trust-server-cert

# Print the saved JSON config directory
uv run dts-util configs path

# Print PEM path and pin server cert locally
uv run dts-util tls path
uv run dts-util tls export

# Restart the server
uv run dts-util server restart

# Enable model browser and restart the server
uv run dts-util server restart --model-browser

# Uninstall the server
uv run dts-util server uninstall
```

## Image generation

If you only run one command, run this:

```bash
uv run dts-util generate \
  --prompt "a small robot painting clouds" \
  --configuration portrait \
  --trust-server-cert \
  --open
```

Generation fails before opening a gRPC stream if neither `--configuration-json` nor `--configuration` is provided. This avoids the opaque socket-close behavior the server can produce for prompt-only requests.

Each successful run writes timestamped filenames derived from `--output` (default `output/generated.png`): `-<unix_ms>` is inserted before the extension (for example `output/generated.png` → `output/generated-1735123456789.png`). When the server returns multiple images in one invocation, additional files append `-2`, `-3`, … before the extension.

Common tasks:

| Goal | Command | What you get |
| --- | --- | --- |
| Generate from a saved config | `uv run dts-util generate --prompt "..." --configuration portrait --trust-server-cert` | A decoded PNG under `./output` (`output/generated-<unix_ms>.png` by default) using `portrait.json` from the saved config directory. |
| Generate from Draw Things JSON | `uv run dts-util generate --prompt "..." --configuration config.json --trust-server-cert` | A decoded PNG under `./output` after JSON-to-FlatBuffer conversion. |
| Generate and open the result | `uv run dts-util generate --prompt "..." --configuration config.json --trust-server-cert --open` | Timestamp-suffixed PNG under `./output`, opened in the platform default viewer. |
| Use prebuilt FlatBuffer bytes | `uv run dts-util generate --prompt "..." --configuration config.bin --trust-server-cert` | PNG written without invoking [`flatc`](https://github.com/google/flatbuffers). |
| Use a pinned certificate | `uv run dts-util generate --prompt "..." --configuration config.json --root-cert cert.pem` | TLS verification against a known PEM file. |
| Force trust for remote diagnostics | `uv run dts-util generate --host gpu.local --prompt "..." --configuration config.json --force-trust-server-cert` | Remote trust-on-first-use with MITM risk. |

For remote or LAN servers, prefer `--root-cert PATH`. Use `--force-trust-server-cert` only when you cannot pin a cert and accept the risk for that connection.

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
  uv run dts-util server install
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
- `2`: Invalid arguments (for example, bare LaunchAgent lifecycle verbs without the `server` prefix)

## See Also

- [API Documentation](API.md): Notes on the upstream Draw Things gRPC API used by this repository
- [Protocol and Schema Reference](PROTOBUF.md): Practical reference for the upstream protobuf and FlatBuffer schemas
- [README.md](README.md): General package information and usage