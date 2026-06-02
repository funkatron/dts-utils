# Tests

From the repo root:

```bash
uv sync --dev
uv run pytest
```

Some tests are **skipped** (integration / optional): see [gRPC integration tests](../PROTOBUF.md#grpc-integration-tests) in `PROTOBUF.md` for why, and for the **maintainer playbook**—ephemeral ports, in-process fakes vs optional real `gRPCServerCLI`, and keeping tests aligned when Draw Things updates the wire protocol.

**`models fetch`** tests exercise bundled JSON and CLI parsing only (no network downloads). Maintainer backlog and phased work: [models-fetch-roadmap.md](../docs/models-fetch-roadmap.md). Optional **`@pytest.mark.integration`** **`models fetch`** smoke may appear guarded by **`DTS_UTILS_FETCH_INTEGRATION=1`** — unset means skip.

---

## Ephemeral `gRPCServerCLI` (pytest)

Upstream-aligned smoke (**same proto as `generate`**) without LaunchAgent:

1. Install or locate **`gRPCServerCLI`** (e.g. `dts-utils server install`, or ensure `/usr/local/bin/gRPCServerCLI` / `~/.local/bin/gRPCServerCLI` is on `PATH`).
2. Ensure a **models root directory** exists — typically Draw Things’ **`Models`** folder. Override with **`DTS_GRPC_TEST_MODEL_PATH`** if needed.
3. Run:

```bash
export DTS_GRPC_TEST_SPAWN_SERVER=1
uv run pytest tests/test_grpc_server.py tests/test_generate_functional_live.py -v
```

Optional: **`DTS_GRPC_TEST_SERVER_BINARY=/path/to/gRPCServerCLI`** if the binary is not on `PATH`.

The **`spawned_live_cli`** fixture lives in **`conftest.py`** (session scope): **one** subprocess per **`pytest` invocation**, shared by **`tests/test_grpc_server.py`** (RPC smoke via **`live_upstream_stub`**) and **`tests/test_generate_functional_live.py`** (runs **`dts_utils.generate.main`** with **`--configuration default`** and **`--no-tls`** — requires **`flatc`** on `PATH`; **`ensure_default_generation_json_config()`** ensures **`default.json`** like shorthand).

This listens on **`127.0.0.1:<free port>`** with **`--no-tls`**, then tears down when the session finishes. It does not load or modify your LaunchAgent plist.

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

**Debugging logs** when a step fails or the server misbehaves:

```bash
uv run dts-utils server tail              # macOS Unified Logging (gRPCServerCLI)
uv run dts-utils server tail --last 1h    # more history before live follow
```

Optional **web UI** (HTTP front-end to the same gRPC stack):

```bash
uv run dts-utils web --open
# second terminal:
uv run dts-utils web tail
```

`dts-utils web` prints the log file path on **stdout** (default `~/.config/dts-utils/web.log`; override with `DTS_WEB_LOG_FILE` or `--log-file`). The Setup panel and `GET /api/health` expose the same path and a ready-made `tail_cli` command.

In the browser, match TLS mode to your server (`no-TLS` vs trust loopback cert), pick a profile, generate, and confirm a PNG downloads. See [CLI.md § web](../CLI.md#web-dts-utils-web).

If you **cannot** run against a live server for a release, say so in **Tested with** (e.g. “pytest + CI only; not smoke-tested against gRPCServerCLI”).
