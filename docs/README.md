# Documentation map

**Operators:** start with [README.md](../README.md) (install, quickstart with a sample PNG, TLS, troubleshooting).

**Exact flags and web HTTP API:** [CLI.md](../CLI.md) — open the **How to use this doc** table first if the page feels long.

---

## Read order by goal

| Goal | Document |
| --- | --- |
| Install server, first PNG, common failures | [README.md](../README.md) |
| Clean Mac → **`gRPCServerCLI`** + Z Image Turbo (community-models) | [setup-clean-install-z-image-turbo.md](setup-clean-install-z-image-turbo.md) |
| Install + **`generate`** smoke (SD 1.5‑class, SDXL, Z‑Turbo, LTX‑2.3 distilled) | [smoke-multi-model-demo.md](smoke-multi-model-demo.md) |
| Subcommands, shorthand, environment variables, **web UI** | [CLI.md](../CLI.md) |
| gRPC messages and streaming | [DRAW-THINGS-GRPC-API.md](../DRAW-THINGS-GRPC-API.md) |
| Protobuf, FlatBuffers, integration tests, **`GenerateImage`** stream debugging | [PROTOBUF.md](../PROTOBUF.md) |
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
| Web UI | `dts-utils web` serves a loopback HTTP UI; optional `DTS_WEB_TOKEN` secures `/api/*` (except `/api/health`). Details in [CLI.md § web](../CLI.md#web-dts-utils-web). |
| Stability | 0.x: expect breaking changes; pin a version or commit when depending on this repo ([README.md](../README.md)). |
