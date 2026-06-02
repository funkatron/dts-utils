# dts-utils — Draw Things gRPC helper

A Python CLI for macOS that installs, manages, and talks to the Draw Things `gRPCServerCLI`. It can install the server as a LaunchAgent, generate images over gRPC, and browse community model metadata.

This project is alpha (0.x). Expect breaking changes; pin a commit or version if you depend on it.

- **Command reference:** [CLI.md](CLI.md) — full flags plus a **How to use this doc** table at the top.
- **Wire format:** [DRAW-THINGS-GRPC-API.md](DRAW-THINGS-GRPC-API.md) (messages and streaming), [PROTOBUF.md](PROTOBUF.md) (FlatBuffer config and protos).
- **Documentation map:** [docs/README.md](docs/README.md).
- **Product docs (Draw Things):** [drawthings.ai/docs](https://drawthings.ai/docs).

---

## Requirements

- Python 3.12+ and [`uv`](https://github.com/astral-sh/uv).
- macOS only if you use `dts-utils server …` to install or manage `gRPCServerCLI` with LaunchAgent. `generate`, `reflect`, and `dts-utils web` run anywhere Python can reach the server.
- [`flatc`](https://github.com/google/flatbuffers) on `PATH` when you pass JSON configuration (conversion uses the bundled `config.fbs`).

---

## Install

```bash
git clone https://github.com/funkatron/dts-utils.git
cd dts-utils
uv sync
uv run dts-utils --help
```

---

## Quickstart

Three steps to a generated PNG on a fresh Mac: install the server, confirm it is listening, then run prompt-first shorthand (quotes keep multi-word prompts as one argument):

```bash
uv run dts-utils server install
uv run dts-utils server check
uv run dts-utils "a beautiful sunset over mountains"
```

Example output below is the repo’s sample PNG ([`docs/assets/sample-output.png`](docs/assets/sample-output.png), 768×1024), produced with:

```bash
uv run dts-utils "an incredibly detailed mech from Mechwarrior, Depth of field, extreme zoom, tilt-shift, extreme angles, dramatic perspective"
```

Your runs will vary with model, `default.json`, and prompt.

![Sample image written by dts-utils generate](docs/assets/sample-output.png)

What each step does:

1. `server install` installs the LaunchAgent and starts `gRPCServerCLI` with default settings.
2. `server check` probes the local port to confirm a listener. (`server test` is the same probe with a different name.)
3. Shorthand runs `generate` with `--trust-server-cert`, `--open`, and the configuration described under [Shorthand profile (default)](#shorthand-profile-default).
   - First run may create `default.json` in the saved-config directory and print a hint on stderr if it cannot guess a checkpoint name for `model`.
   - PNGs default to `./output` (`output/generated.png`). Each run gets a millisecond suffix before the extension so files are not overwritten.

To call `generate` explicitly with a saved profile (for example `portrait.json` from `dts-utils configs path`):

```bash
uv run dts-utils generate \
  --prompt "a beautiful sunset over mountains" \
  --configuration portrait \
  --trust-server-cert
```

Skip `server install` / `server check` if the server already runs elsewhere; see [Remote or existing servers](#remote-or-existing-servers).

**Blank Mac with no checkpoints yet:** the quickstart assumes something usable ends up in **`default.json`** (often after Draw Things has populated **`Models`**). For an explicit walkthrough — install the Draw Things app preset **Z Image Turbo 1.0 (Exact)**, **`dts-utils`**, **`models build`**, **`configs scaffold-from-metadata`**, then **`generate`** — see [docs/setup-clean-install-z-image-turbo.md](docs/setup-clean-install-z-image-turbo.md).

Optional **browser UI** (same gRPC server; loopback HTTP only by default):

```bash
uv run dts-utils web --open
# second terminal: uv run dts-utils web tail
```

See [CLI.md — web](CLI.md#web-dts-utils-web) for bind address, `DTS_WEB_TOKEN`, and API shape.

---

## Configuration files

`dts-utils generate` (explicit subcommand) requires a Draw Things configuration via `--configuration` or `--configuration-json`. Without one it exits before opening a stream.

`--configuration VALUE` accepts three forms:

| You pass | Resolution |
| --- | --- |
| A name like `portrait` (no slashes, not an existing path) | `portrait.json` inside the directory printed by `dts-utils configs path`. |
| A `.json` file path | Converted to FlatBuffer bytes with `flatc` and the bundled `config.fbs`. |
| Any other existing file | Read as raw FlatBuffer bytes; extension may differ from `.bin`. |

`--configuration-json` is JSON-only (name or path) and is mutually exclusive with `--configuration`. Most people use `--configuration` only.

Saved configs:

```bash
uv run dts-utils configs path     # print the directory (creates it)
uv run dts-utils configs list     # list saved JSON names (no `.json` suffix in the listing)
uv run dts-utils configs scaffold-from-metadata --scan ~/.cache/community-models/models --limit 50 --dry-run   # batch starter profiles from cloned community metadata (see CLI.md)
```

Default locations: **macOS**, **Linux**, and other Unix-like systems use **`~/.config/dts-utils`** when **`XDG_CONFIG_HOME`** is unset (**`$XDG_CONFIG_HOME/dts-utils`** otherwise). **Windows** uses **`%APPDATA%\dts-utils`**.

### Shorthand profile (default)

When you run prompt-first shorthand (`dts-utils "prompt"`, optional profile as the second argument, optional flags after that), configuration is chosen in this order:

1. Second positional argument, if present (same resolution as `--configuration`: saved name, path to `.json`, or raw FlatBuffer path).
2. `DTS_UTILS_DEFAULT_CONFIGURATION`, if set and non-empty (name or path).
3. Otherwise the saved profile `default` (`default.json` next to `dts-utils configs path`).
   - If `default.json` is missing but `zit.json` exists there (older installs), the tool renames `zit.json` → `default.json` once.
   - If neither exists, the tool creates `default.json` once: 512×512, typical sampling fields, and `model` chosen from (in order) the first `.ckpt` / `.safetensors` under your Draw Things models directory or `DRAW_THINGS_MODEL_PATH`, or `DTS_UTILS_DEFAULT_MODEL`, or left blank with a short stderr hint to edit the file.

After that, the process calls `os.environ.setdefault("DTS_UTILS_DEFAULT_CONFIGURATION", "default")`, so an environment value you already exported keeps precedence.

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
uv run dts-utils tls path         # default PEM destination
uv run dts-utils tls export       # fetch and write PEM
```

`server install --export-tls-cert` runs the export after a successful local check (not used with `--no-tls`). Only client-side files change; `gRPCServerCLI` keystores are not modified.

---

## Server lifecycle (macOS)

Commands assume the LaunchAgent layout and use local probes (`pgrep` / `lsof`). The `server` prefix is required so these verbs are not confused with other tools.

| Goal | Command |
| --- | --- |
| Install with defaults | `uv run dts-utils server install` |
| Confirm process and port | `uv run dts-utils server check` (or `server test`) |
| Follow server logs (macOS) | `uv run dts-utils server tail` |
| Custom port, secret, or models path | `uv run dts-utils server install --port 7860 --shared-secret "…" --model-path /path/to/models` |
| Enable model browsing on an existing install | `uv run dts-utils server restart --model-browser` |
| Stop / start without removing install | `uv run dts-utils server stop` · `uv run dts-utils server start` |
| Restart or fully remove | `uv run dts-utils server restart` · `uv run dts-utils server uninstall` |

Flag-level detail: [CLI.md](CLI.md).

---

## Remote or existing servers

If `gRPCServerCLI` runs elsewhere, point `generate` and `reflect` at the host:

```bash
uv run dts-utils generate \
  --host gpu.local \
  --prompt "a beautiful sunset over mountains" \
  --configuration portrait \
  --root-cert ./gpu.pem
```

`server check` only probes localhost. For reachability and API surface on a remote host, use `reflect`:

```bash
uv run dts-utils reflect --host gpu.local --root-cert ./gpu.pem
uv run dts-utils reflect --host gpu.local --root-cert ./gpu.pem --json
```

---

## Generation tasks

| Goal | Command pattern |
| --- | --- |
| Prompt-first with defaults (local TLS trust, open viewer) | `uv run dts-utils "PROMPT"` (optional profile and flags; see [CLI.md](CLI.md#generate-shorthand-prompt-first)) |
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
uv run dts-utils models build              # clone/update metadata, build local tables
uv run dts-utils models fetch --dry-run    # bundled recipe plan (roadmap: docs/models-fetch-roadmap.md)
uv run dts-utils models search flux
uv run dts-utils models search sdxl anime
uv run dts-utils models search --family Flux --has-hf
uv run dts-utils models show MODEL_ID
uv run dts-utils models report
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
| `server check` fails | Wrong port; or use `dts-utils server check --no-tls` when the server runs with `--no-tls`. Otherwise `dts-utils server tail`, plist, `server restart`, or `server stop` then `server start` |
| TLS error against `localhost` | Add `--trust-server-cert` for loopback on `generate`. See [TLS](#tls) |
| `generate` exits before streaming | For explicit `generate`, pass `--configuration` / `--configuration-json`. For shorthand, see [Shorthand profile (default)](#shorthand-profile-default). Wrong or missing `model` in JSON often fails at the server |
| `reflect` returns `UNIMPLEMENTED` | Draw Things `gRPCServerCLI` often omits gRPC reflection; generation can still work |
| PNG looks like noise | Usually wrong `model` in `default.json` (or your chosen profile) — basename must exist in the server model directory — or a bad tensor decode. Open the JSON from `dts-utils configs path` and fix `model` / width / height. Trim accidental spaces in quoted prompts |
| “Cannot resolve … config” | `dts-utils configs path` and `dts-utils configs list`; save the file there or pass an absolute path |

---

## Repo layout

```
src/
└── dts_utils/
    ├── installer/       # LaunchAgent-backed install lifecycle (macOS)
    ├── cli_router.py    # Top-level dispatch (`dts-utils`) and prompt-first shorthand
    ├── configs.py       # Saved JSON configs and default implicit profile materialization
    ├── generate.py      # Prompt → gRPC GenerateImage → PNG
    ├── tls_export.py    # Pin/export server PEM (`dts-utils tls`)
    ├── grpc/            # Channels, reflection, stubs, protobuf copies (`grpc/utils.py`, …)
    ├── model_index/     # Community metadata index (`dts-utils models`)
    └── web/             # Loopback Starlette UI (`dts-utils web`)
```

Per-flag behavior: [CLI.md](CLI.md).

---

## Related documentation

| Doc | Covers |
| --- | --- |
| [CLI.md](CLI.md) | Subcommands, shorthand, environment variables, flags |
| [docs/README.md](docs/README.md) | Where to read what (operator map) |
| [DRAW-THINGS-GRPC-API.md](DRAW-THINGS-GRPC-API.md) | `ImageGenerationService`, `ImageGenerationRequest`, streaming |
| [PROTOBUF.md](PROTOBUF.md) | Proto + FlatBuffer `GenerationConfiguration`, test notes |
| [tests/README.md](tests/README.md) | Pytest and manual release smoke (live server) |
| [AGENTS.md](AGENTS.md) | Conventions for contributors and automation |
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

Contributors and automation: see [AGENTS.md](AGENTS.md) and the [documentation map](docs/README.md).

Releases: when tagging a version, follow [CHANGELOG.md § Maintainer release checklist](CHANGELOG.md#maintainer-release-checklist-grpcservercli) — record the draw-things-community `gRPCServerCLI` release tag you smoke-tested, or state that you did not run a live server.
