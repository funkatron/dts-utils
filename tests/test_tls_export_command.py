"""Tests for ``dts-util tls`` and PEM export helpers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from dts_util import cli_router
from dts_util import tls_export


def test_default_server_pem_path_inside_user_config(monkeypatch, tmp_path):
    monkeypatch.setattr(tls_export, "user_config_dir", lambda: tmp_path / "dts-util")
    p = tls_export.default_server_pem_path()
    assert "trusted" in p.parent.parts
    assert p.name == tls_export.DEFAULT_SERVER_PEM_NAME


def test_export_presented_certificate_writes_pem(monkeypatch, tmp_path):
    monkeypatch.setattr(
        tls_export,
        "fetch_presented_pem",
        lambda _h, _p: b"-----BEGIN CERTIFICATE-----\nfake\n-----END CERTIFICATE-----\n",
    )
    dest = tmp_path / "srv.pem"
    out = tls_export.export_presented_certificate("localhost", 7859, dest)
    assert out == dest.resolve()
    assert b"BEGIN CERTIFICATE" in dest.read_bytes()


def test_export_presented_certificate_refuses_overwrite(monkeypatch, tmp_path):
    monkeypatch.setattr(tls_export, "fetch_presented_pem", lambda _h, _p: b"abc\n")
    dest = tmp_path / "srv.pem"
    dest.write_bytes(b"old")
    with pytest.raises(FileExistsError):
        tls_export.export_presented_certificate("localhost", 7859, dest, force=False)


def test_tls_main_path_subcommand(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(tls_export, "user_config_dir", lambda: tmp_path / "cfg")
    assert tls_export.main(["path"]) == 0
    out = capsys.readouterr().out.strip()
    assert str(tmp_path / "cfg") in out
    assert (tmp_path / "cfg" / "trusted").exists()


def test_tls_main_path_no_create(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(tls_export, "user_config_dir", lambda: tmp_path / "cfg")
    assert tls_export.main(["path", "--no-create"]) == 0
    out = capsys.readouterr().out.strip()
    assert Path(out).parts[-3:] == ("cfg", "trusted", tls_export.DEFAULT_SERVER_PEM_NAME)
    assert not (tmp_path / "cfg" / "trusted").exists()


def test_tls_main_export_writes_file(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(tls_export, "fetch_presented_pem", lambda _h, _p: b"fetched-pem\n")
    dest = tmp_path / "out.pem"

    assert tls_export.main(["export", "-o", str(dest), "--retries", "2"]) == 0

    assert dest.read_bytes() == b"fetched-pem\n"
    out = capsys.readouterr().out
    assert "Wrote presented server certificate" in out
    assert "--root-cert" in out


def test_dts_util_main_dispatches_tls(monkeypatch):
    monkeypatch.setattr("sys.argv", ["dts-util", "tls", "path", "--no-create"])
    with patch.object(cli_router, "tls_main", return_value=0) as tls_main:
        with pytest.raises(SystemExit) as exc_info:
            cli_router.main()

    tls_main.assert_called_once_with(["path", "--no-create"])
    assert exc_info.value.code == 0
