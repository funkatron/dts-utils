"""Programmatic API for listing locally installed Draw Things model files."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from dts_utils.model_index.local import (
    InstalledModelSummary,
    default_models_dir,
    scan_local_models,
    summarize_installed_models,
)
from dts_utils.model_index.parse import ModelRecord
from dts_utils.model_index.search import load_records

_DEFAULT_DATA_DIR = Path("data")
_INDEX_JSON_NAME = "drawthings_uncurated_models.json"


def resolve_draw_things_models_dir(models_dir: Path | str | None = None) -> Path:
    """Return the Draw Things ``Models`` directory (``DRAW_THINGS_MODEL_PATH`` or macOS default)."""
    if models_dir is not None:
        return Path(models_dir).expanduser()
    configured = os.environ.get("DRAW_THINGS_MODEL_PATH")
    if configured:
        return Path(configured).expanduser()
    return default_models_dir()


@dataclass(frozen=True)
class InstalledModelsOptions:
    """Options for :func:`list_installed_models`."""

    models_dir: Path | str | None = None
    data_dir: Path | str | None = None
    limit: int | None = None
    use_index: bool = True
    sort_by_size: bool = True


@dataclass(frozen=True)
class InstalledModelsResult:
    """Scan result: directory path, raw file count, and grouped summaries."""

    models_dir: Path
    local_file_count: int
    summaries: list[InstalledModelSummary]


def _index_json_path(data_dir: Path) -> Path:
    return data_dir / _INDEX_JSON_NAME


def _try_load_index_records(data_dir: Path) -> list[ModelRecord] | None:
    json_path = _index_json_path(data_dir)
    if not json_path.exists():
        return None
    try:
        return load_records(json_path)
    except Exception:
        return None


def list_installed_models(options: InstalledModelsOptions | None = None) -> InstalledModelsResult:
    """List model files installed under the Draw Things ``Models`` directory.

    Scans the local folder and groups related files (checkpoints, tensor sidecars, etc.).
    When ``use_index`` is true and ``data/drawthings_uncurated_models.json`` exists
    (from ``dts-utils models build``), summaries include ``matched_record_ids`` from the
    community catalog. Missing or unreadable index data is ignored.
    """
    opts = options or InstalledModelsOptions()
    models_dir = resolve_draw_things_models_dir(opts.models_dir)
    local_files = scan_local_models(models_dir)

    indexed_records = None
    if opts.use_index:
        data_dir = Path(opts.data_dir).expanduser() if opts.data_dir is not None else _DEFAULT_DATA_DIR
        indexed_records = _try_load_index_records(data_dir)

    summaries = summarize_installed_models(local_files, indexed_records=indexed_records)
    if opts.sort_by_size:
        summaries = sorted(
            summaries,
            key=lambda summary: (summary.total_size_bytes, summary.base_name.lower()),
            reverse=True,
        )
    if opts.limit is not None:
        summaries = summaries[: opts.limit]

    return InstalledModelsResult(
        models_dir=models_dir,
        local_file_count=len(local_files),
        summaries=summaries,
    )


def list_installed_model_filenames(models_dir: Path | str | None = None) -> list[str]:
    """Return basenames of every file in the Draw Things ``Models`` directory."""
    resolved = resolve_draw_things_models_dir(models_dir)
    return [file_record.name for file_record in scan_local_models(resolved)]


def installed_models_result_to_dict(result: InstalledModelsResult) -> dict[str, Any]:
    """JSON-serializable view of :class:`InstalledModelsResult`."""
    return {
        "model_dir": str(result.models_dir),
        "local_file_count": result.local_file_count,
        "models": [asdict(summary) for summary in result.summaries],
    }
