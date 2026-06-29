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
    ImageGenerationRequestOptions,
    expand_prompt_templates_for_batch,
    generate_png_batch,
)
from dts_utils.generation_session import (
    clear_generation_cancel,
    execute_lock,
    generation_cancel_event,
    request_generation_cancel,
)
from dts_utils.grpc.utils import is_server_running
from dts_utils.image_output import indexed_output_path, unique_ms_timestamp_output_path
from dts_utils.mcp.client_options import build_grpc_client_options, non_loopback_warning
from dts_utils.mcp.errors import raise_tool_error
from dts_utils.mcp.serialize import model_record_to_dict
from dts_utils.model_index.local import (
    doctor_local_models,
    scan_local_models,
    summarize_doctor_counts,
)
from dts_utils.model_index.search import filter_records, load_records, search_records
from dts_utils.models_api import (
    InstalledModelsOptions,
    installed_models_result_to_dict,
    list_installed_models,
    resolve_draw_things_models_dir,
)
from dts_utils.pipeline.profile import is_pipeline_profile
from dts_utils.pipeline.run_plan import (
    PipelineRunRequest,
    default_run_id,
    default_run_root,
    execute_pipeline_run,
)

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

PHASE_2_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "dts_models_search",
        "dts_models_doctor",
        "dts_pipeline_run",
        "dts_pipeline_status",
        "dts_generate_cancel",
    }
)

MCP_TOOL_NAMES: frozenset[str] = PHASE_1_TOOL_NAMES | PHASE_2_TOOL_NAMES

LIFECYCLE_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "dts_server_status",
        "dts_server_start",
        "dts_server_stop",
        "dts_server_restart",
    }
)

_DEFAULT_INDEX_JSON = "drawthings_uncurated_models.json"


def _optional_path(value: str | None) -> Path | None:
    if value is None or not str(value).strip():
        return None
    return Path(value).expanduser()


def _configuration_default() -> str:
    env = os.environ.get(DEFAULT_CONFIGURATION_ENV, "").strip()
    return env or DEFAULT_PROFILE_NAME


def _default_data_dir() -> Path:
    return Path("data")


def _index_json_path(data_dir: Path) -> Path:
    return data_dir / _DEFAULT_INDEX_JSON


def _with_warning(payload: dict[str, Any], host: str) -> dict[str, Any]:
    warning = non_loopback_warning(host)
    if warning:
        payload = dict(payload)
        payload["warning"] = warning
    return payload


def _write_png_batch(images: list[bytes], output_base: Path) -> list[Path]:
    output_base.parent.mkdir(parents=True, exist_ok=True)
    stamped = unique_ms_timestamp_output_path(output_base)
    paths: list[Path] = []
    for index, png in enumerate(images):
        path = indexed_output_path(stamped, index)
        path.write_bytes(png)
        paths.append(path)
    return paths


