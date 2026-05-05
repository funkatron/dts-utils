# Documentation map

**Operators:** start with [README.md](../README.md) (install, quickstart with a sample PNG, TLS, troubleshooting). **Exact flags:** [CLI.md](../CLI.md).

---

## Read order by goal

| Goal | Document |
| --- | --- |
| Install server, first PNG, common failures | [README.md](../README.md) |
| Subcommands, shorthand, environment variables, **web UI** | [CLI.md](../CLI.md) |
| gRPC messages and streaming | [DRAW-THINGS-GRPC-API.md](../DRAW-THINGS-GRPC-API.md) |
| Protobuf, FlatBuffers, integration tests | [PROTOBUF.md](../PROTOBUF.md) |
| Pytest and release smoke | [tests/README.md](../tests/README.md) |
| Release history | [CHANGELOG.md](../CHANGELOG.md) |
| Contributing or agent automation | [AGENTS.md](../AGENTS.md) |
| **`dts-util web` layout (wireframe, Canvas)** | [web-ui-layout.md](web-ui-layout.md) |

---

## Operator notes

| Topic | What to know |
| --- | --- |
| Implicit profile | Shorthand (`dts-util "…"`) uses `zit` / `zit.json` when you omit a second positional profile and leave `DTS_UTIL_DEFAULT_CONFIGURATION` unset. First run may create that file and print a hint if it could not infer `model`. |
| TLS | Default installs use TLS. Clients use `--trust-server-cert` (shorthand adds it) unless you pinned a PEM with `--root-cert`. If the server was installed with `--no-tls`, use `--no-tls` on clients and `server check --no-tls` / `server test --no-tls`. |
| Reflection | `reflect` may return `UNIMPLEMENTED` while `generate` still works; see README troubleshooting. |
| Web UI | `dts-util web` serves a loopback HTTP UI; optional `DTS_WEB_TOKEN` secures `/api/*` (except `/api/health`). Details in [CLI.md § web](../CLI.md#web-dts-util-web). |
| Stability | 0.x: expect breaking changes; pin a version or commit when depending on this repo ([README.md](../README.md)). |
