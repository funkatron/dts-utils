from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from dts_utils import cli_router
from dts_utils.pipeline import cli as pipeline_cli
import dts_utils.pipeline.run_plan as pipeline_run_plan


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

    monkeypatch.setattr(pipeline_run_plan, "PipelineRunner", FakeRunner)
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

    monkeypatch.setattr(pipeline_run_plan, "PipelineRunner", FakeRunner)
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

    monkeypatch.setattr(pipeline_run_plan, "PipelineRunner", FakeRunner)
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
    assert captured["steps"][1].executor.name == "placeholder_image_to_video"


def test_pipeline_run_profile_applies_defaults(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    captured = {}
    config_dir = tmp_path / "configurations"
    config_dir.mkdir()
    (config_dir / "infomux.json").write_text(
        (
            Path(__file__).parent / "fixtures/pipeline_profiles/infomux.json"
        ).read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    class FakeRunner:
        def __init__(self, run_root, allow_cache, max_oom_retries):
            pass

        def run(self, *, run_id, steps):
            captured["steps"] = steps
            return SimpleNamespace(run_id=run_id, run_root="/tmp", artifacts=[])

    monkeypatch.setattr(pipeline_run_plan, "PipelineRunner", FakeRunner)
    profile_file = config_dir / "infomux.json"
    monkeypatch.setattr(
        "dts_utils.pipeline.profile.resolve_configuration_value",
        lambda value, config_dir=None: profile_file,
    )
    code = pipeline_cli.main(
        [
            "run",
            "--profile",
            "infomux",
            "--prompt",
            "sunset city",
            "--run-id",
            "profile-run",
        ]
    )
    assert code == 0
    assert captured["steps"][0].executor.name == "drawthings_prompt_text_to_image"
    assert captured["steps"][0].request["configuration"] == "default"
    assert captured["steps"][1].executor.name == "drawthings_grpc_image_to_video"
    assert captured["steps"][1].request["configuration"] == "ltx-2.3-22b-distilled-exact"


def test_pipeline_profiles_lists_names(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(
        "dts_utils.pipeline.cli.list_pipeline_profile_names",
        lambda config_dir=None: ["infomux"],
    )
    code = pipeline_cli.main(["profiles"])
    assert code == 0
    assert "infomux" in capsys.readouterr().out


def test_pipeline_run_video_configuration_uses_drawthings_i2v(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}

    class FakeRunner:
        def __init__(self, run_root, allow_cache, max_oom_retries):
            pass

        def run(self, *, run_id, steps):
            captured["steps"] = steps
            return SimpleNamespace(run_id=run_id, run_root="/tmp", artifacts=[])

    monkeypatch.setattr(pipeline_run_plan, "PipelineRunner", FakeRunner)
    code = pipeline_cli.main(
        [
            "run",
            "--prompt",
            "scene",
            "--configuration",
            "default",
            "--video-configuration",
            "ltx-2.3-22b-distilled-exact",
            "--run-id",
            "video-cfg",
        ]
    )
    assert code == 0
    assert captured["steps"][1].executor.name == "drawthings_grpc_image_to_video"
    assert captured["steps"][1].request["prompt"] == "scene"
