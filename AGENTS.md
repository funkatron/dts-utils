# Conventions for coding agents and automation

This file is for people and tools that edit or test `dts-utils`. End-user CLI behaviour lives in [README.md](README.md) and [CLI.md](CLI.md).

## Build and test

```bash
uv sync --dev
uv run pytest
```

Integration-style gRPC tests may skip without a live server; see [tests/README.md](tests/README.md) and [PROTOBUF.md](PROTOBUF.md).

### Pytest markers

[`pyproject.toml`](pyproject.toml) registers:

| Marker | Meaning |
| --- | --- |
| `integration` | Tests that may assume a reachable gRPC server or local model assets; often skip when prerequisites are missing. |

CI (`.github/workflows/ci.yml`) runs **`uv run pytest`** with **no `-m` filter**, so default runs include marked tests; those tests should **skip** cleanly on Ubuntu when a server is absent rather than fail.

## CLI dispatch (`dts-utils`)

Console entrypoint: [`dts_utils.cli_router:main`](src/dts_utils/cli_router.py). Named subcommands (after `dts-utils`) route roughly as follows:

| Subcommand | Implementation |
| --- | --- |
| `server …` | [`installer/server_installer.py`](src/dts_utils/installer/server_installer.py) (`install`, `uninstall`, `start`, `stop`, `restart`, `test`, `check`) |
| `generate` | [`generate.py`](src/dts_utils/generate.py) |
| Prompt-first shorthand (`dts-utils "…"`) | Same as `generate` after argv rewrite in `cli_router` |
| `configs` | [`configs.py`](src/dts_utils/configs.py) |
| `reflect` | [`grpc/reflect.py`](src/dts_utils/grpc/reflect.py) |
| `tls` | [`tls_export.py`](src/dts_utils/tls_export.py) |
| `models` | [`model_index/cli.py`](src/dts_utils/model_index/cli.py) |
| `web` | [`web/cli.py`](src/dts_utils/web/cli.py) |

## Layout

- `src/dts_utils/cli_router.py` — top-level dispatch and prompt-first shorthand.
- `src/dts_utils/configs.py` — saved JSON configs; implicit shorthand profile **`default`** (`DEFAULT_PROFILE_NAME` → **`default.json`**), env `DTS_UTILS_DEFAULT_CONFIGURATION` / `DTS_UTILS_DEFAULT_MODEL`.
- `src/dts_utils/generate*.py` — generation pipeline and public Python API (see package `__init__`).
- `src/dts_utils/installer/` — macOS LaunchAgent install lifecycle.
- `src/dts_utils/grpc/` — channels, stubs, `is_server_running` (TLS-first loopback probe, plaintext fallback; `prefer_plaintext` for `--no-tls` servers).
- `src/dts_utils/model_index/` — community metadata index (`dts-utils models`).
- `src/dts_utils/tls_export.py` — PEM path/export (`dts-utils tls`).
- `src/dts_utils/web/` — loopback Starlette UI (`dts-utils web`); see [CLI.md](CLI.md#web-dts-utils-web).

## Implicit profile: `default` / `default.json`

Shorthand and the web UI use **`default`** as the saved profile stem (**`default.json`** under **`dts-utils configs path`**). Legacy **`zit.json`** in that directory is renamed to **`default.json`** on first bootstrap when **`default.json`** is missing (`ensure_default_generation_json_config`). Docs and tests should say **`default`** unless discussing historical **`zit`** releases (see [CHANGELOG.md](CHANGELOG.md)).

## Behaviour agents often trip over

- **`reflect` and `UNIMPLEMENTED`:** Draw Things `gRPCServerCLI` often does not expose gRPC reflection. That is expected; image generation can still work. README troubleshooting covers this.
- **`server check` / `server test`:** Probes try TLS against loopback (trust server-presented cert), then plaintext. Installs with `--no-tls` need **`server check --no-tls`** (or `server test --no-tls`).
- **Shorthand:** `dts-utils "prompt"` implies `--trust-server-cert` and `--open` for local happy paths; explicit `generate` still requires `--configuration` when not using shorthand.

## Documentation boundaries

- **User-facing:** [README.md](README.md), [CLI.md](CLI.md), [DRAW-THINGS-GRPC-API.md](DRAW-THINGS-GRPC-API.md), [PROTOBUF.md](PROTOBUF.md) — direct operational prose, no “internal review” voice.
- **Operators:** [docs/README.md](docs/README.md) — where to read what.
- **Agents:** this file.

When you change CLI behaviour, update [CLI.md](CLI.md) and the user-facing sections of [README.md](README.md); add a [CHANGELOG.md](CHANGELOG.md) note when the change is user-visible.

## CLI and automation

Prefer non-interactive flags documented in [CLI.md](CLI.md). Keep exit codes and stderr messages actionable for scripts (see existing `server` / `generate` behaviour).
