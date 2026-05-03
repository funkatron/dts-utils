# Conventions for coding agents and automation

This file is for people and tools that edit or test `dts-utils`. End-user CLI behaviour lives in [README.md](README.md) and [CLI.md](CLI.md).

## Build and test

```bash
uv sync --dev
uv run pytest
```

Integration-style gRPC tests may skip without a live server; see [tests/README.md](tests/README.md) and [PROTOBUF.md](PROTOBUF.md).

## Layout

- `src/dts_util/cli_router.py` — top-level dispatch and prompt-first shorthand.
- `src/dts_util/configs.py` — saved JSON configs; implicit shorthand profile name **`zit`** (`DEFAULT_PROFILE_NAME`), env `DTS_UTIL_DEFAULT_CONFIGURATION` / `DTS_UTIL_DEFAULT_MODEL`.
- `src/dts_util/generate*.py` — generation pipeline and public Python API (see package `__init__`).
- `src/dts_util/installer/` — macOS LaunchAgent install lifecycle.
- `src/dts_util/grpc/` — channels, stubs, `is_server_running` (TLS-first loopback probe, plaintext fallback; `prefer_plaintext` for `--no-tls` servers).
- `src/dts_util/web/` — loopback Starlette UI (`dts-util web`); see [CLI.md](CLI.md#web-dts-util-web).

## Do not reintroduce `default.json` as the implicit profile

Older releases documented a **`default`** / **`default.json`** bootstrap. Current code uses **`zit`** / **`zit.json`** only. There is no migration that copies `default.json` → `zit.json`. If docs or tests mention an implicit profile, they must say **`zit`** unless describing a historical version (see [CHANGELOG.md](CHANGELOG.md)).

## Behaviour agents often trip over

- **`reflect` and `UNIMPLEMENTED`:** Draw Things `gRPCServerCLI` often does not expose gRPC reflection. That is expected; image generation can still work. README troubleshooting covers this.
- **`server check` / `server test`:** Probes try TLS against loopback (trust server-presented cert), then plaintext. Installs with `--no-tls` need **`server check --no-tls`** (or `server test --no-tls`).
- **Shorthand:** `dts-util "prompt"` implies `--trust-server-cert` and `--open` for local happy paths; explicit `generate` still requires `--configuration` when not using shorthand.

## Documentation boundaries

- **User-facing:** [README.md](README.md), [CLI.md](CLI.md), [DRAW-THINGS-GRPC-API.md](DRAW-THINGS-GRPC-API.md), [PROTOBUF.md](PROTOBUF.md) — direct operational prose, no “internal review” voice.
- **Operators:** [docs/README.md](docs/README.md) — where to read what.
- **Agents:** this file.

When you change CLI behaviour, update [CLI.md](CLI.md) and the user-facing sections of [README.md](README.md); add a [CHANGELOG.md](CHANGELOG.md) note when the change is user-visible.

## CLI and automation

Prefer non-interactive flags documented in [CLI.md](CLI.md). Keep exit codes and stderr messages actionable for scripts (see existing `server` / `generate` behaviour).
