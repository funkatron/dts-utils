# 2026-05-02 — gRPC integration test strategy + release server pin

## Trigger

Discussion of ephemeral test ports, in-process fake gRPC servers vs optional real `gRPCServerCLI`, keeping tests aligned when Draw Things updates the wire protocol, and recording which `gRPCServerCLI` tag releases were smoke-tested against.

## Documentation

- `PROTOBUF.md`: section **gRPC integration tests** (current skips / legacy proto, intended fake + `:0` bind + env opt-in for real server, contract drift playbook); bullet pointing releases to CHANGELOG **Tested with**.
- `tests/README.md`: pytest entry + pointer to gRPC integration tests in `PROTOBUF.md`.
- `README.md`: Development blurb + Related documentation table; Contributing release pointer to CHANGELOG.
- `CHANGELOG.md`: **Documenting `gRPCServerCLI` for each release** (template + markdown example for `### Tested with` under each `## [x.y.z]`).

No application code changed in these passes.
