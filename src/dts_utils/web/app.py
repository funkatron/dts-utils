"""Starlette application: health, server probe, config list, generate."""

from __future__ import annotations

import asyncio
import base64
import functools
import json
import os
import queue
import secrets
import shutil
import threading
import time
from pathlib import Path

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, HTMLResponse, JSONResponse, Response, StreamingResponse
from starlette.routing import Route
from starlette.templating import Jinja2Templates

from dts_utils.configs import (
    DEFAULT_PROFILE_NAME,
    configurations_dir,
    ensure_default_generation_json_config,
    list_configuration_names,
    user_config_dir,
)
from dts_utils.web.log_io import web_log_info
from dts_utils.exceptions import (
    ChannelSetupError,
    ConfigurationError,
    GenerationCancelledError,
    GenerationEmptyError,
    GenerationRpcError,
)
from dts_utils.generate_api import (
    GeneratePngBatchResult,
    GrpcClientOptions,
    ImageGenerationRequestOptions,
    coerce_generations_json,
    expand_prompt_templates_for_batch,
    generate_png_batch,
    iter_generate_stream_dicts,
)
from dts_utils.grpc.connection import is_loopback_host
from dts_utils.grpc.utils import is_server_running
from dts_utils.pipeline.profile import is_pipeline_profile
from dts_utils.pipeline.run_plan import (
    PipelineRunRequest,
    build_pipeline_steps,
    default_run_root,
    prepare_pipeline_run,
    validate_pipeline_run,
)
from dts_utils.pipeline.runner import PipelineRunner

_templates_dir = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(_templates_dir))

_DEFAULT_GENERATE_TIMEOUT = 900.0

from dts_utils.generation_session import (
    clear_generation_cancel,
    execute_lock,
    generation_cancel_event,
    request_generation_cancel,
)
_ENV_GENERATE_TIMEOUT = "DTS_WEB_GENERATE_TIMEOUT"
_ENV_WEB_TOKEN = "DTS_WEB_TOKEN"
_ENV_HISTORY_DIR = "DTS_WEB_HISTORY_DIR"
_ENV_PIPELINE_RUN_ROOT = "DTS_WEB_PIPELINE_RUN_ROOT"

# Bound SSE chunks waiting on a slow client (producer blocks on put when full).
_GENERATE_STREAM_QUEUE_MAXSIZE = 64

# Some proxies cap individual header values; omit expanded-prompt metadata when larger.
_MAX_EXPANDED_WILDCARDS_B64_LEN = 6000
_HISTORY_MAX_ITEMS = 30
_HISTORY_INDEX = "index.json"
_UI_PIPELINE_PROFILES_FALLBACK = (
    "sdxl-turbo",
    "z-image-turbo-1.0-exact",
    "ltx-2.3-22b-distilled-exact",
)


def _pipeline_profile_names_for_ui() -> list[str]:
    try:
        from dts_utils.pipeline.profile import list_pipeline_profile_names

        names = list_pipeline_profile_names()
        if names:
            return names
    except OSError:
        pass
    return list(_UI_PIPELINE_PROFILES_FALLBACK)


def _expanded_wildcards_b64(prompts: list[str], negatives: list[str]) -> str | None:
    raw = json.dumps(
        {"prompts": prompts, "negative_prompts": negatives},
        ensure_ascii=False,
    ).encode("utf-8")
    b64 = base64.standard_b64encode(raw).decode("ascii")
    if len(b64) > _MAX_EXPANDED_WILDCARDS_B64_LEN:
        return None
    return b64


def _generate_timeout_seconds() -> float:
    raw = os.environ.get(_ENV_GENERATE_TIMEOUT, "").strip()
    if not raw:
        return _DEFAULT_GENERATE_TIMEOUT
    try:
        return float(raw)
    except ValueError:
        return _DEFAULT_GENERATE_TIMEOUT


def _auth_token() -> str | None:
    tok = os.environ.get(_ENV_WEB_TOKEN, "").strip()
    return tok or None


def _require_bearer(request: Request) -> JSONResponse | None:
    expected = _auth_token()
    if not expected:
        return None
    auth = request.headers.get("authorization", "")
    if auth != f"Bearer {expected}":
        return JSONResponse({"detail": "Unauthorized. Set Authorization: Bearer to match DTS_WEB_TOKEN."}, status_code=401)
    return None


def _history_dir() -> Path:
    override = os.environ.get(_ENV_HISTORY_DIR, "").strip()
    if override:
        return Path(override).expanduser()
    return user_config_dir() / "web-history"


def _history_index_path() -> Path:
    return _history_dir() / _HISTORY_INDEX


def _empty_history_state() -> dict[str, object]:
    return {"version": 1, "items": []}


