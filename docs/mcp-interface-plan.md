# Plan: MCP interface for `dts-utils`

Operator-facing MCP setup (after ship) will live in [CLI.md](../CLI.md) and [README.md](../README.md). This document is for **maintainers and contributors**: goals, architecture, phased delivery, acceptance criteria, and risks.

**Status:** Planned (not shipped).

---

## Problem

Coding agents (Cursor, Claude Desktop, custom runners) need to drive Draw Things generation without:

- fragile `dts-utils …` subprocess argv parsing,
- a separate `dts-utils web` HTTP process plus `DTS_WEB_TOKEN`, or
- re-implementing gRPC / FlatBuffer config conversion.

`dts-utils` already exposes programmatic APIs (`generate_api`, `models_api`, pipeline runner) and a web HTTP layer that mirrors generation flows. An MCP server over **stdio** is the natural agent integration surface.

---

## Goals

| Goal | Notes |
| --- | --- |
| **G1** | Expose read + generate tools callable from MCP hosts (Cursor first). |
| **G2** | Reuse existing Python APIs — no duplicate business logic vs CLI/web. |
| **G3** | Safe defaults: loopback gRPC, `trust_server_cert` on loopback, stdio-only transport in v1. |
| **G4** | Actionable structured errors (`ConfigurationError`, `GenerationRpcError`, …) in tool results. |
| **G5** | Testable without live `gRPCServerCLI` (stubs / fakes like existing pytest suite). |

---

## Non-goals (v1)

| Item | Reason |
| --- | --- |
| Remote / Streamable HTTP MCP by default | stdio is enough for local agents; HTTP adds auth surface. |
| `models fetch` / weight downloads | Network, disk, Hugging Face creds; high blast radius. |
| `reflect` tool | Often `UNIMPLEMENTED` on Draw Things; low agent value. |
| Bulk `configs import-draw-things` | Prefer explicit human or CLI workflow. |
| Un-gated `server install` / lifecycle | Agents could restart or misconfigure LaunchAgent. |

Lifecycle tools may ship later behind an explicit env gate (see Phase 4).

---

## Architecture

```text
MCP host (Cursor)
       │  stdio (JSON-RPC / MCP)
       ▼
dts-utils-mcp  (new entrypoint)
       │
       ├── tools/*.py  →  dts_utils.generate_api, models_api, configs, grpc.utils
       ├── optional resources  →  config JSON, output PNGs, pipeline artifacts
       └── shared with web via same APIs (not HTTP proxy)
       │
       ▼
gRPCServerCLI  (localhost:7859, TLS default)
```

**Rejected alternatives**

| Approach | Verdict |
| --- | --- |
| Subprocess CLI wrapper | Slow, brittle argv, poor errors. |
| HTTP proxy to `dts-utils web` | Extra process, token auth, duplicated deployment. |
| Native Python API layer | **Chosen** — matches `web/app.py` intent. |

### Code layout (target)

```text
src/dts_utils/mcp/
  __init__.py
  server.py       # MCP server lifecycle, stdio transport
  tools.py        # tool handlers (thin)
  schema.py       # JSON Schema / typed payloads for tool I/O
  resources.py    # optional Phase 3
  env.py          # env gates (lifecycle, base64 default, …)
```

Optional thin refactor (Phase 1 or 2): extract shared request-building helpers from `web/app.py` into `dts_utils/service/` **only if** MCP and web would otherwise duplicate `_build_client_options` / `_build_generation_options` logic. Prefer calling `generate_api` directly when sufficient.

### Dependency

```toml
[project.optional-dependencies]
mcp = ["mcp>=1.27,<2"]

[project.scripts]
dts-utils-mcp = "dts_utils.mcp.server:main"
```

Use official **`mcp`** Python SDK (v1.x stable line). Pin `<2` until MCP SDK v2 is stable. **Do not** add `fastmcp` unless maintainers explicitly prefer it — one MCP stack keeps CI lean.

`uv sync --extra mcp` for developers; end users: `uv pip install 'dts-utils[mcp]'`.

---

## Tool surface

### Connection defaults (all generate tools)

