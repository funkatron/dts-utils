---
name: MCP Phase 1 — stdio MVP tools
overview: >-
  Ship dts-utils-mcp (stdio) with six core tools over existing Python APIs so coding agents
  can probe the gRPC server, read configs, expand prompts, generate PNGs, and list installed models.
  Phases 2–4 (pipeline, resources, lifecycle) are explicitly out of scope for this task.
todos:
  - id: branch-from-main
    content: "Cut feature/dts-mcp-phase-1-mvp from origin/main (after plan PR merge or rebase as needed)"
    status: pending
  - id: optional-dep-entrypoint
    content: "Add [mcp] optional extra, dts-utils-mcp script, src/dts_utils/mcp/ skeleton"
    status: pending
  - id: error-mapping
    content: "Implement map_dts_exception → MCP tool error (mirror web _map_exc semantics)"
    status: pending
  - id: register-six-tools
    content: "Register dts_server_check, list_configs, get_config, expand_prompt, generate_image, list_installed_models"
    status: pending
  - id: tests-stubs
    content: "Add tests/test_mcp_server.py — in-process MCP client, stubbed generate, schema checks"
    status: pending
  - id: docs-changelog
    content: "CLI.md MCP section, CHANGELOG [Unreleased], AGENTS.md entrypoint note"
    status: pending
  - id: verify-pytest
    content: "uv sync --extra mcp --dev && uv run pytest (full suite, CI-compatible)"
    status: pending
isProject: false
---

# Task: dts-mcp — MCP Phase 1 (stdio MVP)

Deliver **Phase 1** of the MCP interface: a stdio MCP server (`dts-utils-mcp`) with six tools, backed by existing `dts_utils` APIs, tested without live `gRPCServerCLI`.

---

## TL;DR

- **Problem:** Agents must subprocess the CLI or run `dts-utils web` + HTTP to drive Draw Things generation.
- **Planned fix:** New optional `[mcp]` package slice + `dts-utils-mcp` stdio server exposing six read/generate tools via `generate_api`, `configs`, `models_api`, `grpc.utils`.
- **Main layer:** `src/dts_utils/mcp/` (new); touch `pyproject.toml`, `tests/test_mcp_server.py`, `CLI.md`, `CHANGELOG.md`.
- **Out of scope:** Pipeline tools, MCP resources/prompts, server lifecycle, `models fetch`, HTTP MCP transport, web `service/` refactor (only if duplication forces it).

---

## Quickstart

