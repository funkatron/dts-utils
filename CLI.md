# dts-util CLI reference

Reference for the `dts-util` command-line tool (flags, shorthand, environment variables). For install, TLS, and troubleshooting, use [README.md](README.md).

## Command structure

```
uv run dts-util <command> [options]
```

Some invocations omit `<command>` and use [Generate shorthand](#generate-shorthand-prompt-first) instead.

## Server lifecycle (LaunchAgent)

These commands manage macOS LaunchAgent + `gRPCServerCLI` (not pytest, not Docker).

Required spelling: `dts-util server <subcommand>` for `install`, `uninstall`, `restart`, `test`, and `check`. Running `dts-util install` without `server` prints a usage error (stderr, exit code `2`).

Bare `dts-util server` prints a short summary.

## Available commands

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
- `--export-tls-cert`: After a successful install with TLS, write the server's presented PEM (see tls export below)
- `--export-tls-cert-path PATH`: Destination PEM for `--export-tls-cert` (default: `dts-util tls path`)
- `--export-tls-cert-force`: Overwrite an existing PEM during `--export-tls-cert`

### uninstall

Removes the Draw Things gRPC server and related files managed by this tool.

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

Probes localhost for a reachable gRPC listener (installer workflow; not the pytest test suite).

```bash
uv run dts-util server test [--port PORT]
uv run dts-util server check [--port PORT]
```

Options:

- `--port PORT`: Port to probe (default: 7859)
- `--no-tls`: Probe plaintext gRPC only (use when `gRPCServerCLI` was installed with `--no-tls`).

On `localhost` / loopback, the default probe tries **TLS** with the server-presented certificate first (same idea as client `--trust-server-cert`), then falls back to plaintext.

`check` is a synonym for `test` (same flags). Both require the `server` prefix, like `install`, `uninstall`, and `restart`.

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

For remote or LAN servers, prefer `--root-cert`. `--trust-server-cert` is limited to `localhost` and loopback. `--force-trust-server-cert` is for diagnostics only.

Draw Things often builds `gRPCServerCLI` without gRPC reflection. `reflect` may therefore return `UNIMPLEMENTED` even when `generate` works. See [README.md § Troubleshooting](README.md#troubleshooting).

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

Save files such as `portrait.json` in this directory, then use `--configuration portrait` with `dts-util generate`.

### tls

Writes the server’s presented TLS certificate to a PEM file for `dts-util generate --root-cert …` / `dts-util reflect --root-cert …` (trust-on-fetch; same bytes Python’s `ssl.get_server_certificate` returns). `gRPCServerCLI` keystores are not modified.

```bash
uv run dts-util tls path
uv run dts-util tls export
```

Subcommands:

- `tls path`: Print default PEM destination (under the `dts-util` application support / config tree), creating parents unless `--no-create`.
- `tls export`: Connect with TLS, capture the presented PEM; use `--output` / `-o` (defaults to `tls path`), `--force` to replace, `--host` / `--port`, `--retries` for post-install backoff.

With `server install` (macOS): `uv run dts-util server install --export-tls-cert` runs export to the default PEM after `server test` passes (skipped when `--no-tls` is set).

### web (`dts-util web`)

Runs a loopback-first web UI for prompt-first image generation. The browser talks HTTP to `dts-util`; the tool forwards to Draw Things over gRPC (same stack as `generate`).

```bash
uv run dts-util web [--bind ADDR] [--port N] [--open]
```

- **Defaults:** bind `127.0.0.1`, HTTP port `8765`.
- **`--open`:** open the default browser after the server starts (URL uses `127.0.0.1` when bind is `0.0.0.0` or `::`).
- **Auth:** If **`DTS_WEB_TOKEN`** is set, all **`/api/*`** routes except **`GET /api/health`** require **`Authorization: Bearer <token>`**. Prefer loopback; binding more broadly without a token prints a **stderr warning**—set the token for mutating routes.
- **Probe:** **`GET /api/server-status`** mirrors listener checks (`no_tls` query flag aligns with `server check --no-tls`). The message is **probe only**; generation can still fail (config, `flatc`, TLS mismatch).
- **Generate:** **`POST /api/generate`** accepts JSON (`prompt`, optional `negative_prompt`, optional **`generations`** integer 1–25 default 1 for independent runs with fresh wildcard expansion each time, `configuration`, `host`, `port`, `no_tls`, `trust_server_cert`, `force_trust_server_cert`, `root_cert`, `shared_secret`, `config_dir`). Success responses are **`multipart/mixed`** PNG parts (all images concatenated). Response headers **`X-Generated-Count`** (PNG parts) and **`X-Generation-Runs`** (batch size). Errors return JSON `{"detail": "…"}` with the same actionable messages as the CLI where applicable.
- **Timeout:** Optional **`DTS_WEB_GENERATE_TIMEOUT`** (seconds, default `900`) caps wall-clock generation time.
- **Browser UI:** **⌘↵** (macOS) or **Ctrl+Enter** runs **Generate** from the prompt field (hammer icon). While a request is in flight, **Stop** (square icon) replaces **Generate** and aborts the fetch (the server may still finish the current RPC). **Setup** is the building FAB (top-right); **History** is the clock FAB stacked below it — lists recent successful generations stored only in **localStorage** (this browser); each row has **Download** links for PNGs. **Clear all** removes that storage.

LaunchAgent lifecycle stays in Terminal (`dts-util server …`); the UI footer links to the README quickstart.

### generate

Sends a prompt through the upstream Draw Things streaming gRPC API and writes PNG output.

If you only run one explicit `generate` command, run this:

```bash
uv run dts-util generate \
  --prompt "a small robot painting clouds" \
  --configuration portrait \
  --trust-server-cert \
  --open
```

Important options:

- `--output PATH`: Base path for output files. Default: `output/generated.png`. The CLI inserts `-<unix_ms>` before the extension (for example `output/generated.png` → `output/generated-1735123456789.png`). Multiple images append `-2`, `-3`, … before the extension. Success lines print as `Wrote …` on stdout.
- `--configuration VALUE`: Draw Things configuration. Existing `.json` files are converted to FlatBuffer bytes; other existing files are sent as raw FlatBuffer bytes; simple names resolve to saved JSON configs.
- `--configuration-json VALUE`: JSON configuration file or saved config name (mutually exclusive with `--configuration`).
- `--trust-server-cert`: Trust the certificate presented by a localhost server for this connection.
- `--force-trust-server-cert`: Trust the certificate presented by any server (MITM risk).
- `--root-cert PATH`: Pinned PEM root/server certificate.
- `--no-tls`: Plaintext gRPC when the server was installed with `--no-tls`.
- `--max-message-mb N`: gRPC send/receive limits in MiB.
- `--open`: Open written images with the platform default viewer.
- **Prompt wildcards:** `{a|b}` picks one branch at random; `{a, b}` does the same when the block has no `|`. Only **depth‑0** delimiters split (nested `{…}` may contain `|` or commas). Choices can nest; expansion repeats until done, with limits on passes (~128) and output length (~100k chars). Bad or stuck templates raise an error (HTTP 400 from **`dts-util web`**). **`--generations N`** (CLI) or **`generations`** (web JSON) runs **N** separate RPCs; the template prompt is wildcard-expanded again on every run.

### Generate shorthand (prompt-first)

When the first argument after the program name is not a known subcommand (`generate`, `configs`, `reflect`, `tls`, `models`, `web`, `server`, …), not a lifecycle verb, and not a flag, the line is treated as shorthand for image generation.

Syntax:

```text
dts-util PROMPT [PROFILE] [flags…]
```

Rules:

1. `PROMPT` is one shell word unless you quote a multi-word prompt.
2. Optional `PROFILE` is the second word before any flag; it uses the same resolution as `--configuration` (saved name, path to `.json`, or raw FlatBuffer path).
3. Flags and their values must appear after `PROFILE` (if any). Example: `dts-util "hello" portrait --negative-prompt blur`.

Expansion (conceptually): `generate --prompt PROMPT --configuration … --trust-server-cert --open` plus your trailing flags. `--trust-server-cert` and `--open` are always added for shorthand so local TLS and opening the PNG match the common interactive path.

Configuration when `PROFILE` is omitted:

1. `DTS_UTIL_DEFAULT_CONFIGURATION` if set (non-empty) in the environment.
2. Otherwise saved profile `zit` (`zit.json` under `configs path`). If `zit.json` is missing, the tool creates a starter JSON once (512×512, default sampling fields, `model` guessed like `generate`, or empty with stderr).
3. After materializing the implicit profile, the process runs `os.environ.setdefault("DTS_UTIL_DEFAULT_CONFIGURATION", "zit")` so child processes can see the profile name if you did not already export something else.

**Common tasks (shorthand)**

| Goal | Command | What you get |
| --- | --- | --- |
| Single-line local generate | `uv run dts-util "a small robot"` | Same as `generate` with trust + open + implicit `zit` profile after first-run materialization |
| Named saved profile | `uv run dts-util "a small robot" portrait` | Uses `portrait` (or path) as `--configuration` |
| Extra TLS flags | `uv run dts-util "…" --root-cert ./pem` | Adds your flags after the injected defaults |

Explicit `dts-util generate` without `--configuration` / `--configuration-json` still fails fast; shorthand is the path that auto-bootstraps `zit.json`.

---

## Examples

### Basic installation

```bash
uv run dts-util server install
uv run dts-util server install -m /path/to/models
```

### Advanced installation

```bash
uv run dts-util server install -p 7860 -n "MyServer" -m /path/to/models
uv run dts-util server install -s "your-secret-here"
uv run dts-util server install --model-browser --debug --no-flash-attention
```

### Server management

```bash
uv run dts-util server test
uv run dts-util server test --port 7860
uv run dts-util reflect --trust-server-cert
uv run dts-util configs path
uv run dts-util tls path
uv run dts-util tls export
uv run dts-util server restart
uv run dts-util server restart --model-browser
uv run dts-util server uninstall
```

## Image generation

If you only run one explicit generate invocation, run this:

```bash
uv run dts-util generate \
  --prompt "a small robot painting clouds" \
  --configuration portrait \
  --trust-server-cert \
  --open
```

Explicit `generate` requires `--configuration` or `--configuration-json` so the server receives FlatBuffer configuration bytes before streaming.

**Common tasks (`generate`)**

| Goal | Command | What you get |
| --- | --- | --- |
| Saved config | `uv run dts-util generate --prompt "…" --configuration portrait --trust-server-cert` | PNG under `./output` with default output naming |
| Draw Things JSON file | `uv run dts-util generate --prompt "…" --configuration config.json --trust-server-cert` | PNG after JSON → FlatBuffer via [`flatc`](https://github.com/google/flatbuffers) |
| Open result | `uv run dts-util generate --prompt "…" --configuration config.json --trust-server-cert --open` | PNG plus viewer launch |
| Prebuilt FlatBuffer | `uv run dts-util generate --prompt "…" --configuration config.bin --trust-server-cert` | PNG without running `flatc` on JSON |
| Pinned cert | `uv run dts-util generate --prompt "…" --configuration config.json --root-cert cert.pem` | TLS verified against a known PEM |
| Remote diagnostic | `uv run dts-util generate --host gpu.local --prompt "…" --configuration config.json --force-trust-server-cert` | Trust-on-first-use for that host (MITM risk) |

Prefer `--root-cert` off localhost. Use `--force-trust-server-cert` only when you cannot pin a cert and accept the risk for that connection.

## Environment variables

| Variable | Used for |
| --- | --- |
| `DRAW_THINGS_MODEL_PATH` | Default Draw Things models directory for `server install` (CLI `--model-path` overrides). Also used when guessing `model` in auto-created `zit.json`. |
| `DTS_UTIL_DEFAULT_CONFIGURATION` | Shorthand: profile name or path when you omit the second positional. Set automatically to `zit` (via `setdefault`) when the tool materializes the implicit profile, unless you already exported another value. |
| `DTS_UTIL_DEFAULT_MODEL` | Basename (e.g. `my.ckpt`) for the `model` field when creating `zit.json` the first time; overrides guessing from the models directory. |

`DRAW_THINGS_MODEL_PATH` example:

```bash
export DRAW_THINGS_MODEL_PATH=/path/to/your/models
uv run dts-util server install
```

If both the variable and `--model-path` are set, the CLI option wins.

## Development workflow with uv

```bash
uv sync --dev
uv run pytest
```

## Exit codes

- `0`: Success
- `1`: Runtime error (connection, configuration, RPC, I/O, and similar)
- `2`: Invalid arguments (for example, bare LaunchAgent lifecycle verbs without the `server` prefix, or too many positional tokens in shorthand)

## See also

- [DRAW-THINGS-GRPC-API.md](DRAW-THINGS-GRPC-API.md): upstream service this repository calls
- [PROTOBUF.md](PROTOBUF.md): protobuf and FlatBuffer schemas
- [README.md](README.md): overview and quickstart
