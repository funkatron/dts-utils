# Tests

From the repo root:

```bash
uv sync --dev
uv run pytest
```

Some tests are **skipped** (integration / optional): see [gRPC integration tests](../PROTOBUF.md#grpc-integration-tests) in `PROTOBUF.md` for why, and for the **maintainer playbook**—ephemeral ports, in-process fakes vs optional real `gRPCServerCLI`, and keeping tests aligned when Draw Things updates the wire protocol.

---

## Manual release smoke

Exercise the CLI against a **live** Draw Things **`gRPCServerCLI`** (not only `pytest`). Record the server release **tag** you used under **Tested with** in [CHANGELOG.md](../CHANGELOG.md) for that version.

**Prerequisites:** A running server at your host/port (often `localhost:7859` with TLS). Use a saved generation config you know works for a realistic `generate` pass.

Minimal check (adjust TLS / port flags to match how you run):

```bash
uv sync
uv run dts-util server check
uv run dts-util reflect --trust-server-cert
uv run dts-util generate \
  --prompt "smoke test" \
  --configuration portrait \
  --trust-server-cert \
  --output output/smoke.png
```

- **`server check`:** listener / process probe (macOS LaunchAgent layout where applicable).
- **`reflect`:** gRPC channel + reflection (add `--no-tls` or `--root-cert` if needed).
- **`generate`:** streaming decode and PNG write.

If you **cannot** run against a live server for a release, say so in **Tested with** (e.g. “pytest + CI only; not smoke-tested against gRPCServerCLI”).
