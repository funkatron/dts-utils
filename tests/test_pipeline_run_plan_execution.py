from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from dts_utils.exceptions import ConfigurationError
from dts_utils.pipeline.run_plan import PipelineRunRequest, execute_pipeline_run
import dts_utils.pipeline.run_plan as pipeline_run_plan


def test_execute_pipeline_run_uses_z_preset(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}

    class FakeRunner:
        def __init__(self, run_root, allow_cache, max_oom_retries):
            self._run_root = run_root
            captured["allow_cache"] = allow_cache
            captured["max_oom_retries"] = max_oom_retries

        def run(self, *, run_id, steps):
            captured["run_id"] = run_id
            captured["steps"] = steps
            return SimpleNamespace(run_id=run_id, run_root=str(self._run_root), artifacts=[])

    monkeypatch.setattr(pipeline_run_plan, "PipelineRunner", FakeRunner)
    execute_pipeline_run(
        PipelineRunRequest(
            preset="z-to-ltx",
            run_id="demo",
            allow_cache=False,
            max_oom_retries=2,
        )
    )
    assert captured["allow_cache"] is False
    assert captured["max_oom_retries"] == 2
    assert captured["run_id"] == "demo"
    assert captured["steps"][0].executor.name == "z_image_turbo_text_to_image"


def test_execute_pipeline_run_with_image_skips_t2i(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}

    class FakeRunner:
        def __init__(self, run_root, allow_cache, max_oom_retries):
            self._run_root = run_root

        def run(self, *, run_id, steps):
            captured["steps"] = steps
            return SimpleNamespace(run_id=run_id, run_root=str(self._run_root), artifacts=[])

    monkeypatch.setattr(pipeline_run_plan, "PipelineRunner", FakeRunner)
    execute_pipeline_run(
        PipelineRunRequest(
            image_path=Path("/tmp/in.png"),
            run_id="img-only",
            video_configuration="ltx-2.3-22b-distilled-exact",
            video_prompt="motion",
        )
    )
    assert len(captured["steps"]) == 1
    assert captured["steps"][0].step_id == "i2v"
    assert captured["steps"][0].request["image_path"] == "/tmp/in.png"


def test_execute_pipeline_run_with_prompt_requires_configuration() -> None:
    with pytest.raises(ConfigurationError):
        execute_pipeline_run(PipelineRunRequest(prompt="hello", run_id="prompt-missing-config"))


def test_execute_pipeline_run_profile_applies_defaults(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured = {}
    config_dir = tmp_path / "configurations"
    config_dir.mkdir()
    profile_file = config_dir / "prompt-to-video.json"
    profile_file.write_text(
        (Path(__file__).parent / "fixtures/pipeline_profiles/prompt-to-video.json").read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "dts_utils.pipeline.profile.resolve_configuration_value",
        lambda value, config_dir=None: profile_file,
    )

    class FakeRunner:
        def __init__(self, run_root, allow_cache, max_oom_retries):
            self._run_root = run_root

        def run(self, *, run_id, steps):
            captured["steps"] = steps
            return SimpleNamespace(run_id=run_id, run_root=str(self._run_root), artifacts=[])

    monkeypatch.setattr(pipeline_run_plan, "PipelineRunner", FakeRunner)
    execute_pipeline_run(
        PipelineRunRequest(
            profile="prompt-to-video",
            prompt="sunset city",
            run_id="profile-run",
        )
    )
    assert captured["steps"][0].executor.name == "drawthings_prompt_text_to_image"
    assert captured["steps"][0].request["configuration"] == "default"
    assert captured["steps"][1].executor.name == "drawthings_grpc_image_to_video"
    assert captured["steps"][1].request["configuration"] == "ltx-2.3-portrait"
