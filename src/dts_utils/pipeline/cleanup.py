"""Run-root retention helpers for pipeline artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import shutil
from pathlib import Path


@dataclass(slots=True)
class RunEntry:
    run_id: str
    path: Path
    modified_at: datetime
    size_bytes: int


@dataclass(slots=True)
class CleanupResult:
    deleted: list[RunEntry]
    kept: list[RunEntry]
    reclaimed_bytes: int
    dry_run: bool


def list_run_entries(run_root: Path) -> list[RunEntry]:
    if not run_root.exists():
        return []
    entries: list[RunEntry] = []
    for child in run_root.iterdir():
        if not child.is_dir():
            continue
        if not (child / "pipeline_run.json").exists():
            continue
        stat = child.stat()
        entries.append(
            RunEntry(
                run_id=child.name,
                path=child,
                modified_at=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
                size_bytes=_dir_size_bytes(child),
            )
        )
    # newest first
    entries.sort(key=lambda x: x.modified_at, reverse=True)
    return entries


def cleanup_runs(
    run_root: Path,
    *,
    older_than_days: float | None = None,
    keep_last: int | None = None,
    max_run_root_gb: float | None = None,
    dry_run: bool = False,
) -> CleanupResult:
    runs = list_run_entries(run_root)
    if not runs:
        return CleanupResult(deleted=[], kept=[], reclaimed_bytes=0, dry_run=dry_run)

    to_delete: set[str] = set()
    now = datetime.now(UTC)
    keep_last_n = max(0, int(keep_last)) if keep_last is not None else None

    if older_than_days is not None and older_than_days >= 0:
        cutoff = now - timedelta(days=float(older_than_days))
        for idx, run in enumerate(runs):
            if keep_last_n is not None and idx < keep_last_n:
                continue
            if run.modified_at < cutoff:
                to_delete.add(run.run_id)

    kept_after_age = [r for r in runs if r.run_id not in to_delete]
    if max_run_root_gb is not None and max_run_root_gb >= 0:
        budget = int(max_run_root_gb * (1024**3))
        total = sum(r.size_bytes for r in kept_after_age)
        if total > budget:
            # delete oldest first, but do not evict newest keep_last entries
            protected = set(r.run_id for r in kept_after_age[: keep_last_n or 0])
            for run in reversed(kept_after_age):
                if total <= budget:
                    break
                if run.run_id in protected:
                    continue
                to_delete.add(run.run_id)
                total -= run.size_bytes

    deleted_entries = [r for r in runs if r.run_id in to_delete]
    kept_entries = [r for r in runs if r.run_id not in to_delete]
    reclaimed = sum(r.size_bytes for r in deleted_entries)
    if not dry_run:
        for run in deleted_entries:
            shutil.rmtree(run.path, ignore_errors=True)
    return CleanupResult(
        deleted=deleted_entries,
        kept=kept_entries,
        reclaimed_bytes=reclaimed,
        dry_run=dry_run,
    )


def _dir_size_bytes(path: Path) -> int:
    total = 0
    for p in path.rglob("*"):
        try:
            if p.is_file():
                total += p.stat().st_size
        except OSError:
            continue
    return total
