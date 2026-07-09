# Conventions for coding agents and automation

This file is for people and tools that edit or test `dts-utils`. End-user CLI behaviour lives in [README.md](README.md) and [CLI.md](CLI.md).

## Build and test

```bash
uv sync --dev
uv run pytest
```

**`uv sync --dev`** pulls **`huggingface_hub`** (for **`models fetch`** tests) and **`mcp`** (for **`dts-utils-mcp`** tests). End users: **`uv sync --extra download`** for Hugging Face fetch sources; **`uv sync --extra mcp`** or **`dts-utils[mcp]`** for the MCP server.

Integration-style gRPC tests may skip without a live server; see [tests/README.md](tests/README.md) (ephemeral `gRPCServerCLI` via `DTS_GRPC_TEST_SPAWN_SERVER`) and [PROTOBUF.md](PROTOBUF.md#grpc-integration-tests).

### Pytest markers

[`pyproject.toml`](pyproject.toml) registers:

| Marker | Meaning |
| --- | --- |
| `integration` | Tests that may assume a reachable gRPC server or local model assets; often skip when prerequisites are missing. |
| `live_grpc_cli` | Opt-in tests that spawn `gRPCServerCLI` (`DTS_GRPC_TEST_SPAWN_SERVER=1`); see [tests/README.md](tests/README.md#ephemeral-grpcservercli-pytest). |

CI (`.github/workflows/ci.yml`) runs **`uv run pytest`** with **no `-m` filter**; **`live_grpc_cli`** tests are **deselected** by default via **`pyproject.toml`** **`addopts`**. Opt-in locally with **`pytest -m live_grpc_cli`** and **`DTS_GRPC_TEST_SPAWN_SERVER=1`** (see [tests/README.md](tests/README.md#ephemeral-grpcservercli-pytest)).

## CLI dispatch (`dts-utils`)

Console entrypoint: [`dts_utils.cli_router:main`](src/dts_utils/cli_router.py). Named subcommands (after `dts-utils`) route roughly as follows:

| Subcommand | Implementation |
| --- | --- |
| `server …` | [`installer/server_installer.py`](src/dts_utils/installer/server_installer.py) (`install`, `uninstall`, `start`, `stop`, `restart`, `test`, `check`, `list-models`, `tail`) |
| `generate` | [`generate.py`](src/dts_utils/generate.py) |
| Prompt-first shorthand (`dts-utils "…"`) | Same as `generate` after argv rewrite in `cli_router` |
| `configs` | [`configs.py`](src/dts_utils/configs.py) |
| `reflect` | [`grpc/reflect.py`](src/dts_utils/grpc/reflect.py) |
| `tls` | [`tls_export.py`](src/dts_utils/tls_export.py) |
| `models` | [`model_index/cli.py`](src/dts_utils/model_index/cli.py) |
| `web` | [`web/cli.py`](src/dts_utils/web/cli.py) (`serve`, `tail`, macOS LaunchAgent **`install` / `start` / `stop` / …** via [`web/launch_agent.py`](src/dts_utils/web/launch_agent.py)) |

## Layout

- `src/dts_utils/cli_router.py` — top-level dispatch and prompt-first shorthand.
- `src/dts_utils/configs.py` — saved JSON configs; implicit shorthand profile **`default`** (`DEFAULT_PROFILE_NAME` → **`default.json`**), env `DTS_UTILS_DEFAULT_CONFIGURATION` / `DTS_UTILS_DEFAULT_MODEL`.
- `src/dts_utils/generate*.py` — generation pipeline and public Python API (see package `__init__`).
- `src/dts_utils/models_api.py` — programmatic installed-model listing (`list_installed_models`, `list_installed_model_filenames`).
- `src/dts_utils/installer/` — macOS LaunchAgent install lifecycle.
- `src/dts_utils/grpc/` — channels, stubs, `is_server_running` (TLS-first loopback probe, plaintext fallback; `prefer_plaintext` for `--no-tls` servers).
- `src/dts_utils/model_index/` — community metadata index (`dts-utils models`); **`fetch`** loads bundled recipes from `dts_utils/model_fetch/recipe_files/` (optional **`uv sync --extra download`** for Hugging Face sources).
- `src/dts_utils/tls_export.py` — PEM path/export (`dts-utils tls`).
- `src/dts_utils/web/` — loopback Starlette UI (`dts-utils web`, `dts-utils web tail`); see [CLI.md](CLI.md#web-dts-utils-web).
- `src/dts_utils/generation_session.py` — shared execute lock and cooperative cancel (web + MCP).
- `src/dts_utils/mcp/` — MCP server (`dts-utils-mcp` stdio + **`serve`** Streamable HTTP); lifecycle tools gated by `DTS_MCP_ALLOW_SERVER_LIFECYCLE` (stdio only). Operator docs: [CLI.md](CLI.md#mcp-dts-utils-mcp). Agent guide: [docs/mcp-for-agents.md](docs/mcp-for-agents.md). Maintainer record: [docs/mcp-interface-plan.md](docs/mcp-interface-plan.md).

## Implicit profile: `default` / `default.json`

Shorthand and the web UI use **`default`** as the saved profile stem (**`default.json`** under **`dts-utils configs path`**). Legacy **`zit.json`** in that directory is renamed to **`default.json`** on first bootstrap when **`default.json`** is missing (`ensure_default_generation_json_config`). Docs and tests should say **`default`** unless discussing historical **`zit`** releases (see [CHANGELOG.md](CHANGELOG.md)).

## Saved profile naming

Use **lowercase kebab-case** stems (letters, digits, hyphens; optional dots for version segments). Examples: **`default`**, **`pikon-tall`**, **`ltx-2.3-portrait`**, **`prompt-to-video`**.

- **`default`** and bundled pipeline names (**`prompt-to-video`**) are reserved — do not rename them.
- Prefer **`{model-family}-{qualifier}`**: step count (**`-8step`**, **`-40step`**), aspect (**`-tall`**, **`-9x16`**, **`-landscape`**, **`-portrait`**), tuning (**`-gs-2.1`**), or feature (**`-pony-lora`**, **`-2x-up`**).
- **`configs import-draw-things`** applies mechanical normalization via **`normalize_profile_stem`** (lowercase, underscores → hyphens). Draw Things preset titles may still need manual renaming for clarity.
- Pipeline manifests reference other profile stems in **`t2i_configuration`** / **`video_configuration`** — update those when renaming video/T2I JSON profiles.

## Behaviour agents often trip over

- **`reflect` and `UNIMPLEMENTED`:** Draw Things `gRPCServerCLI` often does not expose gRPC reflection. That is expected; image generation can still work. README troubleshooting covers this.
- **`server check` / `server test`:** Probes try TLS against loopback (trust server-presented cert), then plaintext. Installs with `--no-tls` need **`server check --no-tls`** (or `server test --no-tls`).
- **`server list-models` vs `models installed`:** **`server list-models`** = live gRPC **`Echo`** catalog from **`gRPCServerCLI`** (needs **`--model-browser`**). **`models installed`** = filesystem scan of the Models dir; no server required. Do not conflate them in docs or scripts.
- **`server tail` / `web tail`:** **`server tail`** wraps macOS **`log show`** + **`log stream`** for **`gRPCServerCLI`**. **`web tail`** follows **`~/.config/dts-utils/web.log`** ( **`dts-utils web`** appends there by default; path also on **stdout** at web startup and in **`GET /api/health`**).
- **Shorthand:** `dts-utils "prompt"` implies `--trust-server-cert` and `--open` for local happy paths; explicit `generate` still requires `--configuration` when not using shorthand.

## Documentation boundaries

- **User-facing:** [README.md](README.md), [CLI.md](CLI.md), [DRAW-THINGS-GRPC-API.md](DRAW-THINGS-GRPC-API.md), [PROTOBUF.md](PROTOBUF.md) — direct operational prose, no “internal review” voice.
- **Operators:** [docs/README.md](docs/README.md) — where to read what.
- **Agents:** this file.

When you change CLI behaviour, update [CLI.md](CLI.md) and the user-facing sections of [README.md](README.md); add a [CHANGELOG.md](CHANGELOG.md) note when the change is user-visible.

When you add or rename **web routes**, **MCP tools**, or top-level **CLI command sections**, update the matching user doc (or run **`uv run python scripts/generate_docs.py`** for MCP params). **`tests/test_docs_drift.py`** fails CI if docs drift from code.

## CLI and automation

Prefer non-interactive flags documented in [CLI.md](CLI.md). Keep exit codes and stderr messages actionable for scripts (see existing `server` / `generate` behaviour).