def _load_history_state() -> dict[str, object]:
    path = _history_index_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return _empty_history_state()
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        return _empty_history_state()
    return data


def _save_history_state(state: dict[str, object]) -> None:
    directory = _history_dir()
    directory.mkdir(parents=True, exist_ok=True)
    _history_index_path().write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _safe_history_id(raw: str) -> bool:
    return bool(raw) and all(ch.isalnum() or ch in {"-", "_"} for ch in raw)


def _coerce_history_generations(value: object) -> int | None:
    try:
        n = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if n < 1 or n > 25:
        return None
    return n


def _coerce_history_images(images_raw: object) -> list[bytes] | JSONResponse:
    if not isinstance(images_raw, list):
        return JSONResponse({"detail": "images must be an array of PNG base64 strings."}, status_code=400)
    if len(images_raw) > 25:
        return JSONResponse({"detail": "images cannot contain more than 25 entries."}, status_code=400)
    images: list[bytes] = []
    for i, image_raw in enumerate(images_raw):
        if not isinstance(image_raw, str):
            return JSONResponse({"detail": f"images[{i}] must be a base64 string."}, status_code=400)
        try:
            png = base64.b64decode(image_raw, validate=True)
        except ValueError:
            return JSONResponse({"detail": f"images[{i}] is not valid base64."}, status_code=400)
        if not png.startswith(b"\x89PNG\r\n\x1a\n"):
            return JSONResponse({"detail": f"images[{i}] is not a PNG."}, status_code=400)
        images.append(png)
    return images


def _history_public_item(entry: dict[str, object]) -> dict[str, object]:
    item_id = str(entry.get("id") or "")
    images = entry.get("images") if isinstance(entry.get("images"), list) else []
    out = dict(entry)
    out["images"] = [
        {
            "url": f"/history/{item_id}/{str(name)}",
            "download": str(name),
        }
        for name in images
        if isinstance(name, str)
    ]
    return out


def _cleanup_history_files(items: list[object]) -> None:
    keep_ids = {str(item.get("id")) for item in items if isinstance(item, dict) and item.get("id")}
    directory = _history_dir()
    if not directory.is_dir():
        return
    for child in directory.iterdir():
        if child.name == _HISTORY_INDEX:
            continue
        if child.is_dir() and child.name not in keep_ids:
            shutil.rmtree(child, ignore_errors=True)


def _multipart_png_response(
    images: list[bytes],
    *,
    generation_runs: int = 1,
    expanded_prompts: list[str] | None = None,
    expanded_negative_prompts: list[str] | None = None,
) -> Response:
    boundary = f"dtsweb{secrets.token_hex(12)}"
    chunks: list[bytes] = []
    for i, png in enumerate(images):
        chunks.append(f"--{boundary}\r\n".encode("ascii"))
        chunks.append(
            f"Content-Type: image/png\r\n"
            f'Content-Disposition: inline; filename="generated_{i}.png"\r\n\r\n'.encode("ascii")
        )
        chunks.append(png)
        chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode("ascii"))
    body = b"".join(chunks)
    hdrs: dict[str, str] = {
        "X-Generated-Count": str(len(images)),
        "X-Generation-Runs": str(generation_runs),
    }
    if expanded_prompts is not None and expanded_negative_prompts is not None:
        b64 = _expanded_wildcards_b64(expanded_prompts, expanded_negative_prompts)
        if b64 is not None:
            hdrs["X-Expanded-Wildcards-B64"] = b64
    return Response(
        body,
        media_type=f"multipart/mixed; boundary={boundary}",
        headers=hdrs,
    )


def _map_exc(exc: Exception) -> JSONResponse:
    if isinstance(exc, ConfigurationError):
        return JSONResponse({"detail": str(exc)}, status_code=400)
    if isinstance(exc, ChannelSetupError):
        return JSONResponse({"detail": str(exc)}, status_code=502)
    if isinstance(exc, GenerationRpcError):
        return JSONResponse({"detail": str(exc)}, status_code=502)
    if isinstance(exc, GenerationEmptyError):
        return JSONResponse({"detail": str(exc)}, status_code=502)
    if isinstance(exc, GenerationCancelledError):
        return JSONResponse({"detail": str(exc)}, status_code=499)
    if isinstance(exc, RuntimeError):
        return JSONResponse({"detail": str(exc)}, status_code=502)
    return JSONResponse({"detail": str(exc)}, status_code=500)


def _pipeline_run_root() -> Path:
    raw = os.environ.get(_ENV_PIPELINE_RUN_ROOT, "").strip()
    if raw:
        return Path(raw).expanduser()
    return default_run_root()


