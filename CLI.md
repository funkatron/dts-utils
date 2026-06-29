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
| MCP server for coding agents | [MCP (`dts-utils-mcp`)](#mcp-dts-utils-mcp) |
| Copy example commands | [Examples](#examples) |
| Script-friendly env vars | [Environment variables](#environment-variables) |

---

## Command structure

```
uv run dts-utils <command> [options]
```

Some invocations omit `<command>` and use [Generate shorthand](#generate-shorthand-prompt-first) instead.

Run **`uv run dts-utils --help`** for a short command-tree summary. Subcommands have their own help, for example **`uv run dts-utils server --help`**, **`uv run dts-utils web --help`**, and **`uv run dts-utils generate --help`**.

## Server lifecycle (LaunchAgent)

These commands manage macOS LaunchAgent + `gRPCServerCLI` (not pytest, not Docker).

Required spelling: `dts-utils server <subcommand>` for `install`, `uninstall`, `start`, `stop`, `restart`, `test`, `check`, and `tail`. Running `dts-utils install` without `server` prints a usage error (stderr, exit code `2`).

Bare `dts-utils server`, `dts-utils server --help`, and `dts-utils server -h` print a short server lifecycle summary.

## Available commands

### install (`dts-utils server install`)

Installs and configures the Draw Things gRPC server via the macOS LaunchAgent workflow.

```bash
uv run dts-utils server install [options]
```

Options:

- `-m, --model-path PATH`: Custom path to store models (default: Draw Things app models directory)
- `-q, --quiet`: Minimize output and assume default answers to prompts
- `-y, --yes`: Overwrite an existing LaunchAgent plist without prompting (use with **`install`** when updating settings)
- `-n, --name NAME`: Server name in local network (default: machine name)
- `-p, --port PORT`: Port to run the server on (default: 7859)
- `-a, --address ADDR`: Address to bind to (default: 0.0.0.0)
- `-g, --gpu INDEX`: GPU index to use (default: 0)
- `-d, --datadog-api-key KEY`: Datadog API key for monitoring
- `-s, --shared-secret SECRET`: Authentication key for secure connections
- `--no-tls`: Disable encryption (not recommended)
- `--no-response-compression`: Disable compression
- `--model-browser`: Explicitly enable model browsing (on by default)
- `--no-model-browser`: Disable model browsing on **gRPCServerCLI** (Echo file list). Omit both flags to keep the default (**enabled**). Verify with **`server status`**.
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

Stops then starts the Draw Things gRPC server service (same effect as `server stop` then `server start`). **Settings are whatever is already in** `~/Library/LaunchAgents/com.drawthings.grpcserver.plist` **`ProgramArguments`**, except **`restart`** ensures **`--model-browser`** is present unless you pass **`--no-model-browser`** (model browsing is on by default).

```bash
uv run dts-utils server restart [--no-model-browser]
```

Options:

- `--no-model-browser`: Remove **`--model-browser`** from the plist before restarting

### status

Print the installed LaunchAgent **`ProgramArguments`**, whether **`--model-browser`** is set, listener state, and (when enabled) how many model files **Echo** returns.

```bash
uv run dts-utils server status
```

Exit code **0** when the listener is up; **2** when the plist exists but nothing is listening.

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

### tail

Print recent **`gRPCServerCLI`** unified logs, then follow live output (macOS only; uses `log show` + `log stream`). Handy when **`server check`** passes but generation fails, or after a failed **`server install`**.

```bash
uv run dts-utils server tail
uv run dts-utils server tail --last 1h
uv run dts-utils server tail --last 0
```

Options:

- `--last DURATION`: History window before streaming (default: `5m`). Pass `0` to skip history and stream only.
- `--log-style {compact,syslog,default}`: `log(1)` output style (default: `compact`).

Stop with **Ctrl+C** (exit code `0`). On non-macOS platforms the command prints an error and exits `1`.

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
uv run dts-utils models installed
uv run dts-utils models installed --no-index --json
```

**`installed`:** List checkpoint and companion files under the Draw Things **`Models`** directory (default: **`DRAW_THINGS_MODEL_PATH`** or the macOS container **`Models`** folder). Runs without **`models build`**; when **`data/drawthings_uncurated_models.json`** exists, rows include community **`MATCHED`** ids. **`--no-index`** skips catalog lookup. **`--json`** prints a machine-readable object for scripts. Python: **`from dts_utils import list_installed_models, list_installed_model_filenames`**.

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
- **`configs scaffold-pipeline [NAME]`:** Install a bundled **pipeline profile manifest** (`_dts_utils_pipeline` only) into **`configs path`**. Default **`NAME`** is **`prompt-to-video`** (prompt → T2I via **`default`** → I2V via **`ltx-2.3-portrait`**, loopback gRPC with **`trust_server_cert`**). **`--list`** shows bundled template names. You still need the referenced Draw Things JSON profiles (create **`default`** via normal bootstrap; import or copy **`ltx-2.3-portrait`** from Draw Things, etc.).

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

Runtime checks, profile listing, and run-root cleanup for prompt-to-video workflows. **To run a pipeline**, use **`generate --profile`** (see [generate](#generate) and the profile block below)—not `pipeline run`.

```bash
uv run dts-utils configs scaffold-pipeline prompt-to-video
uv run dts-utils generate --profile prompt-to-video --prompt "a quiet street at dusk" --trust-server-cert
uv run dts-utils pipeline check
uv run dts-utils pipeline profiles
uv run dts-utils pipeline cleanup --older-than 7 --keep-last 20 --dry-run
```

Subcommands:

- `pipeline check`: Report `ffmpeg` availability, run-root writability, and Gatekeeper note. Returns non-zero when required runtime prerequisites are missing.
- `pipeline profiles`: List saved JSON profiles that contain a `_dts_utils_pipeline` block (same idea as picking a profile in the web UI).
- `pipeline cleanup`: Prune old run directories under `--run-root` to control disk usage.
  - `--older-than DAYS`: delete runs older than this age.
  - `--keep-last N`: always preserve newest `N` runs.
  - `--max-run-root-gb GB`: cap total run-root usage by evicting oldest runs.
  - `--dry-run`: print what would be deleted without removing files.
  - `--json`: machine-readable cleanup summary.

**Profile-first (recommended):** put pipeline defaults in a saved profile under `dts-utils configs path` (see `configs path`). The block is stripped before `flatc` and does not affect Draw Things generation JSON.

```json
{
  "_dts_utils_pipeline": {
    "t2i_configuration": "default",
    "video_configuration": "ltx-2.3-portrait",
    "t2i_mode": "drawthings",
    "i2v_backend": "drawthings",
    "fps": 25,
    "video_width": 1024,
    "video_height": 576,
    "grpc": { "trust_server_cert": true }
  }
}
```

Then run with only the profile name and a prompt (CLI flags override profile fields when set):

```bash
uv run dts-utils generate --profile prompt-to-video --prompt "your scene" --trust-server-cert
```

Shorthand (same flow when the second token is a pipeline profile):

```bash
uv run dts-utils "your scene" prompt-to-video
```

If you still type **`pipeline run`**, the CLI prints a short hint and exits non-zero—use **`generate --profile`** instead.

Optional env: `DTS_UTILS_DEFAULT_PIPELINE_PROFILE` (omit `--profile` on **`generate`** when set to a pipeline profile name).

**Generate inputs (pipeline profiles):**

- `--profile NAME` loads `_dts_utils_pipeline` defaults (T2I/I2V config names, gRPC, sizes, prompts).
- `--prompt "..."` runs Draw Things T2I when the profile sets `t2i_mode: drawthings`.
- `--image PATH` runs image-to-video only (with a pipeline profile).
- `--fps`, `--seconds`, `--video-width`, `--video-height`, `--run-root`, `--run-id`, `--no-cache` override profile fields when set.

**Web UI:** Profiles with `_dts_utils_pipeline` appear as **`name (prompt → video)`** in the profile list. The **Generate** button always posts to **`POST /api/generate/stream`** — video profiles send **`profile`**, single-image profiles send **`configuration`**. Legacy **`POST /api/pipeline/run/stream`** still works as an alias.

<a id="web-dts-utils-web"></a>

### web (`dts-utils web`)

Loopback HTTP UI: the browser talks to `dts-utils`; the tool calls Draw Things over gRPC (same idea as `dts-utils generate`).

```bash
uv run dts-utils web [--bind ADDR] [--port N] [--log-level LEVEL] [--no-access-log] [--open]
uv run dts-utils web install [--port N] [--bind ADDR] [-y]   # macOS LaunchAgent
uv run dts-utils web start|stop|restart|uninstall|status     # macOS LaunchAgent lifecycle
uv run dts-utils web tail [-n N] [--file PATH] [--no-follow]
```

Run **`uv run dts-utils web --help`** for a mode summary that lists foreground serve, log tailing, and LaunchAgent lifecycle commands. Run **`uv run dts-utils web install --help`** for service-install options.

**macOS LaunchAgent:** **`web install`** writes **`~/Library/LaunchAgents/com.dts-utils.web.plist`**, runs **`dts-utils web`** at login (**`RunAtLoad`** + **`KeepAlive`**), and uses the same **`dts-utils`** console script that was on **`PATH`** at install time (override with **`--executable`**). **`web status`** probes the listener and **`GET /api/health`**. Lifecycle commands are macOS-only; on Linux use a terminal session or your own unit file.

#### Run / defaults

| Item | Value |
| --- | --- |
| Bind | `127.0.0.1` by default |
| HTTP port | `8765` |
| `--log-level` | Uvicorn verbosity: `critical`, `error`, `warning`, `info`, `debug`, `trace` (default **`info`**) |
| `--no-access-log` | Turn off per-request access lines on stdout and in the web log file |
| `--open` | Open the default browser after startup (URL uses `127.0.0.1` when bind is `0.0.0.0` or `::`) |
| Log file | By default, uvicorn logs append to **`~/.config/dts-utils/web.log`** (override with **`--log-file`**, **`DTS_WEB_LOG_FILE`**, or disable with **`--no-log-file`**) |

#### tail (`dts-utils web tail`)

In a **second terminal**, follow the web UI log while **`dts-utils web`** runs in the first:

```bash
uv run dts-utils web tail
uv run dts-utils web tail -n 200
uv run dts-utils web tail --no-follow
```

Options:

- **`-n` / `--lines`**: Recent lines to print before following (default: **50**).
- **`--file PATH`**: Log file (default: same path as **`dts-utils web`** uses).
- **`--no-follow`**: Print recent lines only (no live follow).

Stop with **Ctrl+C** (exit code **0**). If the log file is missing, start **`dts-utils web`** first (unless you used **`--no-log-file`**).

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
| **`preview`** | `run`, `seq`, `png_b64` — live **`previewImage`** frame while the RPC is in flight. |
| **`image`** | `run`, `index` (global image counter), `png_b64`. Multiple **`image`** events per run if the server returns several tensors. |
| **`done`** | `expanded_prompts`, `expanded_negative_prompts`, `total_images` — only after full success. |
| **`error`** | `detail` — validation, RPC failure, cancel, or timeout. No **`done`** after **`error`**. |

#### Browser UI (built-in page)

- **⌘↵** (macOS) or **Ctrl+Enter**: Generate from the prompt.
- **Stop**: **`POST /api/generate/cancel`** + abort fetch; cancel applies between runs (see above).
- Busy panel shows the JSON sent to **`/api/generate/stream`** (`shared_secret` redacted in the preview).
- **Fullscreen viewer:** Click any PNG thumbnail in the main **results** grid or in **History** for a near-black fullscreen view. **Escape** or tap the dim backdrop (outside the picture) closes it. **Arrow Left / Right**, the **‹ ›** side zones, or a **horizontal swipe** moves between images **in that batch only** (same generation row or the same History entry). **F** toggles **Fit** (whole image, letterboxed) vs **Fill** (crop to the frame so the picture uses the full viewer box — useful for inspecting detail); the bottom caption shows which mode is active.
- **Composer (footer):** **Image / Video** toggle, grouped **profile** menu (recent + categories), **listener status**, optional **negative prompt**, visible **Generate** label, and errors above the prompt. Last profile/output mode persist in browser **`localStorage`** (`dts_web_ui_v1`). Default profile is **`default`** (image), not **`prompt-to-video`**.
- **Setup** FAB (top-right): **Connection** (host, port, TLS, check listener) and **Advanced** (custom profile path, shared secret, cert paths, config dir). Profile and negative prompt live in the composer. A dot on the Setup icon reflects listener state (green/amber/red). **History** FAB: recent PNGs saved by the web server under the resolved **`dts-utils`** config directory (see **`dts-utils configs path`**), with download links and a **Reuse** action that restores the prompt, saved JSON **profile** (`configuration`, same value sent to generate), **runs**, and **negative prompt** to match that batch. Each row’s subtitle shows the profile name when it was stored. Older entries without a stored profile behave as before on Reuse (prompt only unless other fields were saved). Existing browser **`localStorage`** history is imported the first time you open History (`configuration` is forwarded when present on legacy rows). Set **`DTS_WEB_HISTORY_DIR`** to override the image/history storage directory. **Clear all** wipes web history files. Prompt-to-video runs show a **run folder** path with **Copy path** when the pipeline finishes.

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

- `--profile NAME`: Saved profile name. When the JSON includes **`_dts_utils_pipeline`** (for example **`prompt-to-video`**), runs the full prompt → image → video flow and writes artifacts under **`--run-root`** (default `~/Movies/infomux-runs`). A non-pipeline name is treated as **`--configuration`** for a single PNG.
- `--fps`, `--seconds`, `--video-width`, `--video-height`: Override pipeline video timing/size (with **`--profile`**).
- `--run-root`, `--run-id`, `--no-cache`: Pipeline run layout and caching (with **`--profile`**).
- `--image PATH`: Existing image for pipeline image-to-video only (with a pipeline **`--profile`**).
- `--output PATH`: Base path for output files. Default: `output/generated.png`. The CLI inserts `-<unix_ms>` before the extension (for example `output/generated.png` → `output/generated-1735123456789.png`). Multiple images append `-2`, `-3`, … before the extension. Success lines print as `Wrote …` on stdout. Ignored for pipeline profiles (use artifact paths printed after the run).
- `--configuration VALUE`: Draw Things configuration. Existing `.json` files are converted to FlatBuffer bytes; other existing files are sent as raw FlatBuffer bytes; simple names resolve to saved JSON configs.
- `--configuration-json VALUE`: JSON configuration file or saved config name (mutually exclusive with **`--profile`** / **`--configuration`**).
- `--trust-server-cert`: Trust the certificate presented by a localhost server for this connection.
- `--force-trust-server-cert`: Trust the certificate presented by any server (MITM risk).
- `--root-cert PATH`: Pinned PEM root/server certificate.
- `--no-tls`: Plaintext gRPC when the server was installed with `--no-tls`.
- `--max-message-mb N`: gRPC send/receive limits in MiB.
- `--open`: Open written images with the platform default viewer.
- **Prompt wildcards:** Write **`{option A | option B}`** (or **`{option A, option B}`** when the block has no `|`). Each time a prompt is sent to the server, every `{…}` block picks **one** branch at random—so multi-image runs (**`--generations N`** or **`generations`** in JSON) **re-roll** the whole template for **each** image. Only **depth‑0** delimiters split (nested `{…}` may contain `|` or commas). Choices can nest; expansion repeats until done, with limits on passes (~128) and output length (~100k chars). Bad or stuck templates raise an error (HTTP **400** from **`dts-utils web`**). Use **`POST /api/prompt/expand`** in the web server to sample expansions without generating.

Explicit `generate` requires **`--profile`**, **`--configuration`**, or **`--configuration-json`** (unlike shorthand, which can materialize **`default.json`**). Set **`DTS_UTILS_DEFAULT_PIPELINE_PROFILE`** to omit **`--profile`** when it names a pipeline profile.

**Common tasks (explicit `generate`):**

| Goal | Command | What you get |
| --- | --- | --- |
| Prompt to video | `uv run dts-utils generate --profile prompt-to-video --prompt "…" --trust-server-cert --fps 10 --seconds 2.5` | MP4 (and intermediates) under `~/Movies/infomux-runs/…` |
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
2. Optional `PROFILE` is the second word before any flag. Pipeline profiles (saved JSON with **`_dts_utils_pipeline`**, for example **`prompt-to-video`**) expand to **`generate --profile …`**; other names expand to **`--configuration …`**.
3. Flags and their values must appear after `PROFILE` (if any). Example: `dts-utils "hello" portrait --negative-prompt blur`.

Expansion (conceptually): `generate --prompt PROMPT` plus either `--profile …` or `--configuration …`, then `--trust-server-cert --open` and your trailing flags. `--trust-server-cert` and `--open` are always added for shorthand so local TLS and opening the result match the common interactive path.

Configuration when `PROFILE` is omitted:

1. `DTS_UTILS_DEFAULT_CONFIGURATION` if set (non-empty) in the environment.
2. Otherwise saved profile `default` (`default.json` under `configs path`). If only legacy `zit.json` exists there, it is renamed to `default.json` once. If neither exists, the tool creates `default.json` as a starter JSON once (512×512, default sampling fields, `model` guessed like `generate`, or empty with stderr).
3. After materializing the implicit profile, the process runs `os.environ.setdefault("DTS_UTILS_DEFAULT_CONFIGURATION", "default")` so child processes can see the profile name if you did not already export something else.

**Common tasks (shorthand)**

| Goal | Command | What you get |
| --- | --- | --- |
| Single-line local generate | `uv run dts-utils "a small robot"` | Same as `generate` with trust + open + implicit `default` profile after first-run materialization |
| Named saved profile | `uv run dts-utils "a small robot" portrait` | Uses `portrait` (or path) as `--configuration` |
| Prompt to video | `uv run dts-utils "a rainy street" prompt-to-video` | Full pipeline via `--profile prompt-to-video` |
| Extra TLS flags | `uv run dts-utils "…" --root-cert ./pem` | Adds your flags after the injected defaults |

Explicit `dts-utils generate` without `--configuration` / `--configuration-json` still fails fast; shorthand is the path that auto-bootstraps `default.json`.

<a id="mcp-dts-utils-mcp"></a>

### MCP (`dts-utils-mcp`)

stdio Model Context Protocol server for coding agents (Cursor, Claude Desktop, etc.). Tools call the same Python APIs as **`generate`** and **`web`** — no separate HTTP server.

**Install:** `uv sync --extra mcp` (or `uv pip install 'dts-utils[mcp]'`). Dev/CI: **`mcp`** is included in **`uv sync --dev`**.

**Run:**

```bash
uv run dts-utils-mcp
```

**Cursor** (`settings` → MCP): point **`command`** at **`uv`** with **`args`**: `run`, `--directory`, `/path/to/dts-utils`, `dts-utils-mcp` — or use **`dts-utils-mcp`** on `PATH` after install.

| Tool | Purpose |
| --- | --- |
| `dts_server_check` | Probe gRPC listener (`host`, `port`, `no_tls`) |
| `dts_list_configs` | List saved profile stems |
| `dts_get_config` | Read one profile JSON |
| `dts_expand_prompt` | Preview `{a\|b}` wildcards |
| `dts_generate_image` | Generate PNG(s); paths by default, optional `include_image_data` |
| `dts_list_installed_models` | Scan Draw Things **`Models`** directory |
| `dts_models_search` | Search local index from **`models build`** (`data/drawthings_uncurated_models.json`) |
| `dts_models_doctor` | Partial downloads, orphan sidecars, index mismatches |
| `dts_pipeline_run` | Run a pipeline profile (e.g. **`prompt-to-video`**); blocks until complete |
| `dts_pipeline_status` | Read **`heartbeat.json`** / **`pipeline_run.json`** for a run |
| `dts_generate_cancel` | Cooperative cancel for in-flight generate (between batch iterations) |

**Optional lifecycle tools** (macOS only; set `DTS_MCP_ALLOW_SERVER_LIFECYCLE=1` on the MCP server process):

| Tool | Purpose |
| --- | --- |
| `dts_server_status` | LaunchAgent plist summary + listener probe |
| `dts_server_start` | Bootstrap LaunchAgent job |
| `dts_server_stop` | Boot out LaunchAgent job |
| `dts_server_restart` | Restart job (`ensure_model_browser` default true) |

**Defaults:** `localhost:7859`, `trust_server_cert=true` on loopback, configuration profile **`default`** (or `DTS_UTILS_DEFAULT_CONFIGURATION`). Errors map to MCP tool failures with readable text (same classes as CLI/web). **`shared_secret`** is never logged.

macOS server lifecycle tools are not exposed via MCP unless **`DTS_MCP_ALLOW_SERVER_LIFECYCLE=1`** (stdio server env). **`server install` / `uninstall` are not exposed** via MCP.

| Resource URI | Content |
| --- | --- |
| `dts://config/{stem}` | Saved profile JSON (`application/json`) |
| `dts://output/{relative_path}` | File under `./output` (or `DTS_MCP_OUTPUT_ROOTS`) |
| `dts://pipeline/{run_id}/{step_id}/{filename}` | Pipeline artifact under pipeline run root (`DTS_MCP_PIPELINE_RUN_ROOT` or default `~/Movies/infomux-runs`) |

Path traversal (`..`) is rejected for all resource URIs.

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
uv run dts-utils server install --debug --no-flash-attention
```

### Server management

```bash
uv run dts-utils server test
uv run dts-utils server test --port 7860
uv run dts-utils server tail
uv run dts-utils server tail --last 1h
uv run dts-utils server stop
uv run dts-utils server start
uv run dts-utils reflect --trust-server-cert
uv run dts-utils configs path
uv run dts-utils tls path
uv run dts-utils tls export
uv run dts-utils web --open
uv run dts-utils web tail
uv run dts-utils server restart
uv run dts-utils server restart
uv run dts-utils server uninstall
```

## Environment variables

| Variable | Used for |
| --- | --- |
| `DRAW_THINGS_MODEL_PATH` | Default Draw Things models directory for `server install` (CLI `--model-path` overrides). Also used when guessing `model` in auto-created `default.json`. |
| `DTS_UTILS_DEFAULT_CONFIGURATION` | Shorthand: profile name or path when you omit the second positional. Set automatically to `default` (via `setdefault`) when the tool materializes the implicit profile, unless you already exported another value. |
| `DTS_UTILS_DEFAULT_MODEL` | Basename (e.g. `my.ckpt`) for the `model` field when creating `default.json` the first time; overrides guessing from the models directory. |
| `DTS_WEB_TOKEN` | When set, `dts-utils web` requires `Authorization: Bearer …` on `/api/*` except `GET /api/health`. |
| `DTS_WEB_LOG_FILE` | Override default web log path (`~/.config/dts-utils/web.log`); used by **`dts-utils web`** and **`dts-utils web tail`**. |
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
