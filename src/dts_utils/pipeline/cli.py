"""CLI entrypoints for pipeline checks, profiles listing, and cleanup."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dts_utils.configs import DEFAULT_PROFILE_NAME
from dts_utils.pipeline import collect_apple_runtime_checks
from dts_utils.pipeline.cleanup import cleanup_runs
from dts_utils.pipeline.profile import list_pipeline_profile_names
from dts_utils.pipeline.run_plan import default_run_root


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dts-utils pipeline",
        description="Pipeline runtime checks, profile listing, and run-root cleanup.",
        epilog=(
            "To run prompt-to-video, use generate with a pipeline profile:\n"
            "  dts-utils generate --profile prompt-to-video --prompt \"…\" --trust-server-cert\n"
            "  dts-utils \"…\" prompt-to-video"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="Validate Apple runtime prerequisites for pipeline runs.")
    check.add_argument("--run-root", type=Path, default=default_run_root())
    check.add_argument("--json", action="store_true", help="Print machine-readable JSON.")

    profiles = sub.add_parser("profiles", help="List saved profiles that include pipeline defaults.")
    profiles.add_argument("--json", action="store_true", help="Print machine-readable JSON.")

    cleanup = sub.add_parser(
        "cleanup",
        help="Prune old pipeline run directories to control disk usage.",
        description="Prune old pipeline runs under --run-root to keep disk usage bounded.",
        epilog=(
            "Examples:\n"
            "  dts-utils pipeline cleanup --older-than 7 --keep-last 20 --dry-run\n"
            "  dts-utils pipeline cleanup --max-run-root-gb 25 --keep-last 10\n"
            "  dts-utils pipeline cleanup --older-than 30 --max-run-root-gb 50"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    cleanup.add_argument("--run-root", type=Path, default=default_run_root())
    cleanup.add_argument(
        "--older-than",
        type=float,
        default=None,
        metavar="DAYS",
        help="Delete runs older than DAYS (except newest --keep-last runs).",
    )
    cleanup.add_argument(
        "--keep-last",
        type=int,
        default=0,
        metavar="N",
        help="Always keep the newest N runs.",
    )
    cleanup.add_argument(
        "--max-run-root-gb",
        type=float,
        default=None,
        metavar="GB",
        help="After age pruning, evict oldest runs until run-root is <= GB.",
    )
    cleanup.add_argument("--dry-run", action="store_true", help="Show what would be deleted, but do not remove files.")
    cleanup.add_argument("--json", action="store_true", help="Print machine-readable JSON.")

    return parser


def pipeline_run_removed_message(argv: list[str]) -> str:
    """Build a short hint when someone still invokes ``pipeline run``."""
    profile = "prompt-to-video"
    prompt = "your scene"
    for index, token in enumerate(argv):
        if token == "--profile" and index + 1 < len(argv):
            profile = argv[index + 1]
        if token == "--prompt" and index + 1 < len(argv):
            prompt = argv[index + 1]
    return "\n".join(
        [
            "pipeline run was removed.",
            "Use generate with a pipeline profile instead, for example:",
            f'  dts-utils generate --profile {profile} --prompt "{prompt}" --trust-server-cert',
            f'  dts-utils "{prompt}" {profile}',
            "Still available: dts-utils pipeline check | cleanup | profiles",
        ]
    )


def handle_removed_run(argv: list[str]) -> int:
    print(pipeline_run_removed_message(argv), file=sys.stderr)
    return 2


def handle_profiles(args: argparse.Namespace) -> int:
    names = list_pipeline_profile_names()
    payload = {"profiles": names, "default_profile": DEFAULT_PROFILE_NAME}
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        if not names:
            print("No pipeline profiles found (JSON files with _dts_utils_pipeline under configs path).")
            print("Run: dts-utils configs path")
            return 0
        for name in names:
            print(name)
    return 0


def handle_check(args: argparse.Namespace) -> int:
    checks = collect_apple_runtime_checks(args.run_root)
    payload = {
        "run_root": str(args.run_root),
        "ffmpeg_path": checks.ffmpeg_path,
        "run_root_writable": checks.run_root_writable,
        "gatekeeper_note": checks.gatekeeper_note,
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"run_root: {payload['run_root']}")
        print(f"run_root_writable: {payload['run_root_writable']}")
        print(f"ffmpeg_path: {payload['ffmpeg_path'] or 'missing'}")
        print(f"note: {payload['gatekeeper_note']}")
    return 0 if (checks.run_root_writable and checks.ffmpeg_path) else 1


def handle_cleanup(args: argparse.Namespace) -> int:
    res = cleanup_runs(
        args.run_root,
        older_than_days=args.older_than,
        keep_last=args.keep_last,
        max_run_root_gb=args.max_run_root_gb,
        dry_run=args.dry_run,
    )
    payload = {
        "run_root": str(args.run_root),
        "dry_run": args.dry_run,
        "deleted_count": len(res.deleted),
        "kept_count": len(res.kept),
        "reclaimed_bytes": res.reclaimed_bytes,
        "deleted_runs": [r.run_id for r in res.deleted],
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        mode = "would delete" if args.dry_run else "deleted"
        print(f"run_root: {payload['run_root']}")
        print(f"{mode}: {payload['deleted_count']} run(s)")
        print(f"kept: {payload['kept_count']} run(s)")
        print(f"reclaimed_bytes: {payload['reclaimed_bytes']}")
        if payload["deleted_runs"]:
            print("deleted_runs:")
            for rid in payload["deleted_runs"]:
                print(f"- {rid}")
    return 0


def main(argv: list[str] | None = None) -> int:
    tail = list(argv or [])
    if tail and tail[0] == "run":
        return handle_removed_run(tail[1:])
    parser = build_parser()
    args = parser.parse_args(tail)
    if args.command == "check":
        return handle_check(args)
    if args.command == "profiles":
        return handle_profiles(args)
    if args.command == "cleanup":
        return handle_cleanup(args)
    parser.error(f"Unknown command: {args.command}")
    return 2
