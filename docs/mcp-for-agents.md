# MCP for coding agents

**`dts-utils-mcp`** exposes Draw Things to Cursor and other MCP hosts: check the server, read profiles, generate images, search models, run pipelines. Same Python APIs as **`dts-utils generate`** and **`dts-utils web`**.

Setup flags and env vars: [CLI.md § MCP](../CLI.md#mcp-dts-utils-mcp). Parameter types and defaults: [generated/mcp-tools.md](generated/mcp-tools.md).

## Quickstart (local Cursor)

Open this repo as the workspace — **`.cursor/mcp.json`** runs **`scripts/run-mcp.sh`**.

```bash
git pull
uv sync --extra mcp
uv run dts-utils server check   # exit 0 before generating
```

Refresh MCP in Cursor after **`git pull`**. If **`dts-utils`** appears twice (global **`~/.cursor/mcp.json`** and project config), disable one.

**Needs on the Mac:** Python 3.12+, **`uv`**, **`flatc`**, listening **`gRPCServerCLI`**, a saved profile (e.g. **`default.json`**).

**Try in Agent chat:** “Is Draw Things running? If yes, generate a cyberpunk alley at night.”

**Defaults:** gRPC **`localhost:7859`**, **`trust_server_cert=true`** on loopback, profile **`default`** (override with **`DTS_UTILS_DEFAULT_CONFIGURATION`**).

## How do I…?

| Goal | Tools / URIs |
| --- | --- |
| Check the server before generating | **`dts_server_check`** |
| List or read a saved profile | **`dts_list_configs`**, **`dts_get_config`**, **`dts://config/{stem}`** |
| Text → PNG | **`dts_generate_image`** (after check) |
| Img2img (one source, N runs) | **`dts_generate_image`** + **`input_image_path`** |
| Img2img batch (N paths, one prompt) | **`dts_generate_image`** + **`input_image_paths`** |
| Preview **`{a\|b}`** wildcards | **`dts_expand_prompt`**, then generate with **`generations`** |
| Stop a multi-run batch | **`dts_generate_cancel`** (between runs only, not mid-RPC) |
| Files in Draw Things **`Models`** dir | **`dts_list_installed_models`** |
| Search community index | **`dts_models_search`** (run **`dts-utils models build`** first) |
| Missing weights / orphan sidecars | **`dts_models_doctor`** |
| Prompt → image → video | **`dts_pipeline_run`** (e.g. profile **`prompt-to-video`**; **`prompt`** required) |
| Pipeline still running? | **`dts_pipeline_status`** on **`run_id`** |
| Read PNG/MP4 bytes in the host | **`dts://output/{path}`**, **`dts://pipeline/{run_id}/{step}/{file}`** |
| macOS service control (opt-in) | **`dts_server_status`**, **`dts_server_start`**, **`dts_server_stop`**, **`dts_server_restart`** with **`DTS_MCP_ALLOW_SERVER_LIFECYCLE=1`** |

Install/uninstall **`gRPCServerCLI`**, **`models fetch`**, and **`reflect`** stay in Terminal — not MCP tools.

**Output shape:** tools return JSON (paths, stems, counts). Prefer path fields + MCP **resources** over **`include_image_data: true`** unless you need inline base64.

## Typical flow

1. **`dts_server_check`**
2. **`dts_list_configs`** or **`dts://config/{stem}`**
3. Optional **`dts_expand_prompt`**
4. **`dts_generate_image`** or **`dts_pipeline_run`**
5. **`dts://output/…`** or **`dts://pipeline/…`** if the host needs bytes

## Tool reference

Grouped by job. Full schemas: [generated/mcp-tools.md](generated/mcp-tools.md).

**Server & configs**

| Tool | Notes |
| --- | --- |
| **`dts_server_check`** | TCP/TLS probe; run before generate/pipeline |
| **`dts_list_configs`** | Profile stems (no **`.json`**) |
| **`dts_get_config`** | One profile as JSON |

**Generate**

| Tool | Notes |
| --- | --- |
| **`dts_expand_prompt`** | Expands **`{a\|b}`** wildcards; no gRPC call |
| **`dts_generate_image`** | **`generations`** 1–25; **`output`** path; img2img via **`input_image_path`** / **`input_image_paths`** |
| **`dts_generate_cancel`** | Cooperative cancel between batch iterations |

**Models**

| Tool | Notes |
| --- | --- |
| **`dts_list_installed_models`** | Filesystem scan of **`Models`** — not live gRPC catalog |
| **`dts_models_search`** | Local index; build with **`dts-utils models build`** |
| **`dts_models_doctor`** | Partial downloads, orphans, index mismatches |

**Pipeline**

| Tool | Notes |
| --- | --- |
| **`dts_pipeline_run`** | Blocks until finished; optional **`input_image_path`** start frame |
| **`dts_pipeline_status`** | **`heartbeat.json`**, **`pipeline_run.json`** for a **`run_id`** |

**Lifecycle (macOS, optional)**

Set **`DTS_MCP_ALLOW_SERVER_LIFECYCLE=1`** on the MCP process ([CLI.md](../CLI.md#mcp-dts-utils-mcp)).

| Tool | Notes |
| --- | --- |
| **`dts_server_status`** | Plist, listener, model browser; secrets redacted |
| **`dts_server_start`** | Start installed LaunchAgent |
| **`dts_server_stop`** | Stop service; plist remains |
| **`dts_server_restart`** | Restart; syncs **`--model-browser`** by default |

## Resources and prompts

| URI / prompt | Content |
| --- | --- |
| **`dts://config/{stem}`** | Profile JSON |
| **`dts://output/{relative_path}`** | Under **`./output`** or **`DTS_MCP_OUTPUT_ROOTS`** |
| **`dts://pipeline/{run_id}/{step_id}/{filename}`** | Pipeline artifact |
| Prompt **`generate_image`** | Short workflow hint (hosts that support MCP prompts) |

**`..`** in paths is rejected.

## Remote agents (Streamable HTTP)

Skip if you only use local Cursor stdio MCP.

On the Draw Things Mac:

```bash
export DTS_MCP_TOKEN="$(openssl rand -hex 32)"
uv run --extra mcp dts-utils-mcp serve
# http://127.0.0.1:1976/mcp
```

Clients on another machine: **`http://<host>:1976/mcp`**, header **`Authorization: Bearer $DTS_MCP_TOKEN`**, **`serve --bind`** when not loopback. No lifecycle tools over HTTP — use Terminal **`dts-utils server …`** on the Mac. REST alternative: [web-api.md](web-api.md) (port **1975**).

## Limits

| Not via MCP | Use instead |
| --- | --- |
| **`server install`** / **`uninstall`** | Terminal |
| **`models fetch`** | Terminal (HF token, large downloads) |
| **`reflect`** | **`dts-utils reflect`** |
| Cancel during one gRPC call | Wait; cancel applies between batch runs |
| Lifecycle over HTTP | stdio MCP or Terminal on the Mac |

On failure, show the tool’s **`detail`** string (TLS, **`flatc`**, bad profile, RPC errors).

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| MCP red in Cursor | **`bash scripts/run-mcp.sh`**; **`uv sync --extra mcp`** |
| **`running: false`** | **`uv run dts-utils server check`** or **`server start`** |
| Profile / **`flatc`** error | **`which flatc`**; validate JSON and **`model`** checkpoint name |
| TLS mismatch | Trust loopback cert, or **`no_tls: true`** if server uses **`--no-tls`** |
| Empty search/doctor | **`dts-utils models build`** |
| Two **`dts-utils`** MCP entries | Drop global or project duplicate in **`mcp.json`** |

## See also

| Doc | Why |
| --- | --- |
| [CLI.md § MCP](../CLI.md#mcp-dts-utils-mcp) | Env vars, lifecycle gate, **`serve`** flags |
| [README.md § Coding agents](../README.md#coding-agents-mcp) | One-screen setup |
| [mcp-local-handoff.md](mcp-local-handoff.md) | Mac checklist for operators |
| [generated/mcp-tools.md](generated/mcp-tools.md) | Generated params ( **`uv run python scripts/generate_docs.py`** ) |
| [mcp-interface-plan.md](mcp-interface-plan.md) | Maintainer phase notes |
| [AGENTS.md](../AGENTS.md) | Tests and doc drift |
