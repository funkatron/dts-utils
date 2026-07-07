# MCP for coding agents

How agents (Cursor, Claude Desktop, custom MCP hosts) use **`dts-utils-mcp`** to drive Draw Things generation from natural language — without shelling out to **`dts-utils …`** or running **`dts-utils web`**.

**Setup and flags:** [CLI.md § MCP](../CLI.md#mcp-dts-utils-mcp) · **Implementation record:** [mcp-interface-plan.md](mcp-interface-plan.md)

## Contents

- [What you get](#what-you-get)
- [Setup](#setup)
- [How agents should work](#how-agents-should-work)
- [Tools](#tools)
- [Resources and prompts](#resources-and-prompts)
- [What users can do](#what-users-can-do)
- [Example user requests](#example-user-requests)
- [Limits](#limits)
- [Troubleshooting](#troubleshooting)

---

## What you get

| Layer | Role |
| --- | --- |
| **User** | Describes intent in chat (“make three portrait variants”, “is my LTX model installed?”) |
| **Agent** | Chooses MCP tools, reads configs/resources, returns paths or summaries |
| **`dts-utils-mcp`** | stdio MCP server (local Cursor); **`serve`** for Streamable HTTP on the DT host |
| **`gRPCServerCLI`** | Draw Things server on the Mac (default **`localhost:7859`**) |

Agents get structured JSON from tools (paths, stems, doctor counts) instead of parsing CLI stdout. Images default to **filesystem paths** under **`output/`** — use MCP **resources** to fetch bytes when needed, not giant base64 in tool results.

---

## Setup

**Recommended:** open the **`dts-utils`** repo as the Cursor workspace. Project config **`.cursor/mcp.json`** runs **`scripts/run-mcp.sh`** (no hand-edited paths).

```bash
git pull
uv sync --extra mcp
uv run dts-utils server check   # exit 0 before generating
```

Refresh MCP in Cursor after **`git pull`**. Optional: remove duplicate **`dts-utils`** entries from **`~/.cursor/mcp.json`** to avoid clashes.

### Remote agents (Streamable HTTP)

On the Mac that runs **`gRPCServerCLI`**, start the HTTP listener beside Draw Things:

```bash
export DTS_MCP_TOKEN="$(openssl rand -hex 32)"
uv run --extra mcp dts-utils-mcp serve
# default: http://127.0.0.1:1976/mcp
```

Remote MCP clients (on a tailnet/VPN) point at **`http://<dt-host>:1976/mcp`** with **`Authorization: Bearer $DTS_MCP_TOKEN`**. Lifecycle tools are not available over HTTP — use Terminal **`dts-utils server …`** locally. For non-MCP apps, see **[web-api.md](web-api.md)** (REST on port **1975**).

**Prerequisites on the Mac:** Python 3.12+, **`uv`**, **`flatc`** (for JSON profiles), a listening **`gRPCServerCLI`**, and at least one saved profile (e.g. **`default.json`**).

---

## How agents should work

Typical flow:

1. **`dts_server_check`** — fail fast if nothing is listening.
2. **`dts_list_configs`** or resource **`dts://config/{stem}`** — pick or inspect a profile.
3. **`dts_expand_prompt`** (optional) — preview **`{a|b}`** wildcards before a multi-run batch.
4. **`dts_generate_image`** or **`dts_pipeline_run`** — produce output.
5. Read **`dts://output/…`** or **`dts://pipeline/…`** if the host needs file contents.
6. **`dts_generate_cancel`** — only if the user stops a long batch (between runs, not mid-RPC).

**Defaults agents can rely on:** **`localhost:7859`**, **`trust_server_cert=true`** on loopback, configuration **`default`** (or **`DTS_UTILS_DEFAULT_CONFIGURATION`**).

**Prefer tools over shell** for: probe, configs, generate, models search/doctor, pipeline status. Use Terminal **`dts-utils server …`** for install/uninstall (not exposed via MCP).

---

## Tools

### Always available (11)

| Tool | Use when |
| --- | --- |
| **`dts_server_check`** | User asks if the server is up; before any generate/pipeline call |
| **`dts_list_configs`** | List saved profile names |
| **`dts_get_config`** | Read one profile as JSON (stem or path) |
| **`dts_expand_prompt`** | User wants to see wildcard expansions without generating |
| **`dts_generate_image`** | Text → PNG(s); main image workflow |
| **`dts_list_installed_models`** | What checkpoints/files are in Draw Things **`Models`** |
| **`dts_models_search`** | Search community index (after **`models build`**) |
| **`dts_models_doctor`** | Missing weights, orphan sidecars, index mismatches |
| **`dts_pipeline_run`** | Prompt → image → video (e.g. **`prompt-to-video`** profile) |
| **`dts_pipeline_status`** | Inspect **`heartbeat.json`** / **`pipeline_run.json`** for a run |
| **`dts_generate_cancel`** | User says stop during a multi-generation batch |

**`dts_generate_image` highlights:** **`generations`** 1–25; **`output`** base path (CLI-style ms suffix); **`include_image_data`** default **false** (paths only).

**`dts_pipeline_run`:** blocks until the pipeline finishes; returns artifact paths / run folder info.

### Optional lifecycle (macOS, 4 tools)

Set **`DTS_MCP_ALLOW_SERVER_LIFECYCLE=1`** on the MCP server process (see [CLI.md](../CLI.md#mcp-dts-utils-mcp)).

| Tool | Use when |
| --- | --- |
| **`dts_server_status`** | Installed LaunchAgent, port, listener, model browser (secrets redacted) |
| **`dts_server_start`** | Start installed service |
| **`dts_server_stop`** | Stop service (plist remains) |
| **`dts_server_restart`** | Restart; syncs **`--model-browser`** by default |

**Not exposed:** **`server install`**, **`server uninstall`**, **`models fetch`**, **`reflect`**.

---

## Resources and prompts

| URI / prompt | Content |
| --- | --- |
| **`dts://config/{stem}`** | Saved profile JSON |
| **`dts://output/{relative_path}`** | File under **`./output`** (or **`DTS_MCP_OUTPUT_ROOTS`**) |
| **`dts://pipeline/{run_id}/{step_id}/{filename}`** | Pipeline artifact under run root |
| Prompt **`generate_image`** | Built-in workflow cheat sheet for hosts that support MCP prompts |

Path traversal (`..`) is rejected. Prefer resources over **`include_image_data: true`** for large PNGs.

---

## What users can do

These are realistic things an agent can orchestrate end-to-end via MCP (user describes the goal; agent picks tools).

### Generate and iterate

- **Quick sketch:** one prompt → PNG, path returned for the user to open.
- **A/B prompts:** **`dts_expand_prompt`** then **`generations: 3`** with a wildcard prompt (`{sunset|sunrise} over {mountains|ocean}`).
- **Profile comparison:** same prompt against **`default`** vs **`portrait`** vs **`ltx-2.3-portrait`** (read configs first, then generate).
- **Batch storyboards:** N variants for a script or slide deck; agent lists all **`output/`** paths.

### Models and configs

- **“Do I have Z Image Turbo?”** — **`dts_list_installed_models`** + optional **`dts_models_search`**.
- **“Why won’t my preset work?”** — **`dts_models_doctor`** + read **`dts://config/{stem}`** to compare expected vs installed basenames.
- **Explain a profile** — **`dts_get_config`** or config resource; agent summarizes steps, resolution, LoRAs in plain language.
- **Scaffold awareness** — agent checks which pipeline profiles exist (**`prompt-to-video`**) before **`dts_pipeline_run`**.

### Video / pipeline

- **Prompt-to-video:** **`dts_pipeline_run`** with **`prompt-to-video`** (or custom **`_dts_utils_pipeline`** profile); user gets run folder + MP4 path.
- **Status while waiting:** **`dts_pipeline_status`** on **`run_id`** if the user asks “is it still running?”.
- **Pull intermediates** — resource **`dts://pipeline/{run_id}/{step_id}/{filename}`** for keyframes or the final video.

### Operator assist (lifecycle gate on)

- **“Is Draw Things running?”** — **`dts_server_status`** (richer than check alone on macOS).
- **“Restart the server with model browser”** — **`dts_server_restart`** (user must opt in via env gate).

### Dev and repo workflows

- **Docs with real assets:** agent generates sample PNGs into **`output/`** for README or design review.
- **CI parity checks:** agent runs **`dts_server_check`** and config listing before suggesting a generate command in a PR comment.
- **Preset tuning loop:** user asks to “try 512 vs 768” — agent edits are still manual on JSON files, but generate/compare loops stay in chat via repeated **`dts_generate_image`** calls.

### What this enables philosophically

The user stays in **conversation**; the agent handles **probe → configure → run → fetch results → explain errors**. Good fit for: creative iteration, model inventory questions, pipeline smoke tests, and “why did generation fail?” debugging — without the user memorizing CLI flags or opening the web UI.

---

## Example user requests

Copy or adapt these in Agent chat (ensure MCP **`dts-utils`** is connected):

| User says | Agent likely uses |
| --- | --- |
| “Is the Draw Things server running?” | **`dts_server_check`** |
| “What profiles do I have?” | **`dts_list_configs`** |
| “Generate a cyberpunk alley at night” | check → **`dts_generate_image`** |
| “Show me three random versions of `{neon\|rain} street`” | **`dts_expand_prompt`** → generate with **`generations: 3`** |
| “Make a 5-second video from: calm lake at dawn” | **`dts_pipeline_run`** + **`prompt-to-video`** |
| “Which models are installed?” | **`dts_list_installed_models`** |
| “Search the index for flux” | **`dts_models_search`** |
| “Something’s wrong with my downloads” | **`dts_models_doctor`** |
| “Stop generating” | **`dts_generate_cancel`** |
| “Read my default profile and explain it” | **`dts_get_config`** or **`dts://config/default`** |

---

## Limits

| Not via MCP | Alternative |
| --- | --- |
| Install/uninstall **`gRPCServerCLI`** | Terminal: **`dts-utils server install`** |
| Download weights (**`models fetch`**) | Terminal; avoids HF creds / disk risk in agents |
| gRPC reflection | Terminal: **`dts-utils reflect`** |
| Mid-RPC cancel | Cancel applies **between** batch runs only |
| Non-macOS lifecycle | Lifecycle tools error; **`generate`** still works if server is reachable |
| Remote MCP over HTTP | **`dts-utils-mcp serve`** on the DT host (**`DTS_MCP_TOKEN`**, port **1976**); REST alternative: **[web-api.md](web-api.md)** |

Errors return readable tool failures (configuration, TLS, missing **`flatc`**, RPC errors) — agents should surface **`detail`** text to the user.

---

## Troubleshooting

| Symptom | Check |
| --- | --- |
| MCP server red in Cursor | **`bash scripts/run-mcp.sh`** in repo root; **`uv sync --extra mcp`** |
| **`running: false`** | **`uv run dts-utils server check`** / **`server start`** |
| Configuration / flatc error | **`which flatc`**; validate profile JSON and **`model`** checkpoint name |
| TLS errors | Match server: TLS + trust loopback, or **`no_tls: true`** if server uses **`--no-tls`** |
| Empty doctor/search | Run **`dts-utils models build`** for index-backed tools |
| Duplicate MCP servers | Disable global **`~/.cursor/mcp.json`** **`dts-utils`** if using project **`.cursor/mcp.json`** |

---

## See also

| Document | Contents |
| --- | --- |
| [CLI.md § MCP](../CLI.md#mcp-dts-utils-mcp) | Install, env vars, lifecycle gate |
| [README.md § Coding agents](../README.md#coding-agents-mcp) | Quick local setup |
| [mcp-interface-plan.md](mcp-interface-plan.md) | Maintainer phase record |
| [AGENTS.md](../AGENTS.md) | pytest, layout, automation |
