# Documentation map

**Operators:** start with [README.md](../README.md) (install, quickstart with a sample PNG, TLS, troubleshooting).

**Exact flags and web HTTP API:** [CLI.md](../CLI.md) — use the **Contents** list at the top to jump to a subcommand.

---

## Read order by goal

| Goal | Document |
| --- | --- |
| Install server, first PNG, common failures | [README.md](../README.md) |
| Clean Mac → **`gRPCServerCLI`** + Z Image Turbo (community-models) | [setup-clean-install-z-image-turbo.md](setup-clean-install-z-image-turbo.md) |
| Install + **`generate`** smoke (SD 1.5‑class, SDXL, Z‑Turbo, LTX‑2.3 distilled) | [smoke-multi-model-demo.md](smoke-multi-model-demo.md) |
| Subcommands, shorthand, environment variables | [CLI.md](../CLI.md) |
| **MCP for agents** (workflows, tool guide, use cases) | [mcp-for-agents.md](mcp-for-agents.md) |
| **MCP local handoff** (Mac setup checklist) | [mcp-local-handoff.md](mcp-local-handoff.md) |
| **MCP server** (operator setup, flags) | [CLI.md § MCP](../CLI.md#mcp-dts-utils-mcp) |
| **MCP implementation** (maintainer record, phases) | [mcp-interface-plan.md](mcp-interface-plan.md) |
| **Web UI layout** (screen map, shortcuts, DOM IDs) | [web-ui-layout.md](web-ui-layout.md) |
| gRPC messages and streaming | [DRAW-THINGS-GRPC-API.md](../DRAW-THINGS-GRPC-API.md) |
| Protobuf, FlatBuffers, integration tests, **`GenerateImage`** stream debugging | [PROTOBUF.md](../PROTOBUF.md) |
| Apple-first pipeline runtime notes (`dts_utils.pipeline`) | [apple-infomux-pipeline-ops.md](apple-infomux-pipeline-ops.md) |
| Pytest and release smoke | [tests/README.md](../tests/README.md) |
| Release history | [CHANGELOG.md](../CHANGELOG.md) |
| Contributing or agent automation | [AGENTS.md](../AGENTS.md) |
| Weight orchestration / `models fetch` backlog | [models-fetch-roadmap.md](models-fetch-roadmap.md) |

---

## Operator notes

| Topic | What to know |
| --- | --- |
| Implicit profile | Shorthand (`dts-utils "…"`) uses `default` / `default.json` when you omit a second positional profile and leave `DTS_UTILS_DEFAULT_CONFIGURATION` unset. First run may create that file (or rename legacy `zit.json`) and print a hint if it could not infer `model`. |
| TLS | Default installs use TLS. Clients use `--trust-server-cert` (shorthand adds it) unless you pinned a PEM with `--root-cert`. If the server was installed with `--no-tls`, use `--no-tls` on clients and `server check --no-tls` / `server test --no-tls`. |
| Reflection | `reflect` may return `UNIMPLEMENTED` while `generate` still works; see README troubleshooting. |
| Web UI | Loopback **`dts-utils web`**; optional **`DTS_WEB_TOKEN`**. Layout and shortcuts: [web-ui-layout.md](web-ui-layout.md). Flags and HTTP API: [CLI.md § web](../CLI.md#web-dts-utils-web). Logs: **`~/.config/dts-utils/web.log`** — **`dts-utils web tail`** or **`GET /api/health`**. |
| Server / web logs | macOS: `dts-utils server tail` (`gRPCServerCLI` via Unified Logging). Any platform: `dts-utils web tail` (file written by `dts-utils web`). |
| Pipeline disk usage | Use `dts-utils pipeline cleanup` with `--older-than`, `--keep-last`, or `--max-run-root-gb`; see [apple-infomux-pipeline-ops.md](apple-infomux-pipeline-ops.md). |
| Stability | 0.x: expect breaking changes; pin a version or commit when depending on this repo ([README.md](../README.md)). |
