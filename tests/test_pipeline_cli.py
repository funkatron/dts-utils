from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from dts_utils import cli_router
from dts_utils.pipeline import cli as pipeline_cli


def test_cli_router_dispatches_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["dts-utils", "pipeline", "check"])
    with patch.object(cli_router, "pipeline_main", return_value=0) as pipeline_main:
        with pytest.raises(SystemExit) as exc_info:
            cli_router.main()
    pipeline_main.assert_called_once_with(["check"])
    assert exc_info.value.code == 0


def test_pipeline_check_json(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    fake_checks = SimpleNamespace(
        ffmpeg_path="/usr/local/bin/ffmpeg",
        run_root_writable=True,
        gatekeeper_note="note",
    )
    monkeypatch.setattr("dts_utils.pipeline.cli.collect_apple_runtime_checks", lambda _p: fake_checks)
    code = pipeline_cli.main(["check", "--json"])
    out = capsys.readouterr().out
    assert code == 0
    assert '"ffmpeg_path": "/usr/local/bin/ffmpeg"' in out
    assert '"run_root_writable": true' in out


def test_pipeline_check_fails_without_ffmpeg(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_checks = SimpleNamespace(
        ffmpeg_path=None,
        run_root_writable=True,
        gatekeeper_note="note",
    )
    monkeypatch.setattr("dts_utils.pipeline.cli.collect_apple_runtime_checks", lambda _p: fake_checks)
    code = pipeline_cli.main(["check"])
    assert code == 1


def test_pipeline_run_uses_z_preset(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    captured = {}

    class FakeRunner:
        def __init__(self, run_root, allow_cache, max_oom_retries):
            captured["run_root"] = run_root
            captured["allow_cache"] = allow_cache
            captured["max_oom_retries"] = max_oom_retries

        def run(self, *, run_id, steps):
            captured["run_id"] = run_id
            captured["steps"] = steps
            return SimpleNamespace(
                run_id=run_id,
                run_root=str(captured["run_root"]),
                artifacts=[{"path": "/tmp/image.png"}, {"path": "/tmp/video.mp4"}],
            )

    monkeypatch.setattr("dts_utils.pipeline.cli.PipelineRunner", FakeRunner)
    code = pipeline_cli.main(
        [
            "run",
            "--preset",
            "z-to-ltx",
            "--run-id",
            "demo",
            "--no-cache",
            "--max-oom-retries",
            "2",
        ]
    )
    out = capsys.readouterr().out
    assert code == 0
    assert captured["allow_cache"] is False
    assert captured["max_oom_retries"] == 2
    assert captured["run_id"] == "demo"
    assert captured["steps"][0].executor.name == "z_image_turbo_text_to_image"
    assert "artifact_2: /tmp/video.mp4" in out


def test_pipeline_run_with_image_skips_t2i(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}

    class FakeRunner:
        def __init__(self, run_root, allow_cache, max_oom_retries):
            pass

        def run(self, *, run_id, steps):
            captured["steps"] = steps
            return SimpleNamespace(run_id=run_id, run_root="/tmp", artifacts=[{"path": "/tmp/video.mp4"}])

    monkeypatch.setattr("dts_utils.pipeline.cli.PipelineRunner", FakeRunner)
    code = pipeline_cli.main(["run", "--image", "/tmp/in.png", "--run-id", "img-only"])
    assert code == 0
    assert len(captured["steps"]) == 1
    assert captured["steps"][0].step_id == "i2v"
    assert captured["steps"][0].request["image_path"] == "/tmp/in.png"


def test_pipeline_run_with_prompt_requires_configuration() -> None:
    with pytest.raises(SystemExit):
        pipeline_cli.main(["run", "--prompt", "hello", "--run-id", "prompt-missing-config"])


def test_pipeline_run_with_prompt_uses_drawthings_executor(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}

    class FakeRunner:
        def __init__(self, run_root, allow_cache, max_oom_retries):
            pass

        def run(self, *, run_id, steps):
            captured["steps"] = steps
            return SimpleNamespace(run_id=run_id, run_root="/tmp", artifacts=[{"path": "/tmp/img.png"}, {"path": "/tmp/video.mp4"}])

    monkeypatch.setattr("dts_utils.pipeline.cli.PipelineRunner", FakeRunner)
    code = pipeline_cli.main(
        [
            "run",
            "--prompt",
            "a cool scene",
            "--configuration",
            "default",
            "--run-id",
            "prompt-ok",
        ]
    )
    assert code == 0
    assert captured["steps"][0].executor.name == "drawthings_prompt_text_to_image"
    assert captured["steps"][1].input_from_step == "t2i"
