"""Tests for the loopback web UI (Starlette ASGI app)."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from dts_util.exceptions import GenerationCancelledError
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
    assert 'id="btnStop"' in r.text


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

    def fake_generate(_c: object, _g: object, *, generations: int = 1, cancel_event=None) -> list[bytes]:
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
    assert r.headers.get("x-generation-runs") == "1"
    assert b"\x89PNG" in r.content


def test_generate_multipart_respects_generations(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    def fake_generate(_c: object, _g: object, *, generations: int = 1, cancel_event=None) -> list[bytes]:
        assert generations == 2
        return [b"\x89PNG\r\n\x1a\nx", b"\x89PNG\r\n\x1a\ny"]

    monkeypatch.setattr("dts_util.web.app.generate_png_bytes", fake_generate)
    r = client.post(
        "/api/generate",
        json={
            "prompt": "a sunset",
            "generations": 2,
            "host": "127.0.0.1",
            "port": 7859,
            "trust_server_cert": True,
            "no_tls": True,
        },
    )
    assert r.status_code == 200
    assert r.headers.get("x-generated-count") == "2"
    assert r.headers.get("x-generation-runs") == "2"


def test_generate_invalid_generations_returns_400(client: TestClient) -> None:
    r = client.post(
        "/api/generate",
        json={
            "prompt": "x",
            "generations": 0,
            "no_tls": True,
        },
    )
    assert r.status_code == 400


def test_generate_generations_above_cap_returns_400(client: TestClient) -> None:
    r = client.post(
        "/api/generate",
        json={
            "prompt": "x",
            "generations": 99,
            "no_tls": True,
        },
    )
    assert r.status_code == 400


def test_generate_wildcard_error_returns_400(client: TestClient) -> None:
    """Invalid `{…}` expansion raises before gRPC (ConfigurationError → HTTP 400)."""
    r = client.post(
        "/api/generate",
        json={
            "prompt": "{||}",
            "host": "127.0.0.1",
            "port": 7859,
            "trust_server_cert": True,
            "no_tls": True,
        },
    )
    assert r.status_code == 400
    assert "Unresolved" in r.json()["detail"]


def test_generate_unauthorized_when_token_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DTS_WEB_TOKEN", "sekrit")
    client = TestClient(create_app())
    r = client.post("/api/generate", json={"prompt": "x", "no_tls": True})
    assert r.status_code == 401


def test_generate_cancel_endpoint(client: TestClient) -> None:
    r = client.post("/api/generate/cancel", json={})
    assert r.status_code == 200
    body = r.json()
    assert body.get("ok") is True
    assert body.get("cancel_requested") is True


def test_generate_cancel_requires_bearer_when_token_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DTS_WEB_TOKEN", "sekrit")
    client = TestClient(create_app())
    assert client.post("/api/generate/cancel", json={}).status_code == 401
    r = client.post(
        "/api/generate/cancel",
        json={},
        headers={"Authorization": "Bearer sekrit"},
    )
    assert r.status_code == 200


def test_generate_returns_499_when_generation_cancelled(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    def boom(*_a: object, **_k: object) -> list[bytes]:
        raise GenerationCancelledError("Generation cancelled.")

    monkeypatch.setattr("dts_util.web.app.generate_png_bytes", boom)
    r = client.post(
        "/api/generate",
        json={
            "prompt": "x",
            "host": "127.0.0.1",
            "port": 7859,
            "trust_server_cert": True,
            "no_tls": True,
        },
    )
    assert r.status_code == 499
    assert "cancelled" in r.json()["detail"].lower()
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