def read_pipeline_status(run_root: Path, run_id: str) -> dict[str, Any]:
    """Read heartbeat and manifest JSON for a pipeline run directory."""
    run_dir = run_root / run_id
    payload: dict[str, Any] = {
        "run_id": run_id,
        "run_root": str(run_root),
        "run_dir": str(run_dir),
    }
    if not run_dir.exists():
        payload["status"] = "not_found"
        return payload

    heartbeat_path = run_dir / "heartbeat.json"
    if heartbeat_path.is_file():
        try:
            payload["heartbeat"] = json.loads(heartbeat_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            payload["heartbeat_error"] = str(exc)

    manifest_path = run_dir / "pipeline_run.json"
    if manifest_path.is_file():
        try:
            payload["manifest"] = json.loads(manifest_path.read_text(encoding="utf-8"))
            payload["status"] = "completed"
        except json.JSONDecodeError as exc:
            payload["manifest_error"] = str(exc)
            payload["status"] = "manifest_invalid"
    else:
        payload["status"] = "running_or_incomplete"
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
        with execute_lock:
            clear_generation_cancel()
            batch = generate_png_batch(
                client,
                gen,
                generations=generations,
                cancel_event=generation_cancel_event,
            )
        paths = _write_png_batch(batch.images, output_base)
        result: dict[str, Any] = {
            "paths": [str(p) for p in paths],
            "configuration": cfg,
            "generations": generations,
            "expanded_prompts": batch.expanded_prompts,
            "expanded_negative_prompts": batch.expanded_negative_prompts,
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
        payload["models_dir"] = payload.get("model_dir", str(result.models_dir))
        summaries = payload.get("models", [])
        payload["summaries"] = summaries
        return payload
    except Exception as exc:
        raise_tool_error(exc)
        raise AssertionError("raise_tool_error always raises")


def tool_models_search(
    query: str = "",
    data_dir: str | None = None,
    limit: int = 25,
    family: str | None = None,
    model_type: str | None = None,
    author: str | None = None,
    license_name: str | None = None,
) -> dict[str, Any]:
    """Search the local community model index (from ``dts-utils models build``)."""
    try:
        data_path = _optional_path(data_dir) or _default_data_dir()
        index_path = _index_json_path(data_path)
        if not index_path.is_file():
            raise ConfigurationError(
                f"Index not found: {index_path}. Run: dts-utils models build --data-dir {data_path}"
            )
        records = load_records(index_path)
        filtered = filter_records(
            records,
            family=family,
            model_type=model_type,
            author=author,
            license_name=license_name,
        )
        terms = [t for t in query.split() if t.strip()]
        matches = search_records(filtered, terms, limit=limit) if terms else filtered[:limit]
        return {
            "data_dir": str(data_path),
            "index_path": str(index_path),
            "query": query,
            "count": len(matches),
            "results": [model_record_to_dict(record) for record in matches],
        }
    except Exception as exc:
        raise_tool_error(exc)
        raise AssertionError("raise_tool_error always raises")


def tool_models_doctor(
    models_dir: str | None = None,
    data_dir: str | None = None,
    limit: int = 50,
    severity: str = "warning",
) -> dict[str, Any]:
    """Check the local Models directory for partial downloads, orphans, and index mismatches."""
    try:
        model_path = resolve_draw_things_models_dir(models_dir)
        data_path = _optional_path(data_dir) or _default_data_dir()
        local_files = scan_local_models(model_path)
        records = None
        index_path = _index_json_path(data_path)
        if index_path.is_file():
            records = load_records(index_path)
        findings = doctor_local_models(local_files, indexed_records=records)
        if severity != "all":
            findings = [f for f in findings if f.severity == severity]
        if limit > 0:
            findings = findings[:limit]
        counts = summarize_doctor_counts(findings)
        return {
            "models_dir": str(model_path),
            "data_dir": str(data_path),
            "counts": counts,
            "findings": [asdict(f) for f in findings],
        }
    except Exception as exc:
        raise_tool_error(exc)
        raise AssertionError("raise_tool_error always raises")


def tool_pipeline_run(
    profile: str,
    prompt: str,
    negative_prompt: str = "",
    allow_cache: bool = True,
    run_root: str | None = None,
    run_id: str | None = None,
    host: str = "localhost",
    port: int = 7859,
    no_tls: bool = False,
    trust_server_cert: bool = True,
    force_trust_server_cert: bool = False,
    root_cert: str | None = None,
    max_message_mb: int = 64,
    shared_secret: str | None = None,
    user: str = "dts-utils-mcp",
    fps: int | None = None,
    seconds: float | None = None,
    video_width: int | None = None,
    video_height: int | None = None,
) -> dict[str, Any]:
    """Run a pipeline profile (e.g. prompt-to-video); blocks until complete."""
    try:
        profile_stem = profile.strip()
        if not is_pipeline_profile(profile_stem):
            raise ConfigurationError(
                f"Profile {profile_stem!r} is not a pipeline profile (no _dts_utils_pipeline block). "
                "Use dts-utils configs scaffold-pipeline prompt-to-video or pass a pipeline JSON profile."
            )
        client = build_grpc_client_options(
            host=host,
            port=port,
            no_tls=no_tls,
            trust_server_cert=trust_server_cert,
            force_trust_server_cert=force_trust_server_cert,
            root_cert=root_cert,
            max_message_mb=max_message_mb,
        )
        secret = shared_secret.strip() if shared_secret and shared_secret.strip() else None
        request = PipelineRunRequest(
            profile=profile_stem,
            prompt=prompt.strip(),
            negative_prompt=negative_prompt,
            allow_cache=allow_cache,
            run_root=_optional_path(run_root) or default_run_root(),
            run_id=(run_id or "").strip() or default_run_id(),
            host=client.host,
            port=client.port,
            no_tls=client.no_tls,
            trust_server_cert=client.trust_server_cert,
            force_trust_server_cert=client.force_trust_server_cert,
            root_cert=client.root_cert,
            max_message_mb=client.max_message_mb,
            shared_secret=secret,
            user=user,
            fps=fps,
            seconds=seconds,
            video_width=video_width,
            video_height=video_height,
        )
        with execute_lock:
            clear_generation_cancel()
            manifest = execute_pipeline_run(request)
        payload: dict[str, Any] = {
            "run_id": manifest.run_id,
            "run_root": manifest.run_root,
            "profile": profile_stem,
            "artifacts": manifest.artifacts,
            "steps": manifest.steps,
            "pipeline_manifest": str(Path(manifest.run_root) / manifest.run_id / "pipeline_run.json"),
        }
        return _with_warning(payload, host)
    except Exception as exc:
        raise_tool_error(exc)
        raise AssertionError("raise_tool_error always raises")


def tool_pipeline_status(
    run_id: str,
    run_root: str | None = None,
) -> dict[str, Any]:
    """Read heartbeat.json and pipeline_run.json for a pipeline run."""
    try:
        root = _optional_path(run_root) or default_run_root()
        run_id_clean = run_id.strip()
        if not run_id_clean:
            raise ConfigurationError("run_id is required.")
        return read_pipeline_status(root, run_id_clean)
    except Exception as exc:
        raise_tool_error(exc)
        raise AssertionError("raise_tool_error always raises")


def tool_generate_cancel() -> dict[str, Any]:
    """Request cooperative cancel for in-flight MCP or web generation (between batch iterations)."""
    return request_generation_cancel()
