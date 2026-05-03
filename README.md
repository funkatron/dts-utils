# dts-util — Draw Things gRPC helper

A Python CLI for macOS that installs, manages, and talks to the Draw Things `gRPCServerCLI`. It can install the server as a LaunchAgent, generate images over gRPC, and browse community model metadata.

This project is alpha (0.x). Expect breaking changes; pin a commit or version if you depend on it.

Deeper references: [CLI.md](CLI.md) (flags and shorthand), [DRAW-THINGS-GRPC-API.md](DRAW-THINGS-GRPC-API.md) (Draw Things gRPC service and streaming), [PROTOBUF.md](PROTOBUF.md) (protobuf and FlatBuffer schema). Draw Things product documentation: [drawthings.ai/docs](https://drawthings.ai/docs).

---

## Requirements

- Python 3.12+ and [`uv`](https://github.com/astral-sh/uv).
- macOS only if you use `dts-util server …` to install or manage `gRPCServerCLI` with LaunchAgent. `generate` and `reflect` run anywhere Python can reach the server.
- [`flatc`](https://github.com/google/flatbuffers) on `PATH` when you pass JSON configuration (conversion uses the bundled `config.fbs`).

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

Three steps to a generated PNG on a fresh Mac: install the server, confirm it is listening, then run prompt-first shorthand (quotes keep multi-word prompts as one argument):

```bash
uv run dts-util server install
uv run dts-util server check
uv run dts-util "a beautiful sunset over mountains"
```

What each step does:

1. `server install` installs the LaunchAgent and starts `gRPCServerCLI` with default settings.
2. `server check` probes the local port to confirm a listener. (`server test` is the same probe with a different name.)
3. Shorthand runs `generate` with `--trust-server-cert`, `--open`, and a configuration from [Implicit default profile](#implicit-default-profile-shorthand). On first use the tool may create `default.json` under the saved-config directory and print a stderr hint if it cannot guess a checkpoint name. PNGs go under `./output` by default (`output/generated.png` with a Unix millisecond suffix before the extension so repeated runs do not overwrite earlier files).

To call `generate` explicitly with a saved profile (for example `portrait.json` from `dts-util configs path`):

```bash
uv run dts-util generate \
  --prompt "a beautiful sunset over mountains" \
  --configuration portrait \
  --trust-server-cert
```

Skip `server install` / `server check` if the server already runs elsewhere; see [Remote or existing servers](#remote-or-existing-servers).

---

## Configuration files

`dts-util generate` (explicit subcommand) requires a Draw Things configuration via `--configuration` or `--configuration-json`. Without one it exits before opening a stream.

`--configuration VALUE` accepts three forms:

| You pass | Resolution |
| --- | --- |
| A name like `portrait` (no slashes, not an existing path) | `portrait.json` inside the directory printed by `dts-util configs path`. |
| A `.json` file path | Converted to FlatBuffer bytes with `flatc` and the bundled `config.fbs`. |
| Any other existing file | Read as raw FlatBuffer bytes; extension may differ from `.bin`. |

`--configuration-json` is JSON-only (name or path) and is mutually exclusive with `--configuration`. Most people use `--configuration` only.

Saved configs:

```bash
uv run dts-util configs path     # print the directory (creates it)
uv run dts-util configs list     # list saved JSON names (no `.json` suffix in the listing)
```

### Implicit default profile (shorthand)

When you run prompt-first shorthand (`dts-util "prompt"`, optional second argument for a profile name, optional flags after that), configuration is chosen in this order:

1. Second positional argument, if present (same resolution rules as `--configuration` for a name or path).
2. Otherwise `DTS_UTIL_DEFAULT_CONFIGURATION`, if set in the environment (profile name or path).
3. Otherwise `default.json` in the saved-config directory. If that file is missing, the tool creates it once: starter JSON (512×512, common sampling fields), `model` set from the first `.ckpt` / `.safetensors` in your Draw Things models directory (or `DRAW_THINGS_MODEL_PATH`), or from `DTS_UTIL_DEFAULT_MODEL` if set, or left empty with a short stderr hint to edit the file.

After auto-creating or using the default profile, the process sets `DTS_UTIL_DEFAULT_CONFIGURATION` to `default` with `setenv` semantics only when the variable is unset, so a value you already exported in the shell still wins.

Full rules and examples: [CLI.md § Generate shorthand](CLI.md#generate-shorthand-prompt-first).

---

## TLS

| Situation | Flag |
| --- | --- |
| Localhost, server cert not in system trust | `--trust-server-cert` (loopback only) |
| Remote or LAN, PEM you trust | `--root-cert PATH` (often with `--host`) |
| Server installed with `--no-tls` | `--no-tls` on the client |
| Shared secret on the server | `--shared-secret SECRET` |
| Short remote diagnostic without a PEM | `--force-trust-server-cert` (accepts any cert; **MITM risk**) |

Pin the server’s presented certificate:

```bash
uv run dts-util tls path         # default PEM destination
uv run dts-util tls export       # fetch and write PEM
```

`server install --export-tls-cert` runs the export after a successful local check (not used with `--no-tls`). Only client-side files change; `gRPCServerCLI` keystores are not modified.

---

## Server lifecycle (macOS)

Commands assume the LaunchAgent layout and use local probes (`pgrep` / `lsof`). The `server` prefix is required so these verbs are not confused with other tools.

| Goal | Command |
| --- | --- |
| Install with defaults | `uv run dts-util server install` |
| Confirm process and port | `uv run dts-util server check` (or `server test`) |
| Custom port, secret, or models path | `uv run dts-util server install --port 7860 --shared-secret "…" --model-path /path/to/models` |
| Enable model browsing on an existing install | `uv run dts-util server restart --model-browser` |
| Restart or remove | `uv run dts-util server restart` · `uv run dts-util server uninstall` |

Flag-level detail: [CLI.md](CLI.md).

---

## Remote or existing servers

If `gRPCServerCLI` runs elsewhere, point `generate` and `reflect` at the host:

```bash
uv run dts-util generate \
  --host gpu.local \
  --prompt "a beautiful sunset over mountains" \
  --configuration portrait \
  --root-cert ./gpu.pem
```

`server check` only probes localhost. For reachability and API surface on a remote host, use `reflect`:

```bash
uv run dts-util reflect --host gpu.local --root-cert ./gpu.pem
uv run dts-util reflect --host gpu.local --root-cert ./gpu.pem --json
```

---

## Generation tasks

| Goal | Command pattern |
| --- | --- |
| Prompt-first with defaults (local TLS trust, open viewer) | `uv run dts-util "PROMPT"` (optional profile and flags; see [CLI.md](CLI.md#generate-shorthand-prompt-first)) |
| Saved config | `--configuration NAME --trust-server-cert` (add `--open` to open the PNG) |
| Inline JSON path | `--configuration path/to/config.json --trust-server-cert` |
| Pinned PEM | `--root-cert cert.pem` (often with `--host`) |
| Plaintext gRPC | `--no-tls` |
| Raw FlatBuffer on disk | `--configuration /path/to/payload` |

`--open` uses the platform default viewer (`open` on macOS, `xdg-open` on Linux, `start` on Windows).

`--output` always gets the millisecond suffix on disk; scripts should read stdout (`Wrote …`) or glob the parent directory for the exact path.

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

| Path | Contents |
| --- | --- |
| `data/drawthings_uncurated_models.json` | Full dataset |
| `data/drawthings_uncurated_models.csv` | CSV slice |
| `data/drawthings_models.sqlite` | SQLite database |
| `data/report.html` | HTML report |
| `.cache/community-models/` | Cloned `drawthingsai/community-models` |
| `.cache/huggingface/` | Hugging Face API cache |

`build` reads `uncurated_models.txt`, SHA manifests, and `metadata.json` trees. Bad rows surface as warnings rather than failing the build.

---

## Troubleshooting

| Symptom | Where to look |
| --- | --- |
| `server check` fails | System log / service plist; `dts-util server restart`; match `--port` if you changed the default |
| TLS error against `localhost` | Add `--trust-server-cert` for loopback. See [TLS](#tls) |
| `generate` exits before streaming | For explicit `generate`, pass `--configuration` / `--configuration-json`. For shorthand, see [Implicit default profile](#implicit-default-profile-shorthand). Wrong or missing `model` in JSON also fails at the server |
| Unsure what the server exposes | `dts-util reflect` (add `--json` for machine-readable output) |
| “Cannot resolve … config” | `dts-util configs path` and `dts-util configs list`; save the file there or pass an absolute path |

---

## Repo layout

```
src/
└── dts_util/
    ├── installer/       # LaunchAgent-backed install lifecycle (macOS)
    ├── generate.py      # Prompt → gRPC GenerateImage → PNG
    ├── configs.py       # Saved JSON configs and default profile materialization
    ├── cli_router.py    # Top-level dispatch and generate shorthand
    ├── grpc/            # Channels, reflection, stubs, protobuf copies
    └── utils/           # Shared helpers (e.g. gRPC errors)
```

Per-flag behavior: [CLI.md](CLI.md).

---

## Related documentation

| Doc | Covers |
| --- | --- |
| [CLI.md](CLI.md) | Subcommands, shorthand, environment variables, flags |
| [DRAW-THINGS-GRPC-API.md](DRAW-THINGS-GRPC-API.md) | Draw Things gRPC service, `ImageGenerationRequest`, streaming |
| [PROTOBUF.md](PROTOBUF.md) | Proto + FlatBuffer `GenerationConfiguration` and gRPC test notes |
| [tests/README.md](tests/README.md) | Pytest and manual release smoke (live server) |
| [Draw Things docs](https://drawthings.ai/docs) | Product documentation outside this repo |

---

## Development

```bash
uv sync --dev
uv run pytest
```

Optional integration tests may skip without a local gRPC server; maintainer notes: [PROTOBUF.md § gRPC integration tests](PROTOBUF.md#grpc-integration-tests) and [tests/README.md](tests/README.md).

---

## License

MIT — see [LICENSE](LICENSE).

## Contributing

Pull requests welcome. Pair behavioral changes with `pytest` updates in the same change when practical.

Releases: when tagging a version, follow [CHANGELOG.md § Documenting `gRPCServerCLI` for each release](CHANGELOG.md#documenting-grpcservercli-for-each-release) — record the draw-things-community `gRPCServerCLI` release tag you smoke-tested, or state that you did not run a live server.
