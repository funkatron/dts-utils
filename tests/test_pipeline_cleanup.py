from __future__ import annotations

from datetime import UTC, datetime, timedelta
import os
from pathlib import Path

from dts_utils.pipeline.cleanup import cleanup_runs, list_run_entries


def _make_run(run_root: Path, run_id: str, *, age_days: float, payload_size: int = 32) -> Path:
    run_dir = run_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "pipeline_run.json").write_text("{}", encoding="utf-8")
    (run_dir / "artifact.bin").write_bytes(b"x" * payload_size)
    ts = (datetime.now(UTC) - timedelta(days=age_days)).timestamp()
    os.utime(run_dir, (ts, ts))
    os.utime(run_dir / "pipeline_run.json", (ts, ts))
    os.utime(run_dir / "artifact.bin", (ts, ts))
    return run_dir


def test_list_run_entries_filters_non_runs(tmp_path: Path) -> None:
    run_root = tmp_path / "runs"
    run_root.mkdir()
    _make_run(run_root, "run-a", age_days=1)
    (run_root / "misc").mkdir()
    entries = list_run_entries(run_root)
    assert [e.run_id for e in entries] == ["run-a"]


def test_cleanup_older_than_respects_keep_last(tmp_path: Path) -> None:
    run_root = tmp_path / "runs"
    _make_run(run_root, "newest", age_days=0)
    _make_run(run_root, "middle", age_days=5)
    _make_run(run_root, "oldest", age_days=10)
    res = cleanup_runs(run_root, older_than_days=2, keep_last=1, dry_run=False)
    assert sorted(r.run_id for r in res.deleted) == ["middle", "oldest"]
    assert sorted(r.run_id for r in res.kept) == ["newest"]
    assert (run_root / "newest").exists()
    assert not (run_root / "middle").exists()


def test_cleanup_budget_evicts_oldest(tmp_path: Path) -> None:
    run_root = tmp_path / "runs"
    _make_run(run_root, "r1", age_days=0, payload_size=4000)
    _make_run(run_root, "r2", age_days=1, payload_size=4000)
    _make_run(run_root, "r3", age_days=2, payload_size=4000)
    res = cleanup_runs(run_root, max_run_root_gb=0.000005, keep_last=1, dry_run=True)
    # keep newest run protected, evict older ones in dry-run plan
    assert "r1" not in [r.run_id for r in res.deleted]
    assert res.deleted
