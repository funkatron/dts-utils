# Documentation map

**Start here if you use the tool:** [README.md](../README.md) (quickstart, TLS, troubleshooting). **Every flag:** [CLI.md](../CLI.md).

## Read order by goal

| Goal | Document |
| --- | --- |
| Install server, run first generation, fix common failures | [README.md](../README.md) |
| Exact subcommands, shorthand rules, environment variables | [CLI.md](../CLI.md) |
| gRPC messages and streaming semantics | [DRAW-THINGS-GRPC-API.md](../DRAW-THINGS-GRPC-API.md) |
| Protobuf / FlatBuffers / integration test notes | [PROTOBUF.md](../PROTOBUF.md) |
| Pytest and manual release smoke | [tests/README.md](../tests/README.md) |
| Release notes and breaking changes | [CHANGELOG.md](../CHANGELOG.md) |
| Editing the codebase or automation | [AGENTS.md](../AGENTS.md) |

## Operator UX notes

- **Implicit profile is `zit`:** Prompt-first shorthand (`dts-util "…"`) uses saved config **`zit.json`** when you do not pass a second positional profile or set `DTS_UTIL_DEFAULT_CONFIGURATION`. First run may auto-create that JSON and print a hint if no model name could be guessed.
- **TLS vs no TLS:** Default local installs use TLS. Use `--trust-server-cert` on `generate` (shorthand does this for you). If the server was installed with `--no-tls`, use `--no-tls` on clients and **`server check --no-tls`** / **`server test --no-tls`** for the loopback probe.
- **`reflect`:** May return `UNIMPLEMENTED` even when generation works; do not treat it as proof the server is broken.
- **Alpha:** Breaking changes are possible; pin a version or commit for downstream use ([README.md](../README.md)).