def _parse_pipeline_payload(body: object) -> tuple[dict[str, object], JSONResponse | None]:
    if not isinstance(body, dict):
        return {}, JSONResponse({"detail": "Expected JSON object"}, status_code=400)
    profile = body.get("profile")
    if not isinstance(profile, str) or not profile.strip():
        return {}, JSONResponse({"detail": "Field 'profile' is required (prompt-to-video profile name)."}, status_code=400)
    prompt = body.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        return {}, JSONResponse({"detail": "Field 'prompt' is required (non-empty string)."}, status_code=400)
    return body, None


def _build_pipeline_run_request(data: dict[str, object]) -> tuple[PipelineRunRequest, JSONResponse | None]:
    profile = str(data["profile"]).strip()
    if not is_pipeline_profile(profile):
        return PipelineRunRequest(profile=profile, prompt=""), JSONResponse(
            {
                "detail": (
                    f"Profile {profile!r} is not a prompt-to-video profile "
                    "(missing _dts_utils_pipeline in saved JSON). "
                    "Run: dts-utils configs scaffold-pipeline prompt-to-video — "
                    "or use a single-image profile with configuration instead of profile."
                )
            },
            status_code=400,
        )

    client, err = _build_client_options(data)
    if err:
        return PipelineRunRequest(profile=profile, prompt=""), err

    neg = data.get("negative_prompt")
    negative_prompt = str(neg).strip() if isinstance(neg, str) else ""
    shared = data.get("shared_secret")
    shared_secret = str(shared).strip() if isinstance(shared, str) and shared.strip() else None

    return (
        PipelineRunRequest(
            profile=profile,
            prompt=str(data["prompt"]).strip(),
            run_root=_pipeline_run_root(),
            allow_cache=bool(data.get("allow_cache", True)),
            negative_prompt=negative_prompt,
            host=client.host,
            port=client.port,
            no_tls=client.no_tls,
            trust_server_cert=client.trust_server_cert,
            force_trust_server_cert=client.force_trust_server_cert,
            root_cert=client.root_cert,
            max_message_mb=client.max_message_mb,
            shared_secret=shared_secret,
            user=str(data.get("user", "dts-utils-web")),
        ),
        None,
    )


def _pipeline_artifact_url(run_id: str, step_id: str, filename: str) -> str:
    from urllib.parse import quote

    return (
        f"/api/pipeline/artifact/{quote(run_id, safe='')}/"
        f"{quote(step_id, safe='')}/{quote(filename, safe='')}"
    )


def _manifest_artifact_events(manifest: object) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for artifact in manifest.artifacts:
        step_id = str(artifact.get("created_by_step", "artifact"))
        path = Path(str(artifact.get("path", "")))
        if not path.is_file():
            continue
        filename = path.name
        kind = artifact.get("kind", "image")
        events.append(
            {
                "type": "artifact",
                "kind": kind,
                "step_id": step_id,
                "filename": filename,
                "url": _pipeline_artifact_url(manifest.run_id, step_id, filename),
                "path": str(path),
            }
        )
    return events


async def health(_: Request) -> JSONResponse:
    return JSONResponse({"ok": True, **web_log_info()})


async def server_status(request: Request) -> JSONResponse:
    if err := _require_bearer(request):
        return err
    host = request.query_params.get("host") or "localhost"
    try:
        port = int(request.query_params.get("port") or "7859")
    except ValueError:
        return JSONResponse({"detail": "Invalid port"}, status_code=400)
    no_tls = request.query_params.get("no_tls", "false").lower() in {"1", "true", "yes"}

    listener_ok = is_server_running(host, port, prefer_plaintext=no_tls)
    probe = "plaintext_only" if no_tls else "tls_then_plaintext"
    return JSONResponse(
        {
            "listener_ok": listener_ok,
            "host": host,
            "port": port,
            "no_tls": no_tls,
            "probe": probe,
            "message": ("Listener OK (probe only — generation may still fail)." if listener_ok else "Unreachable."),
        }
    )


async def api_configs(request: Request) -> JSONResponse:
    if err := _require_bearer(request):
        return err
    try:
        ensure_default_generation_json_config()
        directory = configurations_dir()
        names = list_configuration_names(directory)
    except OSError as exc:
        return JSONResponse(
            {"detail": f"Cannot read or create saved JSON configs directory: {exc}"},
            status_code=500,
        )
    return JSONResponse(
        {
            "names": names,
            "default_profile": DEFAULT_PROFILE_NAME,
            "config_dir": str(directory),
            "pipeline_profiles": _pipeline_profile_names_for_ui(),
            "video_profiles": _pipeline_profile_names_for_ui(),
        }
    )


