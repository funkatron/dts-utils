"""CLI for indexing Draw Things uncurated models."""

from __future__ import annotations

import argparse
from collections import Counter
import os
from pathlib import Path
import sys

from .export import write_csv, write_html_report, write_json, write_sqlite
from .local import (
    compute_index_status,
    default_models_dir,
    doctor_local_models,
    format_doctor_findings,
    format_index_statuses,
    format_installed_summaries,
    scan_local_models,
    summarize_doctor_counts,
    summarize_installed_models,
    summarize_status_counts,
)
from .parse import build_records, enrich_huggingface_records
from .repo import COMMUNITY_MODELS_REPO_URL, RepoSyncError, ensure_repo
from .search import (
    filter_records,
    format_record_detail,
    format_search_results,
    format_summary,
    load_records,
    search_records,
)


def _default_repo_dir() -> Path:
    return Path(".cache") / "community-models"


def _default_hf_cache_dir() -> Path:
    return Path(".cache") / "huggingface"


def _default_data_dir() -> Path:
    return Path("data")


def _default_models_dir() -> Path:
    configured = os.environ.get("DRAW_THINGS_MODEL_PATH")
    return Path(configured) if configured else default_models_dir()


def _json_output_path(data_dir: Path) -> Path:
    return data_dir / "drawthings_uncurated_models.json"


def _csv_output_path(data_dir: Path) -> Path:
    return data_dir / "drawthings_uncurated_models.csv"


def _sqlite_output_path(data_dir: Path) -> Path:
    return data_dir / "drawthings_models.sqlite"


def _report_output_path(data_dir: Path) -> Path:
    return data_dir / "report.html"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dts-utils models",
        description="Inspect and search Draw Things uncurated models locally.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build", help="Clone/update and build the local model index.")
    build_parser.add_argument("--repo-dir", type=Path, default=_default_repo_dir())
    build_parser.add_argument("--cache-dir", type=Path, default=_default_hf_cache_dir())
    build_parser.add_argument("--data-dir", type=Path, default=_default_data_dir())
    build_parser.add_argument("--skip-hf", action="store_true", help="Skip Hugging Face API enrichment.")
    build_parser.add_argument("--refresh-hf", action="store_true", help="Refresh cached Hugging Face responses.")
    build_parser.add_argument(
        "--repo-url",
        default=COMMUNITY_MODELS_REPO_URL,
        help=argparse.SUPPRESS,
    )

    search_parser = subparsers.add_parser("search", help="Search the local model index.")
    search_parser.add_argument("terms", nargs="*")
    search_parser.add_argument("--data-dir", type=Path, default=_default_data_dir())
    search_parser.add_argument("--limit", type=int, default=25)
    search_parser.add_argument("--family")
    search_parser.add_argument("--type")
    search_parser.add_argument("--author")
    search_parser.add_argument("--license")
    search_parser.add_argument("--has-source", action="store_true")
    search_parser.add_argument("--has-hf", action="store_true")
    search_parser.add_argument("--has-license", action="store_true")
    search_parser.add_argument("--has-downloads", action="store_true")
    search_parser.add_argument("--has-warnings", action="store_true")

    show_parser = subparsers.add_parser("show", help="Show one model by id.")
    show_parser.add_argument("model_id")
    show_parser.add_argument("--data-dir", type=Path, default=_default_data_dir())
    show_parser.add_argument("--model-dir", type=Path, default=_default_models_dir())
    show_parser.add_argument("--local", action="store_true", help="Include local install status details.")

    report_parser = subparsers.add_parser("report", help="Build a local HTML report from the JSON index.")
    report_parser.add_argument("--data-dir", type=Path, default=_default_data_dir())
    report_parser.add_argument("--summary-only", action="store_true")

    installed_parser = subparsers.add_parser("installed", help="List locally installed Draw Things model files.")
    installed_parser.add_argument("--model-dir", type=Path, default=_default_models_dir())
    installed_parser.add_argument("--data-dir", type=Path, default=_default_data_dir())
    installed_parser.add_argument("--limit", type=int, default=50)

    status_parser = subparsers.add_parser("status", help="Compare the local model directory against the index.")
    status_parser.add_argument("--model-dir", type=Path, default=_default_models_dir())
    status_parser.add_argument("--data-dir", type=Path, default=_default_data_dir())
    status_parser.add_argument("--limit", type=int, default=50)

    doctor_parser = subparsers.add_parser("doctor", help="Check the local model directory for common issues.")
    doctor_parser.add_argument("--model-dir", type=Path, default=_default_models_dir())
    doctor_parser.add_argument("--data-dir", type=Path, default=_default_data_dir())
    doctor_parser.add_argument("--limit", type=int, default=50)
    doctor_parser.add_argument(
        "--severity",
        choices=["warning", "info", "all"],
        default="warning",
        help="Show only warnings by default; include info findings with `all`.",
    )

    return parser


def _load_index_or_exit(data_dir: Path):
    json_path = _json_output_path(data_dir)
    if not json_path.exists():
        print(f"Index not found at {json_path}. Run `uv run dts-utils models build` first.")
        return None
    try:
        return load_records(json_path)
    except Exception as exc:  # noqa: BLE001
        print(f"Failed to load index at {json_path}: {exc}")
        return None