| Parameter | Default | Notes |
| --- | --- | --- |
| `host` | `localhost` | |
| `port` | `7859` | |
| `trust_server_cert` | `true` when loopback | Same as shorthand / web happy path |
| `no_tls` | `false` | Set when server installed with `--no-tls` |
| `configuration` | `default` | Saved profile stem under `configs path` |
| `shared_secret` | env / omitted | Never log |

Environment fallbacks align with CLI: `DTS_UTILS_DEFAULT_CONFIGURATION`, `DRAW_THINGS_MODEL_PATH`, etc.

---

## Phase 1 — MVP (stdio + core tools)

**Goal:** Agent can probe server, list configs, expand wildcards, generate PNG(s), list installed models.

| Tool | Input (summary) | Output (summary) | Implementation |
| --- | --- | --- | --- |
| `dts_server_check` | `host`, `port`, `no_tls` | `{ "running": bool }` | `grpc.utils.is_server_running` |
| `dts_list_configs` | optional `config_dir` | `{ "configs": [stems] }` | `configs.list_configuration_names` |
| `dts_get_config` | `configuration`, optional `config_dir` | `{ "stem", "path", "json" }` | resolve + read JSON |
| `dts_expand_prompt` | `prompt`, `negative_prompt`, `count` | `{ "prompts", "negative_prompts" }` | `expand_prompt_templates_for_batch` |
| `dts_generate_image` | prompt, configuration, gRPC opts, `generations`, `output`, `include_image_data` | paths, expanded prompts, optional base64 | `generate_to_paths` / `generate_png_batch` |
| `dts_list_installed_models` | optional `models_dir`, `limit` | summaries from `list_installed_models` | `models_api` |

**`dts_generate_image` details**

- Default `include_image_data=false` — return filesystem paths only (avoids huge MCP payloads).
- Output path behavior matches CLI: ms suffix under `output/` default.
- Map exceptions to MCP tool errors with `isError: true` and human-readable `detail` (mirror `_map_exc` in web).

**Acceptance**

- [ ] `uv run dts-utils-mcp` starts stdio server without live gRPC.
- [ ] `uv sync --extra mcp --dev` + pytest module `tests/test_mcp_server.py` passes with stubs.
- [ ] Cursor example config documented in CLI.md (command + args).
- [ ] CHANGELOG entry under `[Unreleased]`.
- [ ] AGENTS.md one-line pointer to this plan + entrypoint.

**Tests**

- In-process MCP client against server object (SDK test pattern).
- Stub channel/stub for generate; no `live_grpc_cli` required.
- Tool schema validation (required fields, `generations` max 25).

---

## Phase 2 — Models index + pipeline + cancel

**Goal:** Agents can search community metadata, run pipeline profiles, poll long jobs, cancel generation.

| Tool | Purpose | Implementation |
| --- | --- | --- |
| `dts_models_search` | Query built index | `model_index.search` + `data/drawthings_uncurated_models.json` |
| `dts_models_doctor` | Installed vs expected files | `model_index.local.doctor_local_models` |
| `dts_pipeline_run` | Start pipeline profile | `pipeline.run_plan` + `PipelineRunner` |
| `dts_pipeline_status` | Heartbeat + manifest summary | read `heartbeat.json`, `pipeline_run.json` |
| `dts_generate_cancel` | Cancel in-flight generate | shared cancel event (same as web) |

**Long-running work**

- Emit MCP **logging** notifications during gRPC stream (preview / progress), matching `api_generate_stream` events where possible.
- `dts_pipeline_run` returns `{ "run_id", "run_root" }` immediately when async mode is used, or blocks with progress until complete (document host timeout expectations).

**Concurrency**

- Reuse web `_execute_lock` and `_generation_cancel_event` via a shared module (e.g. `dts_utils.generation_session`) so web and MCP cannot double-submit to gRPC.

**Acceptance**

- [ ] Pipeline smoke with stub executors in pytest.
- [ ] Cancel test: cancel event stops stub stream.
- [ ] CLI.md tools table updated.

---

## Phase 3 — Resources + prompts

**Goal:** Hosts fetch configs and images via MCP resources instead of bloated tool returns.

