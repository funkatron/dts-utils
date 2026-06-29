"""MCP tool implementations (thin wrappers over ``dts_utils`` APIs)."""

from __future__ import annotations

import base64
import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

from dts_utils.configs import (
    DEFAULT_CONFIGURATION_ENV,
    DEFAULT_PROFILE_NAME,
    configurations_dir,
    list_configuration_names,
    resolve_configuration_value,
)
from dts_utils.exceptions import ConfigurationError
from dts_utils.generate_api import (
    GrpcClientOptions,
    ImageGenerationRequestOptions,
    expand_prompt_templates_for_batch,
    generate_to_paths,
)
from dts_utils.grpc.utils import is_server_running
from dts_utils.mcp.client_options import build_grpc_client_options, non_loopback_warning
from dts_utils.mcp.errors import raise_tool_error
from dts_utils.models_api import InstalledModelsOptions, installed_models_result_to_dict, list_installed_models

PHASE_1_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "dts_server_check",
        "dts_list_configs",
        "dts_get_config",
        "dts_expand_prompt",
        "dts_generate_image",
        "dts_list_installed_models",
    }
)


def _optional_path(value: str | None) -> Path | None:
    if value is None or not str(value).strip():
        return None
    return Path(value).expanduser()


def _configuration_default() -> str:
    env = os.environ.get(DEFAULT_CONFIGURATION_ENV, "").strip()
    return env or DEFAULT_PROFILE_NAME


def _with_warning(payload: dict[str, Any], host: str) -> dict[str, Any]:
    warning = non_loopback_warning(host)
    if warning:
        payload = dict(payload)
        payload["warning"] = warning
    return payload


def tool_server_check(
    host: str = "localhost",
    port: int = 7859,
    no_tls: bool = False,
) -> dict[str, Any]:
    """Probe whether Draw Things gRPCServerCLI accepts connections on host:port."""
    try:
        running = is_server_running(
            host=host,
            port=port,
            prefer_plaintext=no_tls,
        )
        return _with_warning({"running": running, "host": host, "port": port, "no_tls": no_tls}, host)
    except Exception as exc:
        raise_tool_error(exc)
        raise AssertionError("raise_tool_error always raises")


def tool_list_configs(config_dir: str | None = None) -> dict[str, Any]:
    """List saved generation profile stems (no ``.json`` suffix)."""
    try:
        cfg_dir = _optional_path(config_dir)
        names = list_configuration_names(cfg_dir)
        directory = str(cfg_dir if cfg_dir is not None else configurations_dir())
        return {"configs": names, "config_dir": directory}
    except Exception as exc:
        raise_tool_error(exc)
        raise AssertionError("raise_tool_error always raises")


def tool_get_config(configuration: str, config_dir: str | None = None) -> dict[str, Any]:
    """Return stem, resolved path, and parsed JSON for one saved profile."""
    try:
        cfg_dir = _optional_path(config_dir)
        path = resolve_configuration_value(configuration, cfg_dir)
        if not path.exists():
            raise ConfigurationError(f"Configuration file not found: {path}")
        text = path.read_text(encoding="utf-8")
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            raise ConfigurationError(f"Configuration JSON must be an object: {path}")
        stem = path.stem
        return {"stem": stem, "path": str(path), "json": parsed}
    except json.JSONDecodeError as exc:
        raise_tool_error(ConfigurationError(f"Invalid JSON in configuration: {exc}"))
        raise AssertionError("raise_tool_error always raises")
    except Exception as exc:
        raise_tool_error(exc)
        raise AssertionError("raise_tool_error always raises")


def tool_expand_prompt(
    prompt: str,
    negative_prompt: str = "",
    count: int = 1,
) -> dict[str, Any]:
    """Expand ``{a|b}`` prompt wildcards (independent random picks per count)."""
    try:
        prompts, negatives = expand_prompt_templates_for_batch(
            prompt,
            negative_prompt,
            count=count,
        )
        return {"prompts": prompts, "negative_prompts": negatives}
    except Exception as exc:
        raise_tool_error(exc)
        raise AssertionError("raise_tool_error always raises")


def tool_generate_image(
    prompt: str,
    configuration: str | None = None,
    negative_prompt: str = "",
    host: str = "localhost",
    port: int = 7859,
    no_tls: bool = False,
    trust_server_cert: bool = True,
    force_trust_server_cert: bool = False,
    root_cert: str | None = None,
    max_message_mb: int = 64,
    shared_secret: str | None = None,
    generations: int = 1,
    output: str = "output/generated.png",
    include_image_data: bool = False,
    config_dir: str | None = None,
    user: str = "dts-utils-mcp",
) -> dict[str, Any]:
    """Generate image(s) via gRPC; returns paths (and optional base64 PNG data)."""
    try:
        client = build_grpc_client_options(
            host=host,
            port=port,
            no_tls=no_tls,
            trust_server_cert=trust_server_cert,
            force_trust_server_cert=force_trust_server_cert,
            root_cert=root_cert,
            max_message_mb=max_message_mb,
        )
        cfg = (configuration or "").strip() or _configuration_default()
        cfg_dir = _optional_path(config_dir)
        secret = shared_secret.strip() if shared_secret and shared_secret.strip() else None
        gen = ImageGenerationRequestOptions(
            prompt=prompt,
            negative_prompt=negative_prompt,
            configuration=cfg,
            shared_secret=secret,
            config_dir=cfg_dir,
            user=user,
        )
        output_base = Path(output).expanduser()
        paths = generate_to_paths(client, gen, output_base, generations=generations)
        result: dict[str, Any] = {
            "paths": [str(p) for p in paths],
            "configuration": cfg,
            "generations": generations,
        }
        if include_image_data:
            result["images_base64"] = [base64.b64encode(p.read_bytes()).decode("ascii") for p in paths]
        return _with_warning(result, host)
    except Exception as exc:
        raise_tool_error(exc)
        raise AssertionError("raise_tool_error always raises")


def tool_list_installed_models(
    models_dir: str | None = None,
    limit: int | None = None,
    use_index: bool = True,
) -> dict[str, Any]:
    """List model files under the Draw Things Models directory."""
    try:
        opts = InstalledModelsOptions(
            models_dir=models_dir,
            limit=limit,
            use_index=use_index,
        )
        result = list_installed_models(opts)
        payload = installed_models_result_to_dict(result)
        # Normalize key for tool consumers (models_api uses model_dir).
        payload["models_dir"] = payload.get("model_dir", str(result.models_dir))
        summaries = payload.get("models", [])
        payload["summaries"] = summaries
        return payload
    except Exception as exc:
        raise_tool_error(exc)
        raise AssertionError("raise_tool_error always raises")