async def index(request: Request) -> Response:
    api_token = _auth_token()
    # Serve HTML via Jinja render + HTMLResponse (not Jinja2Templates.TemplateResponse).
    # Starlette's internal _TemplateResponse does ``if "http.response.debug" in extensions``
    # after ``extensions = request.get("extensions", {})``; if the ASGI scope sets the
    # ``extensions`` key to ``None``, ``.get`` returns ``None`` and membership raises → HTTP 500.
    html = templates.get_template("index.html.j2").render(
        {"request": request, "api_token": api_token},
    )
    return HTMLResponse(html)


def _parse_generate_payload(body: object) -> tuple[dict[str, object], JSONResponse | None]:
    if not isinstance(body, dict):
        return {}, JSONResponse({"detail": "Expected JSON object"}, status_code=400)
    data = body
    prompts = data.get("prompts")
    prompt = data.get("prompt")
    if prompts is not None:
        if not isinstance(prompts, list):
            return {}, JSONResponse({"detail": "'prompts' must be an array of strings."}, status_code=400)
    elif not isinstance(prompt, str) or not prompt.strip():
        return {}, JSONResponse(
            {"detail": "Field 'prompt' is required (non-empty string), or send 'prompts' array."},
            status_code=400,
        )
    return data, None


def _coerce_prompt_arrays(
    data: dict[str, object],
    generation_runs: int,
) -> tuple[list[str] | None, list[str] | None, JSONResponse | None]:
    """If body contains ``prompts``, validate length and entries; optional ``negative_prompts`` same length."""
    raw = data.get("prompts")
    if raw is None:
        return None, None, None
    if not isinstance(raw, list):
        return None, None, JSONResponse({"detail": "'prompts' must be an array."}, status_code=400)
    if len(raw) != generation_runs:
        return None, None, JSONResponse(
            {
                "detail": (
                    f"'prompts' length ({len(raw)}) must equal generations ({generation_runs})."
                )
            },
            status_code=400,
        )
    out_p: list[str] = []
    for i, p in enumerate(raw):
        if not isinstance(p, str) or not p.strip():
            return None, None, JSONResponse(
                {"detail": f"prompts[{i}] must be a non-empty string."},
                status_code=400,
            )
        out_p.append(p.strip())

    neg_multi = data.get("negative_prompts")
    neg_out: list[str] | None = None
    if neg_multi is not None:
        if not isinstance(neg_multi, list):
            return None, None, JSONResponse(
                {"detail": "'negative_prompts' must be an array."},
                status_code=400,
            )
        if len(neg_multi) != generation_runs:
            return None, None, JSONResponse(
                {
                    "detail": (
                        f"'negative_prompts' length ({len(neg_multi)}) must equal "
                        f"generations ({generation_runs})."
                    )
                },
                status_code=400,
            )
        neg_out = [str(x).strip() if isinstance(x, str) else "" for x in neg_multi]

    return out_p, neg_out, None


def _parse_expand_payload(body: object) -> tuple[str, str, int, JSONResponse | None]:
    if not isinstance(body, dict):
        return "", "", 1, JSONResponse({"detail": "Expected JSON object"}, status_code=400)
    prompt = body.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        return "", "", 1, JSONResponse(
            {"detail": "Field 'prompt' is required (non-empty string)."},
            status_code=400,
        )
    neg_raw = body.get("negative_prompt")
    negative_prompt = str(neg_raw).strip() if isinstance(neg_raw, str) else ""
    try:
        count = coerce_generations_json(body.get("count"))
    except ConfigurationError as e:
        return "", "", 1, JSONResponse({"detail": str(e)}, status_code=400)
    return prompt.strip(), negative_prompt, count, None


def _build_client_options(data: dict[str, object]) -> tuple[GrpcClientOptions, JSONResponse | None]:
    host = data.get("host") if isinstance(data.get("host"), str) else "localhost"
    port_raw = data.get("port", 7859)
    try:
        port = int(port_raw) if port_raw is not None else 7859
    except (TypeError, ValueError):
        return GrpcClientOptions(), JSONResponse({"detail": "Invalid port"}, status_code=400)

    no_tls = bool(data.get("no_tls"))
    trust_server_cert = bool(data.get("trust_server_cert", True))
    force_trust_server_cert = bool(data.get("force_trust_server_cert"))
    root_cert_raw = data.get("root_cert")
    root_cert: Path | None = None
    if isinstance(root_cert_raw, str) and root_cert_raw.strip():
        root_cert = Path(root_cert_raw).expanduser()

    if (
        not is_loopback_host(host)
        and not no_tls
        and trust_server_cert
        and not force_trust_server_cert
        and not root_cert
    ):
        return GrpcClientOptions(), JSONResponse(
            {
                "detail": "For non-loopback hosts, set root_cert or force_trust_server_cert, "
                "or disable TLS with no_tls if the server uses plaintext.",
            },
            status_code=400,
        )

    opts = GrpcClientOptions(
        host=host,
        port=port,
        no_tls=no_tls,
        root_cert=root_cert,
        trust_server_cert=trust_server_cert,
        force_trust_server_cert=force_trust_server_cert,
    )
    return opts, None


