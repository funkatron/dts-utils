# Cursor MCP config (`.cursor/mcp.json`)

Project-local MCP server for **`dts-utils`**. Cursor loads **`scripts/run-mcp.sh`**, which runs **`uv run --extra mcp dts-utils-mcp`**.

**Open this repo as the Cursor workspace** so `.cursor/mcp.json` resolves `scripts/run-mcp.sh`. Do not duplicate **`dts-utils`** in **`~/.cursor/mcp.json`** with a relative path — global MCP runs from an arbitrary cwd and fails with **`No such file or directory`**. If you need a user-global entry, use the **absolute** path to **`scripts/run-mcp.sh`** (see troubleshooting).

## Environment variables

| Variable | Default in `mcp.json` | Purpose |
| --- | --- | --- |
| `DTS_UTILS_DEFAULT_CONFIGURATION` | `default` | Default saved profile stem when tools omit **`configuration`**. |
| `DTS_MCP_ALLOW_SERVER_LIFECYCLE` | `0` | When **`1`**, register macOS LaunchAgent tools: **`dts_server_status`**, **`dts_server_start`**, **`dts_server_stop`**, **`dts_server_restart`**. |

### Enable lifecycle tools (macOS)

Set in **`.cursor/mcp.json`** → **`env`**:

```json
"DTS_MCP_ALLOW_SERVER_LIFECYCLE": "1"
```

Refresh MCP in Cursor after editing (reload window or restart).

**Not exposed via MCP:** **`server install`**, **`server uninstall`**, **`models fetch`**, **`reflect`**. Use the terminal for those.

**Always available without the gate:** **`dts_server_check`**, generate/config/models/pipeline tools (see [docs/mcp-for-agents.md](../docs/mcp-for-agents.md)).

## Troubleshooting

| Problem | Fix |
| --- | --- |
| **`bash: scripts/run-mcp.sh: No such file or directory`** | **`dts-utils`** in **`~/.cursor/mcp.json`** with relative **`scripts/run-mcp.sh`** — remove it and use project **`.cursor/mcp.json`** only, **or** set **`args`** to the absolute script path (e.g. **`/Users/you/.../dts-utils/scripts/run-mcp.sh`**) |
| MCP server red | Run **`bash scripts/run-mcp.sh`** from repo root; **`uv sync --extra mcp`** |
| Duplicate **`dts-utils`** servers | Remove **`~/.cursor/mcp.json`** **`dts-utils`** entry; use project **`.cursor/mcp.json`** only |
| Lifecycle tools missing | Expected when **`DTS_MCP_ALLOW_SERVER_LIFECYCLE`** is **`0`** |

See also [docs/mcp-local-handoff.md](../docs/mcp-local-handoff.md) and [CLI.md § MCP](../CLI.md#mcp-dts-utils-mcp).
