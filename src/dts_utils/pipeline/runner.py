"""Pipeline runner with step manifests, cache, and retry policy."""

from __future__ import annotations

import json
import platform as py_platform
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dts_utils.pipeline.cache import cache_request_payload, stable_sha256, step_cache_key
from dts_utils.pipeline.contracts import PipelineRunManifest, StepRun, run_layout_paths
from dts_utils.pipeline.executors import SubprocessExecutor


def _iso_now() -> str:
    return datetime.now(UTC).isoformat()


def _platform_dict() -> dict[str, str]:
    return {
        "system": py_platform.system(),
        "machine": py_platform.machine(),
        "python": py_platform.python_version(),
        "platform": py_platform.platform(),
    }


@dataclass(slots=True)
class PipelineStep:
    step_id: str
    executor: SubprocessExecutor
    request: dict[str, Any] = field(default_factory=dict)
    input_from_step: str | None = None


class PipelineRunner:
    """Sequential runner with file-backed cache index."""

    def __init__(self, run_root: Path, *, allow_cache: bool = True, max_oom_retries: int = 1) -> None:
        self.run_root = run_root
        self.allow_cache = allow_cache
        self.max_oom_retries = max_oom_retries
        self.run_root.mkdir(parents=True, exist_ok=True)
        self._cache_index_path = self.run_root / "cache_index.json"

    def _read_cache(self) -> dict[str, Any]:
        if self._cache_index_path.exists():
            return json.loads(self._cache_index_path.read_text(encoding="utf-8"))
        return {}

    def _write_cache(self, cache: dict[str, Any]) -> None:
        self._cache_index_path.write_text(json.dumps(cache, indent=2, sort_keys=True), encoding="utf-8")

    def run(self, *, run_id: str, steps: list[PipelineStep]) -> PipelineRunManifest:
        cache = self._read_cache()
        step_records: list[dict[str, Any]] = []
        artifacts: list[dict[str, Any]] = []
        artifacts_by_step: dict[str, dict[str, Any]] = {}
        run_dir = self.run_root / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        heartbeat_path = run_dir / "heartbeat.json"

        def write_heartbeat(step_index: int, step_id: str, status: str) -> None:
            remaining = max(0, len(steps) - step_index - (1 if status == "completed" else 0))
            payload = {
                "run_id": run_id,
                "step_id": step_id,
                "step_index": step_index,
                "total_steps": len(steps),
                "status": status,
                "estimated_remaining_steps": remaining,
                "updated_at": _iso_now(),
            }
            heartbeat_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

        for idx, step in enumerate(steps):
            write_heartbeat(idx, step.step_id, "running")
            request = dict(step.request)
            parent_ids: list[str] = []
            if step.input_from_step:
                if step.input_from_step not in artifacts_by_step:
                    raise ValueError(f"Missing upstream step output: {step.input_from_step}")
                source = artifacts_by_step[step.input_from_step]
                parent_ids = [source["artifact_id"]]
                request.setdefault("image_path", source["path"])
                request.setdefault("width", source.get("width", request.get("width", 1024)))
                request.setdefault("height", source.get("height", request.get("height", 1024)))

            started = _iso_now()
            step_status = "completed"
            metadata: dict[str, Any] = {}
            artifact: dict[str, Any]
            model: dict[str, Any]
            retries = 0

            while True:
                cache_payload = cache_request_payload(request)
                input_hash = stable_sha256({"request": cache_payload, "parents": parent_ids})
                ck = step_cache_key(
                    cache_namespace=step.executor.cache_namespace,
                    executor_version=step.executor.executor_version,
                    request_payload=request,
                    upstream_artifact_ids=parent_ids,
                    model_fingerprint=step.executor.model_fingerprint(),
                )
                cached = cache.get(ck, {})
                if self.allow_cache and ck in cache and Path(cached.get("path", "")).exists():
                    artifact = cached
                    step_status = "cached"
                    metadata["cache_hit"] = True
                    model = {
                        "id": step.executor.model_id,
                        "sha256": step.executor.model_sha256,
                        "backend": step.executor.backend,
                        "fingerprint": step.executor.model_fingerprint(),
                    }
                    break

                try:
                    result = step.executor.execute(
                        run_root=self.run_root,
                        run_id=run_id,
                        step_id=step.step_id,
                        cache_key=ck,
                        request=request,
                        parent_artifact_ids=parent_ids,
                    )
                    artifact = result.artifact.to_dict()
                    metadata.update(result.metadata)
                    model = result.model
                    cache[ck] = artifact
                    self._write_cache(cache)
                    break
                except RuntimeError as e:
                    if (
                        step.executor.step_kind == "image_to_video"
                        and "out of memory" in str(e).lower()
                        and retries < self.max_oom_retries
                    ):
                        retries += 1
                        request["width"] = max(512, int(request.get("width", 1024)) // 2)
                        request["height"] = max(288, int(request.get("height", 576)) // 2)
                        request["seconds"] = max(1.0, float(request.get("seconds", 2.0)) / 2.0)
                        # Test/dev knob: only simulate one OOM failure before retry.
                        request.pop("simulate_oom", None)
                        metadata.setdefault("oom_retries", []).append(
                            {
                                "retry": retries,
                                "width": request["width"],
                                "height": request["height"],
                                "seconds": request["seconds"],
                            }
                        )
                        continue
                    raise

            artifacts.append(artifact)
            artifacts_by_step[step.step_id] = artifact
            finished = _iso_now()
            step_record = StepRun(
                run_id=run_id,
                step_id=step.step_id,
                step_kind=step.executor.step_kind,
                status=step_status,  # type: ignore[arg-type]
                executor=step.executor.name,
                executor_version=step.executor.executor_version,
                cache_namespace=step.executor.cache_namespace,
                cache_key=ck,
                input_hash=input_hash,
                started_at=started,
                finished_at=finished,
                platform=_platform_dict(),
                model=model,
                outputs=[artifact],
                metadata=metadata,
            )
            step_records.append(step_record.to_dict())
            layout = run_layout_paths(self.run_root, run_id, step.step_id, step.executor.artifact_basename)
            layout["step_run_path"].parent.mkdir(parents=True, exist_ok=True)
            layout["step_run_path"].write_text(json.dumps(step_record.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
            write_heartbeat(idx, step.step_id, "completed")

        manifest = PipelineRunManifest(run_id=run_id, run_root=str(self.run_root), steps=step_records, artifacts=artifacts)
        (run_dir / "pipeline_run.json").write_text(json.dumps(manifest.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
        return manifest