def handle_build(args: argparse.Namespace) -> int:
    try:
        status = ensure_repo(args.repo_dir, repo_url=args.repo_url)
    except RepoSyncError as exc:
        print(exc)
        return 1

    print(f"Repository {status}: {args.repo_dir}")
    records = build_records(args.repo_dir)
    print(f"Loaded {len(records)} uncurated model ids.")

    if not args.skip_hf:
        enrich_huggingface_records(records, cache_dir=args.cache_dir, refresh=args.refresh_hf)
        hf_count = sum(1 for record in records if record.huggingface_repo_id)
        print(f"Processed Hugging Face enrichment for {hf_count} records.")

    args.data_dir.mkdir(parents=True, exist_ok=True)
    json_path = _json_output_path(args.data_dir)
    csv_path = _csv_output_path(args.data_dir)
    sqlite_path = _sqlite_output_path(args.data_dir)
    report_path = _report_output_path(args.data_dir)

    write_json(records, json_path)
    write_csv(records, csv_path)
    write_sqlite(records, sqlite_path)
    write_html_report(records, report_path)

    warning_count = sum(len(record.warnings) for record in records)
    print(f"Wrote {json_path}")
    print(f"Wrote {csv_path}")
    print(f"Wrote {sqlite_path}")
    print(f"Wrote {report_path}")
    print(f"Warnings recorded: {warning_count}")
    return 0


def handle_search(args: argparse.Namespace) -> int:
    records = _load_index_or_exit(args.data_dir)
    if records is None:
        return 1

    filtered = filter_records(
        records,
        family=args.family,
        model_type=args.type,
        author=args.author,
        license_name=args.license,
        has_source=args.has_source,
        has_hf=args.has_hf,
        has_license=args.has_license,
        has_downloads=args.has_downloads,
        has_warnings=args.has_warnings,
    )
    matches = search_records(filtered, args.terms, limit=args.limit)
    print(format_search_results(matches))
    return 0 if matches else 1


def handle_show(args: argparse.Namespace) -> int:
    records = _load_index_or_exit(args.data_dir)
    if records is None:
        return 1

    wanted = args.model_id.lower()
    for record in records:
        if record.id.lower() == wanted:
            detail = format_record_detail(record)
            if args.local:
                local_files = scan_local_models(args.model_dir)
                local_names = {file_record.name for file_record in local_files}
                expected_names = []
                payload = record.raw_metadata_json
                for key in ("file", "autoencoder", "text_encoder", "clip_encoder", "t5_encoder"):
                    value = payload.get(key)
                    if isinstance(value, str) and value.strip():
                        expected_names.append(Path(value).name)
                matched_names = sorted({name for name in expected_names if name in local_names})
                missing_names = sorted({name for name in expected_names if name not in local_names})
                local_lines = [
                    "",
                    "Local Install Status:",
                    f"Model Directory: {args.model_dir}",
                    f"Matched Files: {', '.join(matched_names) if matched_names else 'None'}",
                    f"Missing Files: {', '.join(missing_names) if missing_names else 'None'}",
                ]
                detail = f"{detail}\n" + "\n".join(local_lines)
            print(detail)
            return 0

    print(f"Model id not found: {args.model_id}")
    return 1


def handle_report(args: argparse.Namespace) -> int:
    records = _load_index_or_exit(args.data_dir)
    if records is None:
        return 1
    print(format_summary(records))
    if args.summary_only:
        return 0
    report_path = _report_output_path(args.data_dir)
    write_html_report(records, report_path)
    print(f"Wrote {report_path}")
    return 0


def handle_installed(args: argparse.Namespace) -> int:
    local_files = scan_local_models(args.model_dir)
    records = _load_index_or_exit(args.data_dir)
    if records is None:
        return 1
    summaries = summarize_installed_models(local_files, indexed_records=records)
    summaries = sorted(
        summaries,
        key=lambda summary: (summary.total_size_bytes, summary.base_name.lower()),
        reverse=True,
    )[: args.limit]
    print(f"Model Directory: {args.model_dir}")
    print(f"Local Files: {len(local_files)}")
    print("")
    print(format_installed_summaries(summaries))
    return 0


def handle_status(args: argparse.Namespace) -> int:
    records = _load_index_or_exit(args.data_dir)
    if records is None:
        return 1
    local_files = scan_local_models(args.model_dir)
    statuses = compute_index_status(records, local_files)
    counts = summarize_status_counts(statuses)
    print(f"Model Directory: {args.model_dir}")
    print(
        "Status Counts: "
        + ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))
    )
    print("")
    print(format_index_statuses(statuses, limit=args.limit))
    return 0


def handle_doctor(args: argparse.Namespace) -> int:
    local_files = scan_local_models(args.model_dir)
    records = _load_index_or_exit(args.data_dir)
    if records is None:
        return 1
    findings = doctor_local_models(local_files, indexed_records=records)
    if args.severity != "all":
        findings = [finding for finding in findings if finding.severity == args.severity]
    counts = summarize_doctor_counts(findings)
    findings = findings[: args.limit]
    print(f"Model Directory: {args.model_dir}")
    if counts:
        print("Findings: " + ", ".join(f"{key}={value}" for key, value in sorted(counts.items())))
    print("")
    print(format_doctor_findings(findings))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    handlers = {
        "build": handle_build,
        "search": handle_search,
        "show": handle_show,
        "report": handle_report,
        "installed": handle_installed,
        "status": handle_status,
        "doctor": handle_doctor,
    }
    handler = handlers[args.command]
    return handler(args)


def print_report_summary(records_path: Path) -> str:
    records = load_records(records_path)
    families = Counter(record.model_family for record in records)
    return "\n".join(f"{family}: {count}" for family, count in families.most_common())


if __name__ == "__main__":
    sys.exit(main())
