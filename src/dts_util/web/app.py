"""Starlette application: health, server probe, config list, generate."""

from __future__ import annotations

import asyncio
import base64
import functools
import json
import os
import queue
import secrets
import threading
from pathlib import Path

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.routing import Route
from starlette.templating import Jinja2Templates

from dts_util.configs import (
    DEFAULT_PROFILE_NAME,
    configurations_dir,
    ensure_default_generation_json_config,
    list_configuration_names,
)
from dts_util.exceptions import (
    ChannelSetupError,
    ConfigurationError,
    GenerationCancelledError,
    GenerationEmptyError,
    GenerationRpcError,
)
from dts_util.generate_api import (
    GeneratePngBatchResult,
    GrpcClientOptions,
    ImageGenerationRequestOptions,
    coerce_generations_json,
    expand_prompt_templates_for_batch,
    generate_png_batch,
    iter_generate_stream_dicts,
)
from dts_util.grpc.connection import is_loopback_host
from dts_util.grpc.utils import is_server_running

_templates_dir = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(_templates_dir))

_execute_lock = threading.Lock()
_generation_cancel_event = threading.Event()

_DEFAULT_GENERATE_TIMEOUT = 900.0
_ENV_GENERATE_TIMEOUT = "DTS_WEB_GENERATE_TIMEOUT"
_ENV_WEB_TOKEN = "DTS_WEB_TOKEN"

# Bound SSE chunks waiting on a slow client (producer blocks on put when full).
_GENERATE_STREAM_QUEUE_MAXSIZE = 64

# Some proxies cap individual header values; omit expanded-prompt metadata when larger.
_MAX_EXPANDED_WILDCARDS_B64_LEN = 6000


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
    return JSONResponse({"detail": str(exc)}, status_code=500)


async def health(_: Request) -> JSONResponse:
    return JSONResponse({"ok": True})


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
    ensure_default_generation_json_config()
    directory = configurations_dir()
    names = list_configuration_names(directory)
    return JSONResponse({"names": names, "default_profile": DEFAULT_PROFILE_NAME, "config_dir": str(directory)})


async def index(request: Request) -> Response:
    api_token = _auth_token()
    return templates.TemplateResponse(
        request,
        "index.html.j2",
        {
            "api_token": api_token,
        },
    )


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
    with _execute_lock:
        _generation_cancel_event.clear()
        return generate_png_batch(
            client,
            gen,
            generations=generations,
            cancel_event=_generation_cancel_event,
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
    _generation_cancel_event.set()
    return JSONResponse({"ok": True, "cancel_requested": True})


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
        with _execute_lock:
            _generation_cancel_event.clear()
            try:
                for evt in iter_generate_stream_dicts(
                    client,
                    gen,
                    generations=generation_runs,
                    cancel_event=_generation_cancel_event,
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
                _generation_cancel_event.set()
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


def create_app() -> Starlette:
    routes: list[Route] = [
        Route("/", index),
        Route("/api/health", health, methods=["GET"]),
        Route("/api/server-status", server_status, methods=["GET"]),
        Route("/api/configs", api_configs, methods=["GET"]),
        Route("/api/prompt/expand", api_prompt_expand, methods=["GET", "POST"]),
        Route("/api/generate/cancel", api_generate_cancel, methods=["POST"]),
        Route("/api/generate/stream", api_generate_stream, methods=["POST"]),
        Route("/api/generate", api_generate, methods=["POST"]),
    ]
    return Starlette(routes=routes)