def _build_generation_options(
    data: dict[str, object],
    *,
    prompts_per_run: list[str] | None = None,
) -> tuple[ImageGenerationRequestOptions, JSONResponse | None]:
    if prompts_per_run is not None:
        prompt = prompts_per_run[0]
    else:
        prompt = str(data["prompt"]).strip()
    neg = data.get("negative_prompt")
    negative_prompt = str(neg).strip() if isinstance(neg, str) else ""

    configuration = data.get("configuration")
    if configuration is not None and not isinstance(configuration, str):
        return ImageGenerationRequestOptions(prompt=prompt), JSONResponse({"detail": "configuration must be a string"}, status_code=400)
    configuration = configuration.strip() if isinstance(configuration, str) else None
    if not configuration:
        configuration = DEFAULT_PROFILE_NAME

    shared = data.get("shared_secret")
    shared_secret = str(shared).strip() if isinstance(shared, str) and shared.strip() else None

    config_dir_raw = data.get("config_dir")
    config_dir: Path | None = None
    if isinstance(config_dir_raw, str) and config_dir_raw.strip():
        config_dir = Path(config_dir_raw).expanduser()

    gen = ImageGenerationRequestOptions(
        prompt=prompt,
        negative_prompt=negative_prompt,
        configuration=configuration,
        shared_secret=shared_secret,
        config_dir=config_dir,
    )
    return gen, None


def _run_generate(
    client: GrpcClientOptions,
    gen: ImageGenerationRequestOptions,
    generations: int = 1,
    *,
    prompts_per_run: list[str] | None = None,
    negative_prompts_per_run: list[str] | None = None,
) -> GeneratePngBatchResult:
    with execute_lock:
        clear_generation_cancel()
        return generate_png_batch(
            client,
            gen,
            generations=generations,
            cancel_event=generation_cancel_event,
            prompts_per_run=prompts_per_run,
            negative_prompts_per_run=negative_prompts_per_run,
        )


async def api_prompt_expand(request: Request) -> JSONResponse:
    """Expand `{…}` prompt templates without generating images.

    Each returned expansion applies one random pass through the template—the same wildcard logic
    used when sending a single generate request. Multiple expansions are independent rolls; they
    are not seeded to match your next batch."""
    if err := _require_bearer(request):
        return err
    if request.method == "GET":
        return JSONResponse(
            {
                "endpoint": "/api/prompt/expand",
                "method": "POST",
                "content_type": "application/json",
                "body": {
                    "prompt": "required — template string with optional `{a|b}` wildcards",
                    "negative_prompt": "optional string",
                    "count": "optional — number of independent expansions (1–25, default 1)",
                },
                "response_shape": {"prompts": ["…"], "negative_prompts": ["…"]},
            }
        )
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"detail": "Invalid JSON"}, status_code=400)

    prompt, negative_prompt, count, err = _parse_expand_payload(body)
    if err:
        return err

    try:
        prompts_out, negatives_out = expand_prompt_templates_for_batch(
            prompt,
            negative_prompt,
            count=count,
        )
    except ConfigurationError as e:
        return JSONResponse({"detail": str(e)}, status_code=400)

    return JSONResponse({"prompts": prompts_out, "negative_prompts": negatives_out})


async def api_generate_cancel(request: Request) -> JSONResponse:
    """Signal cooperative cancel for the generation worker (between batch iterations)."""
    if err := _require_bearer(request):
        return err
    return JSONResponse(request_generation_cancel())


