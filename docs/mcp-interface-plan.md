# MCP interface for `dts-utils`

Maintainer record for the stdio MCP server (**`dts-utils-mcp`**). Operator setup, tool list, and Cursor config: [CLI.md § MCP](../CLI.md#mcp-dts-utils-mcp).

**Status:** Shipped (Phases 1–5). Merged in PRs [#13](https://github.com/funkatron/dts-utils/pull/13), [#14](https://github.com/funkatron/dts-utils/pull/14), [#15](https://github.com/funkatron/dts-utils/pull/15); follow-up fixes in [#16](https://github.com/funkatron/dts-utils/pull/16). Phase 5 (Streamable HTTP) in [#24](https://github.com/funkatron/dts-utils/pull/24) — merge-ready on **`feature/phase-5-mcp-streamable-http`**.

---

## Contents

- [Summary](#summary)
- [Architecture](#architecture)
- [Shipped layout](#shipped-layout)
- [Tool surface](#tool-surface)
- [Phases (delivered)](#phases-delivered)
- [Deviations from the original plan](#deviations-from-the-original-plan)
- [Security](#security)
- [Tests](#tests)
- [See also](#see-also)

---

## Summary

Coding agents drive Draw Things generation over MCP **stdio** (local hosts) or **Streamable HTTP** on the Draw Things machine — same Python APIs as **`generate`** and **`web`**, no CLI subprocess wrapper and no HTTP proxy to **`dts-utils web`**.

| Item | Value |
| --- | --- |
| Entrypoint | **`dts-utils-mcp`** → **`dts_utils.mcp.server:main`** |
| Optional dep | **`uv sync --extra mcp`** or **`dts-utils[mcp]`**; dev/CI via **`uv sync --dev`** |
| Transport | **stdio** (default); **`serve`** → Streamable HTTP **`127.0.0.1:1976/mcp`** |
| HTTP auth | **`DTS_MCP_TOKEN`** bearer when set (separate from **`DTS_WEB_TOKEN`**) |
| Default gRPC | **`localhost:7859`**, **`trust_server_cert`** on loopback, profile **`default`** |
| Lifecycle gate | **`DTS_MCP_ALLOW_SERVER_LIFECYCLE=1`** (stdio only; macOS; **`install`/`uninstall` not exposed**) |

---

## Architecture

```text
MCP host (Cursor, Claude Desktop, remote app, …)
       │  stdio (MCP)  or  HTTP Streamable /mcp
       ▼
dts-utils-mcp  (FastMCP)
       │
       ├── tools.py / lifecycle.py  →  generate_api, models_api, configs, pipeline, grpc.utils
       ├── resources.py             →  config / output / pipeline URIs + generate_image prompt
       ├── client_options.py          →  GrpcClientOptions (shared semantics with web)
       ├── http_auth.py               →  bearer token + bind warnings (HTTP only)
       └── generation_session.py      →  execute lock + cooperative cancel (shared with web)
       │
       ▼
gRPCServerCLI  (TLS default; plaintext when installed with --no-tls)
```

**Rejected alternatives (unchanged):** CLI subprocess wrapper; HTTP proxy to **`dts-utils web`**.

---

## Shipped layout

```text
src/dts_utils/mcp/
  server.py          # FastMCP registration; stdio default, serve → HTTP
  tools.py           # core + pipeline + models tools
  lifecycle.py       # gated macOS LaunchAgent tools
  resources.py       # URI templates + generate_image prompt
  client_options.py  # build_grpc_client_options, non_loopback_warning
  errors.py          # raise_tool_error (mirrors web _map_exc)
  paths.py           # resource path allowlists
  env.py             # lifecycle_tools_enabled(), HTTP defaults
  http_auth.py       # DTS_MCP_TOKEN bearer + bind warnings
  serialize.py       # model/index dict helpers

src/dts_utils/generation_session.py   # execute_lock, generation_cancel_event (web + MCP)
```

No separate **`schema.py`** or **`dts_utils/service/`** module — handlers call **`generate_api`** directly; **`client_options.py`** holds shared gRPC option building.

---

## Tool surface

### Always registered (11 tools)

| Tool | Purpose |
| --- | --- |
| `dts_server_check` | Probe gRPC listener |
| `dts_list_configs` | Saved profile stems |
| `dts_get_config` | Read one profile JSON |
| `dts_expand_prompt` | Preview `{a\|b}` wildcards |
| `dts_generate_image` | Generate PNG(s); paths by default |
| `dts_list_installed_models` | Scan Draw Things **`Models`** |
| `dts_models_search` | Search built community index |
| `dts_models_doctor` | Partial downloads, orphans, index mismatches |
| `dts_pipeline_run` | Run pipeline profile (blocks until complete) |
| `dts_pipeline_status` | Read **`heartbeat.json`** / **`pipeline_run.json`** |
| `dts_generate_cancel` | Cooperative cancel between batch iterations |

### Gated lifecycle (4 tools, macOS)

Requires **`DTS_MCP_ALLOW_SERVER_LIFECYCLE=1`** on the MCP process:

| Tool | Purpose |
| --- | --- |
| `dts_server_status` | LaunchAgent plist summary (secrets redacted) + listener probe |
| `dts_server_start` | Bootstrap LaunchAgent job |
| `dts_server_stop` | Boot out job |
| `dts_server_restart` | Restart; optional model-browser plist sync |

### Resources and prompts

| URI / name | Content |
| --- | --- |
| `dts://config/{stem}` | Saved profile JSON |
| `dts://output/{relative_path}` | File under **`./output`** or **`DTS_MCP_OUTPUT_ROOTS`** |
| `dts://pipeline/{run_id}/{step_id}/{filename}` | Pipeline artifact (**`DTS_MCP_PIPELINE_RUN_ROOT`** or default run root) |
| Prompt **`generate_image`** | Short workflow hint for agents |

Path traversal (`..`) rejected for all resource URIs.

---

## Phases (delivered)

### Phase 1 — MVP

- [x] Six core tools (see table above, first six).
- [x] **`uv run dts-utils-mcp`** starts without live gRPC.
- [x] **`tests/test_mcp_server.py`** with stubs.
- [x] Cursor config in **CLI.md** (with **`--extra mcp`**).
- [x] **CHANGELOG**, **AGENTS.md** pointers.

### Phase 2 — Models, pipeline, cancel

- [x] **`dts_models_search`**, **`dts_models_doctor`**, **`dts_pipeline_run`**, **`dts_pipeline_status`**, **`dts_generate_cancel`**.
- [x] Shared **`generation_session.py`** with web (lock + cancel event).
- [x] Pipeline/cancel tests in **`test_mcp_server.py`**.

### Phase 3 — Resources + prompts

- [x] Three resource URI templates + **`generate_image`** prompt.
- [x] **`tests/test_mcp_resources.py`** (reads, traversal rejection).

### Phase 4 — Gated lifecycle

- [x] Four lifecycle tools behind **`DTS_MCP_ALLOW_SERVER_LIFECYCLE=1`**.
- [x] Absent by default; macOS requirement at invocation.
- [x] **`tests/test_mcp_lifecycle.py`**.

### Phase 5 — Streamable HTTP on DT host

- [x] **`dts-utils-mcp serve`** — Streamable HTTP on **`127.0.0.1:1976/mcp`** (override **`--bind`**, **`--port`**, **`--path`**).
- [x] Bearer auth when **`DTS_MCP_TOKEN`** set; **401** without token.
- [x] Lifecycle tools **not** registered over HTTP.
- [x] Non-loopback bind warning without token (matches web pattern).
- [x] **`tests/test_mcp_http_transport.py`**.

### Post-ship fixes ([#16](https://github.com/funkatron/dts-utils/pull/16))

- [x] Clear conflicting **`trust_server_cert`** when **`root_cert`** or **`force_trust_server_cert`** set.
- [x] Redact **`--shared-secret`** in **`dts_server_status`** **`program_arguments`**.
- [x] Catch **`SystemExit`** from plist model-browser helpers (return tool error, do not kill MCP process).

---

## Deviations from the original plan

| Planned | Shipped |
| --- | --- |
| Plain **`mcp`** SDK server module | **FastMCP** from official **`mcp`** package (**`mcp>=1.27,<2`**) |
| **`schema.py`** for tool I/O | Inline tool signatures + **`serialize.py`** helpers |
| Optional **`dts_utils/service/`** refactor | **`client_options.py`** only; web still has local helpers |
| **`dts_pipeline_run`** async + immediate **`run_id`** | Blocks until pipeline completes (hosts rely on cancel + timeouts) |
| MCP logging notifications during gRPC stream | Not implemented; tool returns final result |
| Second gate for **`install`** | **`install`/`uninstall` not registered** (no second gate needed) |

Non-goals unchanged: no **`models fetch`**, no **`reflect`** tool, no lifecycle/install over HTTP, no LaunchAgent for MCP HTTP in v1.

---

## Security

| Risk | Mitigation |
| --- | --- |
| Remote MCP listener | Bearer **`DTS_MCP_TOKEN`** when exposed; default loopback bind; wide-bind stderr warning |
| Path exfiltration | Resource allowlists + canonical paths; **`..`** rejected |
| Accidental server misconfig | Lifecycle gated (stdio only); no install/uninstall tools |
| Secret leakage | **`shared_secret`** never logged; redacted in status **`program_arguments`** |
| Non-loopback gRPC | Allowed with warning; TLS trust flags mutually exclusive in **`client_options`** |
| Huge payloads | **`include_image_data`** default false; prefer resource URIs |

---

## Tests

| Module | Coverage |
| --- | --- |
| **`tests/test_mcp_server.py`** | Tool registration, core handlers, pipeline/cancel (stubs) |
| **`tests/test_mcp_resources.py`** | Resource reads, traversal rejection |
| **`tests/test_mcp_lifecycle.py`** | Gate, macOS check, status redaction, plist errors |
| **`tests/test_mcp_http_transport.py`** | HTTP auth, tool list, stub check, stdio regression |
| **`tests/test_mcp_client_options.py`** | TLS option mutual exclusion |

Run: **`uv sync --dev`** && **`uv run pytest tests/test_mcp*.py`**. No live **`gRPCServerCLI`** required for CI.

Manual smoke (macOS): Cursor MCP panel → **`dts_server_check`** → **`dts_generate_image`** against local server.

---

## See also

| Document | Contents |
| --- | --- |
| [CLI.md § MCP](../CLI.md#mcp-dts-utils-mcp) | Install, Cursor JSON, tool/resource tables |
| [AGENTS.md](../AGENTS.md) | Build/test, **`mcp/`** layout pointer |
| [DRAW-THINGS-GRPC-API.md](../DRAW-THINGS-GRPC-API.md) | Streaming RPC behavior |
| [CLI.md § web](../CLI.md#web-dts-utils-web) | Parallel HTTP API |
