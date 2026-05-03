# dts-util — Draw Things gRPC helper

A Python CLI for macOS that installs, manages, and talks to the Draw Things `gRPCServerCLI`. It can install the server as a LaunchAgent, generate images over gRPC, and browse community model metadata.

**Status:** Alpha (0.x). Expect breaking changes; the Python surface and CLI are still settling—pin a commit or version if you depend on it.

For deeper references see [CLI.md](CLI.md) (every flag), [DRAW-THINGS-GRPC-API.md](DRAW-THINGS-GRPC-API.md) (Draw Things gRPC service and streaming), and [PROTOBUF.md](PROTOBUF.md) (protobuf + FlatBuffer schema). Draw Things product docs live at [drawthings.ai/docs](https://drawthings.ai/docs).

---

## Requirements

- Python 3.12+ and [`uv`](https://github.com/astral-sh/uv).
- macOS, only if you want `dts-util server …` to install or manage `gRPCServerCLI` locally. `generate` and `reflect` work anywhere Python runs as long as they can reach the server.
- [`flatc`](https://github.com/google/flatbuffers) (FlatBuffers compiler) on `PATH`, so you can use JSON for configuration files.

---

## Install

```bash
git clone https://github.com/funkatron/dts-utils.git
cd dts-utils
uv sync
uv run dts-util --help
```

---

## Quickstart

Three steps to a generated PNG on a fresh Mac:

```bash
uv run dts-util server install
uv run dts-util server check
uv run dts-util generate \
  --prompt "a beautiful sunset over mountains" \
  --configuration portrait \
  --trust-server-cert
```

What each step does:

1. `server install` writes the LaunchAgent and starts `gRPCServerCLI` with default settings.
2. `server check` probes the local port to confirm the process is listening. (`server test` is a synonym.)
3. `generate` streams an image from the server using the saved config `portrait.json` and writes a PNG under `./output` by default (`output/generated.png`). The path you pass to `--output` gets a Unix millisecond suffix before the extension (for example `output/generated.png` becomes `output/generated-1735123456789.png`) so repeated runs do not overwrite earlier files.

Skip steps 1 and 2 if the server already runs elsewhere — see [Remote or existing servers](#remote-or-existing-servers).

---

## Configuration files

`generate` requires a Draw Things configuration. Without one it exits immediately rather than producing a confusing socket error.

`--configuration VALUE` accepts three forms:


| You pass                                                  | What happens                                                                         |
| --------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| A name like `portrait` (no slashes, not an existing path) | Resolves to `portrait.json` inside the directory printed by `dts-util configs path`. |
| A `.json` file path                                       | Converted to FlatBuffer bytes via [`flatc`](https://github.com/google/flatbuffers) and the bundled `config.fbs`.              |
| Any other existing file                                   | Read as raw FlatBuffer bytes. The extension does not have to be `.bin`.              |


`--configuration-json` is a JSON-only variant (name or path) and is mutually exclusive with `--configuration`. Most users only need `--configuration`.

Saved configs live in:

```bash
uv run dts-util configs path     # print the directory (creates it)
uv run dts-util configs list     # list saved JSON config names
```

---

## TLS

Pick the flag that matches your situation:


| Situation                                  | Flag                                                      |
| ------------------------------------------ | --------------------------------------------------------- |
| Localhost, server cert not in system trust | `--trust-server-cert` (loopback only)                     |
| Remote or LAN, you have a PEM you trust    | `--root-cert PATH` (usually with `--host`)                |
| Server installed with `--no-tls`           | `--no-tls` on the client                                  |
| Server uses a shared secret                | `--shared-secret SECRET`                                  |
| Short remote diagnostic, no PEM available  | `--force-trust-server-cert` (accepts any cert; MITM risk) |


To pin the server's presented certificate to a local PEM file:

```bash
uv run dts-util tls path         # print default PEM destination
uv run dts-util tls export       # connect, capture cert, write PEM
```

`server install --export-tls-cert` runs the export automatically after `server check` passes (skipped under `--no-tls`). The `gRPCServerCLI` keystore is never modified — this is a client-side I/O step.

---

## Server lifecycle (macOS)

These commands assume the macOS LaunchAgent layout and use `pgrep` / `lsof` to probe the local process. The `server` prefix is required so they are never confused with `pytest` or other "test" commands.


| Goal                                             | Command                                                                                       |
| ------------------------------------------------ | --------------------------------------------------------------------------------------------- |
| Install with defaults                            | `uv run dts-util server install`                                                              |
| Confirm process + port                           | `uv run dts-util server check` (or `server test`)                                             |
| Install with custom port, secret, or models path | `uv run dts-util server install --port 7860 --shared-secret "…" --model-path /path/to/models` |
| Enable model browsing on an existing install     | `uv run dts-util server restart --model-browser`                                              |
| Restart or remove                                | `uv run dts-util server restart` · `uv run dts-util server uninstall`                         |


Full flag text is in [CLI.md](CLI.md).

---

## Remote or existing servers

If `gRPCServerCLI` runs on another machine or under another supervisor, skip `server install` / `server check` and point `generate` and `reflect` at the host:

```bash
uv run dts-util generate \
  --host gpu.local \
  --prompt "a beautiful sunset over mountains" \
  --configuration portrait \
  --root-cert ./gpu.pem
```

`server check` only probes localhost — it is not a substitute for "is my remote server up?". Use `reflect` for that:

```bash
uv run dts-util reflect --host gpu.local --root-cert ./gpu.pem
uv run dts-util reflect --host gpu.local --root-cert ./gpu.pem --json
```

---

## Generation tasks


| Goal                          | Flags                                                     |
| ----------------------------- | --------------------------------------------------------- |
| Saved config + open in viewer | `--configuration NAME --trust-server-cert --open`         |
| Inline JSON path              | `--configuration path/to/config.json --trust-server-cert` |
| Pinned PEM verification       | `--root-cert cert.pem` (often with `--host`)              |
| Plaintext gRPC                | `--no-tls`                                                |
| Raw FlatBuffer file on disk   | `--configuration /path/to/payload` (any extension)        |
| Remote diagnostic, no PEM     | `--host HOST --force-trust-server-cert` (MITM risk)       |


`--open` opens the written file with the platform default viewer (`open` on macOS, `xdg-open` on Linux, `start` on Windows).

`--output` always receives that millisecond suffix on disk; scripts should parse stdout (`Wrote …`) or glob the parent directory if they need the exact path.

---

## Model inspector (in flux)

Local index over public Draw Things community-model metadata. No `GenerateImage` server required.

```bash
uv run dts-util models build              # clone/update metadata, build local tables
uv run dts-util models search flux
uv run dts-util models search sdxl anime
uv run dts-util models search --family Flux --has-hf
uv run dts-util models show MODEL_ID
uv run dts-util models report
```

Filters: `--family`, `--type`, `--author`, `--license`, `--has-source`, `--has-hf`, `--has-license`, `--has-downloads`, `--has-warnings`.

Output paths:


| Path                                    | Contents                               |
| --------------------------------------- | -------------------------------------- |
| `data/drawthings_uncurated_models.json` | Full dataset                           |
| `data/drawthings_uncurated_models.csv`  | CSV slice                              |
| `data/drawthings_models.sqlite`         | SQLite database                        |
| `data/report.html`                      | HTML report                            |
| `.cache/community-models/`              | Cloned `drawthingsai/community-models` |
| `.cache/huggingface/`                   | Hugging Face API cache                 |


`build` reads `uncurated_models.txt`, SHA manifests, and `metadata.json` trees. Bad rows become warnings rather than failing the build.

---

## Troubleshooting


| Symptom                                         | Where to look                                                                                                           |
| ----------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| `server check` fails                            | `~/.config/draw-things/server.log`; reload with `dts-util server restart`; try `--port PORT` if you changed the default |
| TLS error against `localhost`                   | Add `--trust-server-cert` (loopback restriction). See [TLS](#tls)                                                       |
| `generate` exits immediately or "socket closed" | Missing `--configuration` / `--configuration-json`, or checkpoints on the server do not match the config                |
| Unsure what the server exposes                  | `dts-util reflect` (add `--json` for machine-readable output)                                                           |
| "Cannot resolve … config"                       | Check `dts-util configs path` and `dts-util configs list`; either save the file there or pass an absolute path          |


---

## Repo layout

```
src/
└── dts_util/
    ├── installer/       # LaunchAgent-backed install lifecycle (macOS)
    ├── generate.py      # Prompt → gRPC GenerateImage → PNG
    ├── configs.py       # Resolves named JSON configs
    ├── grpc/            # Channels, reflection, stubs, protobuf copies
    └── utils/           # Shared helpers (e.g. gRPC errors)
```

Per-flag behavior lives in [CLI.md](CLI.md), not here.

---

## Related documentation


| Doc                                            | Covers                                                            |
| ---------------------------------------------- | ----------------------------------------------------------------- |
| [CLI.md](CLI.md)                               | Every subcommand and flag                                         |
| [DRAW-THINGS-GRPC-API.md](DRAW-THINGS-GRPC-API.md) | Draw Things gRPC service, `ImageGenerationRequest`, streaming      |
| [PROTOBUF.md](PROTOBUF.md)                     | Proto + FlatBuffer `GenerationConfiguration` + gRPC test strategy |
| [tests/README.md](tests/README.md)             | Pytest + **manual release smoke** (live server)                   |
| [Draw Things docs](https://drawthings.ai/docs) | Product documentation outside this repo                           |


---

## Development

```bash
uv sync --dev
uv run pytest
```

Integration tests may skip without a local gRPC server; keeping those tests honest when Draw Things updates the server is covered in [PROTOBUF.md § gRPC integration tests](PROTOBUF.md#grpc-integration-tests) and [tests/README.md](tests/README.md).

---

## License

MIT — see [LICENSE](LICENSE).

## Contributing

Pull requests welcome. Behavioral changes should land alongside `pytest` updates in the same merge when practical.

**Releases:** When tagging a version, follow [CHANGELOG.md § Documenting gRPCServerCLI for each release](CHANGELOG.md#documenting-grpcservercli-for-each-release)—record which `**gRPCServerCLI`** release tag (draw-things-community) you smoke-tested against, or note if you did not run a live server.