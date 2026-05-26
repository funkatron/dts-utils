"""Tests for the loopback web UI (Starlette ASGI app)."""

from __future__ import annotations

import base64
import json

import pytest
from starlette.testclient import TestClient

from dts_utils.exceptions import ConfigurationError, GenerationCancelledError
from dts_utils.generate_api import GeneratePngBatchResult
from dts_utils.web.app import create_app


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
    assert "dts-utils web" in r.text
    assert 'id="historyDialog"' in r.text
    assert "Ctrl+Enter" in r.text
    assert 'id="btnStop"' in r.text
    assert 'id="busyProgress"' in r.text
    assert 'id="busyRequestJson"' in r.text
    assert 'id="expandedPromptsNote"' in r.text
    assert "Generate request JSON" in r.text
    assert "/api/generate/stream" in r.text
    assert 'id="dtsLightbox"' in r.text


def test_index_history_rows_can_reuse_prompt_and_profile(client: TestClient) -> None:
    r = client.get("/")
    assert r.status_code == 200
    assert "Reuse" in r.text
    assert "restoreHistoryEntryToComposer(entry)" in r.text
    assert 'reuse.setAttribute("aria-label", "Reuse prompt and profile from history")' in r.text
    assert 'promptEl.value = String(entry.prompt || "")' in r.text


def test_index_history_contract_stores_optional_reuse_metadata(client: TestClient) -> None:
    r = client.get("/")
    assert r.status_code == 200
    assert 'var HISTORY_KEY = "dts_web_gen_history_v1"' in r.text
    assert 'fetch("/api/history"' in r.text
    assert "migrateLegacyHistoryToServer" in r.text
    assert "applyHistoryConfiguration" in r.text
    assert "payload.configuration" in r.text
    assert 'await historyAppend(' in r.text
    assert "body.configuration" in r.text


