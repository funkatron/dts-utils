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

**Prerequisites:** A running server at your host/port (often `localhost:7859` with TLS). You need a generation configuration that matches models on the server (saved name such as `portrait`, or rely on shorthand after the tool creates `default.json`; see [README.md](../README.md#shorthand-profile-default)).

Minimal check (adjust TLS / port flags to match how you run):

```bash
uv sync
uv run dts-utils server check
uv run dts-utils reflect --trust-server-cert
uv run dts-utils generate \
  --prompt "smoke test" \
  --configuration portrait \
  --trust-server-cert \
  --output output/smoke.png
```

Optional: after `portrait` (or another saved profile) exists, you can smoke the prompt-first path on a trusted localhost install:

```bash
uv run dts-utils "smoke test" --output output/smoke-shorthand.png
```

(Shorthand always adds `--trust-server-cert` and `--open`; omit `--open` by using explicit `dts-utils generate …` if you need that.)

- **`server check`:** gRPC readiness on the port (TLS first on loopback, then plaintext fallback; use `server check --no-tls` if the server runs with `--no-tls`).
- **`reflect`:** gRPC **server reflection**. Many `gRPCServerCLI` builds do not implement it, so `UNIMPLEMENTED` is common even when generation works; treat this step as optional for Draw Things.
- **`generate` / shorthand:** streaming decode and PNG write.

Optional **web UI** (HTTP front-end to the same gRPC stack):

```bash
uv run dts-utils web --open
```

In the browser, match TLS mode to your server (`no-TLS` vs trust loopback cert), pick a profile, generate, and confirm a PNG downloads. See [CLI.md § web](../CLI.md#web-dts-utils-web).

If you **cannot** run against a live server for a release, say so in **Tested with** (e.g. “pytest + CI only; not smoke-tested against gRPCServerCLI”).
