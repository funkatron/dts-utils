# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `dts-util restart --model-browser` to enable model browsing for an existing LaunchAgent service before restart.
- `dts-util generate` for sending a prompt to the upstream Draw Things gRPC streaming API and writing returned images to PNG, including JSON-to-FlatBuffer configuration, local certificate trust options, and `--open` viewer launch support.
- Clear prompt-only failure for `dts-util generate` when no generation configuration is provided.
- Documentation for the upstream Draw Things proto/FlatBuffer split, chunked image streaming, local TLS trust options, and the task-first prompt-to-image command.
- `dts-util reflect` to list services and methods from gRPC server reflection, with JSON output for scripts.
- Shared gRPC channel setup that restricts `--trust-server-cert` to localhost/loopback and directs remote or LAN usage to pinned `--root-cert` certificates.
- `--force-trust-server-cert` for explicit remote trust-on-first-use diagnostics when users accept the MITM risk.
- `dts-util configs path/list` and `dts-util generate --configuration` support for saved JSON config names and `.json` auto-conversion.
- Client commands now use `--no-tls` instead of `--insecure` for plaintext connections to servers installed with `--no-tls`.
- `dts-util tls path` and `dts-util tls export` to fetch the server's **presented** certificate over TLS (Python `ssl.get_server_certificate`) and save PEM for **`--root-cert`** on **`generate`** / **`reflect`**. **`install`** can take **`--export-tls-cert`** (with optional **`--export-tls-cert-path`**, **`--export-tls-cert-force`**) after a successful TLS install on macOS. This pins what the binary serves; **`gRPCServerCLI`** keystores are not altered from **`dts-util`**.
- Comprehensive test suite for gRPC utilities
  - Server availability checking
  - Error handling for various gRPC scenarios
  - Channel creation with different configurations
- Improved error handling in `handle_grpc_error`
  - Simplified error code checking
  - Better handling of missing `code()` methods

### Removed

- `scripts/generate_image.py`; use `uv run dts-util generate` instead.
