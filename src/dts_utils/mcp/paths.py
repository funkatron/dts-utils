"""Path allowlists for MCP resource reads."""

from __future__ import annotations

import os
from pathlib import Path

from dts_utils.configs import configuration_search_directories, resolve_configuration_value
from dts_utils.exceptions import ConfigurationError
from dts_utils.pipeline.run_plan import default_run_root


def _invalid_segment(value: str) -> bool:
    if not value or value in {".", ".."}:
        return True
    return "/" in value or "\\" in value or ".." in value


def normalize_resource_segment(value: str, label: str) -> str:
    segment = value.strip()
    if _invalid_segment(segment):
        raise ConfigurationError(f"Invalid {label}.")
    return segment


def path_within_roots(path: Path, roots: list[Path]) -> Path:
    resolved = path.expanduser().resolve()
    for root in roots:
        root_resolved = root.expanduser().resolve()
        try:
            resolved.relative_to(root_resolved)
            return resolved
        except ValueError:
            continue
    raise ConfigurationError("Resource path is outside allowed directories.")


def output_resource_roots() -> list[Path]:
    env = os.environ.get("DTS_MCP_OUTPUT_ROOTS", "").strip()
    if env:
        return [Path(part.strip()).expanduser() for part in env.split(os.pathsep) if part.strip()]
    cwd = Path.cwd()
    return [cwd / "output", cwd]


def pipeline_resource_roots() -> list[Path]:
    roots = [default_run_root().expanduser()]
    env = os.environ.get("DTS_MCP_PIPELINE_RUN_ROOT", "").strip()
    if env:
        roots.insert(0, Path(env).expanduser())
    return roots


def resolve_config_resource_path(stem: str) -> Path:
    stem_clean = normalize_resource_segment(stem, "profile stem")
    try:
        path = resolve_configuration_value(stem_clean)
    except ValueError as exc:
        raise ConfigurationError(str(exc)) from exc
    if not path.is_file():
        raise ConfigurationError(f"Configuration file not found: {path}")
    roots = [directory.resolve() for directory in configuration_search_directories()]
    return path_within_roots(path, roots)


def resolve_output_resource_path(relative_path: str) -> Path:
    rel = relative_path.strip().replace("\\", "/")
    if rel.startswith("/") or not rel:
        raise ConfigurationError("Invalid output relative_path.")
    parts = Path(rel).parts
    if any(part == ".." for part in parts):
        raise ConfigurationError("Invalid output relative_path.")
    roots = [r.resolve() for r in output_resource_roots()]
    for root in roots:
        candidate = (root / rel).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            continue
        if candidate.is_file():
            return candidate
    raise ConfigurationError(f"Output file not found: {relative_path}")


def resolve_pipeline_resource_path(run_id: str, step_id: str, filename: str) -> Path:
    run_id_clean = normalize_resource_segment(run_id, "run_id")
    step_id_clean = normalize_resource_segment(step_id, "step_id")
    filename_clean = normalize_resource_segment(filename, "filename")
    roots = pipeline_resource_roots()
    for root in roots:
        candidate = root / run_id_clean / step_id_clean / filename_clean
        candidate = path_within_roots(candidate, [root.resolve()])
        if candidate.is_file():
            return candidate
    raise ConfigurationError(
        f"Pipeline artifact not found: {run_id}/{step_id}/{filename}"
    )


def mime_type_for_path(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".png":
        return "image/png"
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".mp4":
        return "video/mp4"
    if suffix == ".mov":
        return "video/quicktime"
    if suffix == ".json":
        return "application/json"
    return "application/octet-stream"