1. **Branch / starting point:** `git fetch origin main && git checkout -b feature/dts-mcp-phase-1-mvp origin/main`
   - **Assumption:** Implement after [docs plan PR #12](https://github.com/funkatron/dts-utils/pull/12) merges, or rebase this branch onto `origin/main` if starting from `cursor/mcp-interface-plan-cee0`.
2. **First verification command:** `uv sync --extra mcp --dev && uv run pytest tests/test_mcp_server.py -v` (write reds before green).
3. **First file to touch:** `pyproject.toml` (`[project.optional-dependencies] mcp`, `[project.scripts] dts-utils-mcp`), then `src/dts_utils/mcp/server.py`.

---

## How do I...?

| Goal | Jump to |
| --- | --- |
| Implement now | Implementation checklist / Solution |
| Validate AC coverage | Acceptance criteria + Test-first plan |
| Resolve blockers | Open questions / blockers |
| Maintainer roadmap (all phases) | `docs/mcp-interface-plan.md` |

---

## At a glance

| Constant | Value |
| --- | --- |
| Issue / tracking | No Linear/GitHub issue yet — **dts-mcp** (inferred from planning thread + PR #12) |
| Maintainer doc | `docs/mcp-interface-plan.md` |
| Target branch | `feature/dts-mcp-phase-1-mvp` from `origin/main` |
| MCP SDK | `mcp>=1.27,<2` (official Python SDK v1.x) |
| Entrypoint | `dts-utils-mcp` → `dts_utils.mcp.server:main` |
| Default gRPC | `localhost:7859`, `trust_server_cert=true` on loopback |

---

## Source

- **Link / ID:** [PR #12 — docs MCP plan](https://github.com/funkatron/dts-utils/pull/12), `docs/mcp-interface-plan.md`, prior design thread.
- **Evidence vs assumptions:**

  **Evidence**

  - `docs/mcp-interface-plan.md` § Phase 1 lists six tools, acceptance bullets, and rejected alternatives (CLI subprocess, HTTP proxy).
  - `generate_api`, `models_api`, `configs`, `grpc.utils.is_server_running` already exist and power CLI/web.
  - `web/app.py` `_map_exc` maps `ConfigurationError` → 400, channel/RPC/empty → 502, cancelled → 499.
  - `AGENTS.md` build/test: `uv sync --dev` && `uv run pytest`; `live_grpc_cli` deselected by default.
  - User skill **FUNK-start-new-task** requires this planning artifact before implementation.

  **Assumptions**

  - **Assumption:** Phase 1 only — no pipeline/cancel/resources in this task.
  - **Assumption:** CI does not install `[mcp]` unless we add it to dev dependency-group or CI sync — **verify** so MCP tests run in CI.
  - **Assumption:** Branch naming follows `feature/dts-mcp-phase-1-mvp` (FUNK skill), not cloud-agent `cursor/*-cee0` unless user overrides.
  - **Unknown:** Whether PR #12 is merged before implementation starts.

---

## User stor(y/ies)

**Technical story (primary)** — *As a* coding agent host (Cursor) *I want* a stdio MCP server that exposes Draw Things operations as typed tools *so that* I can generate images without fragile CLI parsing or a separate web process.

**Technical story (maintainer)** — *As a* `dts-utils` maintainer *I want* MCP handlers to call the same Python APIs as `generate` and `web` *so that* behavior and errors stay consistent and testable.

*Traceability:* Derived from `docs/mcp-interface-plan.md` Problem + Goals G1–G2 (not from end-user ticket).

---

## Acceptance criteria

### MVP

| What must be true | How we verify |
| --- | --- |
| `dts-utils-mcp` starts stdio MCP server (no live gRPC required to boot) | Manual: process starts; pytest: server object / lifespan init |
| Tool `dts_server_check` returns `{ "running": bool }` | pytest calls tool with mocked `is_server_running` |
| Tool `dts_list_configs` returns profile stems | pytest with temp config dir |
| Tool `dts_get_config` returns stem, path, parsed JSON | pytest with fixture `default.json` |
| Tool `dts_expand_prompt` returns expanded prompt arrays | pytest; `count` capped at 25 |
| Tool `dts_generate_image` writes PNG path(s); `include_image_data` default false | pytest stubs gRPC stream; asserts paths exist, no base64 by default |
| Tool `dts_list_installed_models` returns summaries | pytest with temp models dir or mocked scan |
| DTS exceptions → MCP tool errors with readable `detail` (no secret leakage) | pytest raises `ConfigurationError` / `GenerationRpcError` through handler |
| `uv run pytest` passes (default markers; no `live_grpc_cli`) | CI-equivalent full run |
| Cursor MCP config example in `CLI.md` | Doc review |
| `CHANGELOG.md` `[Unreleased]` entry | Doc review |

### Follow-up (not this task)

- Phase 2: pipeline, models search, cancel — see `docs/mcp-interface-plan.md` § Phase 2.
- Phase 3: MCP resources — § Phase 3.
- Phase 4: gated lifecycle — § Phase 4.
- Manual smoke with live `gRPCServerCLI` on macOS — maintainer CHANGELOG **Tested with** (optional for merge).

---

## Test-first plan

- **Feasibility:** **Yes** — pytest + in-process MCP client (SDK pattern) + mocks/monkeypatch same as `tests/test_web_app.py`.

| AC area | Red / test intent |
| --- | --- |
| Tool registration | `list_tools` includes exactly six Phase 1 names |
| `dts_server_check` | Monkeypatch `is_server_running` → True/False |
| `dts_expand_prompt` | Invalid `count` → tool error (ConfigurationError path) |
| `dts_generate_image` | Monkeypatch `generate_to_paths` or channel; assert returned paths |
| Error mapping | `ConfigurationError` → isError tool result with detail string |
| `generations` max | `generations=26` rejected before gRPC |

- **Order:** Red tool-list test → implement server skeleton → red per-tool tests → green handlers → full pytest.

- **Not feasible in CI:** Live generation against real `gRPCServerCLI` — substitute: stub stream (same as web tests). Opt-in `live_grpc_cli` manual smoke documented in CHANGELOG only.

---

## Solution

### Primary

- Add `src/dts_utils/mcp/`:
  - `server.py` — MCP `Server`, stdio `run()`, tool registration.
  - `tools.py` — thin async/sync handlers calling library functions.
  - `errors.py` — `map_exception_to_tool_result(exc)` aligned with `_map_exc` status semantics.
  - `schema.py` — optional: shared input dict coercion for tools.
- `pyproject.toml`: optional `mcp = ["mcp>=1.27,<2"]`; script `dts-utils-mcp`.
- **Add `mcp` to `[dependency-groups] dev`** (or CI `uv sync`) so `tests/test_mcp_server.py` runs in CI without every user installing MCP.
- Handlers call directly:
  - `grpc.utils.is_server_running`
  - `configs.list_configuration_names`, resolve + read JSON
  - `expand_prompt_templates_for_batch`
  - `generate_to_paths` / `GrpcClientOptions` + `ImageGenerationRequestOptions`
  - `list_installed_models`

### Alternatives

| Alternate | Why not primary |
| --- | --- |
| FastMCP decorators | Extra dependency; maintainer doc chose official `mcp` SDK only. |
| HTTP proxy to `dts-utils web` | Extra process + `DTS_WEB_TOKEN`; rejected in roadmap. |
| Subprocess `dts-utils generate` | Brittle; rejected in roadmap. |
| Extract `dts_utils/service/` from web first | Valid if handlers duplicate `_build_client_options`; defer until duplication is real. |

### Why primary wins

Matches locked architecture in `docs/mcp-interface-plan.md`, minimizes dependencies, reuses typed exceptions and APIs already covered by web/CLI tests, and keeps MCP optional via `[mcp]` extra.

### Spikes

- **None required** — MCP SDK stdio + tool registration is documented; spike only if `mcp` import fails on CI Python 3.12 (≤30 min: add dev dep + one hello tool test).

---

## Open questions / blockers

1. **CI dependency:** Should `mcp` live only in `[optional-dependencies] mcp` or also in `dependency-groups.dev` so CI always runs MCP tests? **Recommendation:** add to `dependency-groups.dev` with same pin.
2. **Branch convention:** FUNK skill says `feature/dts-mcp-phase-1-mvp`; cloud agent history used `cursor/*-cee0`. **Owner:** confirm one convention before push.
3. **PR #12 merge:** Implementation branch should target `main` with docs plan included or rebased.

---

## Implementation checklist

- [ ] `git fetch origin main && git checkout -b feature/dts-mcp-phase-1-mvp origin/main`
- [ ] `pyproject.toml` — `[mcp]` extra, `dts-utils-mcp` script, dev group includes `mcp`
- [ ] `src/dts_utils/mcp/` — server + tools + errors
- [ ] `tests/test_mcp_server.py` — reds then greens per table above
- [ ] `CLI.md` — MCP section + Cursor JSON example
- [ ] `CHANGELOG.md` — `[Unreleased]` Added
- [ ] `AGENTS.md` — note `dts-utils-mcp` and `uv sync --extra mcp`
- [ ] `uv sync --extra mcp --dev && uv run pytest`

---

## Next step

Create the feature branch from `origin/main`, add a failing `tests/test_mcp_server.py` that expects six registered tools, then add minimal `dts-utils-mcp` entrypoint and `mcp` dev dependency to make the first red compile.

```bash
git fetch origin main
git checkout -b feature/dts-mcp-phase-1-mvp origin/main
# add tests/test_mcp_server.py (red) + pyproject mcp dep + empty src/dts_utils/mcp/server.py
uv sync --extra mcp --dev
uv run pytest tests/test_mcp_server.py -v
```

---

## Appendix — Review optional highlights

*Skip if executing from the checklist above.*

- **Devil's advocate:** `dts_generate_image` without `flatc` fails like CLI — document in tool error text; do not silently skip config conversion. Long-running generate may hit MCP host timeouts — acceptable for Phase 1; Phase 2 adds cancel/progress.
- **Tech writer:** Six tool names are stable contracts — document in CLI.md before external agents depend on them.
- **Senior staff:** stdio-only avoids new network attack surface; `shared_secret` must never appear in logs or error JSON. Non-loopback `host` should return a warning field in tool result text.
