# MCP tools reference (generated)

Do not edit by hand. Regenerate:

```bash
uv run python scripts/generate_docs.py
```

Narrative guide: [mcp-for-agents.md](../mcp-for-agents.md). Operator setup: [CLI.md § MCP](../CLI.md#mcp-dts-utils-mcp).

## `dts_expand_prompt`

Expand ``{a|b}`` prompt wildcards (independent random picks per count).

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `count` | integer | no | (default: `1`) |
| `negative_prompt` | string | no | (default: ``) |
| `prompt` | string | yes |  |

## `dts_generate_cancel`

Request cooperative cancel for in-flight MCP or web generation (between batch iterations).

_No parameters._

## `dts_generate_image`

Generate image(s) via gRPC; returns paths (and optional base64 PNG data).

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `config_dir` | string / null | no |  |
| `configuration` | string / null | no |  |
| `force_trust_server_cert` | boolean | no | (default: `False`) |
| `generations` | integer | no | (default: `1`) |
| `host` | string | no | (default: `localhost`) |
| `include_image_data` | boolean | no | (default: `False`) |
| `input_image_path` | string / null | no |  |
| `input_image_paths` | array / null | no |  |
| `max_message_mb` | integer | no | (default: `64`) |
| `negative_prompt` | string | no | (default: ``) |
| `no_tls` | boolean | no | (default: `False`) |
| `output` | string | no | (default: `output/generated.png`) |
| `port` | integer | no | (default: `7859`) |
| `prompt` | string | yes |  |
| `root_cert` | string / null | no |  |
| `shared_secret` | string / null | no |  |
| `trust_server_cert` | boolean | no | (default: `True`) |
| `user` | string | no | (default: `dts-utils-mcp`) |

## `dts_get_config`

Return stem, resolved path, and parsed JSON for one saved profile.

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `config_dir` | string / null | no |  |
| `configuration` | string | yes |  |

## `dts_list_configs`

List saved generation profile stems (no ``.json`` suffix).

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `config_dir` | string / null | no |  |

## `dts_list_installed_models`

List model files under the Draw Things Models directory.

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `limit` | integer / null | no |  |
| `models_dir` | string / null | no |  |
| `use_index` | boolean | no | (default: `True`) |

## `dts_models_doctor`

Check the local Models directory for partial downloads, orphans, and index mismatches.

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `data_dir` | string / null | no |  |
| `limit` | integer | no | (default: `50`) |
| `models_dir` | string / null | no |  |
| `severity` | string | no | (default: `warning`) |

## `dts_models_search`

Search the local community model index (from ``dts-utils models build``).

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `author` | string / null | no |  |
| `data_dir` | string / null | no |  |
| `family` | string / null | no |  |
| `license_name` | string / null | no |  |
| `limit` | integer | no | (default: `25`) |
| `model_type` | string / null | no |  |
| `query` | string | no | (default: ``) |

## `dts_pipeline_run`

Run a pipeline profile (e.g. prompt-to-video); blocks until complete.

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `allow_cache` | boolean | no | (default: `True`) |
| `force_trust_server_cert` | boolean | no | (default: `False`) |
| `fps` | integer / null | no |  |
| `host` | string | no | (default: `localhost`) |
| `input_image_path` | string / null | no |  |
| `max_message_mb` | integer | no | (default: `64`) |
| `negative_prompt` | string | no | (default: ``) |
| `no_tls` | boolean | no | (default: `False`) |
| `port` | integer | no | (default: `7859`) |
| `profile` | string | yes |  |
| `prompt` | string | no | (default: ``) |
| `root_cert` | string / null | no |  |
| `run_id` | string / null | no |  |
| `run_root` | string / null | no |  |
| `seconds` | number / null | no |  |
| `shared_secret` | string / null | no |  |
| `trust_server_cert` | boolean | no | (default: `True`) |
| `user` | string | no | (default: `dts-utils-mcp`) |
| `video_height` | integer / null | no |  |
| `video_width` | integer / null | no |  |

## `dts_pipeline_status`

Read heartbeat.json and pipeline_run.json for a pipeline run.

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `run_id` | string | yes |  |
| `run_root` | string / null | no |  |

## `dts_server_check`

Probe whether Draw Things gRPCServerCLI accepts connections on host:port.

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `host` | string | no | (default: `localhost`) |
| `no_tls` | boolean | no | (default: `False`) |
| `port` | integer | no | (default: `7859`) |
