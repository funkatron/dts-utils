"""Pipeline executors for Apple-first media workflows."""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from dts_utils.pipeline.contracts import ImageRef, VideoRef, run_layout_paths


def _iso_now() -> str:
    return datetime.now(UTC).isoformat()


def _artifact_id(run_id: str, step_id: str, cache_key: str) -> str:
    return f"{run_id}-{step_id}-{cache_key[:12]}"


def _runtime_version(package: str) -> str:
    try:
        return version(package)
    except PackageNotFoundError:
        return "not-installed"


@dataclass(slots=True)
class ExecutorResult:
    artifact: ImageRef | VideoRef
    model: dict[str, Any]
    metadata: dict[str, Any]


@dataclass(slots=True)
class SubprocessExecutor:
    """Subprocess-backed executor wrapper over `dts_utils.pipeline.worker`."""

    name: str
    step_kind: str
    mode: str
    artifact_basename: str
    cache_namespace: str
    model_id: str
    model_sha256: str
    backend: str
    executor_version: str = "0.1.0"

    def model_fingerprint(self) -> str:
        return f"{self.model_id}:{self.model_sha256}:{self.backend}"

    def execute(
        self,
        *,
        run_root: Path,
        run_id: str,
        step_id: str,
        cache_key: str,
        request: dict[str, Any],
        parent_artifact_ids: list[str],
    ) -> ExecutorResult:
        layout = run_layout_paths(run_root, run_id, step_id, self.artifact_basename)
        layout["step_dir"].mkdir(parents=True, exist_ok=True)
        request_path = layout["step_dir"] / "request.json"
        request_path.write_text(json.dumps(request, sort_keys=True), encoding="utf-8")

        cmd = [
            sys.executable,
            "-m",
            "dts_utils.pipeline.worker",
            "--mode",
            self.mode,
            "--request-json",
            str(request_path),
            "--artifact-path",
            str(layout["artifact_path"]),
            "--metadata-path",
            str(layout["artifact_metadata_path"]),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            stderr = (proc.stderr or proc.stdout or "subprocess failed").strip()
            raise RuntimeError(stderr)

        output_meta = json.loads(layout["artifact_metadata_path"].read_text(encoding="utf-8"))
        common = {
            "artifact_id": _artifact_id(run_id, step_id, cache_key),
            "format": layout["artifact_path"].suffix.lstrip("."),
            "path": str(layout["artifact_path"]),
            "metadata_path": str(layout["artifact_metadata_path"]),
            "created_by_step": step_id,
            "parent_artifact_ids": parent_artifact_ids,
        }
        if self.step_kind == "text_to_image":
            artifact: ImageRef | VideoRef = ImageRef(kind="image", width=int(output_meta["width"]), height=int(output_meta["height"]), **common)
        else:
            artifact = VideoRef(
                kind="video",
                width=int(output_meta["width"]),
                height=int(output_meta["height"]),
                fps=int(output_meta["fps"]),
                seconds=float(output_meta["seconds"]),
                **common,
            )

        model = {
            "id": self.model_id,
            "sha256": self.model_sha256,
            "backend": self.backend,
            "fingerprint": self.model_fingerprint(),
        }
        metadata = {
            "mode": self.mode,
            "worker_started_at": _iso_now(),
            "stderr_truncated": proc.stderr[-800:] if proc.stderr else "",
            "request_path": str(request_path),
            "output_meta": output_meta,
        }
        return ExecutorResult(artifact=artifact, model=model, metadata=metadata)


class StubTextToImageExecutor(SubprocessExecutor):
    def __init__(self) -> None:
        super().__init__(
            name="stub_text_to_image",
            step_kind="text_to_image",
            mode="text_to_image_stub",
            artifact_basename="image.png",
            cache_namespace="text_to_image_stub",
            model_id="stub/rgb",
            model_sha256="stub",
            backend="python-pillow",
        )


class SdxlTextToImageExecutor(SubprocessExecutor):
    """SDXL executor wrapper with runtime metadata for MPS/MLX decisions."""

    def __init__(self, *, runtime: str = "pytorch-mps", model_id: str = "sdxl-turbo", model_sha256: str = "unknown") -> None:
        mode = "text_to_image_sdxl"
        backend = "pytorch-mps" if runtime == "pytorch-mps" else "mlx"
        super().__init__(
            name="sdxl_text_to_image",
            step_kind="text_to_image",
            mode=mode,
            artifact_basename="image.png",
            cache_namespace=f"text_to_image_sdxl_{backend}",
            model_id=model_id,
            model_sha256=model_sha256,
            backend=backend,
        )
        self.runtime = runtime

    def execute(self, **kwargs: Any) -> ExecutorResult:
        res = super().execute(**kwargs)
        package = "torch" if self.runtime == "pytorch-mps" else "mlx"
        res.model["runtime_package"] = package
        res.model["runtime_version"] = _runtime_version(package)
        return res


class ZImageTurboTextToImageExecutor(SubprocessExecutor):
    def __init__(self, *, model_sha256: str = "unknown") -> None:
        super().__init__(
            name="z_image_turbo_text_to_image",
            step_kind="text_to_image",
            mode="text_to_image_z_image_turbo",
            artifact_basename="image.png",
            cache_namespace="text_to_image_z_image_turbo",
            model_id="z-image-turbo-1.0-exact",
            model_sha256=model_sha256,
            backend="pytorch-mps",
        )


class LtxImageToVideoExecutor(SubprocessExecutor):
    def __init__(self, *, model_sha256: str = "unknown") -> None:
        super().__init__(
            name="ltx_image_to_video",
            step_kind="image_to_video",
            mode="image_to_video_ltx",
            artifact_basename="video.mp4",
            cache_namespace="image_to_video_ltx",
            model_id="ltx-2.3-22b-distilled-exact",
            model_sha256=model_sha256,
            backend="ltx-runtime",
        )
