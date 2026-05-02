"""Search and pretty-print helpers for the local model index."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from typing import Callable

from .parse import ModelRecord


def load_records(path: Path) -> list[ModelRecord]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Expected a JSON array in {path}")
    records: list[ModelRecord] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        records.append(
            ModelRecord(
                id=str(item.get("id", "")),
                name=str(item.get("name", "")),
                type=item.get("type"),
                model_family=str(item.get("model_family", "other / unknown")),
                source_url=item.get("source_url"),
                huggingface_repo_id=item.get("huggingface_repo_id"),
                download_url=item.get("download_url"),
                author=item.get("author"),
                license=item.get("license"),
                tags=list(item.get("tags", [])),
                sha256=item.get("sha256"),
                metadata_path=item.get("metadata_path"),
                raw_metadata_json=dict(item.get("raw_metadata_json", {})),
                likes=item.get("likes"),
                downloads=item.get("downloads"),
                last_modified=item.get("last_modified"),
                sibling_file_names=list(item.get("sibling_file_names", [])),
                readme_excerpt=item.get("readme_excerpt"),
                suggested_config=dict(item.get("suggested_config", {})),
                warnings=list(item.get("warnings", [])),
            )
        )
    return records


def filter_records(
    records: list[ModelRecord],
    family: str | None = None,
    model_type: str | None = None,
    author: str | None = None,
    license_name: str | None = None,
    has_source: bool = False,
    has_hf: bool = False,
    has_license: bool = False,
    has_downloads: bool = False,
    has_warnings: bool = False,
) -> list[ModelRecord]:
    filtered = records
    checks: list[Callable[[ModelRecord], bool]] = []

    if family:
        wanted = family.lower()
        checks.append(lambda record: record.model_family.lower() == wanted)
    if model_type:
        wanted_type = model_type.lower()
        checks.append(lambda record: (record.type or "").lower() == wanted_type)
    if author:
        wanted_author = author.lower()
        checks.append(lambda record: wanted_author in (record.author or "").lower())
    if license_name:
        wanted_license = license_name.lower()
        checks.append(lambda record: wanted_license in (record.license or "").lower())
    if has_source:
        checks.append(lambda record: bool(record.source_url))
    if has_hf:
        checks.append(lambda record: bool(record.huggingface_repo_id))
    if has_license:
        checks.append(lambda record: bool(record.license))
    if has_downloads:
        checks.append(lambda record: record.downloads is not None)
    if has_warnings:
        checks.append(lambda record: bool(record.warnings))

    for check in checks:
        filtered = [record for record in filtered if check(record)]
    return filtered


def search_records(records: list[ModelRecord], terms: list[str], limit: int = 25) -> list[ModelRecord]:
    lowered_terms = [term.lower() for term in terms if term.strip()]
    scored: list[tuple[int, int, str, ModelRecord]] = []
    for record in records:
        haystacks = {
            "id": record.id.lower(),
            "name": record.name.lower(),
            "family": record.model_family.lower(),
            "type": (record.type or "").lower(),
            "author": (record.author or "").lower(),
            "tags": " ".join(tag.lower() for tag in record.tags),
        }
        score = 0
        matched_all = True
        for term in lowered_terms:
            term_score = 0
            if term in haystacks["id"]:
                term_score += 5
            if term in haystacks["name"]:
                term_score += 4
            if term in haystacks["family"]:
                term_score += 3
            if term in haystacks["type"]:
                term_score += 2
            if term in haystacks["author"]:
                term_score += 1
            if term in haystacks["tags"]:
                term_score += 2
            if term_score == 0:
                matched_all = False
                break
            score += term_score
        if matched_all or not lowered_terms:
            downloads = record.downloads or -1
            scored.append((score, downloads, record.name.lower(), record))

    scored.sort(key=lambda item: (-item[0], -item[1], item[2]))
    return [item[3] for item in scored[:limit]]


def _clip(value: str, width: int) -> str:
    if len(value) <= width:
        return value
    if width <= 1:
        return value[:width]
    return f"{value[: width - 1]}…"


def format_search_results(records: list[ModelRecord]) -> str:
    if not records:
        return "No matching models found."

    rows = []
    for record in records:
        rows.append(
            {
                "id": record.id,
                "name": record.name,
                "family": record.model_family,
                "type": record.type or "",
                "license": record.license or "",
                "source": "hf" if record.huggingface_repo_id else ("url" if record.source_url else ""),
                "downloads": "" if record.downloads is None else str(record.downloads),
            }
        )

    columns = ["id", "name", "family", "type", "license", "source", "downloads"]
    widths = {
        column: max(
            len(column),
            *(min(len(row[column]), 24 if column in {"id", "name"} else 16) for row in rows),
        )
        for column in columns
    }

    header = "  ".join(column.upper().ljust(widths[column]) for column in columns)
    separator = "  ".join("-" * widths[column] for column in columns)
    lines = [header, separator]
    for row in rows:
        lines.append(
            "  ".join(
                _clip(row[column], widths[column]).ljust(widths[column]) for column in columns
            )
        )
    return "\n".join(lines)


def format_record_detail(record: ModelRecord) -> str:
    sibling_summary = ""
    if record.sibling_file_names:
        preview = ", ".join(record.sibling_file_names[:15])
        remaining = len(record.sibling_file_names) - 15
        if remaining > 0:
            sibling_summary = f"{preview}, ... (+{remaining} more)"
        else:
            sibling_summary = preview

    fields = [
        ("ID", record.id),
        ("Name", record.name),
        ("Type", record.type or ""),
        ("Model Family", record.model_family),
        ("Author", record.author or ""),
        ("License", record.license or ""),
        ("Source URL", record.source_url or ""),
        ("Hugging Face Repo", record.huggingface_repo_id or ""),
        ("Download URL", record.download_url or ""),
        ("SHA256", record.sha256 or ""),
        ("Metadata Path", record.metadata_path or ""),
        ("Tags", ", ".join(record.tags)),
        ("Likes", "" if record.likes is None else str(record.likes)),
        ("Downloads", "" if record.downloads is None else str(record.downloads)),
        ("Last Modified", record.last_modified or ""),
        ("Sibling Files", sibling_summary),
        ("README Excerpt", record.readme_excerpt or ""),
        ("Warnings", "; ".join(record.warnings)),
    ]
    lines = [f"{label}: {value}" for label, value in fields if value]
    if record.suggested_config:
        baseline_config = record.suggested_config.get("baseline_config")
        recommended_tuning = record.suggested_config.get("recommended_tuning")
        if isinstance(baseline_config, dict) and baseline_config:
            lines.append("")
            lines.append("Baseline Config:")
            lines.append(json.dumps(baseline_config, indent=2, sort_keys=True))
        if isinstance(recommended_tuning, dict) and recommended_tuning:
            lines.append("")
            lines.append("Recommended Tuning:")
            lines.append(json.dumps(recommended_tuning, indent=2, sort_keys=True))
    lines.append("")
    lines.append("Raw Metadata JSON:")
    lines.append(json.dumps(record.raw_metadata_json, indent=2, sort_keys=True))
    return "\n".join(lines)


def format_summary(records: list[ModelRecord]) -> str:
    total = len(records)
    lines = [f"Total records: {total}"]

    coverage_fields = [
        ("With source URL", sum(1 for record in records if record.source_url)),
        ("With Hugging Face repo", sum(1 for record in records if record.huggingface_repo_id)),
        ("With license", sum(1 for record in records if record.license)),
        ("With author", sum(1 for record in records if record.author)),
        ("With downloads", sum(1 for record in records if record.downloads is not None)),
        ("With suggested config", sum(1 for record in records if record.suggested_config)),
        ("With warnings", sum(1 for record in records if record.warnings)),
    ]
    lines.append("")
    lines.append("Coverage:")
    for label, count in coverage_fields:
        pct = 0.0 if total == 0 else (count / total) * 100
        lines.append(f"  {label}: {count} ({pct:.1f}%)")

    family_counts = Counter(record.model_family for record in records)
    type_counts = Counter(record.type or "unknown" for record in records)
    license_counts = Counter(record.license or "unknown" for record in records)
    author_counts = Counter(record.author or "unknown" for record in records)

    def append_top(title: str, counts: Counter[str], limit: int = 8) -> None:
        lines.append("")
        lines.append(f"{title}:")
        for name, count in counts.most_common(limit):
            lines.append(f"  {name}: {count}")

    append_top("Top model families", family_counts)
    append_top("Top types", type_counts)
    append_top("Top licenses", license_counts)
    append_top("Top authors", author_counts)

    top_downloads = sorted(
        [record for record in records if record.downloads is not None],
        key=lambda record: (record.downloads or 0, record.likes or 0, record.name.lower()),
        reverse=True,
    )[:10]
    lines.append("")
    lines.append("Top downloadable records:")
    if top_downloads:
        for record in top_downloads:
            downloads = record.downloads if record.downloads is not None else 0
            lines.append(f"  {record.id}: {downloads} downloads [{record.model_family}]")
    else:
        lines.append("  None")

    return "\n".join(lines)
