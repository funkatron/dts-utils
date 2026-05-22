"""Local Draw Things model directory scanning and status helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from .parse import ModelRecord


def expected_filenames_from_community_metadata(metadata: dict[str, Any]) -> list[str]:
    """Basenames that must exist under the Draw Things model dir for this preset.

    Uses the same rules as index/status helpers for ``community-models`` ``metadata.json``
    (``file``, encoder/VAE keys, ``additional_clip_encoders``, ``converted`` keys).
    """
    names: list[str] = []
    for key in ("file", "autoencoder", "text_encoder", "clip_encoder", "t5_encoder"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            names.append(Path(value).name)
    additional = metadata.get("additional_clip_encoders")
    if isinstance(additional, list):
        for item in additional:
            if isinstance(item, str) and item.strip():
                names.append(Path(item).name)
    converted = metadata.get("converted")
    if isinstance(converted, dict):
        for key in converted:
            if isinstance(key, str) and key.strip():
                names.append(Path(key).name)
    deduped: list[str] = []
    seen: set[str] = set()
    for name in names:
        if name not in seen:
            seen.add(name)
            deduped.append(name)
    return deduped


def sha256_by_basename_from_community_metadata(metadata: dict[str, Any]) -> dict[str, str]:
    """Map Draw Things basename -> lowercase SHA-256 hex from ``converted``."""
    out: dict[str, str] = {}
    converted = metadata.get("converted")
    if not isinstance(converted, dict):
        return out
    for raw_key, raw_val in converted.items():
        if not isinstance(raw_key, str) or not raw_key.strip():
            continue
        if not isinstance(raw_val, str) or not raw_val.strip():
            continue
        hexval = raw_val.strip().lower()
        if len(hexval) != 64 or any(c not in "0123456789abcdef" for c in hexval):
            continue
        basename = Path(raw_key).name
        out[basename] = hexval
    return out


def default_models_dir() -> Path:
    return Path.home() / "Library/Containers/com.liuliu.draw-things/Data/Documents/Models"


@dataclass(slots=True)
class LocalFileRecord:
    path: Path
    name: str
    size_bytes: int
    modified_time: float
    category: str
    base_name: str


@dataclass(slots=True)
class InstalledModelSummary:
    base_name: str
    category: str
    total_size_bytes: int
    file_count: int
    primary_files: list[str] = field(default_factory=list)
    companion_files: list[str] = field(default_factory=list)
    matched_record_ids: list[str] = field(default_factory=list)


@dataclass(slots=True)
class IndexedModelStatus:
    model_id: str
    name: str
    model_family: str
    status: str
    matched_files: list[str] = field(default_factory=list)
    missing_files: list[str] = field(default_factory=list)
    metadata_path: str | None = None


@dataclass(slots=True)
class DoctorFinding:
    kind: str
    severity: str
    path: str
    message: str


def _normalize_base_name(file_name: str) -> str:
    if file_name.endswith(".part"):
        return file_name[: -len(".part")]
    if file_name.endswith("-tensordata"):
        return file_name[: -len("-tensordata")]
    return file_name


def _categorize_file(file_name: str) -> str:
    lowered = file_name.lower()
    if lowered.endswith(".json"):
        return "config"
    if lowered.endswith(".part"):
        return "partial"
    if lowered.endswith("-tensordata"):
        return "tensor-data"
    if "_lora_" in lowered or lowered.endswith("_lora_f16.ckpt") or lowered.endswith("_lora_q8p.ckpt"):
        return "lora"
    if "_ti_" in lowered or lowered.endswith(".pt_ti_f16.ckpt"):
        return "textual-inversion"
    if "vae" in lowered:
        return "vae"
    if "encoder" in lowered or "clip_vit" in lowered or "open_clip" in lowered or "llama_" in lowered:
        return "encoder"
    if "controlnet" in lowered:
        return "controlnet"
    if lowered.endswith(".ckpt") or lowered.endswith(".safetensors") or lowered.endswith(".pt"):
        return "model"
    return "other"


def scan_local_models(models_dir: Path) -> list[LocalFileRecord]:
    if not models_dir.exists():
        return []
    records: list[LocalFileRecord] = []
    for path in sorted(models_dir.iterdir()):
        if not path.is_file():
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        records.append(
            LocalFileRecord(
                path=path,
                name=path.name,
                size_bytes=stat.st_size,
                modified_time=stat.st_mtime,
                category=_categorize_file(path.name),
                base_name=_normalize_base_name(path.name),
            )
        )
    return records


def _expected_file_names(record: ModelRecord) -> list[str]:
    return expected_filenames_from_community_metadata(record.raw_metadata_json)


def _primary_expected_name(record: ModelRecord) -> str | None:
    payload = record.raw_metadata_json
    value = payload.get("file")
    if isinstance(value, str) and value.strip():
        return Path(value).name
    names = _expected_file_names(record)
    return names[0] if names else None


def summarize_installed_models(
    local_files: list[LocalFileRecord],
    indexed_records: list[ModelRecord] | None = None,
) -> list[InstalledModelSummary]:
    expected_to_ids: dict[str, set[str]] = {}
    if indexed_records:
        for record in indexed_records:
            for name in _expected_file_names(record):
                expected_to_ids.setdefault(name, set()).add(record.id)

    grouped: dict[str, list[LocalFileRecord]] = {}
    for file_record in local_files:
        grouped.setdefault(file_record.base_name, []).append(file_record)

    summaries: list[InstalledModelSummary] = []
    for base_name, files in sorted(grouped.items()):
        total_size = sum(file_record.size_bytes for file_record in files)
        categories = {file_record.category for file_record in files if file_record.category not in {"tensor-data", "partial"}}
        category = sorted(categories)[0] if categories else files[0].category
        primary = [file_record.name for file_record in files if file_record.category not in {"tensor-data", "partial"}]
        companions = [file_record.name for file_record in files if file_record.category in {"tensor-data", "partial"}]
        matched_ids = sorted(expected_to_ids.get(base_name, set()))
        summaries.append(
            InstalledModelSummary(
                base_name=base_name,
                category=category,
                total_size_bytes=total_size,
                file_count=len(files),
                primary_files=sorted(primary),
                companion_files=sorted(companions),
                matched_record_ids=matched_ids,
            )
        )
    return summaries


def compute_index_status(records: list[ModelRecord], local_files: list[LocalFileRecord]) -> list[IndexedModelStatus]:
    local_names = {file_record.name for file_record in local_files}
    statuses: list[IndexedModelStatus] = []
    for record in records:
        expected = _expected_file_names(record)
        if not expected:
            statuses.append(
                IndexedModelStatus(
                    model_id=record.id,
                    name=record.name,
                    model_family=record.model_family,
                    status="unknown",
                    metadata_path=record.metadata_path,
                )
            )
            continue

        primary = _primary_expected_name(record)
        matched = [name for name in expected if name in local_names]
        missing = [name for name in expected if name not in local_names]

        if primary and primary in local_names:
            status = "installed"
        elif matched:
            status = "partial"
        else:
            status = "indexed-not-installed"

        statuses.append(
            IndexedModelStatus(
                model_id=record.id,
                name=record.name,
                model_family=record.model_family,
                status=status,
                matched_files=matched,
                missing_files=missing,
                metadata_path=record.metadata_path,
            )
        )
    return statuses


def doctor_local_models(
    local_files: list[LocalFileRecord],
    indexed_records: list[ModelRecord] | None = None,
) -> list[DoctorFinding]:
    findings: list[DoctorFinding] = []
    local_names = {file_record.name for file_record in local_files}

    for file_record in local_files:
        if file_record.category == "partial":
            findings.append(
                DoctorFinding(
                    kind="partial-download",
                    severity="warning",
                    path=str(file_record.path),
                    message="Partial download file found; install may be incomplete.",
                )
            )
        if file_record.category == "tensor-data":
            base_name = file_record.base_name
            if base_name not in local_names:
                findings.append(
                    DoctorFinding(
                        kind="orphan-tensordata",
                        severity="warning",
                        path=str(file_record.path),
                        message="Tensor data sidecar exists without its base file.",
                    )
                )

    if indexed_records:
        expected_names = {
            name
            for record in indexed_records
            for name in _expected_file_names(record)
        }
        for file_record in local_files:
            if file_record.category in {"config", "partial", "tensor-data", "other"}:
                continue
            if file_record.name not in expected_names:
                findings.append(
                    DoctorFinding(
                        kind="local-untracked",
                        severity="info",
                        path=str(file_record.path),
                        message="Local model file is not mapped to the current indexed model set.",
                    )
                )
    return findings


def _human_size(size_bytes: int) -> str:
    size = float(size_bytes)
    units = ["B", "KB", "MB", "GB", "TB"]
    for unit in units:
        if size < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{int(size_bytes)} B"


def _clip(value: str, width: int) -> str:
    return value if len(value) <= width else f"{value[: width - 1]}…"


def format_installed_summaries(summaries: list[InstalledModelSummary]) -> str:
    if not summaries:
        return "No local model files found."
    rows = []
    for summary in summaries:
        rows.append(
            {
                "base": summary.base_name,
                "category": summary.category,
                "size": _human_size(summary.total_size_bytes),
                "files": str(summary.file_count),
                "matched": ", ".join(summary.matched_record_ids[:2]) if summary.matched_record_ids else "",
            }
        )
    columns = ["base", "category", "size", "files", "matched"]
    widths = {
        column: max(len(column), *(min(len(row[column]), 32) for row in rows))
        for column in columns
    }
    lines = [
        "  ".join(column.upper().ljust(widths[column]) for column in columns),
        "  ".join("-" * widths[column] for column in columns),
    ]
    for row in rows:
        lines.append(
            "  ".join(_clip(row[column], widths[column]).ljust(widths[column]) for column in columns)
        )
    return "\n".join(lines)


def format_index_statuses(statuses: list[IndexedModelStatus], limit: int = 50) -> str:
    if not statuses:
        return "No index status records available."
    sorted_statuses = sorted(
        statuses,
        key=lambda status: (status.status, status.model_family, status.model_id),
    )[:limit]
    rows = []
    for status in sorted_statuses:
        rows.append(
            {
                "id": status.model_id,
                "family": status.model_family,
                "status": status.status,
                "matched": str(len(status.matched_files)),
                "missing": str(len(status.missing_files)),
            }
        )
    columns = ["id", "family", "status", "matched", "missing"]
    widths = {
        column: max(len(column), *(min(len(row[column]), 28) for row in rows))
        for column in columns
    }
    lines = [
        "  ".join(column.upper().ljust(widths[column]) for column in columns),
        "  ".join("-" * widths[column] for column in columns),
    ]
    for row in rows:
        lines.append(
            "  ".join(_clip(row[column], widths[column]).ljust(widths[column]) for column in columns)
        )
    return "\n".join(lines)


def format_doctor_findings(findings: list[DoctorFinding]) -> str:
    if not findings:
        return "No obvious local model issues found."
    lines = []
    for finding in findings:
        lines.append(f"[{finding.severity}] {finding.kind}: {finding.message}")
        lines.append(f"  {finding.path}")
    return "\n".join(lines)


def summarize_status_counts(statuses: Iterable[IndexedModelStatus]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for status in statuses:
        counts[status.status] = counts.get(status.status, 0) + 1
    return counts


def summarize_doctor_counts(findings: Iterable[DoctorFinding]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for finding in findings:
        counts[finding.kind] = counts.get(finding.kind, 0) + 1
    return counts
