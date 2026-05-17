"""Cache key helpers for pipeline step runs."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def stable_sha256(payload: Any) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


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
            "request": request_payload,
            "upstream_artifact_ids": sorted(upstream_artifact_ids),
            "model_fingerprint": model_fingerprint,
        }
    )
