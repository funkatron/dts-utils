# dts-utils CLI reference

Flags, subcommands, environment variables, and the loopback web HTTP API. For install steps, quickstart, TLS overview, and troubleshooting, see [README.md](README.md).

## Contents

- [Invocation](#invocation)
- [Commands](#commands)
  - [generate](#generate)
  - [Generate shorthand](#generate-shorthand-prompt-first)
  - [server](#server-dts-utils-server)
  - [configs](#configs)
  - [models](#models-dts-utils-models)
  - [pipeline](#pipeline-dts-utils-pipeline)
  - [web](#web-dts-utils-web)
  - [reflect](#reflect)
  - [tls](#tls)
  - [MCP (`dts-utils-mcp`)](#mcp-dts-utils-mcp)
- [Environment variables](#environment-variables)
- [Exit codes](#exit-codes)
- [See also](#see-also)

---

## Invocation

```bash
uv run dts-utils <command> [options]
```

| Pattern | Example | Notes |
| --- | --- | --- |
| Named subcommand | `uv run dts-utils server check` | Most commands use this form. |
| Prompt-first shorthand | `uv run dts-utils "a quiet street"` | Omits `generate`; see [Generate shorthand](#generate-shorthand-prompt-first). |
| Separate MCP entrypoint | `uv run dts-utils-mcp` | stdio MCP server; see [MCP](#mcp-dts-utils-mcp). |

**Help:** `uv run dts-utils --help` prints the command tree. Subcommands have their own help, for example `server --help`, `web --help`, and `generate --help`.

**Explicit vs shorthand:** `dts-utils generate` requires `--profile`, `--configuration`, or `--configuration-json`. Shorthand can bootstrap `default.json` on first run and always adds `--trust-server-cert` and `--open` for local use.

---

## Commands

### generate

Send a prompt through Draw Things streaming gRPC and write PNG output (or run a pipeline profile to produce video artifacts).

```bash
uv run dts-utils generate \
  --prompt "a small robot painting clouds" \
  --configuration portrait \
  --trust-server-cert \
  --open
```

**Options**

| Flag | Purpose |
| --- | --- |
| `--profile NAME` | Saved profile. JSON with **`_dts_utils_pipeline`** (e.g. **`prompt-to-video`**) runs prompt → image → video under **`--run-root`** (default `~/Movies/infomux-runs`). Other names act like **`--configuration`** for a single PNG. |
| `--fps`, `--seconds`, `--video-width`, `--video-height` | Override pipeline video timing/size (with **`--profile`**). |
| `--run-root`, `--run-id`, `--no-cache` | Pipeline run layout and caching (with **`--profile`**). |
| `--image PATH` | Existing image for pipeline image-to-video only (with a pipeline **`--profile`**). |
| `--output PATH` | Base path for PNG output. Default: `output/generated.png`. Inserts `-<unix_ms>` before the extension; multiple images use `-2`, `-3`, … Success lines print `Wrote …` on stdout. Ignored for pipeline profiles (use artifact paths printed after the run). |
| `--configuration VALUE` | Draw Things configuration: saved `.json` (converted via **`flatc`**), raw FlatBuffer file, or simple name resolving to saved JSON. |
| `--configuration-json VALUE` | JSON file or saved config name (mutually exclusive with **`--profile`** / **`--configuration`**). |
| `--trust-server-cert` | Trust the certificate presented by a localhost server for this connection. |
| `--force-trust-server-cert` | Trust the presented certificate for any host (MITM risk). |
| `--root-cert PATH` | Pinned PEM root/server certificate. |
| `--no-tls` | Plaintext gRPC when the server was installed with **`--no-tls`**. |
| `--max-message-mb N` | gRPC send/receive limits in MiB. |
| `--open` | Open written images with the platform default viewer. |

**Prompt wildcards:** Write **`{option A \| option B}`** (or **`{option A, option B}`** when the block has no `|`). Each `{…}` block picks one branch at random per server request, so **`--generations N`** re-rolls for each image. Only depth‑0 delimiters split. Limits: ~128 passes, ~100k chars output. Bad templates error (HTTP **400** from **`dts-utils web`**). **`POST /api/prompt/expand`** samples without generating.

Set **`DTS_UTILS_DEFAULT_PIPELINE_PROFILE`** to omit **`--profile`** when it names a pipeline profile.

**Common tasks**

| Goal | Command |
| --- | --- |
| Prompt to video | `uv run dts-utils generate --profile prompt-to-video --prompt "…" --trust-server-cert --fps 10 --seconds 2.5` |
| Saved config | `uv run dts-utils generate --prompt "…" --configuration portrait --trust-server-cert` |
| Draw Things JSON | `uv run dts-utils generate --prompt "…" --configuration config.json --trust-server-cert` |
| Open result | Add **`--open`** to any of the above |
| Prebuilt FlatBuffer | `uv run dts-utils generate --prompt "…" --configuration config.bin --trust-server-cert` |
| Pinned cert | `uv run dts-utils generate --prompt "…" --configuration config.json --root-cert cert.pem` |
| Remote diagnostic | `uv run dts-utils generate --host gpu.local --prompt "…" --configuration config.json --force-trust-server-cert` |

Prefer **`--root-cert`** off localhost. Use **`--force-trust-server-cert`** only when you cannot pin a cert and accept MITM risk for that connection.

<a id="generate-shorthand-prompt-first"></a>

### Generate shorthand (prompt-first)

When the first argument is not a known subcommand, lifecycle verb, or flag, the line is shorthand for generation.

```text
dts-utils PROMPT [PROFILE] [flags…]
```

**Rules**

1. **`PROMPT`** is one shell word unless quoted.
2. Optional **`PROFILE`** is the second word before flags. Pipeline profiles (JSON with **`_dts_utils_pipeline`**, e.g. **`prompt-to-video`**) → **`generate --profile …`**; other names → **`--configuration …`**.
3. Flags appear after **`PROFILE`** (if any). Example: `dts-utils "hello" portrait --negative-prompt blur`.

Expansion (conceptually): `generate --prompt PROMPT` plus profile or configuration, then **`--trust-server-cert --open`** and your trailing flags.

**Configuration when `PROFILE` is omitted**

1. **`DTS_UTILS_DEFAULT_CONFIGURATION`** if set (non-empty).
2. Otherwise saved profile **`default`** (`default.json` under **`configs path`**). Legacy **`zit.json`** is renamed to **`default.json`** once if needed. If neither exists, the tool creates starter **`default.json`** once (512×512 defaults, **`model`** guessed or empty with stderr hint).
3. After materializing the implicit profile, **`os.environ.setdefault("DTS_UTILS_DEFAULT_CONFIGURATION", "default")`** runs unless you already exported another value.

**Common tasks**

| Goal | Command |
| --- | --- |
| Local generate | `uv run dts-utils "a small robot"` |
| Named profile | `uv run dts-utils "a small robot" portrait` |
| Prompt to video | `uv run dts-utils "a rainy street" prompt-to-video` |
| Extra TLS flags | `uv run dts-utils "…" --root-cert ./pem` |

Explicit **`dts-utils generate`** without **`--configuration`** / **`--configuration-json`** still fails fast; shorthand is the path that auto-bootstraps **`default.json`**.

<a id="server-dts-utils-server"></a>

### server (`dts-utils server`)

Manage **`gRPCServerCLI`** through the macOS LaunchAgent workflow (not pytest, not Docker).

**Required spelling:** `dts-utils server <subcommand>` for `install`, `uninstall`, `start`, `stop`, `restart`, `test`, `check`, `status`, and `tail`. `dts-utils install` without **`server`** prints usage (stderr, exit **`2`**).

Bare **`dts-utils server`**, **`server --help`**, and **`server -h`** print a short lifecycle summary.

#### install

Install and configure Draw Things gRPC server via LaunchAgent.

```bash
uv run dts-utils server install [options]
```

| Option | Purpose |
| --- | --- |
| `-m, --model-path PATH` | Models directory (default: Draw Things app models) |
| `-q, --quiet` | Minimize output; default answers to prompts |
| `-y, --yes` | Overwrite existing LaunchAgent plist without prompting |
| `-n, --name NAME` | Server name on local network (default: machine name) |
| `-p, --port PORT` | Listen port (default: **7859**) |
| `-a, --address ADDR` | Bind address (default: **0.0.0.0**) |
| `-g, --gpu INDEX` | GPU index (default: **0**) |
| `-d, --datadog-api-key KEY` | Datadog API key |
| `-s, --shared-secret SECRET` | Authentication key |
| `--no-tls` | Disable encryption (not recommended) |
| `--no-response-compression` | Disable compression |
| `--model-browser` | Explicitly enable model browsing (default: on) |
| `--no-model-browser` | Disable model browsing on **`gRPCServerCLI`** (Echo file list) |
| `--no-flash-attention` | Disable Flash Attention |
| `--debug` | Verbose logging |
| `--join JSON` | JSON configuration for proxy setup |
| `--export-tls-cert` | After successful install with TLS, write presented PEM |
| `--export-tls-cert-path PATH` | Destination for **`--export-tls-cert`** (default: **`dts-utils tls path`**) |
| `--export-tls-cert-force` | Overwrite existing PEM during export |

Verify model browser with **`server status`**. Omit both **`--model-browser`** and **`--no-model-browser`** to keep the default (enabled).

#### uninstall

Remove Draw Things gRPC server and related files managed by this tool.

```bash
uv run dts-utils server uninstall
```

#### start

Load `~/Library/LaunchAgents/com.drawthings.grpcserver.plist` and start the job (requires **`install`** first). Uses **`launchctl bootstrap`**; **`kickstart`** if already registered; legacy **`load`** fallback.

```bash
uv run dts-utils server start
```

#### stop

Boot the job out of launchd. Plist and binary remain (**`restart`** = stop + start; **`uninstall`** removes files). Uses **`bootout`**; **`unload`**/**`remove`** fallback.

```bash
uv run dts-utils server stop
```

#### restart

Stop then start the service. Settings come from plist **`ProgramArguments`**, except **`restart`** ensures **`--model-browser`** unless you pass **`--no-model-browser`**.

```bash
uv run dts-utils server restart [--no-model-browser]
```

| Option | Purpose |
| --- | --- |
| `--no-model-browser` | Remove **`--model-browser`** from plist before restarting |

#### status

Print plist **`ProgramArguments`**, **`--model-browser`** flag, listener state, and Echo model file count when browsing is enabled.

```bash
uv run dts-utils server status
```

Exit **`0`** when the listener is up; **`2`** when plist exists but nothing is listening.

#### test / check

Probe localhost for a reachable gRPC listener (installer workflow; not pytest).

```bash
uv run dts-utils server test [--port PORT]
uv run dts-utils server check [--port PORT]
```

| Option | Purpose |
| --- | --- |
| `--port PORT` | Port to probe (default: **7859**) |
| `--no-tls` | Plaintext only (when server was installed with **`--no-tls`**) |

On loopback, default probe tries TLS with server-presented cert first, then plaintext. **`check`** is a synonym for **`test`**.

#### tail

Recent **`gRPCServerCLI`** unified logs, then live follow (macOS only; **`log show`** + **`log stream`**).

```bash
uv run dts-utils server tail
uv run dts-utils server tail --last 1h
uv run dts-utils server tail --last 0
```

| Option | Purpose |
| --- | --- |
| `--last DURATION` | History before streaming (default: **`5m`**). **`0`** = stream only. |
| `--log-style {compact,syslog,default}` | **`log(1)`** style (default: **`compact`**) |

Stop with **Ctrl+C** (exit **`0`**). Non-macOS: error and exit **`1`**.

### configs

Show, list, import, and scaffold saved Draw Things JSON generation configurations.

```bash
uv run dts-utils configs path
uv run dts-utils configs list
uv run dts-utils configs import-draw-things --dry-run
uv run dts-utils configs scaffold-from-metadata ~/.cache/community-models/models/flux-2-klein-base-9b/metadata.json --dry-run
```

| Subcommand | Purpose |
| --- | --- |
| **`configs path`** | Print saved-config directory, creating it if needed. |
| **`configs path --no-create`** | Print directory without creating it. |
| **`configs list`** | List saved JSON configuration names. |
| **`configs list --directory PATH`** | List from another directory. |
| **`configs import-draw-things`** | macOS only — read Draw Things **`custom_configs.json`**, write **`NAME.json`** per preset (inner **`configuration`** object only). **`--source`**, **`--directory`**, **`--dry-run`**, **`--force`**. **`--mirror-app-json`** copies ancillary app JSON into **`draw-things-app/`** (not used by **`generate`**). May need Terminal Full Disk Access. |
| **`configs scaffold-from-metadata METADATA.json`** | Starter profile from one cloned **`metadata.json`** (local checkpoint **`file`** only). **`--name`**, **`--directory`**, **`--dry-run`**, **`--force`**. Prefills width/height/steps from **`note`** when possible. |
| **`configs scaffold-from-metadata --scan DIR`** | Walk **`DIR`** for **`metadata.json`** (skips **`apis/`**). **`--limit N`**, **`--verbose`**, **`--force`**. Do not combine **`--scan`** with positional **`METADATA.json`** or **`--name`**. |
| **`configs scaffold-pipeline [NAME]`** | Install bundled pipeline manifest (**`_dts_utils_pipeline`** only). Default **`prompt-to-video`**. **`--list`** shows templates. You still need referenced Draw Things profiles (**`default`**, **`ltx-2.3-portrait`**, etc.). |

Save files such as **`portrait.json`** in the configs directory, then **`--configuration portrait`** with **`generate`**.

<a id="models-dts-utils-models"></a>

### models (`dts-utils models`)

Inspect the cloned **`drawthingsai/community-models`** index and optionally download weights via bundled fetch recipes.

```bash
uv run dts-utils models fetch --dry-run
uv run dts-utils models fetch RECIPE_ID --yes --model-dir /path/to/Models
uv run dts-utils models installed
uv run dts-utils models installed --no-index --json
```

**`installed`:** Checkpoint and companion files under Draw Things **`Models`** (**`DRAW_THINGS_MODEL_PATH`** or macOS container default). No **`models build`** required; **`MATCHED`** ids when index exists. **`--no-index`**, **`--json`**. Python: **`list_installed_models`**, **`list_installed_model_filenames`**.

**`fetch`**

| Flag / arg | Purpose |
| --- | --- |
| **`--dry-run`** | Planned artifacts only — no HTTP, no writes. |
| **`--yes`** | Required for mutating downloads (else exit **`2`**). **`DTS_UTILS_DEFAULT_FETCH_RECIPE`** does not bypass **`--yes`**. |
| **`RECIPE_ID`** | Optional positional. Omitted: env override, then **`registry.json`** **`default_recipe_id`**. Unknown id or missing default → exit **`2`**. |
| **`--model-dir`** | Destination (**`DRAW_THINGS_MODEL_PATH`** or Draw Things default). |
| **`--force`** | Re-fetch when not satisfied (**`sha256`**, **`expected_size_bytes`**, or non-empty file). |
| **`--from-metadata PATH`** | Expected basenames from one **`metadata.json`**. **`--manifest`**: basename + SHA on stdout; URL hints once on stderr. **`--manifest-wide`**: legacy four-column rows. |

Recipes allow **`https://`** only (TLS always on). **`type`: `huggingface`** needs **`huggingface_hub`** (**`uv sync --extra download`**); **`HF_TOKEN`** passed when set. Bundled recipes under **`dts_utils/model_fetch/recipe_files/`**. Roadmap: **[docs/models-fetch-roadmap.md](docs/models-fetch-roadmap.md)**.

Smoke recipes: **`sdxl-turbo`**, **`z-image-turbo-1.0-exact`**, **`ltx-2.3-22b-distilled-exact`**.

<a id="pipeline-dts-utils-pipeline"></a>

### pipeline (`dts-utils pipeline`)

Runtime checks, profile listing, and run-root cleanup for prompt-to-video workflows.

**To run a pipeline**, use **`generate --profile`** — not **`pipeline run`**. Typing **`pipeline run`** prints a hint and exits non-zero.

```bash
uv run dts-utils configs scaffold-pipeline prompt-to-video
uv run dts-utils generate --profile prompt-to-video --prompt "a quiet street at dusk" --trust-server-cert
uv run dts-utils pipeline check
uv run dts-utils pipeline profiles
uv run dts-utils pipeline cleanup --older-than 7 --keep-last 20 --dry-run
```

| Subcommand | Purpose |
| --- | --- |
| **`pipeline check`** | **`ffmpeg`**, run-root writability, Gatekeeper note. Non-zero when prerequisites missing. |
| **`pipeline profiles`** | Saved JSON with **`_dts_utils_pipeline`** (same idea as web UI profile list). |
| **`pipeline cleanup`** | Prune old runs under **`--run-root`**. **`--older-than DAYS`**, **`--keep-last N`**, **`--max-run-root-gb GB`**, **`--dry-run`**, **`--json`**. |

**Profile block** (stripped before **`flatc`**; does not affect Draw Things generation JSON):

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

Shorthand equivalent: `uv run dts-utils "your scene" prompt-to-video`

Optional env: **`DTS_UTILS_DEFAULT_PIPELINE_PROFILE`** (omit **`--profile`** on **`generate`** when set).

**Generate inputs (pipeline profiles):** **`--profile`**, **`--prompt`**, **`--image`**, **`--fps`**, **`--seconds`**, **`--video-width`**, **`--video-height`**, **`--run-root`**, **`--run-id`**, **`--no-cache`** — CLI flags override profile fields.

**Web UI:** Profiles show as **`name (prompt → video)`**. Generate posts to **`POST /api/generate/stream`** with **`profile`** for video, **`configuration`** for image. Legacy **`POST /api/pipeline/run/stream`** is an alias.

<a id="web-dts-utils-web"></a>

### web (`dts-utils web`)

Loopback HTTP UI: browser → **`dts-utils`** → Draw Things gRPC (same stack as **`generate`**).

```bash
uv run dts-utils web [--bind ADDR] [--port N] [--log-level LEVEL] [--no-access-log] [--open]
uv run dts-utils web install [--port N] [--bind ADDR] [-y]   # macOS LaunchAgent
uv run dts-utils web start|stop|restart|uninstall|status
uv run dts-utils web tail [-n N] [--file PATH] [--no-follow]
```

Run **`web --help`** for serve, tail, and LaunchAgent modes. **`web install --help`** for service options.

**macOS LaunchAgent:** **`web install`** writes **`~/Library/LaunchAgents/com.dts-utils.web.plist`**, **`RunAtLoad`** + **`KeepAlive`**. Uses **`dts-utils`** on **`PATH`** at install (**`--executable`** override). **`web status`** probes listener and **`GET /api/health`**. Lifecycle commands are macOS-only; on Linux use a terminal or your own unit file.

#### Defaults

| Item | Value |
| --- | --- |
| Bind | **`127.0.0.1`** |
| HTTP port | **8765** |
| **`--log-level`** | Uvicorn: **`critical`**, **`error`**, **`warning`**, **`info`**, **`debug`**, **`trace`** (default **`info`**) |
| **`--no-access-log`** | Disable per-request access lines |
| **`--open`** | Open browser after startup |
| Log file | **`~/.config/dts-utils/web.log`** ( **`--log-file`**, **`DTS_WEB_LOG_FILE`**, **`--no-log-file`**) |

#### tail (`dts-utils web tail`)

```bash
uv run dts-utils web tail
uv run dts-utils web tail -n 200
uv run dts-utils web tail --no-follow
```

| Option | Purpose |
| --- | --- |
| **`-n` / `--lines`** | Recent lines before follow (default **50**) |
| **`--file PATH`** | Log file path |
| **`--no-follow`** | Print recent lines only |

**Ctrl+C** exits **`0`**. Missing log file: start **`dts-utils web`** first.

#### Auth and limits

- **`DTS_WEB_TOKEN`:** Required on **`/api/*`** except **`GET /api/health`** when set (**`Authorization: Bearer <token>`**). Bind widely without token → stderr warning.
- **`DTS_WEB_GENERATE_TIMEOUT`:** Wall-clock cap in seconds (default **900**) for **`POST /api/generate`** (**504**) and **`/api/generate/stream`** (SSE **`error`**). Timeout applies between batch runs, not mid-RPC.
- **Streaming backpressure:** Up to **64** buffered SSE payloads; slow readers stall generation until space is available.

#### HTTP endpoints

**Probe:** **`GET /api/server-status`** — listener check (**`no_tls`** query matches **`server check --no-tls`**). Probe success does not guarantee generation (config, **`flatc`**, TLS).

**Generate — pick one response style:**

| Endpoint | Response | Client |
| --- | --- | --- |
| **`POST /api/generate`** | **`multipart/mixed`** PNG + **`X-Generated-Count`**, **`X-Generation-Runs`** | Scripts |
| **`POST /api/generate/stream`** | **`text/event-stream`** (SSE) | Browser UI |

Same JSON body and bearer rules. Common keys: **`prompt`**, **`negative_prompt`**, **`generations`** (1–25), **`prompts`** / **`negative_prompts`** arrays, **`configuration`**, **`host`**, **`port`**, **`no_tls`**, **`trust_server_cert`**, **`force_trust_server_cert`**, **`root_cert`**, **`shared_secret`**, **`config_dir`**.

Errors: JSON **`{"detail":"…"}`** for bad requests; generation failures mirror CLI messages where possible.

| Route | Purpose |
| --- | --- |
| **`POST /api/generate/cancel`** | Cooperative cancel between batch iterations. Multipart in-flight → **499**; streaming → SSE **`error`**. |
| **`POST /api/prompt/expand`** | Random **`{…}`** expansions without generating. **`GET`** describes POST shape. |
| **`GET /api/configs`** | Saved profile names |

#### SSE events (`/api/generate/stream`)

One line per event: `data: <json>\n\n`.

| `type` | Meaning |
| --- | --- |
| **`meta`** | **`total_runs`** |
| **`progress`** | **`run`**, **`total_runs`** |
| **`preview`** | **`run`**, **`seq`**, **`png_b64`** — live preview frame |
| **`image`** | **`run`**, **`index`**, **`png_b64`** |
| **`done`** | **`expanded_prompts`**, **`expanded_negative_prompts`**, **`total_images`** |
| **`error`** | **`detail`** — no **`done`** after **`error`** |

#### Browser UI

- **⌘↵** / **Ctrl+Enter**: Generate.
- **Stop**: **`POST /api/generate/cancel`** + abort fetch.
- Busy panel shows request JSON (**`shared_secret`** redacted).
- **Fullscreen viewer:** Click thumbnails; **Escape** or backdrop closes. **Arrow keys**, **‹ ›**, swipe within batch. **F** toggles Fit vs Fill.
- **Composer:** Image/Video toggle, grouped profiles, listener status, negative prompt, **`localStorage`** (**`dts_web_ui_v1`**). Default profile **`default`** (image).
- **Setup FAB:** Connection + Advanced (host, TLS, secrets, paths). **History FAB:** recent PNGs under configs directory (**`DTS_WEB_HISTORY_DIR`** override). Prompt-to-video shows run folder with **Copy path**.

LaunchAgent server lifecycle stays in Terminal (**`dts-utils server …`**).

### reflect

List gRPC services and methods via server reflection.

```bash
uv run dts-utils reflect --trust-server-cert
```

| Option | Purpose |
| --- | --- |
| **`--host HOST`** | gRPC host (default: **`localhost`**) |
| **`--port PORT`** | gRPC port (default: **7859**) |
| **`--timeout SECONDS`** | Connection timeout (default: **2**) |
| **`--json`** | Machine-readable JSON |
| **`--trust-server-cert`** | Trust presented cert on localhost only |
| **`--force-trust-server-cert`** | Trust any host (MITM risk) |
| **`--root-cert PATH`** | Pinned PEM |
| **`--no-tls`** | Plaintext when server uses **`--no-tls`** |

For remote/LAN servers, prefer **`--root-cert`**. Draw Things often builds without reflection — **`UNIMPLEMENTED`** while **`generate`** works is expected. See [README.md § Troubleshooting](README.md#troubleshooting).

### tls

Export the server's presented TLS certificate to PEM for **`--root-cert`** on clients.

```bash
uv run dts-utils tls path
uv run dts-utils tls export
```

| Subcommand | Purpose |
| --- | --- |
| **`tls path`** | Default PEM path under **`dts-utils`** config dir (**`~/.config/dts-utils`** on macOS/Linux when **`XDG_CONFIG_HOME`** unset). **`--no-create`** skips parent creation. |
| **`tls export`** | Capture presented PEM. **`--output`/` -o`**, **`--force`**, **`--host`**, **`--port`**, **`--retries`**. |

**`server install --export-tls-cert`** exports after **`server test`** passes (skipped with **`--no-tls`**).

<a id="mcp-dts-utils-mcp"></a>

### MCP (`dts-utils-mcp`)

stdio Model Context Protocol server for coding agents (Cursor, Claude Desktop). Tools use the same Python APIs as **`generate`** and **`web`** — no HTTP proxy.

**Install:** `uv sync --extra mcp` or `uv pip install 'dts-utils[mcp]'`. Dev/CI: **`mcp`** is in **`uv sync --dev`**.

```bash
uv run dts-utils-mcp
```

**Cursor** (`settings` → MCP):

```json
{
  "mcpServers": {
    "dts-utils": {
      "command": "uv",
      "args": ["run", "--extra", "mcp", "--directory", "/path/to/dts-utils", "dts-utils-mcp"]
    }
  }
}
```

Or **`dts-utils-mcp`** on **`PATH`** after install with **`[mcp]`**.

| Tool | Purpose |
| --- | --- |
| `dts_server_check` | Probe gRPC listener |
| `dts_list_configs` | Saved profile stems |
| `dts_get_config` | One profile JSON |
| `dts_expand_prompt` | Preview **`{a\|b}`** wildcards |
| `dts_generate_image` | Generate PNG(s); paths by default |
| `dts_list_installed_models` | Scan **`Models`** directory |
| `dts_models_search` | Search local index |
| `dts_models_doctor` | Partial downloads, orphans, index mismatches |
| `dts_pipeline_run` | Run pipeline profile (blocks until complete) |
| `dts_pipeline_status` | **`heartbeat.json`** / **`pipeline_run.json`** |
| `dts_generate_cancel` | Cooperative cancel between batch iterations |

**Optional lifecycle tools** (macOS; **`DTS_MCP_ALLOW_SERVER_LIFECYCLE=1`** on the MCP process):

| Tool | Purpose |
| --- | --- |
| `dts_server_status` | LaunchAgent summary + listener probe |
| `dts_server_start` | Bootstrap LaunchAgent job |
| `dts_server_stop` | Boot out job |
| `dts_server_restart` | Restart job (**`ensure_model_browser`** default true) |

**Defaults:** **`localhost:7859`**, **`trust_server_cert=true`** on loopback, profile **`default`**. Errors map to readable tool failures. **`shared_secret`** never logged. **`server install` / `uninstall` not exposed** via MCP.

| Resource URI | Content |
| --- | --- |
| `dts://config/{stem}` | Saved profile JSON |
| `dts://output/{relative_path}` | File under **`./output`** or **`DTS_MCP_OUTPUT_ROOTS`** |
| `dts://pipeline/{run_id}/{step_id}/{filename}` | Pipeline artifact |

Path traversal (`..`) rejected for all resource URIs.

---

## Environment variables

| Variable | Used for |
| --- | --- |
| `DRAW_THINGS_MODEL_PATH` | Default models directory for **`server install`** (**`--model-path`** overrides). Also guesses **`model`** in auto-created **`default.json`**. |
| `DTS_UTILS_DEFAULT_CONFIGURATION` | Shorthand profile when second positional omitted. Set via **`setdefault`** to **`default`** when implicit profile materializes, unless already exported. |
| `DTS_UTILS_DEFAULT_MODEL` | Basename for **`model`** when creating **`default.json`** first time. |
| `DTS_UTILS_DEFAULT_PIPELINE_PROFILE` | Omit **`--profile`** on **`generate`** when set to a pipeline profile name. |
| `DTS_WEB_TOKEN` | Bearer auth on **`/api/*`** except **`GET /api/health`**. |
| `DTS_WEB_LOG_FILE` | Web log path (**`web`** and **`web tail`**). |
| `DTS_WEB_GENERATE_TIMEOUT` | Wall-clock cap (seconds, default **900**) for web generate endpoints. |
| `DTS_UTILS_DEFAULT_FETCH_RECIPE` | Default **`models fetch`** recipe when **`RECIPE_ID`** omitted. |
| `DTS_GRPC_GENERATE_DEBUG` | **`1`** / **`true`** / **`yes`** / **`on`**: one stderr summary line per **`GenerateImage`** stream response. See [PROTOBUF.md § Debugging](PROTOBUF.md#debugging-generateimage-streams). |
| `HF_TOKEN` | Hugging Face token for **`huggingface`** recipe sources (**`uv sync --extra download`**). |

```bash
export DRAW_THINGS_MODEL_PATH=/path/to/your/models
uv run dts-utils server install
```

CLI **`--model-path`** wins when both variable and flag are set.

---

## Exit codes

| Code | Meaning |
| --- | --- |
| **`0`** | Success |
| **`1`** | Runtime error (connection, configuration, RPC, I/O, …) |
| **`2`** | Invalid arguments (e.g. lifecycle verb without **`server`**, shorthand token errors) |

---

## See also

| Document | Contents |
| --- | --- |
| [README.md](README.md) | Install, quickstart, troubleshooting |
| [DRAW-THINGS-GRPC-API.md](DRAW-THINGS-GRPC-API.md) | Upstream gRPC service |
| [PROTOBUF.md](PROTOBUF.md) | Protobuf and FlatBuffer schemas |
| [AGENTS.md](AGENTS.md) | Build, test, and automation conventions |
