# Web HTTP API (`dts-utils web`)

Programmatic access to Draw Things generation over loopback HTTP — same gRPC stack as **`dts-utils generate`** and **`dts-utils-mcp`**.

**Flags and LaunchAgent:** [CLI.md § web](../CLI.md#web-dts-utils-web) · **Browser UI layout:** [web-ui-layout.md](web-ui-layout.md) · **Route handlers:** [`src/dts_utils/web/app.py`](../src/dts_utils/web/app.py)

---

## Quickstart

```bash
uv run dts-utils web
curl -s http://127.0.0.1:1975/api/health
```

With auth (recommended for non-loopback bind):

```bash
export DTS_WEB_TOKEN="$(openssl rand -hex 32)"
uv run dts-utils web --bind 127.0.0.1 --port 1975
curl -s -H "Authorization: Bearer $DTS_WEB_TOKEN" \
  http://127.0.0.1:1975/api/server-status
```

**Default:** bind **`127.0.0.1`**, port **1975**.

### Default ports (`dts-utils`)

| Service | Port | Constant / env |
| --- | --- | --- |
| Draw Things gRPC | **7859** | `gRPCServerCLI` / tool `port` arg |
| **`dts-utils web`** | **1975** | `DEFAULT_WEB_PORT` in `web/defaults.py` |
| **`dts-utils-mcp` HTTP** | **1976** | **`dts-utils-mcp serve`**; **`DEFAULT_MCP_HTTP_PORT`** in `mcp/env.py` |

---

## Authentication

When **`DTS_WEB_TOKEN`** is set, send on all **`/api/*`** routes except health:

```http
Authorization: Bearer <token>
```

| Route | Bearer required? |
| --- | --- |
| **`GET /api/health`** | No |
| All other **`/api/*`** | Yes (when token is set) |

If **`DTS_WEB_TOKEN`** is unset, routes are open. Binding to a non-loopback address without a token prints a stderr warning.

---

## Errors

Failures return JSON:

```json
{"detail": "human-readable message"}
```

| Status | Typical cause |
| --- | --- |
| **400** | Invalid JSON, missing fields, bad wildcards or configuration |
| **401** | Missing or wrong bearer token |
| **404** | History or pipeline artifact not found |
| **499** | Cooperative cancel (`GenerationCancelledError`) |
| **502** | gRPC connection failure, RPC error, or empty generation |
| **504** | **`DTS_WEB_GENERATE_TIMEOUT`** exceeded (default **900** s) |

---

## Shared JSON fields

Used in **`POST /api/generate`**, **`POST /api/generate/stream`**, and pipeline bodies:

| Field | Type | Default | Notes |
| --- | --- | --- | --- |
| **`prompt`** | string | required* | *Or use **`prompts`** array instead |
| **`prompts`** | string[] | — | Length must equal **`generations`** |
| **`negative_prompt`** | string | `""` | |
| **`negative_prompts`** | string[] | — | Same length as **`prompts`** when set |
| **`generations`** | int | `1` | **1–25**; with **`input_images`**, defaults to array length |
| **`input_image`** | string | — | Base64 raster (PNG/JPEG/WebP, …) for img2img or a single pipeline start frame |
| **`input_images`** | string[] | — | Batch img2img only (one generation per image, same **`prompt`**); not allowed with pipeline **`profile`** |
| **`configuration`** | string | `"default"` | Saved profile stem (single-image generation) |
| **`profile`** | string | — | Pipeline profile name (e.g. **`prompt-to-video`**) |
| **`host`** | string | `"localhost"` | gRPC host |
| **`port`** | int | `7859` | gRPC port |
| **`no_tls`** | bool | `false` | Plaintext gRPC |
| **`trust_server_cert`** | bool | `true` | Trust presented cert on loopback |
| **`force_trust_server_cert`** | bool | `false` | Trust any host (MITM risk) |
| **`root_cert`** | string | — | Path to pinned PEM |
| **`shared_secret`** | string | — | gRPC shared secret |
| **`config_dir`** | string | — | Override saved-config directory |
| **`allow_cache`** | bool | `true` | Pipeline only |

Non-loopback **`host`** without **`root_cert`**, **`force_trust_server_cert`**, or **`no_tls`** returns **400**.

---

## Routes

### `GET /api/health`

Liveness and log file hints. No auth.

```json
{
  "ok": true,
  "log_file": "/Users/…/.config/dts-utils/web.log",
  "tail_cli": "uv run dts-utils web tail"
}
```

---

### `GET /api/server-status`

Probe whether **`gRPCServerCLI`** accepts connections (same idea as **`dts-utils server check`**). Does not guarantee generation succeeds.

**Query parameters:** **`host`**, **`port`**, **`no_tls`** (`true` / `1` / `yes`)

```json
{
  "listener_ok": true,
  "host": "localhost",
  "port": 7859,
  "no_tls": false,
  "probe": "tls_then_plaintext",
  "message": "Listener OK (probe only — generation may still fail)."
}
```

---

### `GET /api/configs`

List saved generation profile stems.

```json
{
  "names": ["default", "prompt-to-video"],
  "default_profile": "default",
  "config_dir": "/Users/…/.config/dts-utils/configurations",
  "pipeline_profiles": ["prompt-to-video"],
  "video_profiles": ["prompt-to-video"]
}
```

---

### `GET /api/prompt/expand`

Returns a self-describing schema for the POST body (no generation).

### `POST /api/prompt/expand`

Expand **`{a|b}`** prompt wildcards without calling gRPC. Each expansion is an independent random roll.

**Request:**

```json
{
  "prompt": "{sunset|sunrise} over mountains",
  "negative_prompt": "",
  "count": 3
}
```

**Response:**

```json
{
  "prompts": ["sunset over mountains"],
  "negative_prompts": [""]
}
```

---

### `POST /api/generate`

Single-shot image generation. Returns **`multipart/mixed`** with one PNG part per image.

**Request (minimal):**

```json
{
  "prompt": "a red cube on gray",
  "configuration": "default",
  "generations": 1
}
```

**Response headers:**

| Header | Meaning |
| --- | --- |
| **`X-Generated-Count`** | Number of PNG parts |
| **`X-Generation-Runs`** | Batch size requested |
| **`X-Expanded-Wildcards-B64`** | Optional base64 JSON of expanded prompts |

**Body:** PNG parts (not JSON).

---

### `POST /api/generate/stream`

Server-Sent Events (**`Content-Type: text/event-stream`**). Each event is one line:

```text
data: {"type":"meta",…}

```

Preferred for agents and UIs that want live previews.

**Image generation:** same JSON body as **`POST /api/generate`**.

**Pipeline:** set **`profile`** (not **`configuration`**). **`prompt`** is always required (including when **`input_image`** supplies a start frame):

```json
{
  "profile": "prompt-to-video",
  "prompt": "calm lake at dawn",
  "input_image": "<optional base64 start frame>"
}
```

**Limits:** SSE queue holds up to **64** events; slow clients block the producer. Wall-clock cap: **`DTS_WEB_GENERATE_TIMEOUT`** (default **900** s) between batch runs, not mid-RPC.

#### SSE events — image generation

| `type` | Fields (highlights) |
| --- | --- |
| **`meta`** | **`total_runs`** |
| **`progress`** | **`run`**, **`total_runs`** |
| **`preview`** | **`run`**, **`seq`**, **`png_b64`** — live preview frame |
| **`image`** | **`run`**, **`index`**, **`png_b64`** — final PNG for that run |
| **`done`** | **`expanded_prompts`**, **`expanded_negative_prompts`**, **`total_images`** |
| **`error`** | **`detail`** — no **`done`** after **`error`** |

#### SSE events — pipeline (`profile` in body)

| `type` | Fields (highlights) |
| --- | --- |
| **`meta`** | **`profile`**, **`run_id`**, **`total_steps`** |
| **`progress`** | Heartbeat payload from **`heartbeat.json`** (step, status, …) |
| **`artifact`** | **`kind`**, **`step_id`**, **`url`**, **`filename`** |
| **`done`** | **`run_id`**, **`run_root`**, **`profile`**, **`artifacts`** |
| **`error`** | **`detail`** |

Decode **`png_b64`** with standard base64 when handling **`preview`** or **`image`** events.

---

### `POST /api/generate/cancel`

Request cooperative cancel for in-flight generate or pipeline work. Cancel applies **between** batch iterations, not mid-RPC.

**Response:**

```json
{"ok": true, "cancel_requested": true}
```

In-flight multipart generation may return **499**; streams emit an SSE **`error`** event.

---

### `POST /api/pipeline/run/stream`

Backward-compatible alias for prompt-to-video via **`POST /api/generate/stream`** with a **`profile`** field.

---

### `GET /api/pipeline/artifact/{run_id}/{step_id}/{filename}`

Download a pipeline artifact (PNG or MP4). Path traversal (**`..`**, **`/`** in filename) is rejected.

**Example:** `/api/pipeline/artifact/my-run-id/t2i/generated.png`

---

### History (browser UI storage)

| Method | Path | Purpose |
| --- | --- | --- |
| **GET** | **`/api/history`** | List saved UI history items |
| **POST** | **`/api/history`** | Store prompt + PNG bytes from the client |
| **DELETE** | **`/api/history`** | Clear all history |
| **GET** | **`/history/{item_id}/{filename}`** | Serve a stored PNG (no bearer check on this route) |

Override storage with **`DTS_WEB_HISTORY_DIR`**.

---

## Agent / LLM workflow

Typical tool sequence for a remote orchestrator wrapping this API:

1. **`GET /api/server-status`** — fail fast if gRPC is down
2. **`GET /api/configs`** — pick a profile stem
3. **`POST /api/generate/stream`** — stream **`preview`** / **`image`** / **`done`**
4. **`POST /api/generate/cancel`** — if the user stops a long batch

Optional: **`POST /api/prompt/expand`** before generate to preview **`{a|b}`** wildcards.

**Example:**

```bash
export TOKEN="your-dts-web-token"
BASE="http://127.0.0.1:1975"

curl -s -H "Authorization: Bearer $TOKEN" "$BASE/api/server-status"
curl -s -H "Authorization: Bearer $TOKEN" "$BASE/api/configs"

curl -N -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"a man throwing a bowling ball","configuration":"default"}' \
  "$BASE/api/generate/stream"
```

For remote access, use a private network, set **`DTS_WEB_TOKEN`**, and avoid exposing generation to the public internet.

---

## Not on the web API (MCP or CLI today)

| Capability | Where |
| --- | --- |
| List installed model files | MCP **`dts_list_installed_models`** |
| Community index search | MCP **`dts_models_search`** / **`dts-utils models search`** |
| Model doctor | MCP **`dts_models_doctor`** / **`dts-utils models doctor`** |
| Read one profile JSON | MCP **`dts_get_config`** / disk / **`dts://config/{stem}`** |
| LaunchAgent start/stop | CLI **`dts-utils server …`** or gated MCP lifecycle tools |
| Download weights | CLI **`dts-utils models fetch`** |

---

## Environment variables

| Variable | Purpose |
| --- | --- |
| **`DTS_WEB_TOKEN`** | Bearer token for **`/api/*`** (except health) |
| **`DTS_WEB_GENERATE_TIMEOUT`** | Wall-clock cap in seconds (default **900**) |
| **`DTS_WEB_LOG_FILE`** | Web log path (**`web tail`** reads this) |
| **`DTS_WEB_HISTORY_DIR`** | Override history storage directory |
| **`DTS_WEB_PIPELINE_RUN_ROOT`** | Pipeline run root for web artifact URLs |

---

## See also

| Document | Contents |
| --- | --- |
| [CLI.md § web](../CLI.md#web-dts-utils-web) | Serve flags, LaunchAgent, summary table |
| [mcp-for-agents.md](mcp-for-agents.md) | MCP tools when the host speaks stdio MCP |
| [DRAW-THINGS-GRPC-API.md](../DRAW-THINGS-GRPC-API.md) | Upstream gRPC service |