async def api_history(request: Request) -> JSONResponse:
    if err := _require_bearer(request):
        return err
    if request.method == "GET":
        state = _load_history_state()
        items = state.get("items") if isinstance(state.get("items"), list) else []
        return JSONResponse({"version": 1, "items": [_history_public_item(item) for item in items if isinstance(item, dict)]})

    if request.method == "DELETE":
        shutil.rmtree(_history_dir(), ignore_errors=True)
        return JSONResponse(_empty_history_state())

    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"detail": "Invalid JSON"}, status_code=400)
    if not isinstance(body, dict):
        return JSONResponse({"detail": "Expected JSON object"}, status_code=400)

    prompt = body.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        return JSONResponse({"detail": "prompt is required."}, status_code=400)
    images = _coerce_history_images(body.get("images"))
    if isinstance(images, JSONResponse):
        return images

    item_id = secrets.token_urlsafe(12).replace("-", "_")
    item_dir = _history_dir() / item_id
    item_dir.mkdir(parents=True, exist_ok=True)
    image_names: list[str] = []
    for i, png in enumerate(images, start=1):
        name = f"generated-{i}.png"
        (item_dir / name).write_bytes(png)
        image_names.append(name)

    entry: dict[str, object] = {
        "id": item_id,
        "ts": int(body.get("ts")) if isinstance(body.get("ts"), int) else int(time.time() * 1000),
        "prompt": prompt.strip()[:4000],
        "images": image_names,
        "image_count": len(image_names),
    }
    negative_prompt = body.get("negative_prompt")
    if isinstance(negative_prompt, str) and negative_prompt.strip():
        entry["negative_prompt"] = negative_prompt.strip()[:4000]
    generations = _coerce_history_generations(body.get("generations"))
    if generations is not None:
        entry["generations"] = generations

    configuration = body.get("configuration")
    if isinstance(configuration, str):
        ctrim = configuration.strip()
        if ctrim:
            entry["configuration"] = ctrim[:4096]

    state = _load_history_state()
    items = state.get("items") if isinstance(state.get("items"), list) else []
    items.insert(0, entry)
    del items[_HISTORY_MAX_ITEMS:]
    state = {"version": 1, "items": items}
    _save_history_state(state)
    _cleanup_history_files(items)
    return JSONResponse(_history_public_item(entry), status_code=201)


async def history_image(request: Request) -> Response:
    item_id = request.path_params.get("item_id", "")
    filename = request.path_params.get("filename", "")
    if not _safe_history_id(item_id) or filename.startswith(".") or "/" in filename or "\\" in filename:
        return JSONResponse({"detail": "Not found"}, status_code=404)
    path = _history_dir() / item_id / filename
    if not path.is_file() or path.suffix.lower() != ".png":
        return JSONResponse({"detail": "Not found"}, status_code=404)
    return FileResponse(path, media_type="image/png", filename=filename)


def _generate_stream_exception_payload(exc: BaseException) -> dict[str, object]:
    """Single SSE JSON payload for failures during streaming generation."""
    if isinstance(exc, ConfigurationError):
        return {"type": "error", "detail": str(exc)}
    if isinstance(exc, ChannelSetupError):
        return {"type": "error", "detail": str(exc)}
    if isinstance(exc, GenerationRpcError):
        return {"type": "error", "detail": str(exc)}
    if isinstance(exc, GenerationEmptyError):
        return {"type": "error", "detail": str(exc)}
    if isinstance(exc, GenerationCancelledError):
        return {"type": "error", "detail": str(exc)}
    return {"type": "error", "detail": str(exc)}


