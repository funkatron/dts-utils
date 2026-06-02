"""Cache key helpers for pipeline step runs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

_FILE_PATH_REQUEST_KEYS = ("image_path",)


def stable_sha256(payload: Any) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def file_content_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def cache_request_payload(request: dict[str, Any]) -> dict[str, Any]:
    """Normalize request for cache keys; file paths include content hashes."""
    payload = dict(request)
    for key in _FILE_PATH_REQUEST_KEYS:
        raw = payload.get(key)
        if raw is None:
            continue
        path = Path(str(raw))
        if not path.is_file():
            continue
        payload[key] = {"path": str(path.resolve()), "content_sha256": file_content_sha256(path)}
    return payload


def step_cache_key(
    *,
    cache_namespace: str,
    executor_version: str,
    request_payload: dict[str, Any],
    upstream_artifact_ids: list[str],
    model_fingerprint: str,
) -> str:
    return stable_sha256(
        {
            "cache_namespace": cache_namespace,
            "executor_version": executor_version,
            "request": cache_request_payload(request_payload),
            "upstream_artifact_ids": sorted(upstream_artifact_ids),
            "model_fingerprint": model_fingerprint,
        }
    )
