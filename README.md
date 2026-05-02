# dts-util — Draw Things gRPC helper

A Python CLI tool for macOS to install, manage, and interact with the Draw Things **`gRPCServerCLI`**.

Available commands:
- `dts-util server` (install, uninstall, restart, test, check)
- `dts-util generate`
- `dts-util models` (local community-model index)

**gRPC API, proto, and FlatBuffer layout:** [CLI.md](CLI.md), [API.md](API.md), [PROTOBUF.md](PROTOBUF.md). **Draw Things app** (models, diffusion, GPU): [Draw Things documentation](https://drawthings.ai/docs).

## How to use it

### Clone and CLI overview

```bash
git clone https://github.com/funkatron/dts-utils.git && cd dts-utils && uv sync
uv run dts-util --help
```

### Local macOS server (LaunchAgent)

Use this when you want `dts-util` to install and manage **`gRPCServerCLI`** on the same Mac.

```bash
uv run dts-util server install
uv run dts-util server check
```

Skip both when the server already runs elsewhere (another machine, another supervisor, or you manage the binary yourself).

### Existing or remote server

Point **`generate`** and **`reflect`** at the host with **`--host`** (and the matching TLS flags). **`server install`** / **`server check`** (or **`test`**) assume a **local** macOS LaunchAgent + process checks, so they are not a substitute for “is my remote server up?”

### Generate one PNG (localhost + Draw Things TLS)

**Generation needs a Draw Things configuration:** a **saved name** (JSON under **`configs path`**), a **`.json`** file path, or **raw FlatBuffer bytes** (any **existing** path that is **not** JSON is read as opaque bytes—extension is not limited to **`.bin`**).

```bash
uv run dts-util generate \
  --prompt "a beautiful sunset over mountains" \
  --configuration /path/to/config.json \
  --output generated.png \
  --trust-server-cert
```

**`--trust-server-cert`** only applies to **localhost / loopback**. For **remote or LAN**, use **`--host HOST --root-cert cert.pem`** when you can pin a PEM. **`--force-trust-server-cert`** exists only for **short diagnostic sessions** where you explicitly accept **MITM risk** on that connection—avoid making it the default habit.

### Requirements

- **Python 3.12+** and [**`uv`**](https://github.com/astral-sh/uv) (`uv sync`, `uv run …`).
- **`flatc` on `PATH`** whenever the resolved config is **JSON** (saved names expand to **`NAME.json`** inside the directory from **`uv run dts-util configs path`**). Omitted for **raw FlatBuffer** payloads.
- **`server install`**, **`server restart`**, **`server uninstall`**, **`server check`** / **`server test`**: assume **local macOS** LaunchAgent layout and **`pgrep` / `lsof`** probes for **`gRPCServerCLI`**. Use the **`server …`** prefix so these are not confused with **`pytest`** or other “test” commands.
- **`generate`** and **`reflect`**: run wherever this Python environment runs, given **network** reachability to the server.
- **Pinned PEM (optional):** **`uv run dts-util tls export`** or **`uv run dts-util server install --export-tls-cert`** saves the server's **presented** certificate next to **`configs path`**-style dirs for **`--root-cert`** (**`gRPCServerCLI`** keystores are unchanged—I/O only).
- **`configs path`** / **`configs list`**: local filesystem only.
- **`models`** subcommands: clone and index public metadata (optional Hugging Face calls); **no** **`GenerateImage`** server required.
- **`uv run dts-util <subcommand> --help`** and **[CLI.md](CLI.md)** for the full flag surface.

---

## Reading map

| Topic                              | Section                                                           |
| ---------------------------------- | ----------------------------------------------------------------- |
| Tooling and platform notes         | [Requirements](#requirements) (under **How to use it**)         |
| Repo URL / extra help invocations  | [Installation](#installation)                                   |
| Restart, model browsing, uninstall | [Server lifecycle](#server-lifecycle-macos) (+ [CLI.md](CLI.md))  |
| **`--configuration`**, TLS tables | [Image generation](#image-generation)                             |
| Local Draw Things metadata index   | [Model inspector](#uncurated-model-inspector)                     |
| TLS / sockets / configs            | [Troubleshooting](#troubleshooting)                               |
| Repo tree                          | [Package layout](#package-layout)                                 |

---

## Installation

**[`dts-utils`](https://github.com/funkatron/dts-utils)** is the canonical clone target (older standalone installer-only repos are superseded). The sequence under **[How to use it](#how-to-use-it)** is the source of truth; optional extra invocations:

```bash
uv run dts-util models --help
```

---

## Server lifecycle (macOS)

Reference sequence commonly used during initial setup:

| Step | Command |
| --- | --- |
| 1. Install binary + LaunchAgent defaults | `uv run dts-util server install` |
| 2. Confirm process + port | `uv run dts-util server check` (aliases: **`server test`**, **`server check`**) |
| 3. Optional: TLS secret, port, models path | `uv run dts-util server install --shared-secret "…"` · `--port 7860` · `--model-path /path/to/models` |
| 4. Optional: extra flags once installed | `uv run dts-util server install --model-browser --debug` |
| 5. Turn on **model browsing** without reinstalling everything | `uv run dts-util server restart --model-browser` |
| 6. Routine restart / full removal | `uv run dts-util server restart` · `uv run dts-util server uninstall` |

Full flag text lives in **[CLI.md](CLI.md)**.

---

## Image generation

**Behavior:** omitting generation configuration triggers an immediate CLI exit rather than ambiguous server failures.

### How `--configuration` resolves

| You pass… | Effect |
| --- | --- |
| A **name** (no slashes; not an existing path) | Resolves **`NAME.json`** inside [the directory **`configs path` prints](#saved-config-location). |
| A **`.json` path** | Converts with **`flatc`** + bundled **`config.fbs`**. |
| An **existing path that is not JSON** | Read as raw FlatBuffer bytes (no **`flatc`**; extension is not limited to **`.bin`**). |

`--configuration-json` is JSON-only (name or path), **mutually exclusive** with `--configuration` in argparse. **`--configuration`** is the single knob for names, **`.json`**, and raw bytes.

### Copy-paste examples

Saved name **`portrait`** (expects **`portrait.json`** inside **`configs path`**), localhost TLS, optional viewer (**`--open`** needs a desktop handler—**`open`**, **`xdg-open`**, or Windows **`start`**):

```bash
uv run dts-util generate \
  --prompt "a beautiful sunset over mountains" \
  --configuration portrait \
  --output generated.png \
  --trust-server-cert \
  --open
```

Explicit JSON path (same TLS pattern as the hero block):

```bash
uv run dts-util generate \
  --prompt "a beautiful sunset over mountains" \
  --configuration config.json \
  --output generated.png \
  --trust-server-cert
```

### TLS patterns

| Situation | Typical flag |
| --- | --- |
| Localhost / loopback, cert not in system trust | `--trust-server-cert` (loopback-only) |
| Remote or LAN, PEM you trust | `--root-cert PATH` (often with `--host`) |
| Debugging only — MITM risk accepted for that connection | `--force-trust-server-cert` (+ `--host …` when not local) |
| Server installed without TLS | `--no-tls` on the client |
| plist uses a shared secret | `--shared-secret` on `generate` |

### Behind the scenes (one line each)

Server streams chunked tensors.

Client reassembles chunks → decodes (`fpzip`, NumPy, Pillow) → writes **PNG**.

### Saved config location

```bash
uv run dts-util configs path
uv run dts-util configs list
```

Example: **`portrait.json`** inside that directory matches **`--configuration portrait`**.

### Task cheat sheet

| Goal | Typical flags / shape |
| --- | --- |
| Saved name + open viewer (desktop) | `--configuration NAME … --trust-server-cert --open` |
| Inline JSON path | `--configuration path/to.json …` |
| PEM pinned verification | `--root-cert cert.pem` (often with `--host`; replaces loopback trust) |
| Plaintext gRPC | `--no-tls` |
| Raw FlatBuffer file on disk | `--configuration /path/to/payload` (not **`.json`**; e.g. **`.bin`**) |
| Remote diagnostic trust (**risk**) | `--host HOST --force-trust-server-cert` |

### Reflection (optional)

```bash
uv run dts-util reflect --trust-server-cert
uv run dts-util reflect --json --trust-server-cert
```

Use **`--host`** / TLS flags the same way as **`generate`** when the server is not on localhost.

### Python helper

```python
from dts_util.grpc.utils import handle_grpc_error

try:
    with handle_grpc_error():
        pass  # your stub calls
except Exception as e:
    print(f"{e}")
```

---

## Uncurated model inspector

*This feature is still in flux.*

Clone / update upstream metadata into **`.cache/`**, build local tables:

```bash
uv run dts-util models build
```

Examples:

```bash
uv run dts-util models search flux
uv run dts-util models search sdxl anime
uv run dts-util models search --family Flux --has-hf
uv run dts-util models search --family SDXL --has-license
uv run dts-util models show MODEL_ID
uv run dts-util models report
uv run dts-util models report --summary-only
```

Filters you might use: `--family`, `--type`, `--author`, `--license`, `--has-source`, `--has-hf`, `--has-license`, `--has-downloads`, `--has-warnings`.

### Output paths

| Path | Meaning |
| --- | --- |
| `data/drawthings_uncurated_models.json` | Full dataset |
| `data/drawthings_uncurated_models.csv` | CSV slice |
| `data/drawthings_models.sqlite` | SQLite DB |
| `data/report.html` | HTML report |
| `.cache/community-models/` | Cloned **`drawthingsai/community-models`** |
| `.cache/huggingface/` | HF API cache |

`build` reads `uncurated_models.txt`, SHA manifests, and `metadata.json` trees. Bad rows become warnings instead of crashing the build.

---

## Troubleshooting

| Symptom | Often correlates with |
| --- | --- |
| `dts-util server test` unhappy | Logs: `~/.config/draw-things/server.log` · LaunchAgent reload via **`dts-util server restart`** · alternate port: **`dts-util server test --port PORT`** |
| TLS errors on **`localhost`** | `--trust-server-cert` (loopback restriction) · [TLS patterns](#tls-patterns) |
| `generate` dies fast or “socket closed” | Missing `--configuration` / `--configuration-json` · mismatched checkpoints vs config on server |
| Unsure what the server exposes | `dts-util reflect` · `--json` for machine-readable dumps |
| “Cannot resolve … config” | **`configs path`**, **`configs list`**, file naming inside that directory vs absolute `--configuration` path |

---

## Package layout

```
src/
└── dts_util/
    ├── installer/       # LaunchAgent-backed install lifecycle (macOS)
    ├── generate.py      # Prompt → gRPC GenerateImage → PNG
    ├── configs.py       # Resolved named JSON configs
    ├── grpc/            # Channels, reflection, stubs, protobuf copies
    └── utils/           # Shared helpers (e.g. gRPC errors)
```

Installer + flag behavior stays in **[CLI.md](CLI.md)**, not here.

---

## Related documentation

| Doc | Covers |
| --- | --- |
| [CLI.md](CLI.md) | Every subcommand |
| [API.md](API.md) | `ImageGenerationRequest`, streaming caveats |
| [PROTOBUF.md](PROTOBUF.md) | Proto + FlatBuffer **`GenerationConfiguration`** |
| [Draw Things](https://drawthings.ai/docs) | Product docs outside this repo |

---

## Development

```bash
uv sync --dev
uv run pytest
```

---

## License

MIT — see [LICENSE](LICENSE).

## Contributing

Pull requests welcome. Behavioral changes normally land beside **`pytest`** updates in the same merge when practical.