# dts-utils CLI reference

Reference for the **`dts-utils`** command-line tool (flags, shorthand, environment variables). Install, TLS overview, and troubleshooting: [README.md](README.md).

## How to use this doc

| If you want to… | Go to… |
| --- | --- |
| Run your first image from a prompt | [README.md § Quickstart](README.md#quickstart), then [Generate shorthand](#generate-shorthand-prompt-first) here |
| Look up a flag or subcommand | [Available commands](#available-commands) |
| Run Apple-first media pipeline steps | [pipeline (`dts-utils pipeline`)](#pipeline-dts-utils-pipeline) |
| Community models index / bundled fetch recipes | [models (`dts-utils models`)](#models-dts-utils-models) |
| Use the browser UI or HTTP API | [web (`dts-utils web`)](#web-dts-utils-web) |
| Copy example commands | [Examples](#examples) |
| Script-friendly env vars | [Environment variables](#environment-variables) |

---

## Command structure

```
uv run dts-utils <command> [options]
```

Some invocations omit `<command>` and use [Generate shorthand](#generate-shorthand-prompt-first) instead.

## Server lifecycle (LaunchAgent)

These commands manage macOS LaunchAgent + `gRPCServerCLI` (not pytest, not Docker).

Required spelling: `dts-utils server <subcommand>` for `install`, `uninstall`, `start`, `stop`, `restart`, `test`, and `check`. Running `dts-utils install` without `server` prints a usage error (stderr, exit code `2`).

Bare `dts-utils server` prints a short summary.

## Available commands

### install (`dts-utils server install`)

Installs and configures the Draw Things gRPC server via the macOS LaunchAgent workflow.

```bash
uv run dts-utils server install [options]
```

Options:

- `-m, --model-path PATH`: Custom path to store models (default: Draw Things app models directory)
- `-q, --quiet`: Minimize output and assume default answers to prompts
- `-n, --name NAME`: Server name in local network (default: machine name)
- `-p, --port PORT`: Port to run the server on (default: 7859)
- `-a, --address ADDR`: Address to bind to (default: 0.0.0.0)
- `-g, --gpu INDEX`: GPU index to use (default: 0)
- `-d, --datadog-api-key KEY`: Datadog API key for monitoring
- `-s, --shared-secret SECRET`: Authentication key for secure connections
- `--no-tls`: Disable encryption (not recommended)
- `--no-response-compression`: Disable compression
- `--model-browser`: Enable model browser
- `--no-flash-attention`: Disable Flash Attention
- `--debug`: Enable verbose logging
- `--join JSON`: JSON configuration for proxy setup
- `--export-tls-cert`: After a successful install with TLS, write the server's presented PEM (see tls export below)
- `--export-tls-cert-path PATH`: Destination PEM for `--export-tls-cert` (default: `dts-utils tls path`)
- `--export-tls-cert-force`: Overwrite an existing PEM during `--export-tls-cert`

### uninstall

Removes the Draw Things gRPC server and related files managed by this tool.

```bash
uv run dts-utils server uninstall
```

### start

Loads `~/Library/LaunchAgents/com.drawthings.grpcserver.plist` into your per-user GUI launchd domain and starts the job (requires `server install` first).

Uses `launchctl bootstrap`; if the job is already registered, runs `launchctl kickstart`; falls back to legacy `launchctl load` when needed.

```bash
uv run dts-utils server start
```

### stop

Boots the job out of launchd so `gRPCServerCLI` stops. The plist and binary remain (`restart` is `stop` + `start`; use `uninstall` to remove files).

Uses `launchctl bootout`; falls back to `unload`/`remove` on older or inconsistent registration states.

```bash
uv run dts-utils server stop
```

### restart

Stops then starts the Draw Things gRPC server service (same effect as `server stop` then `server start`). **Settings are whatever is already in** `~/Library/LaunchAgents/com.drawthings.grpcserver.plist` **`ProgramArguments`** — `restart` does not take install flags; only `--model-browser` mutates the plist (appends that flag) before the stop/start cycle.

```bash
uv run dts-utils server restart [--model-browser]
```

Options:

- `--model-browser`: Enable model browser in the installed service before restarting

### test

Probes localhost for a reachable gRPC listener (installer workflow; not the pytest test suite).

```bash
uv run dts-utils server test [--port PORT]
uv run dts-utils server check [--port PORT]
```

Options:

- `--port PORT`: Port to probe (default: 7859)
- `--no-tls`: Probe plaintext gRPC only (use when `gRPCServerCLI` was installed with `--no-tls`).

On `localhost` / loopback, the default probe tries **TLS** with the server-presented certificate first (same idea as client `--trust-server-cert`), then falls back to plaintext.

`check` is a synonym for `test` (same flags). Both require the `server` prefix, like `install`, `uninstall`, and `restart`.

### reflect

Lists gRPC services and methods exposed through server reflection.

```bash
uv run dts-utils reflect --trust-server-cert
```

Options:

- `--host HOST`: gRPC server host (default: `localhost`)
- `--port PORT`: gRPC server port (default: `7859`)
- `--timeout SECONDS`: Connection timeout (default: `2`)
- `--json`: Print machine-readable JSON
- `--trust-server-cert`: Trust the presented certificate for this localhost connection only
- `--force-trust-server-cert`: Trust the presented certificate for any host, with MITM risk
- `--root-cert PATH`: Use a pinned PEM root/server certificate
- `--no-tls`: Connect without TLS when the server was installed with `--no-tls`

For remote or LAN servers, prefer `--root-cert`. `--trust-server-cert` is limited to `localhost` and loopback. `--force-trust-server-cert` is for diagnostics only.

Draw Things often builds `gRPCServerCLI` without gRPC reflection. `reflect` may therefore return `UNIMPLEMENTED` even when `generate` works. See [README.md § Troubleshooting](README.md#troubleshooting).

<a id="models-dts-utils-models"></a>

### models (`dts-utils models`)

Inspect the cloned **`drawthingsai/community-models`** index locally (`build`, `search`, `show`, …) and optionally download Draw Things weight filenames described by **bundled fetch recipes**.

```bash
uv run dts-utils models fetch --dry-run
uv run dts-utils models fetch RECIPE_ID --yes --model-dir /path/to/Models
uv run dts-utils models fetch sdxl-turbo --dry-run
uv run dts-utils models fetch z-image-turbo-1.0-exact --yes
uv run dts-utils models fetch ltx-2.3-22b-distilled-exact --yes
uv run dts-utils models fetch --from-metadata ~/.cache/community-models/models/SOME_MODEL/metadata.json
uv run dts-utils models fetch --from-metadata "$META" --manifest          # stdout: basename + SHA; stderr: URL hints once
uv run dts-utils models fetch --from-metadata "$META" --manifest --manifest-wide   # legacy four-column stdout rows
```

**`fetch`:**

- **`--dry-run`:** Print planned artifacts only — **no HTTP(S), no Hugging Face hub calls, and no writes under `--model-dir`** (zero bytes transferred).
- Without **`--dry-run`**, mutating downloads require **`--yes`** (otherwise exit code **`2`**). **`DTS_UTILS_DEFAULT_FETCH_RECIPE`** selects only the default **recipe id** when **`RECIPE_ID`** is omitted; it does **not** bypass **`--yes`**.
- **`RECIPE_ID`:** Optional positional; when omitted: **`DTS_UTILS_DEFAULT_FETCH_RECIPE`** (if non-empty), **then** shipped **`registry.json`** **`default_recipe_id`**. If the registry cannot be read or **`default_recipe_id`** is missing/empty while the env override is unset, the command exits **`2`** with **`stderr`** (fatal — fix packaging or set **`DTS_UTILS_DEFAULT_FETCH_RECIPE`**). Unknown **`RECIPE_ID`** also exits **`2`**.
- **`--model-dir`:** Destination directory (default: **`DRAW_THINGS_MODEL_PATH`** if set, else Draw Things’ default **`Models`** folder — same idea as other **`models`** subcommands).
- **`--force`:** Re-fetch even when the artifact is already satisfied (**`sha256`** match when set; exact **`expected_size_bytes`** when set without **`sha256`**; otherwise any existing **non-empty** file).
- Recipes only allow **`https://`** direct URLs (TLS verification always on; no **`http://`**, **`file://`**, or insecure bypass flags). Sources with **`type`: `huggingface`** need **`huggingface_hub`** (**`uv sync --extra download`** matches **`[download]`**); **`HF_TOKEN`** is passed through when set.
- **Bundled recipe artifacts** may set **`sha256`** (mandatory verify after download when present), optional **`expected_size_bytes`** when **`sha256`** is omitted (exact-size skip + verify after download), and **`sources`** (HTTPS / Hugging Face entries). Maintainer phases and backlog: **[docs/models-fetch-roadmap.md](docs/models-fetch-roadmap.md)**.
- **`--from-metadata PATH`:** Prints Draw Things basenames using the same rules as **`models`** status / index helpers (parity with **`_expected_file_names`**). **`--manifest`** prints each row as **basename**, then a tab, then **`converted`** SHA when known; **`huggingface_repo_id`** and **`download_url`** print once on **`stderr`** as **`# fetch-manifest-hints`**. **`--manifest-wide`** repeats the URL columns on every stdout row (legacy scripting).

Bundled recipe JSON lives under **`dts_utils/model_fetch/recipe_files/`** in the repository. Current source-backed smoke recipes are **`sdxl-turbo`**, **`z-image-turbo-1.0-exact`**, and **`ltx-2.3-22b-distilled-exact`** (see roadmap for additional presets).

### configs

Shows and lists saved Draw Things JSON generation configurations.

```bash
uv run dts-utils configs path
uv run dts-utils configs import-draw-things --dry-run
uv run dts-utils configs scaffold-from-metadata ~/.cache/community-models/models/flux-2-klein-base-9b/metadata.json --dry-run
uv run dts-utils configs scaffold-from-metadata --scan ~/.cache/community-models/models --limit 50 --dry-run
```

Options:

- `configs path`: Print the directory for saved JSON configurations, creating it if needed.
- `configs path --no-create`: Print the directory without creating it.
- `configs list`: List saved JSON configuration names from the default directory.
- `configs list --directory PATH`: List saved JSON configuration names from another directory.
- **`configs import-draw-things`:** macOS only — reads **`~/Library/Containers/com.liuliu.draw-things/Data/Documents/Models/custom_configs.json`** (Draw Things **Local** configurations), splits each preset into **`NAME.json`** under **`configs path`** using only the inner **`configuration`** object (usual **`dts-utils generate --configuration NAME`** path — copied **as-is** from Draw Things, so validate; simplify JSON if **`flatc`** complains). **`--source`** overrides that JSON path; **`--directory`** sets the output folder; **`--dry-run`** lists targets without writing; **`--force`** overwrites clashes. **`--mirror-app-json`** copies **`Models/custom*.json`**, **`Documents/advanced_sections.json`**, and **`Scripts/custom_scripts.json`** into **`configs path/draw-things-app/`** only — those files are **not** generation configs for **`generate`** (grant Terminal **Full Disk Access** if macOS blocks the container path).
- `configs scaffold-from-metadata METADATA.json`: Create a **starter** saved profile next to your other configs, using one `metadata.json` file from a cloned **`drawthingsai/community-models`** tree (see **`dts-utils models build`**). Only models that ship a local checkpoint (`file`) are supported; cloud/API-only entries are skipped.
  - **Writes:** `NAME.json` where **`NAME`** defaults to the folder that holds `metadata.json` (for example `flux-2-klein-base-9b`). Override with **`--name`**, choose the directory with **`--directory`**, **`--dry-run`** prints JSON without saving, **`--force`** replaces an existing file.
  - **Fills in:** the checkpoint name from **`file`**. If the **`note`** field mentions common resolution or step wording (same rough ideas as the model index), **width**, **height**, and **steps** may be prefilled too.
  - **Otherwise:** you still get the right **model** filename; **width**, **height**, and **steps** stay at the usual starter values until you edit the JSON yourself.
- **`configs scaffold-from-metadata --scan DIR`:** Same starter profiles as above, but walk **`DIR`** recursively for every **`metadata.json`** (skips **`apis/`** trees — those entries are cloud/API). Writes **one `.json` file per local model folder** into **`configs path`** or **`--directory`**. Use **`--dry-run`** to print **`would write …`** lines without saving; a short summary goes to **stderr**. **`--limit N`** processes only the first **`N`** files after sorting paths (sanity check before a full run). **`--verbose`** prints each profile path written and reasons for skips. **`--force`** overwrites existing **`NAME.json`** files. Do not combine **`--scan`** with a positional **`METADATA.json`** or **`--name`**.

Save files such as `portrait.json` in this directory, then use `--configuration portrait` with `dts-utils generate`.

### tls

Writes the server’s presented TLS certificate to a PEM file for `dts-utils generate --root-cert …` / `dts-utils reflect --root-cert …` (trust-on-fetch; same bytes Python’s `ssl.get_server_certificate` returns). `gRPCServerCLI` keystores are not modified.

```bash
uv run dts-utils tls path
uv run dts-utils tls export
```

Subcommands:

- `tls path`: Print default PEM destination next to other **`dts-utils`** config (macOS and Linux: **`~/.config/dts-utils`** when **`XDG_CONFIG_HOME`** is unset; Windows: **`%APPDATA%\\dts-utils`**), creating parents unless `--no-create`.
- `tls export`: Connect with TLS, capture the presented PEM; use `--output` / `-o` (defaults to `tls path`), `--force` to replace, `--host` / `--port`, `--retries` for post-install backoff.

With `server install` (macOS): `uv run dts-utils server install --export-tls-cert` runs export to the default PEM after `server test` passes (skipped when `--no-tls` is set).

### pipeline (`dts-utils pipeline`)

Run Apple-first local media pipeline steps (`text_to_image` -> `image_to_video`) and validate runtime prerequisites.

```bash
uv run dts-utils pipeline check
uv run dts-utils pipeline run --preset sdxl-to-ltx --run-id demo-001
```

Subcommands:

- `pipeline check`: Report `ffmpeg` availability, run-root writability, and Gatekeeper note. Returns non-zero when required runtime prerequisites are missing.
- `pipeline run`: Execute a two-step local pipeline and write artifacts + manifests under `--run-root` (default `~/Movies/infomux-runs`).
  - `--image PATH` runs image-to-video only (uses the provided input image).
  - `--prompt "..." --configuration NAME_OR_PATH` runs prompt-to-image (Draw Things gRPC) then image-to-video in one command.
  - `--preset {stub-to-ltx,sdxl-to-ltx,z-to-ltx}` picks the T2I executor.
  - `--run-id`, `--run-root`, `--no-cache`, `--max-oom-retries` control run behavior.
  - `--host`, `--port`, `--no-tls`, `--trust-server-cert`, `--root-cert`, `--shared-secret` apply to `--prompt` mode.
  - `--sdxl-runtime {pytorch-mps,mlx}` selects SDXL runtime when preset mode is `sdxl-to-ltx`.
  - `--width`/`--height` control image size; `--video-width`/`--video-height`, `--fps`, `--seconds` control I2V output.

<a id="web-dts-utils-web"></a>

### web (`dts-utils web`)

Loopback HTTP UI: the browser talks to `dts-utils`; the tool calls Draw Things over gRPC (same idea as `dts-utils generate`).

```bash
uv run dts-utils web [--bind ADDR] [--port N] [--log-level LEVEL] [--no-access-log] [--open]
```

#### Run / defaults

| Item | Value |
| --- | --- |
| Bind | `127.0.0.1` by default |
| HTTP port | `8765` |
| `--log-level` | Uvicorn verbosity: `critical`, `error`, `warning`, `info`, `debug`, `trace` (default **`info`**) |
| `--no-access-log` | Turn off per-request access lines; errors still print |
| `--open` | Open the default browser after startup (URL uses `127.0.0.1` when bind is `0.0.0.0` or `::`) |

#### Auth and limits

- **`DTS_WEB_TOKEN`:** When set, every **`/api/*`** route except **`GET /api/health`** requires **`Authorization: Bearer <token>`**. Prefer loopback; binding widely without a token prints a **stderr** warning—set the token for anything sensitive.
- **`DTS_WEB_GENERATE_TIMEOUT`:** Optional seconds (default **900**). Caps wall-clock time for **`POST /api/generate`** (**504** JSON) and **`POST /api/generate/stream`** (SSE **`error`** with **`Generation timed out.`**). Cannot cancel a single gRPC mid-flight; timeout + cancel apply **between** batch runs after the current RPC returns.
- **Slow clients (streaming only):** Up to **64** SSE payloads may buffer; if the reader stalls, generation waits until there is space (**backpressure**).

#### HTTP endpoints

**Probe:** **`GET /api/server-status`** checks for a listener (`no_tls` query matches `server check --no-tls`). Result is **probe only**—generation can still fail (bad config, missing `flatc`, TLS mismatch).

**Generate — choose one response style:**

| Endpoint | Response | Typical client |
| --- | --- | --- |
| **`POST /api/generate`** | **`multipart/mixed`** PNG parts + headers **`X-Generated-Count`**, **`X-Generation-Runs`** | Scripts that want all bytes at once |
| **`POST /api/generate/stream`** | **`text/event-stream`** (SSE); browser UI | Live progress and thumbnails |

Both use the **same JSON body and bearer rules**. Common keys (mirror CLI concepts; snake_case in JSON):

`prompt`, `negative_prompt`, `generations` (1–25), optional `prompts` / `negative_prompts` arrays (length must match `generations`), `configuration`, `host`, `port`, `no_tls`, `trust_server_cert`, `force_trust_server_cert`, `root_cert`, `shared_secret`, `config_dir`.

Errors return JSON `{"detail":"…"}` for bad requests; generation failures use the same messages as the CLI where applicable.

**Other routes:**

| Route | Purpose |
| --- | --- |
| **`POST /api/generate/cancel`** | Cooperative cancel between batch iterations (`{}` body). Multipart in-flight → HTTP **499**; streaming → SSE **`error`**. One long RPC cannot be interrupted mid-flight. |
| **`POST /api/prompt/expand`** | **`count`** random expansions of `{…}` templates **without** generating—same wildcard rules as generate; previews are **not** tied to your next batch. **`GET`** describes the POST JSON shape. |
| **`GET /api/configs`** | Saved profile names (used by the UI). |

#### SSE events (`/api/generate/stream`)

One line per event: `data: <json>\n\n`.

| `type` | Meaning |
| --- | --- |
| **`meta`** | `total_runs` |
| **`progress`** | `run`, `total_runs` (one event per generation RPC). |
| **`image`** | `run`, `index` (global image counter), `png_b64`. Multiple **`image`** events per run if the server returns several tensors. |
| **`done`** | `expanded_prompts`, `expanded_negative_prompts`, `total_images` — only after full success. |
| **`error`** | `detail` — validation, RPC failure, cancel, or timeout. No **`done`** after **`error`**. |

#### Browser UI (built-in page)

- **⌘↵** (macOS) or **Ctrl+Enter**: Generate from the prompt.
- **Stop**: **`POST /api/generate/cancel`** + abort fetch; cancel applies between runs (see above).
- Busy panel shows the JSON sent to **`/api/generate/stream`** (`shared_secret` redacted in the preview).
- **Fullscreen viewer:** Click any PNG thumbnail in the main **results** grid or in **History** for a near-black fullscreen view. **Escape** or tap the dim backdrop (outside the picture) closes it. **Arrow Left / Right**, the **‹ ›** side zones, or a **horizontal swipe** moves between images **in that batch only** (same generation row or the same History entry). **F** toggles **Fit** (whole image, letterboxed) vs **Fill** (crop to the frame so the picture uses the full viewer box — useful for inspecting detail); the bottom caption shows which mode is active.
- **Setup** FAB (top-right): connection / profile. **History** FAB: recent PNGs saved by the web server under the resolved **`dts-utils`** config directory (see **`dts-utils configs path`**), with download links and a **Reuse** action that restores the prompt, saved JSON **profile** (`configuration`, same value sent to generate), **runs**, and **negative prompt** to match that batch. Each row’s subtitle shows the profile name when it was stored. Older entries without a stored profile behave as before on Reuse (prompt only unless other fields were saved). Existing browser **`localStorage`** history is imported the first time you open History (`configuration` is forwarded when present on legacy rows). Set **`DTS_WEB_HISTORY_DIR`** to override the image/history storage directory. **Clear all** wipes web history files.

LaunchAgent lifecycle stays in Terminal (`dts-utils server …`); the UI footer links to the README quickstart.

### generate

Sends a prompt through the upstream Draw Things streaming gRPC API and writes PNG output.

```bash
uv run dts-utils generate \
  --prompt "a small robot painting clouds" \
  --configuration portrait \
  --trust-server-cert \
  --open
```

Important options:

- `--output PATH`: Base path for output files. Default: `output/generated.png`. The CLI inserts `-<unix_ms>` before the extension (for example `output/generated.png` → `output/generated-1735123456789.png`). Multiple images append `-2`, `-3`, … before the extension. Success lines print as `Wrote …` on stdout.
- `--configuration VALUE`: Draw Things configuration. Existing `.json` files are converted to FlatBuffer bytes; other existing files are sent as raw FlatBuffer bytes; simple names resolve to saved JSON configs.
- `--configuration-json VALUE`: JSON configuration file or saved config name (mutually exclusive with `--configuration`).
- `--trust-server-cert`: Trust the certificate presented by a localhost server for this connection.
- `--force-trust-server-cert`: Trust the certificate presented by any server (MITM risk).
- `--root-cert PATH`: Pinned PEM root/server certificate.
- `--no-tls`: Plaintext gRPC when the server was installed with `--no-tls`.
- `--max-message-mb N`: gRPC send/receive limits in MiB.
- `--open`: Open written images with the platform default viewer.
- **Prompt wildcards:** Write **`{option A | option B}`** (or **`{option A, option B}`** when the block has no `|`). Each time a prompt is sent to the server, every `{…}` block picks **one** branch at random—so multi-image runs (**`--generations N`** or **`generations`** in JSON) **re-roll** the whole template for **each** image. Only **depth‑0** delimiters split (nested `{…}` may contain `|` or commas). Choices can nest; expansion repeats until done, with limits on passes (~128) and output length (~100k chars). Bad or stuck templates raise an error (HTTP **400** from **`dts-utils web`**). Use **`POST /api/prompt/expand`** in the web server to sample expansions without generating.

Explicit `generate` requires **`--configuration`** or **`--configuration-json`** (unlike shorthand, which can materialize **`default.json`**).

**Common tasks (explicit `generate`):**

| Goal | Command | What you get |
| --- | --- | --- |
| Saved config | `uv run dts-utils generate --prompt "…" --configuration portrait --trust-server-cert` | PNG under `./output` with default output naming |
| Draw Things JSON file | `uv run dts-utils generate --prompt "…" --configuration config.json --trust-server-cert` | PNG after JSON → FlatBuffer via [`flatc`](https://github.com/google/flatbuffers) |
| Open result | `uv run dts-utils generate --prompt "…" --configuration config.json --trust-server-cert --open` | PNG plus viewer launch |
| Prebuilt FlatBuffer | `uv run dts-utils generate --prompt "…" --configuration config.bin --trust-server-cert` | PNG without running `flatc` on JSON |
| Pinned cert | `uv run dts-utils generate --prompt "…" --configuration config.json --root-cert cert.pem` | TLS verified against a known PEM |
| Remote diagnostic | `uv run dts-utils generate --host gpu.local --prompt "…" --configuration config.json --force-trust-server-cert` | Trust-on-first-use for that host (MITM risk) |

Prefer **`--root-cert`** off localhost. Use **`--force-trust-server-cert`** only when you cannot pin a cert and accept the risk for that connection.

### Generate shorthand (prompt-first)

When the first argument after the program name is not a known subcommand (`generate`, `configs`, `reflect`, `tls`, `models`, `web`, `server`, …), not a lifecycle verb, and not a flag, the line is treated as shorthand for image generation.

Syntax:

```text
dts-utils PROMPT [PROFILE] [flags…]
```

Rules:

1. `PROMPT` is one shell word unless you quote a multi-word prompt.
2. Optional `PROFILE` is the second word before any flag; it uses the same resolution as `--configuration` (saved name, path to `.json`, or raw FlatBuffer path).
3. Flags and their values must appear after `PROFILE` (if any). Example: `dts-utils "hello" portrait --negative-prompt blur`.

Expansion (conceptually): `generate --prompt PROMPT --configuration … --trust-server-cert --open` plus your trailing flags. `--trust-server-cert` and `--open` are always added for shorthand so local TLS and opening the PNG match the common interactive path.

Configuration when `PROFILE` is omitted:

1. `DTS_UTILS_DEFAULT_CONFIGURATION` if set (non-empty) in the environment.
2. Otherwise saved profile `default` (`default.json` under `configs path`). If only legacy `zit.json` exists there, it is renamed to `default.json` once. If neither exists, the tool creates `default.json` as a starter JSON once (512×512, default sampling fields, `model` guessed like `generate`, or empty with stderr).
3. After materializing the implicit profile, the process runs `os.environ.setdefault("DTS_UTILS_DEFAULT_CONFIGURATION", "default")` so child processes can see the profile name if you did not already export something else.

**Common tasks (shorthand)**

| Goal | Command | What you get |
| --- | --- | --- |
| Single-line local generate | `uv run dts-utils "a small robot"` | Same as `generate` with trust + open + implicit `default` profile after first-run materialization |
| Named saved profile | `uv run dts-utils "a small robot" portrait` | Uses `portrait` (or path) as `--configuration` |
| Extra TLS flags | `uv run dts-utils "…" --root-cert ./pem` | Adds your flags after the injected defaults |

Explicit `dts-utils generate` without `--configuration` / `--configuration-json` still fails fast; shorthand is the path that auto-bootstraps `default.json`.

---

## Examples

### Basic installation

```bash
uv run dts-utils server install
uv run dts-utils server install -m /path/to/models
```

### Advanced installation

```bash
uv run dts-utils server install -p 7860 -n "MyServer" -m /path/to/models
uv run dts-utils server install -s "your-secret-here"
uv run dts-utils server install --model-browser --debug --no-flash-attention
```

### Server management

```bash
uv run dts-utils server test
uv run dts-utils server test --port 7860
uv run dts-utils server stop
uv run dts-utils server start
uv run dts-utils reflect --trust-server-cert
uv run dts-utils configs path
uv run dts-utils tls path
uv run dts-utils tls export
uv run dts-utils web --open
uv run dts-utils server restart
uv run dts-utils server restart --model-browser
uv run dts-utils server uninstall
```

## Environment variables

| Variable | Used for |
| --- | --- |
| `DRAW_THINGS_MODEL_PATH` | Default Draw Things models directory for `server install` (CLI `--model-path` overrides). Also used when guessing `model` in auto-created `default.json`. |
| `DTS_UTILS_DEFAULT_CONFIGURATION` | Shorthand: profile name or path when you omit the second positional. Set automatically to `default` (via `setdefault`) when the tool materializes the implicit profile, unless you already exported another value. |
| `DTS_UTILS_DEFAULT_MODEL` | Basename (e.g. `my.ckpt`) for the `model` field when creating `default.json` the first time; overrides guessing from the models directory. |
| `DTS_WEB_TOKEN` | When set, `dts-utils web` requires `Authorization: Bearer …` on `/api/*` except `GET /api/health`. |
| `DTS_WEB_GENERATE_TIMEOUT` | Wall-clock cap (seconds, default **900**) for web **`/api/generate`** and **`/api/generate/stream`**. |
| `DTS_UTILS_DEFAULT_FETCH_RECIPE` | Optional override for **`dts-utils models fetch`** when **`RECIPE_ID`** is omitted (otherwise **`registry.json`** **`default_recipe_id`**). |
| `DTS_GRPC_GENERATE_DEBUG` | When set to **`1`** / **`true`** / **`yes`** / **`on`**, **`GenerateImage`** logs one **stderr** summary line per streamed response (field **counts** only). See [PROTOBUF.md § Debugging](PROTOBUF.md#debugging-generateimage-streams). |
| `HF_TOKEN` | Optional Hugging Face token when using **`huggingface`** recipe sources (**`uv sync --extra download`**). |

`DRAW_THINGS_MODEL_PATH` example:

```bash
export DRAW_THINGS_MODEL_PATH=/path/to/your/models
uv run dts-utils server install
```

If both the variable and `--model-path` are set, the CLI option wins.

## Development workflow with uv

```bash
uv sync --dev
uv run pytest
```

## Exit codes

- `0`: Success
- `1`: Runtime error (connection, configuration, RPC, I/O, and similar)
- `2`: Invalid arguments (for example, bare LaunchAgent lifecycle verbs without the `server` prefix, or too many positional tokens in shorthand)

## See also

- [DRAW-THINGS-GRPC-API.md](DRAW-THINGS-GRPC-API.md): upstream service this repository calls
- [PROTOBUF.md](PROTOBUF.md): protobuf and FlatBuffer schemas
- [README.md](README.md): overview and quickstart
