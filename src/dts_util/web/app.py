"""Starlette application: health, server probe, config list, generate."""

from __future__ import annotations

import json
import os
import secrets
import threading
from pathlib import Path

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
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
    GrpcClientOptions,
    ImageGenerationRequestOptions,
    coerce_generations_json,
    generate_png_bytes,
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


def _multipart_png_response(images: list[bytes], *, generation_runs: int = 1) -> Response:
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
    return Response(
        body,
        media_type=f"multipart/mixed; boundary={boundary}",
        headers={
            "X-Generated-Count": str(len(images)),
            "X-Generation-Runs": str(generation_runs),
        },
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
    prompt = data.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        return {}, JSONResponse({"detail": "Field 'prompt' is required (non-empty string)."}, status_code=400)
    return data, None


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


def _build_generation_options(data: dict[str, object]) -> tuple[ImageGenerationRequestOptions, JSONResponse | None]:
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


def _run_generate(client: GrpcClientOptions, gen: ImageGenerationRequestOptions, generations: int = 1) -> list[bytes]:
    with _execute_lock:
        _generation_cancel_event.clear()
        return generate_png_bytes(client, gen, generations=generations, cancel_event=_generation_cancel_event)


async def api_generate_cancel(request: Request) -> JSONResponse:
    """Signal cooperative cancel for the generation worker (between batch iterations)."""
    if err := _require_bearer(request):
        return err
    _generation_cancel_event.set()
    return JSONResponse({"ok": True, "cancel_requested": True})


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

    gen, err = _build_generation_options(data)
    if err:
        return err

    try:
        generation_runs = coerce_generations_json(data.get("generations"))
    except ConfigurationError as e:
        return JSONResponse({"detail": str(e)}, status_code=400)

    import asyncio

    timeout = _generate_timeout_seconds()
    try:
        images = await asyncio.wait_for(
            asyncio.to_thread(_run_generate, client, gen, generation_runs),
            timeout=timeout,
        )
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

    return _multipart_png_response(images, generation_runs=generation_runs)


def create_app() -> Starlette:
    routes: list[Route] = [
        Route("/", index),
        Route("/api/health", health, methods=["GET"]),
        Route("/api/server-status", server_status, methods=["GET"]),
        Route("/api/configs", api_configs, methods=["GET"]),
        Route("/api/generate/cancel", api_generate_cancel, methods=["POST"]),
        Route("/api/generate", api_generate, methods=["POST"]),
    ]
    return Starlette(routes=routes)