| Resource URI | Content |
| --- | --- |
| `dts://config/{stem}` | Saved profile JSON |
| `dts://output/{relative_path}` | PNG under allowed output roots |
| `dts://pipeline/{run_id}/{step_id}/{filename}` | Pipeline artifact |

**Prompts (optional)**

| Prompt | Purpose |
| --- | --- |
| `generate_image` | Documents profile choice, TLS, when to use pipeline vs single-shot |

**Path safety**

- Resolve all paths under allowlist: `configs path`, configured output dir, pipeline `run_root`.
- Reject `..` and paths outside roots.

**Acceptance**

- [ ] Resource read tests for config + fixture PNG.
- [ ] Path traversal rejected in tests.

---

## Phase 4 — Gated server lifecycle (macOS only)

**Goal:** Optional tools for operators who explicitly opt in.

**Gate:** `DTS_MCP_ALLOW_SERVER_LIFECYCLE=1` (unset → tools not registered).

| Tool | Notes |
| --- | --- |
| `dts_server_status` | LaunchAgent flags, model browser |
| `dts_server_start` / `stop` / `restart` | macOS only; clear stderr if unsupported platform |

**Do not** expose `install` / `uninstall` in MCP without a second gate (e.g. `DTS_MCP_ALLOW_SERVER_INSTALL=1`).

**Acceptance**

- [ ] Tools absent when gate unset.
- [ ] Linux CI: lifecycle tools not listed / return platform error.

---

## Security checklist

| Risk | Mitigation |
| --- | --- |
| Unauthenticated remote MCP | v1: stdio only, no HTTP listener. |
| Path exfiltration | Resource allowlist + canonical paths. |
| Accidental server restart | Lifecycle gated; install doubly gated. |
| Secret leakage | `shared_secret` never in logs; omit from error context. |
| Non-loopback gRPC | Allowed but tool result includes warning string. |
| Huge payloads | `include_image_data` default false; resource URIs preferred. |

---

## Documentation map (on ship)

| Audience | Document |
| --- | --- |
| Users / agents | CLI.md § MCP, README quick mention |
| Maintainers | this file |
| Automation | AGENTS.md entrypoint + env gates |
| Tests | tests/README.md if integration opt-in added |

---

## Cursor configuration (target)

```json
{
  "mcpServers": {
    "dts-utils": {
      "command": "uv",
      "args": [
        "run",
        "--directory", "/path/to/dts-utils",
        "dts-utils-mcp"
      ],
      "env": {
        "DTS_UTILS_DEFAULT_CONFIGURATION": "default"
      }
    }
  }
}
```

Installed package:

```json
{
  "mcpServers": {
    "dts-utils": {
      "command": "dts-utils-mcp"
    }
  }
}
```

---

## Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| `flatc` missing | Same as CLI — clear `ConfigurationError` in tool result; document in CLI.md. |
| MCP SDK v2 churn | Pin `mcp>=1.27,<2`; revisit when v2 stable. |
| Host tool timeout | Document long runs; Phase 2 async + status polling. |
| Logic drift web vs MCP | Shared APIs; optional `service` module; web tests + MCP tests same fixtures. |
| macOS-only assumptions | Platform checks for lifecycle; generate works anywhere server is reachable. |

---

## Delivery checklist (per phase)

1. Implement on branch `cursor/mcp-interface-cee0` (or follow `cursor/<name>-cee0` convention).
2. `uv sync --extra mcp --dev` && `uv run pytest`.
3. Update CLI.md / CHANGELOG for user-visible phases.
4. Manual smoke: Cursor MCP panel → `dts_server_check` → `dts_generate_image` against local server.
5. Record `gRPCServerCLI` tag in CHANGELOG **Tested with** when manually smoke-tested.

---

## See also

- [DRAW-THINGS-GRPC-API.md](../DRAW-THINGS-GRPC-API.md) — streaming behavior for progress notifications.
- [CLI.md § web](../CLI.md#web-dts-utils-web) — parallel HTTP API shapes.
- [AGENTS.md](../AGENTS.md) — build/test conventions.
- [models-fetch-roadmap.md](models-fetch-roadmap.md) — example phased maintainer doc.
