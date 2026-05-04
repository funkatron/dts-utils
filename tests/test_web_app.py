"""Tests for the loopback web UI (Starlette ASGI app)."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from dts_util.web.app import create_app


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def test_health_never_requires_token(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    monkeypatch.setenv("DTS_WEB_TOKEN", "secret")
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_index_loads(client: TestClient) -> None:
    r = client.get("/")
    assert r.status_code == 200
    assert "dts-util web" in r.text
    assert 'id="historyDialog"' in r.text
    assert "Ctrl+Enter" in r.text


def test_server_status_without_token(client: TestClient) -> None:
    r = client.get("/api/server-status", params={"host": "localhost", "port": "7859", "no_tls": "false"})
    assert r.status_code == 200
    body = r.json()
    assert "listener_ok" in body
    assert body["probe"] == "tls_then_plaintext"


def test_server_status_unauthorized_with_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DTS_WEB_TOKEN", "sekrit")
    client = TestClient(create_app())
    r = client.get("/api/server-status")
    assert r.status_code == 401
    r = client.get("/api/server-status", headers={"Authorization": "Bearer sekrit"})
    assert r.status_code == 200


def test_configs_with_bearer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DTS_WEB_TOKEN", "sekrit")
    client = TestClient(create_app())
    assert client.get("/api/configs").status_code == 401
    r = client.get("/api/configs", headers={"Authorization": "Bearer sekrit"})
    assert r.status_code == 200
    data = r.json()
    assert "names" in data
    assert data["default_profile"] == "zit"


def test_generate_missing_prompt(client: TestClient) -> None:
    r = client.post("/api/generate", json={})
    assert r.status_code == 400


def test_generate_invalid_json(client: TestClient) -> None:
    r = client.post("/api/generate", content=b"not json", headers={"Content-Type": "application/json"})
    assert r.status_code == 400


def test_generate_invalid_port(client: TestClient) -> None:
    r = client.post("/api/generate", json={"prompt": "a", "port": "nope"})
    assert r.status_code == 400


def test_generate_remote_host_without_pin(client: TestClient) -> None:
    r = client.post(
        "/api/generate",
        json={
            "prompt": "a",
            "host": "192.168.1.5",
            "trust_server_cert": True,
            "no_tls": False,
        },
    )
    assert r.status_code == 400
    assert "non-loopback" in r.json()["detail"]


def test_generate_multipart_on_success(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    """PNG bytes are irrelevant to multipart framing; generation is mocked."""

    def fake_generate(_c: object, _g: object) -> list[bytes]:
        return [b"\x89PNG\r\n\x1a\nplaceholder", b"\x89PNG\r\n\x1a\nother"]

    monkeypatch.setattr("dts_util.web.app.generate_png_bytes", fake_generate)
    r = client.post(
        "/api/generate",
        json={
            "prompt": "a sunset",
            "host": "127.0.0.1",
            "port": 7859,
            "trust_server_cert": True,
            "no_tls": True,
        },
    )
    assert r.status_code == 200
    ct = r.headers.get("content-type", "")
    assert "multipart/mixed" in ct
    assert r.headers.get("x-generated-count") == "2"
    assert b"\x89PNG" in r.content


def test_generate_unauthorized_when_token_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DTS_WEB_TOKEN", "sekrit")
    client = TestClient(create_app())
    r = client.post("/api/generate", json={"prompt": "x", "no_tls": True})
    assert r.status_code == 401


def test_cli_router_dispatches_web(monkeypatch: pytest.MonkeyPatch) -> None:
    import dts_util.cli_router as cr

    monkeypatch.setattr("sys.argv", ["dts-util", "web", "--port", "19999"])
    called: dict[str, object] = {}

    def fake_main(argv: list[str] | None) -> int:
        called["argv"] = list(argv or [])
        return 0

    monkeypatch.setattr(cr, "web_main", fake_main)
    with pytest.raises(SystemExit) as se:
        cr.main()
    assert se.value.code == 0
    assert called["argv"] == ["--port", "19999"]
