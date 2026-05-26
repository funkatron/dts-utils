from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from starlette.testclient import TestClient

from dts_utils.pipeline.contracts import PipelineRunManifest
from dts_utils.web.app import create_app


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def test_index_mentions_pipeline_run(client: TestClient) -> None:
    r = client.get("/")
    assert r.status_code == 200
    assert "/api/pipeline/run/stream" in r.text
    assert "Run pipeline" in r.text


def test_pipeline_run_stream_requires_pipeline_profile(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    monkeypatch.setattr("dts_utils.web.app.is_pipeline_profile", lambda _name: False)
    r = client.post(
        "/api/pipeline/run/stream",
        json={
            "profile": "default",
            "prompt": "hello",
            "host": "127.0.0.1",
            "port": 7859,
            "no_tls": True,
            "trust_server_cert": True,
        },
    )
    assert r.status_code == 400
    assert "not a pipeline profile" in r.json()["detail"]


def test_pipeline_run_stream_sse(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, client: TestClient
) -> None:
    monkeypatch.setattr("dts_utils.web.app.is_pipeline_profile", lambda _name: True)
    monkeypatch.setattr("dts_utils.web.app._pipeline_run_root", lambda: tmp_path)

    image_path = tmp_path / "run-1" / "t2i" / "image.png"
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(b"\x89PNG\r\n\x1a\n")
    video_path = tmp_path / "run-1" / "i2v" / "video.mp4"
    video_path.parent.mkdir(parents=True, exist_ok=True)
    video_path.write_bytes(b"\x00\x00\x00\x18ftyp")

    manifest = PipelineRunManifest(
        run_id="run-1",
        run_root=str(tmp_path),
        steps=[],
        artifacts=[
            {
                "kind": "image",
                "path": str(image_path),
                "created_by_step": "t2i",
            },
            {
                "kind": "video",
                "path": str(video_path),
                "created_by_step": "i2v",
            },
        ],
    )

    class FakeRunner:
        def __init__(self, *args, **kwargs):
            pass

        def run(self, *, run_id, steps):
            return manifest

    monkeypatch.setattr("dts_utils.web.app.PipelineRunner", FakeRunner)
    monkeypatch.setattr(
        "dts_utils.web.app.prepare_pipeline_run",
        lambda req: (
            SimpleNamespace(
                run_id="run-1",
                run_root=tmp_path,
                allow_cache=True,
                max_oom_retries=1,
            ),
            None,
        ),
    )
    monkeypatch.setattr("dts_utils.web.app.build_pipeline_steps", lambda *_a, **_k: [1, 2])
    monkeypatch.setattr("dts_utils.web.app.validate_pipeline_run", lambda *_a, **_k: None)

    with client.stream(
        "POST",
        "/api/pipeline/run/stream",
        json={
            "profile": "infomux",
            "prompt": "sunset",
            "host": "127.0.0.1",
            "port": 7859,
            "no_tls": True,
            "trust_server_cert": True,
        },
    ) as response:
        assert response.status_code == 200
        chunks = list(response.iter_text())

    body = "".join(chunks)
    assert '"type": "meta"' in body or '"type":"meta"' in body
    assert '"type": "done"' in body or '"type":"done"' in body

    artifact_r = client.get("/api/pipeline/artifact/run-1/t2i/image.png")
    assert artifact_r.status_code == 200
    assert artifact_r.content.startswith(b"\x89PNG")