async def api_generate_stream(request: Request) -> StreamingResponse | JSONResponse:
    if err := _require_bearer(request):
        return err
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"detail": "Invalid JSON"}, status_code=400)

    if isinstance(body, dict):
        profile_raw = body.get("profile")
        if isinstance(profile_raw, str) and profile_raw.strip():
            profile_name = profile_raw.strip()
            if is_pipeline_profile(profile_name):
                data, err = _parse_pipeline_payload(body)
                if err:
                    return err
                run_request, err = _build_pipeline_run_request(data)
                if err:
                    return err
                return _streaming_prompt_to_video_response(run_request)
            return JSONResponse(
                {
                    "detail": (
                        f"Profile {profile_name!r} is not a prompt-to-video profile "
                        "(missing _dts_utils_pipeline in saved JSON). "
                        "For single-image generation use field 'configuration' instead of 'profile', "
                        "or run: dts-utils configs scaffold-pipeline prompt-to-video"
                    )
                },
                status_code=400,
            )

    data, err = _parse_generate_payload(body)
    if err:
        return err

    client, err = _build_client_options(data)
    if err:
        return err

    try:
        generation_runs = coerce_generations_json(data.get("generations"))
    except ConfigurationError as e:
        return JSONResponse({"detail": str(e)}, status_code=400)

    prompts_per_run, negative_prompts_per_run, err = _coerce_prompt_arrays(data, generation_runs)
    if err:
        return err

    gen, err = _build_generation_options(data, prompts_per_run=prompts_per_run)
    if err:
        return err

    loop = asyncio.get_running_loop()
    q: queue.Queue[str | None] = queue.Queue(maxsize=_GENERATE_STREAM_QUEUE_MAXSIZE)
    timeout_sec = _generate_timeout_seconds()

    def worker() -> None:
        with execute_lock:
            clear_generation_cancel()
            try:
                for evt in iter_generate_stream_dicts(
                    client,
                    gen,
                    generations=generation_runs,
                    cancel_event=generation_cancel_event,
                    prompts_per_run=prompts_per_run,
                    negative_prompts_per_run=negative_prompts_per_run,
                ):
                    q.put(json.dumps(evt, ensure_ascii=False))
            except BaseException as exc:
                q.put(json.dumps(_generate_stream_exception_payload(exc), ensure_ascii=False))
            finally:
                q.put(None)

    threading.Thread(target=worker, daemon=True).start()

    async def event_iter():
        deadline = loop.time() + timeout_sec
        timed_out = False
        try:
            while True:
                remaining = deadline - loop.time()
                if remaining <= 0:
                    timed_out = True
                    break
                try:
                    line = await asyncio.wait_for(
                        loop.run_in_executor(None, q.get),
                        timeout=remaining,
                    )
                except TimeoutError:
                    timed_out = True
                    break
                if line is None:
                    break
                yield f"data: {line}\n\n"
            if timed_out:
                generation_cancel_event.set()
                err_line = json.dumps(
                    {"type": "error", "detail": "Generation timed out."},
                    ensure_ascii=False,
                )
                yield f"data: {err_line}\n\n"
        finally:
            if timed_out:
                while True:
                    line = await loop.run_in_executor(None, q.get)
                    if line is None:
                        break

    return StreamingResponse(
        event_iter(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def api_generate(request: Request) -> Response:
    if err := _require_bearer(request):
        return err
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"detail": "Invalid JSON"}, status_code=400)

    data, err = _parse_generate_payload(body)
    if err:
        return err

    client, err = _build_client_options(data)
    if err:
        return err

    try:
        generation_runs = coerce_generations_json(data.get("generations"))
    except ConfigurationError as e:
        return JSONResponse({"detail": str(e)}, status_code=400)

    prompts_per_run, negative_prompts_per_run, err = _coerce_prompt_arrays(data, generation_runs)
    if err:
        return err

    gen, err = _build_generation_options(data, prompts_per_run=prompts_per_run)
    if err:
        return err

    run_batch = functools.partial(
        _run_generate,
        client,
        gen,
        generation_runs,
        prompts_per_run=prompts_per_run,
        negative_prompts_per_run=negative_prompts_per_run,
    )
    timeout = _generate_timeout_seconds()
    try:
        batch = await asyncio.wait_for(asyncio.to_thread(run_batch), timeout=timeout)
    except TimeoutError:
        return JSONResponse({"detail": "Generation timed out."}, status_code=504)
    except ConfigurationError as e:
        return _map_exc(e)
    except ChannelSetupError as e:
        return _map_exc(e)
    except GenerationRpcError as e:
        return _map_exc(e)
    except GenerationCancelledError as e:
        return _map_exc(e)
    except GenerationEmptyError as e:
        return _map_exc(e)
    except Exception as e:
        return _map_exc(e)

    return _multipart_png_response(
        batch.images,
        generation_runs=generation_runs,
        expanded_prompts=batch.expanded_prompts,
        expanded_negative_prompts=batch.expanded_negative_prompts,
    )


