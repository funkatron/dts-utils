from __future__ import annotations

from pathlib import Path

from dts_utils.pipeline.apple_ops import collect_apple_runtime_checks, is_run_root_writable
from dts_utils.pipeline.executors import StubTextToImageExecutor
from dts_utils.pipeline.runner import PipelineRunner, PipelineStep


def test_collect_apple_runtime_checks_reports_writable_root(tmp_path: Path) -> None:
    checks = collect_apple_runtime_checks(tmp_path)
    assert checks.run_root_writable is True
    assert "quarantine" in checks.gatekeeper_note
    assert is_run_root_writable(tmp_path) is True


def test_runner_writes_heartbeat_file(tmp_path: Path) -> None:
    runner = PipelineRunner(tmp_path)
    runner.run(
        run_id="hb-run",
        steps=[
            PipelineStep(
                step_id="t2i",
                executor=StubTextToImageExecutor(),
                request={"width": 24, "height": 24, "seed": 1},
            )
        ],
    )
    hb = tmp_path / "hb-run" / "heartbeat.json"
    assert hb.exists()
    text = hb.read_text(encoding="utf-8")
    assert '"status": "completed"' in text
