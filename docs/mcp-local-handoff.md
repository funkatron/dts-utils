# MCP local handoff (Mac)

Move **`dts-utils` + MCP** from cloud/Linux development to your **Mac** where **`gRPCServerCLI`** runs. Cloud agents can run tests and MCP stdio smoke; **image generation requires your machine**.

**Related:** [mcp-for-agents.md](mcp-for-agents.md) · [CLI.md § MCP](../CLI.md#mcp-dts-utils-mcp)

---

## What’s already done (on `main`)

| Item | Status |
| --- | --- |
| **`dts-utils-mcp`** (11 tools + resources + prompt) | Shipped (stdio + **`serve`** HTTP) |
| **`.cursor/mcp.json`** + **`scripts/run-mcp.sh`** | In repo — no path editing |
| **Docs** | [mcp-for-agents.md](mcp-for-agents.md), CLI.md, README |
| **CI / pytest** | `tests/test_mcp*.py` (34 tests) |
| **Cloud smoke** | MCP stdio + tools OK; **`running: false`** (no server there) |

---

## Local setup checklist

### 1. Get the code

```bash
cd ~/src/dts-utils          # or your clone path
git pull origin main
uv sync --extra mcp
which flatc                   # need flatc for JSON profiles
```

### 2. Draw Things server

```bash
uv run dts-utils server check
```

| Exit code | Action |
| --- | --- |
| **0** | Server is listening — skip to step 3 |
| **non-zero** | `uv run dts-utils server install` (first time) or `server start` |

Optional detail:

```bash
uv run dts-utils server status
```

### 3. Default profile

```bash
uv run dts-utils configs list
```

If empty or no usable **`default`**:

```bash
uv run dts-utils "test"     # may create default.json
# or import/scaffold — see README quickstart
```

### 4. Cursor

1. **File → Open Folder…** → **`~/src/dts-utils`** (repo root with `pyproject.toml`).
2. **Settings → MCP** — confirm **`dts-utils`** from **project** config (green).
3. **Fix or remove** broken global config at **`~/.cursor/mcp.json`** if you added one earlier (JSON syntax, wrong `/Users/...` paths, duplicate servers).

Project config (already in repo):

```json
{
  "mcpServers": {
    "dts-utils": {
      "command": "bash",
      "args": ["scripts/run-mcp.sh"],
      "env": {
        "DTS_UTILS_DEFAULT_CONFIGURATION": "default"
      }
    }
  }
}
```

4. **Refresh MCP** after `git pull`.

### 5. Terminal sanity (before Cursor)

```bash
bash scripts/run-mcp.sh
```

Should wait quietly on stdio (**Ctrl+C** to stop). If it crashes, run **`uv sync --extra mcp`** and ensure **`uv`** is on your PATH (Cursor inherits a minimal PATH — the script checks `~/.local/bin`, Homebrew, `/usr/local/bin`).

### 6. Agent smoke (Cursor Agent chat)

Ask in order:

1. > Use MCP **`dts_server_check`** — expect **`"running": true`**.
2. > Use **`dts_list_configs`** — expect **`default`** (or your profiles).
3. > Use **`dts_generate_image`** with prompt `"a small red cube on gray"` and configuration **`default`**.

Open the returned path under **`output/`**.

---

## Optional: lifecycle tools

Only if you want MCP to start/stop/restart LaunchAgent (macOS):

Add to **`.cursor/mcp.json`** → **`env`**:

```json
"DTS_MCP_ALLOW_SERVER_LIFECYCLE": "1"
```

Then **`dts_server_status`**, **`dts_server_start`**, etc. appear. **`install` / `uninstall` are not exposed via MCP.**

---

## Troubleshooting

| Problem | Fix |
| --- | --- |
| **`scripts/run-mcp.sh: No such file or directory`** | Global **`~/.cursor/mcp.json`** used a relative path; remove **`dts-utils`** there or use an absolute path to **`scripts/run-mcp.sh`**. Prefer project **`.cursor/mcp.json`** with this repo as the workspace. |
| MCP red in Cursor | **Output → MCP** log; run **`bash scripts/run-mcp.sh`** in Terminal |
| **`running: false`** | **`server check`** / **`server start`** |
| **`flatc` / configuration error** | Install flatc; fix **`model`** in profile JSON |
| TLS mismatch | Server default TLS → tools use **`trust_server_cert`** on loopback; if server uses **`--no-tls`**, pass **`no_tls: true`** in tools |
| Two **`dts-utils`** servers | Disable global **`~/.cursor/mcp.json`** entry; use project **`.cursor/mcp.json`** only |
| Generate works in CLI, not MCP | Same APIs — compare **`uv run dts-utils "test"`** vs MCP; check MCP **`config_dir`** if set |

---

## What to paste into Agent custom instructions (optional)

```text
For Draw Things / dts-utils: use the dts-utils MCP server (not shell) when
probing the server, listing configs, generating images, or running pipelines.
Always dts_server_check first. Default profile: default. Read docs/mcp-for-agents.md
for tool choice and limits.
```

---

## Cloud vs local split

| Task | Where |
| --- | --- |
| Code, docs, pytest, MCP wiring | Cloud / CI / any clone |
| **`gRPCServerCLI`**, LaunchAgent | **Mac only** |
| **`dts_generate_image`**, **`dts_pipeline_run`** | **Mac** (needs live server + models) |
| Cursor MCP day-to-day | **Mac** with repo open as workspace |
| Remote MCP over tailnet | **Mac:** **`export DTS_MCP_TOKEN=… && dts-utils-mcp serve`** (port **1976**); clients use Bearer auth |

### Optional: HTTP MCP for remote clients

```bash
export DTS_MCP_TOKEN="$(openssl rand -hex 32)"
uv run --extra mcp dts-utils-mcp serve --bind 127.0.0.1 --port 1976
# Remote client URL: http://<tailnet-host>:1976/mcp  (with Authorization: Bearer)
```

Lifecycle tools stay stdio-only. REST alternative: [web-api.md](web-api.md) on port **1975**.

---

## See also

- [README § Coding agents](../README.md#coding-agents-mcp)
- [setup-clean-install-z-image-turbo.md](setup-clean-install-z-image-turbo.md) — blank Mac + model walkthrough