def _streaming_prompt_to_video_response(run_request: PipelineRunRequest) -> StreamingResponse:
    loop = asyncio.get_running_loop()
    q: queue.Queue[str | None] = queue.Queue(maxsize=_GENERATE_STREAM_QUEUE_MAXSIZE)
    timeout_sec = _generate_timeout_seconds()
    run_root = _pipeline_run_root()

    def worker() -> None:
        with execute_lock:
            clear_generation_cancel()
            heartbeat_path: Path | None = None
            try:
                ns, profile_settings = prepare_pipeline_run(run_request)
                validate_pipeline_run(ns, profile_settings)
                run_id = str(ns.run_id)
                heartbeat_path = run_root / run_id / "heartbeat.json"
                steps = build_pipeline_steps(ns, profile_settings)
                q.put(
                    json.dumps(
                        {
                            "type": "meta",
                            "profile": run_request.profile,
                            "run_id": run_id,
                            "total_steps": len(steps),
                        },
                        ensure_ascii=False,
                    )
                )

                runner = PipelineRunner(
                    run_root,
                    allow_cache=run_request.allow_cache,
                    max_oom_retries=max(0, int(run_request.max_oom_retries or 1)),
                )
                last_progress = ""
                stop_poll = threading.Event()

                def poll_heartbeat() -> None:
                    nonlocal last_progress
                    while not stop_poll.is_set():
                        if heartbeat_path.is_file():
                            try:
                                payload = json.loads(heartbeat_path.read_text(encoding="utf-8"))
                                msg = (
                                    f"Step {payload.get('step_id', '?')} "
                                    f"({int(payload.get('step_index', 0)) + 1}/"
                                    f"{payload.get('total_steps', '?')}) — "
                                    f"{payload.get('status', '')}"
                                )
                                if msg != last_progress:
                                    last_progress = msg
                                    q.put(
                                        json.dumps(
                                            {"type": "progress", "message": msg, **payload},
                                            ensure_ascii=False,
                                        )
                                    )
                            except (OSError, json.JSONDecodeError):
                                pass
                        stop_poll.wait(1.0)

                poll_thread = threading.Thread(target=poll_heartbeat, daemon=True)
                poll_thread.start()
                try:
                    manifest = runner.run(run_id=run_id, steps=steps)
                finally:
                    stop_poll.set()
                    poll_thread.join(timeout=2.0)

                for evt in _manifest_artifact_events(manifest):
                    q.put(json.dumps(evt, ensure_ascii=False))
                q.put(
                    json.dumps(
                        {
                            "type": "done",
                            "run_id": manifest.run_id,
                            "run_root": manifest.run_root,
                            "profile": run_request.profile,
                            "artifacts": manifest.artifacts,
                        },
                        ensure_ascii=False,
                    )
                )
            except BaseException as exc:
                q.put(json.dumps(_generate_stream_exception_payload(exc), ensure_ascii=False))
            finally:
                q.put(None)

    threading.Thread(target=worker, daemon=True).start()

    async def event_iter():
        deadline = loop.time() + timeout_sec
        timed_out = False
        try:
            while True:
                remaining = deadline - loop.time()
                if remaining <= 0:
                    timed_out = True
                    break
                try:
                    line = await asyncio.wait_for(loop.run_in_executor(None, q.get), timeout=remaining)
                except TimeoutError:
                    timed_out = True
                    break
                if line is None:
                    break
                yield f"data: {line}\n\n"
            if timed_out:
                generation_cancel_event.set()
                err_line = json.dumps(
                    {"type": "error", "detail": "Prompt-to-video timed out."},
                    ensure_ascii=False,
                )
                yield f"data: {err_line}\n\n"
        finally:
            if timed_out:
                while True:
                    line = await loop.run_in_executor(None, q.get)
                    if line is None:
                        break

    return StreamingResponse(
        event_iter(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def api_pipeline_run_stream(request: Request) -> StreamingResponse | JSONResponse:
    """Backward-compatible alias for prompt-to-video via ``POST /api/generate/stream``."""
    if err := _require_bearer(request):
        return err
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"detail": "Invalid JSON"}, status_code=400)

    data, err = _parse_pipeline_payload(body)
    if err:
        return err

    run_request, err = _build_pipeline_run_request(data)
    if err:
        return err

    return _streaming_prompt_to_video_response(run_request)


async def api_pipeline_artifact(request: Request) -> Response:
    if err := _require_bearer(request):
        return err
    run_id = request.path_params.get("run_id", "")
    step_id = request.path_params.get("step_id", "")
    filename = request.path_params.get("filename", "")
    if not run_id or not step_id or not filename:
        return JSONResponse({"detail": "Missing path segments."}, status_code=400)
    if ".." in run_id or ".." in step_id or ".." in filename or "/" in filename:
        return JSONResponse({"detail": "Invalid path."}, status_code=400)

    run_root = _pipeline_run_root().resolve()
    artifact_path = (run_root / run_id / step_id / filename).resolve()
    allowed_root = (run_root / run_id).resolve()
    if not str(artifact_path).startswith(str(allowed_root)) or not artifact_path.is_file():
        return JSONResponse({"detail": "Not found"}, status_code=404)

    media = "video/mp4" if filename.lower().endswith(".mp4") else "image/png"
    return FileResponse(artifact_path, media_type=media, filename=filename)


def create_app() -> Starlette:
    routes: list[Route] = [
        Route("/", index),
        Route("/api/health", health, methods=["GET"]),
        Route("/api/server-status", server_status, methods=["GET"]),
        Route("/api/configs", api_configs, methods=["GET"]),
        Route("/api/history", api_history, methods=["GET", "POST", "DELETE"]),
        Route("/api/prompt/expand", api_prompt_expand, methods=["GET", "POST"]),
        Route("/api/generate/cancel", api_generate_cancel, methods=["POST"]),
        Route("/api/generate/stream", api_generate_stream, methods=["POST"]),
        Route("/api/generate", api_generate, methods=["POST"]),
        Route("/api/pipeline/run/stream", api_pipeline_run_stream, methods=["POST"]),
        Route(
            "/api/pipeline/artifact/{run_id:str}/{step_id:str}/{filename:str}",
            api_pipeline_artifact,
            methods=["GET"],
        ),
        Route("/history/{item_id:str}/{filename:str}", history_image, methods=["GET"]),
    ]
    return Starlette(routes=routes)
