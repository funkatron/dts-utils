"""Tests for web log file path, uvicorn log config, and ``web tail``."""

from __future__ import annotations

from pathlib import Path

import pytest

from dts_utils.web import cli as web_cli
from dts_utils.web.log_io import (
    WEB_LOG_ENV,
    build_uvicorn_log_config,
    default_web_log_path,
    tail_web_log_file,
)


def test_default_web_log_path_under_user_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv(WEB_LOG_ENV, raising=False)
    assert default_web_log_path() == tmp_path / ".config" / "dts-utils" / "web.log"


def test_build_uvicorn_log_config_omits_access_when_disabled(tmp_path: Path) -> None:
    log_path = tmp_path / "web.log"
    cfg = build_uvicorn_log_config(log_level="info", log_path=log_path, access_log=False)
    assert cfg["loggers"]["uvicorn.access"]["handlers"] == []
    assert log_path.parent.exists() or log_path.parent == tmp_path


def test_tail_web_log_file_prints_recent_and_exits(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    log_path = tmp_path / "web.log"
    log_path.write_text("line1\nline2\nline3\n", encoding="utf-8")
    code = tail_web_log_file(log_path=log_path, lines=2, follow=False)
    assert code == 0
    captured = capsys.readouterr()
    assert "Log file:" in captured.err
    assert str(log_path.resolve()) in captured.err
    assert "line2" in captured.out
    assert "line3" in captured.out
    assert "line1" not in captured.out


def test_tail_web_log_file_missing_returns_one(tmp_path: Path) -> None:
    code = tail_web_log_file(log_path=tmp_path / "missing.log", lines=10, follow=False)
    assert code == 1


def test_web_main_dispatches_tail(monkeypatch: pytest.MonkeyPatch) -> None:
    called: dict[str, object] = {}

    def fake_tail(argv: list[str] | None) -> int:
        called["argv"] = list(argv or [])
        return 0

    monkeypatch.setattr(web_cli, "run_web_tail", fake_tail)
    assert web_cli.main(["tail", "-n", "5"]) == 0
    assert called["argv"] == ["-n", "5"]


def test_web_main_dispatches_serve(monkeypatch: pytest.MonkeyPatch) -> None:
    called: dict[str, object] = {}

    def fake_serve(argv: list[str] | None) -> int:
        called["argv"] = list(argv or [])
        return 0

    monkeypatch.setattr(web_cli, "run_web_server", fake_serve)
    assert web_cli.main(["--port", "9999"]) == 0
    assert called["argv"] == ["--port", "9999"]


def test_run_web_server_uses_log_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    captured: dict[str, object] = {}

    class FakeServer:
        def run(self) -> None:
            return None

    def fake_config(*_a, **kwargs):
        captured["log_config"] = kwargs.get("log_config")
        return object()

    monkeypatch.setattr(web_cli.uvicorn, "Config", fake_config)
    monkeypatch.setattr(web_cli.uvicorn, "Server", lambda _c: FakeServer())
    code = web_cli.run_web_server(["--port", "8765"])
    assert code == 0
    log_config = captured["log_config"]
    assert isinstance(log_config, dict)
    assert "file" in log_config["handlers"]
    log_file = Path(log_config["handlers"]["file"]["filename"])
    assert log_file == tmp_path / ".config" / "dts-utils" / "web.log"
    out = capsys.readouterr()
    assert str(log_file.resolve()) in out.out
    assert "logging to" in out.err


def test_run_web_server_no_log_file_skips_log_config(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class FakeServer:
        def run(self) -> None:
            return None

    def fake_config(*_a, **kwargs):
        captured["log_config"] = kwargs.get("log_config")
        return object()

    monkeypatch.setattr(web_cli.uvicorn, "Config", fake_config)
    monkeypatch.setattr(web_cli.uvicorn, "Server", lambda _c: FakeServer())
    web_cli.run_web_server(["--no-log-file"])
    assert captured["log_config"] is None