def test_history_api_persists_png_files(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("DTS_WEB_HISTORY_DIR", str(tmp_path / "history"))
    client = TestClient(create_app())
    png_b64 = base64.b64encode(b"\x89PNG\r\n\x1a\nfake").decode("ascii")

    r = client.post(
        "/api/history",
        json={
            "ts": 1234567890,
            "prompt": "a saved prompt",
            "negative_prompt": "blur",
            "generations": 2,
            "configuration": "default",
            "images": [png_b64],
        },
    )
    assert r.status_code == 201
    item = r.json()
    assert item["prompt"] == "a saved prompt"
    assert item["negative_prompt"] == "blur"
    assert item["generations"] == 2
    assert item["configuration"] == "default"
    assert item["image_count"] == 1
    assert item["images"][0]["url"].startswith("/history/")

    listed = client.get("/api/history")
    assert listed.status_code == 200
    assert listed.json()["items"][0]["prompt"] == "a saved prompt"
    assert listed.json()["items"][0]["configuration"] == "default"

    image = client.get(item["images"][0]["url"])
    assert image.status_code == 200
    assert image.headers["content-type"] == "image/png"
    assert image.content == b"\x89PNG\r\n\x1a\nfake"

    cleared = client.delete("/api/history")
    assert cleared.status_code == 200
    assert client.get("/api/history").json()["items"] == []


def test_history_api_rejects_non_png(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("DTS_WEB_HISTORY_DIR", str(tmp_path / "history"))
    client = TestClient(create_app())
    r = client.post(
        "/api/history",
        json={"prompt": "x", "images": [base64.b64encode(b"not png").decode("ascii")]},
    )
    assert r.status_code == 400
    assert "not a PNG" in r.json()["detail"]


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
    assert data["default_profile"] == "default"
    profiles = data["pipeline_profiles"]
    assert isinstance(profiles, list)
    assert profiles, "pipeline_profiles should not be empty"
    # Newer builds may surface saved pipeline profiles (e.g. scaffolded `infomux`);
    # fallback defaults are still valid when none are saved.
    assert (
        "infomux" in profiles
        or profiles
        == [
            "sdxl-turbo",
            "z-image-turbo-1.0-exact",
            "ltx-2.3-22b-distilled-exact",
        ]
    )


def test_generate_missing_prompt(client: TestClient) -> None:
    r = client.post("/api/generate", json={})
    assert r.status_code == 400


def test_generate_stream_returns_sse(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    def fake_iter(*_a: object, **_k: object):
        yield {"type": "meta", "total_runs": 1}
        yield {"type": "progress", "run": 1, "total_runs": 1}
        yield {
            "type": "image",
            "run": 1,
            "index": 1,
            "png_b64": base64.standard_b64encode(b"\x89PNG\r\n").decode("ascii"),
        }
        yield {
            "type": "done",
            "expanded_prompts": ["x"],
            "expanded_negative_prompts": [""],
            "total_images": 1,
        }

    monkeypatch.setattr("dts_utils.web.app.iter_generate_stream_dicts", fake_iter)
    with client.stream(
        "POST",
        "/api/generate/stream",
        json={
            "prompt": "hi",
            "host": "127.0.0.1",
            "port": 7859,
            "trust_server_cert": True,
            "no_tls": True,
        },
    ) as r:
        assert r.status_code == 200
        ct = r.headers.get("content-type", "")
        assert "text/event-stream" in ct
        raw = r.read().decode("utf-8")
    data_lines = [ln for ln in raw.splitlines() if ln.startswith("data: ")]
    payloads = [json.loads(ln.removeprefix("data: ")) for ln in data_lines]
    assert [p["type"] for p in payloads] == ["meta", "progress", "image", "done"]


def test_generate_stream_sse_maps_worker_exception(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    def fake_iter(*_a: object, **_k: object):
        raise ConfigurationError("bad cfg")

    monkeypatch.setattr("dts_utils.web.app.iter_generate_stream_dicts", fake_iter)
    with client.stream(
        "POST",
        "/api/generate/stream",
        json={
            "prompt": "hi",
            "host": "127.0.0.1",
            "port": 7859,
            "trust_server_cert": True,
            "no_tls": True,
        },
    ) as r:
        assert r.status_code == 200
        raw = r.read().decode("utf-8")
    data_lines = [ln for ln in raw.splitlines() if ln.startswith("data: ")]
    assert len(data_lines) == 1
    body = json.loads(data_lines[0].removeprefix("data: "))
    assert body["type"] == "error"
    assert "bad cfg" in str(body["detail"])


def test_generate_stream_wall_clock_timeout_emits_sse_error(
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
) -> None:
    """Expired deadline yields SSE error; drain path must unblock the worker (bounded queue)."""

    monkeypatch.setattr("dts_utils.web.app._generate_timeout_seconds", lambda: -1.0)

    def fake_iter(*_a: object, **_k: object):
        yield {"type": "meta", "total_runs": 1}
        yield {
            "type": "done",
            "expanded_prompts": ["x"],
            "expanded_negative_prompts": [""],
            "total_images": 0,
        }

    monkeypatch.setattr("dts_utils.web.app.iter_generate_stream_dicts", fake_iter)
    with client.stream(
        "POST",
        "/api/generate/stream",
        json={
            "prompt": "hi",
            "host": "127.0.0.1",
            "port": 7859,
            "trust_server_cert": True,
            "no_tls": True,
        },
    ) as r:
        assert r.status_code == 200
        raw = r.read().decode("utf-8")

    data_lines = [ln for ln in raw.splitlines() if ln.startswith("data: ")]
    assert len(data_lines) == 1
    body = json.loads(data_lines[0].removeprefix("data: "))
    assert body["type"] == "error"
    assert body["detail"] == "Generation timed out."


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

    def fake_batch(_c: object, _g: object, *,
        generations: int = 1,
        cancel_event=None,
        prompts_per_run=None,
        negative_prompts_per_run=None,
    ) -> GeneratePngBatchResult:
        return GeneratePngBatchResult(
            images=[b"\x89PNG\r\n\x1a\nplaceholder", b"\x89PNG\r\n\x1a\nother"],
            expanded_prompts=["a sunset"],
            expanded_negative_prompts=[""],
        )

    monkeypatch.setattr("dts_utils.web.app.generate_png_batch", fake_batch)
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


def test_generate_multipart_includes_expanded_wildcards_header(
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
) -> None:
    import base64
    import json

    def fake_batch(_c: object, _g: object, *,
        generations: int = 1,
        cancel_event=None,
        prompts_per_run=None,
        negative_prompts_per_run=None,
    ) -> GeneratePngBatchResult:
        return GeneratePngBatchResult(
            images=[b"\x89PNG\r\n\x1a\nx"],
            expanded_prompts=["expanded prompt"],
            expanded_negative_prompts=["bad"],
        )

    monkeypatch.setattr("dts_utils.web.app.generate_png_batch", fake_batch)
    r = client.post(
        "/api/generate",
        json={
            "prompt": "template",
            "host": "127.0.0.1",
            "port": 7859,
            "trust_server_cert": True,
            "no_tls": True,
        },
    )
    assert r.status_code == 200
    b64 = r.headers.get("x-expanded-wildcards-b64")
    assert b64
    payload = json.loads(base64.standard_b64decode(b64).decode("utf-8"))
    assert payload["prompts"] == ["expanded prompt"]
    assert payload["negative_prompts"] == ["bad"]


def test_generate_multipart_respects_generations(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    def fake_batch(_c: object, _g: object, *,
        generations: int = 1,
        cancel_event=None,
        prompts_per_run=None,
        negative_prompts_per_run=None,
    ) -> GeneratePngBatchResult:
        assert generations == 2
        return GeneratePngBatchResult(
            images=[b"\x89PNG\r\n\x1a\nx", b"\x89PNG\r\n\x1a\ny"],
            expanded_prompts=["first", "second"],
            expanded_negative_prompts=["", ""],
        )

    monkeypatch.setattr("dts_utils.web.app.generate_png_batch", fake_batch)
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


def test_prompt_expand_get_describes_post_contract(client: TestClient) -> None:
    r = client.get("/api/prompt/expand")
    assert r.status_code == 200
    data = r.json()
    assert data.get("method") == "POST"
    assert "body" in data


def test_prompt_expand_ok(client: TestClient) -> None:
    r = client.post(
        "/api/prompt/expand",
        json={"prompt": "{a|b}", "negative_prompt": "{x|y}", "count": 2},
    )
    assert r.status_code == 200
    data = r.json()
    assert len(data["prompts"]) == 2
    assert len(data["negative_prompts"]) == 2
    assert all(p in {"a", "b"} for p in data["prompts"])
    assert all(n in {"x", "y"} for n in data["negative_prompts"])


def test_prompt_expand_invalid_wildcard_returns_400(client: TestClient) -> None:
    r = client.post("/api/prompt/expand", json={"prompt": "{||}", "count": 1})
    assert r.status_code == 400
    assert "Unresolved" in r.json()["detail"]


def test_prompt_expand_requires_bearer_when_token_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DTS_WEB_TOKEN", "sekrit")
    client = TestClient(create_app())
    assert client.get("/api/prompt/expand").status_code == 401
    assert client.post("/api/prompt/expand", json={"prompt": "x", "count": 1}).status_code == 401
    r = client.post(
        "/api/prompt/expand",
        json={"prompt": "{a|b}", "count": 1},
        headers={"Authorization": "Bearer sekrit"},
    )
    assert r.status_code == 200


def test_generate_prompts_length_must_match_generations(client: TestClient) -> None:
    r = client.post(
        "/api/generate",
        json={
            "prompts": ["only"],
            "generations": 2,
            "no_tls": True,
        },
    )
    assert r.status_code == 400
    assert "length" in r.json()["detail"].lower()


def test_generate_negative_prompts_length_must_match_generations(client: TestClient) -> None:
    r = client.post(
        "/api/generate",
        json={
            "prompts": ["a", "b"],
            "negative_prompts": [""],
            "generations": 2,
            "no_tls": True,
        },
    )
    assert r.status_code == 400


def test_generate_accepts_prompts_array(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    captured: dict[str, object] = {}

    def fake_batch(
        _c: object,
        _g: object,
        *,
        generations: int = 1,
        cancel_event=None,
        prompts_per_run=None,
        negative_prompts_per_run=None,
    ) -> GeneratePngBatchResult:
        captured["prompts_per_run"] = prompts_per_run
        captured["negative_prompts_per_run"] = negative_prompts_per_run
        assert generations == 2
        return GeneratePngBatchResult(
            images=[b"\x89PNG\r\n\x1a\nx", b"\x89PNG\r\n\x1a\ny"],
            expanded_prompts=["a", "b"],
            expanded_negative_prompts=["", "blur"],
        )

    monkeypatch.setattr("dts_utils.web.app.generate_png_batch", fake_batch)
    r = client.post(
        "/api/generate",
        json={
            "prompts": ["hello", "there"],
            "negative_prompts": ["", "blur"],
            "generations": 2,
            "host": "127.0.0.1",
            "port": 7859,
            "trust_server_cert": True,
            "no_tls": True,
        },
    )
    assert r.status_code == 200
    assert captured["prompts_per_run"] == ["hello", "there"]
    assert captured["negative_prompts_per_run"] == ["", "blur"]


def test_generate_unauthorized_when_token_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DTS_WEB_TOKEN", "sekrit")
    client = TestClient(create_app())
    r = client.post("/api/generate", json={"prompt": "x", "no_tls": True})
    assert r.status_code == 401


def test_generate_stream_unauthorized_when_token_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DTS_WEB_TOKEN", "sekrit")
    client = TestClient(create_app())
    r = client.post("/api/generate/stream", json={"prompt": "x", "no_tls": True})
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
    def boom(*_a: object, **_k: object) -> None:
        raise GenerationCancelledError("Generation cancelled.")

    monkeypatch.setattr("dts_utils.web.app.generate_png_batch", boom)
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


def test_web_cli_router_passes_argv_to_web_main(monkeypatch: pytest.MonkeyPatch) -> None:
    import dts_utils.cli_router as cr

    monkeypatch.setattr("sys.argv", ["dts-utils", "web", "--port", "19999"])
    called: dict[str, object] = {}

    def fake_main(argv: list[str] | None) -> int:
        called["argv"] = list(argv or [])
        return 0

    monkeypatch.setattr(cr, "web_main", fake_main)
    with pytest.raises(SystemExit) as se:
        cr.main()
    assert se.value.code == 0
    assert called["argv"] == ["--port", "19999"]
