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


def test_pipeline_run_removed_points_at_generate(capsys: pytest.CaptureFixture[str]) -> None:
    code = pipeline_cli.main(
        ["run", "--profile", "prompt-to-video", "--prompt", "sunset city", "--run-id", "old-habit"]
    )
    err = capsys.readouterr().err
    assert code == 2
    assert "pipeline run was removed" in err
    assert "generate --profile prompt-to-video" in err
    assert '--prompt "sunset city"' in err


def test_pipeline_profiles_lists_names(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(
        "dts_utils.pipeline.cli.list_pipeline_profile_names",
        lambda config_dir=None: ["prompt-to-video"],
    )
    code = pipeline_cli.main(["profiles"])
    assert code == 0
    assert "prompt-to-video" in capsys.readouterr().out


def test_pipeline_cleanup_json(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    class FakeRes:
        deleted = [SimpleNamespace(run_id="run-a")]
        kept = [SimpleNamespace(run_id="run-b")]
        reclaimed_bytes = 1234

    monkeypatch.setattr("dts_utils.pipeline.cli.cleanup_runs", lambda *a, **k: FakeRes())
    code = pipeline_cli.main(["cleanup", "--json"])
    assert code == 0
    out = capsys.readouterr().out
    assert '"deleted_count": 1' in out
    assert '"deleted_runs": [' in out


def test_pipeline_cleanup_plaintext(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    class FakeRes:
        deleted = [SimpleNamespace(run_id="old-1"), SimpleNamespace(run_id="old-2")]
        kept = []
        reclaimed_bytes = 999

    monkeypatch.setattr("dts_utils.pipeline.cli.cleanup_runs", lambda *a, **k: FakeRes())
    code = pipeline_cli.main(["cleanup", "--dry-run"])
    assert code == 0
    out = capsys.readouterr().out
    assert "would delete: 2 run(s)" in out
    assert "- old-1" in out
