"""Pipeline executors for Apple-first media workflows."""

from __future__ import annotations

import json
import subprocess
import sys
from io import BytesIO
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from PIL import Image

from dts_utils.configuration_build import read_configuration_json_dict
from dts_utils.exceptions import ConfigurationError
from dts_utils.generate_api import (
    GrpcClientOptions,
    ImageGenerationRequestOptions,
    generate_png_bytes,
    generate_video_mp4_bytes,
)
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


class PlaceholderImageToVideoExecutor(SubprocessExecutor):
    """ffmpeg flipbook / loop placeholder (no Draw Things video inference)."""

    def __init__(self, *, model_sha256: str = "unknown") -> None:
        super().__init__(
            name="placeholder_image_to_video",
            step_kind="image_to_video",
            mode="image_to_video_placeholder",
            artifact_basename="video.mp4",
            cache_namespace="image_to_video_placeholder",
            model_id="placeholder/ffmpeg",
            model_sha256=model_sha256,
            backend="ffmpeg-placeholder",
        )


# Back-compat alias (presets/docs may still say "ltx" for the placeholder step).
LtxImageToVideoExecutor = PlaceholderImageToVideoExecutor


class DrawThingsGrpcImageToVideoExecutor(SubprocessExecutor):
    """Image-to-video via Draw Things ``GenerateImage`` (input image tensor + frame mux)."""

    def __init__(
        self,
        *,
        host: str = "localhost",
        port: int = 7859,
        no_tls: bool = False,
        root_cert: Path | None = None,
        trust_server_cert: bool = False,
        force_trust_server_cert: bool = False,
        max_message_mb: int = 64,
        user: str = "dts-utils",
        shared_secret: str | None = None,
        video_configuration: str | Path | None = None,
        video_configuration_json: str | Path | None = None,
    ) -> None:
        super().__init__(
            name="drawthings_grpc_image_to_video",
            step_kind="image_to_video",
            mode="drawthings_grpc_image_to_video",
            artifact_basename="video.mp4",
            cache_namespace="image_to_video_drawthings_grpc",
            model_id="drawthings-grpc-video",
            model_sha256="n/a",
            backend="drawthings-grpc",
        )
        self.client_opts = GrpcClientOptions(
            host=host,
            port=port,
            no_tls=no_tls,
            root_cert=root_cert,
            trust_server_cert=trust_server_cert,
            force_trust_server_cert=force_trust_server_cert,
            max_message_mb=max_message_mb,
        )
        self.user = user
        self.shared_secret = shared_secret
        self.video_configuration = video_configuration
        self.video_configuration_json = video_configuration_json

    def model_fingerprint(self) -> str:
        cfg = self.video_configuration or self.video_configuration_json or ""
        return (
            f"{self.model_id}:{self.backend}:{cfg}:{self.client_opts.host}:{self.client_opts.port}:"
            f"{int(self.client_opts.no_tls)}"
        )

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
        image_path = Path(str(request.get("image_path", "")))
        if not image_path.is_file():
            raise ValueError(f"input image not found: {image_path}")
        configuration = request.get("configuration", self.video_configuration)
        configuration_json = request.get("configuration_json", self.video_configuration_json)
        if not configuration and not configuration_json:
            raise ValueError(
                "either configuration or configuration_json is required for Draw Things image-to-video"
            )
        prompt = str(request.get("prompt", "")).strip()
        if not prompt:
            raise ValueError("prompt is required for Draw Things image-to-video")

        layout = run_layout_paths(run_root, run_id, step_id, self.artifact_basename)
        layout["step_dir"].mkdir(parents=True, exist_ok=True)
        requested_fps = int(request["fps"]) if request.get("fps") is not None else 24
        requested_seconds = float(request["seconds"]) if request.get("seconds") is not None else 1.0
        configuration, configuration_json = self._materialize_video_configuration(
            configuration=configuration,
            configuration_json=configuration_json,
            requested_fps=requested_fps,
            requested_seconds=requested_seconds,
            out_dir=layout["step_dir"],
            config_dir=Path(str(request["config_dir"])) if request.get("config_dir") else None,
        )
        gen = ImageGenerationRequestOptions(
            prompt=prompt,
            negative_prompt=str(request.get("negative_prompt", "")),
            configuration=configuration,
            configuration_json=configuration_json,
            user=str(request.get("user", self.user)),
            shared_secret=request.get("shared_secret", self.shared_secret),
            config_dir=Path(str(request["config_dir"])) if request.get("config_dir") else None,
        )
        mp4, output_meta = generate_video_mp4_bytes(
            self.client_opts,
            gen,
            input_image_path=image_path,
            output_fps=requested_fps,
            scale_width=int(request["width"]) if request.get("width") is not None else None,
            scale_height=int(request["height"]) if request.get("height") is not None else None,
        )
        frame_count = int(output_meta.get("frame_count", 0) or 0)
        if frame_count <= 1 and requested_seconds > (1.0 / max(1, requested_fps)):
            raise RuntimeError(
                "Draw Things image-to-video returned a single frame. "
                "Adjust video configuration (numFrames/fps) or prompt/model settings."
            )
        layout["artifact_path"].write_bytes(mp4)
        layout["artifact_metadata_path"].write_text(json.dumps(output_meta, sort_keys=True), encoding="utf-8")
        artifact = VideoRef(
            artifact_id=_artifact_id(run_id, step_id, cache_key),
            kind="video",
            format=layout["artifact_path"].suffix.lstrip("."),
            path=str(layout["artifact_path"]),
            metadata_path=str(layout["artifact_metadata_path"]),
            created_by_step=step_id,
            parent_artifact_ids=parent_artifact_ids,
            width=int(output_meta["width"]),
            height=int(output_meta["height"]),
            fps=int(output_meta["fps"]),
            seconds=float(output_meta["seconds"]),
        )
        model = {
            "id": self.model_id,
            "sha256": self.model_sha256,
            "backend": self.backend,
            "fingerprint": self.model_fingerprint(),
        }
        metadata = {
            "mode": self.mode,
            "prompt": prompt,
            "negative_prompt": str(request.get("negative_prompt", "")),
            "requested_seconds": requested_seconds,
            "requested_fps": requested_fps,
            "output_meta": output_meta,
        }
        return ExecutorResult(artifact=artifact, model=model, metadata=metadata)

    def _materialize_video_configuration(
        self,
        *,
        configuration: str | Path | None,
        configuration_json: str | Path | None,
        requested_fps: int,
        requested_seconds: float,
        out_dir: Path,
        config_dir: Path | None,
    ) -> tuple[str | Path | None, str | Path | None]:
        """Override fps/numFrames in JSON profiles to request multi-frame video explicitly."""
        target_fps = max(1, int(requested_fps))
        target_frames = max(2, int(round(max(requested_seconds, 0.1) * target_fps)))
        try:
            cfg = read_configuration_json_dict(
                configuration=configuration,
                configuration_json=configuration_json,
                config_dir=config_dir,
            )
        except ConfigurationError:
            # Raw flatbuffer path or unresolved JSON name; use original input as-is.
            return configuration, configuration_json
        cfg = self._maybe_seed_ltx_video_config(cfg, config_dir=config_dir)
        cfg["numFrames"] = target_frames
        cfg["fps"] = target_fps
        override_path = out_dir / "video_configuration.override.json"
        override_path.write_text(json.dumps(cfg, indent=2, sort_keys=True), encoding="utf-8")
        return None, override_path

    def _maybe_seed_ltx_video_config(self, cfg: dict[str, Any], *, config_dir: Path | None) -> dict[str, Any]:
        model = str(cfg.get("model", "")).lower()
        if "ltx" not in model or "numFrames" in cfg:
            return cfg
        for candidate in (
            "ltx-2.3-portrait",
            "ltx-2.3-landscape",
            "ltx-2.3-22b-port",
            "ltx-2.3-22b",
            "LTX-2.3-22B-Port",
            "LTX-2.3-22B",
        ):
            try:
                seeded = read_configuration_json_dict(configuration=candidate, config_dir=config_dir)
            except ConfigurationError:
                continue
            # Preserve exact checkpoint and explicit scalar controls from the source config.
            if isinstance(cfg.get("model"), str) and str(cfg["model"]).strip():
                seeded["model"] = cfg["model"]
            for key in ("width", "height", "steps"):
                if key in cfg:
                    seeded[key] = cfg[key]
            return seeded
        return cfg


class DrawThingsPromptTextToImageExecutor(SubprocessExecutor):
    """Prompt-driven T2I via Draw Things gRPC before I2V."""

    def __init__(
        self,
        *,
        host: str = "localhost",
        port: int = 7859,
        no_tls: bool = False,
        root_cert: Path | None = None,
        trust_server_cert: bool = False,
        force_trust_server_cert: bool = False,
        max_message_mb: int = 64,
        user: str = "dts-utils",
        shared_secret: str | None = None,
    ) -> None:
        super().__init__(
            name="drawthings_prompt_text_to_image",
            step_kind="text_to_image",
            mode="drawthings_prompt_text_to_image",
            artifact_basename="image.png",
            cache_namespace="text_to_image_drawthings_prompt",
            model_id="drawthings-grpc",
            model_sha256="n/a",
            backend="drawthings-grpc",
        )
        self.client_opts = GrpcClientOptions(
            host=host,
            port=port,
            no_tls=no_tls,
            root_cert=root_cert,
            trust_server_cert=trust_server_cert,
            force_trust_server_cert=force_trust_server_cert,
            max_message_mb=max_message_mb,
        )
        self.user = user
        self.shared_secret = shared_secret

    def model_fingerprint(self) -> str:
        return (
            f"{self.model_id}:{self.backend}:{self.client_opts.host}:{self.client_opts.port}:"
            f"{int(self.client_opts.no_tls)}"
        )

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
        prompt = str(request.get("prompt", "")).strip()
        if not prompt:
            raise ValueError("prompt is required for drawthings prompt executor")
        configuration = request.get("configuration")
        configuration_json = request.get("configuration_json")
        if not configuration and not configuration_json:
            raise ValueError("either configuration or configuration_json is required for prompt generation")

        layout = run_layout_paths(run_root, run_id, step_id, self.artifact_basename)
        layout["step_dir"].mkdir(parents=True, exist_ok=True)
        gen = ImageGenerationRequestOptions(
            prompt=prompt,
            negative_prompt=str(request.get("negative_prompt", "")),
            configuration=configuration,
            configuration_json=configuration_json,
            user=str(request.get("user", self.user)),
            shared_secret=request.get("shared_secret", self.shared_secret),
            config_dir=Path(str(request["config_dir"])) if request.get("config_dir") else None,
        )
        pngs = generate_png_bytes(self.client_opts, gen, generations=1)
        if not pngs:
            raise RuntimeError("Draw Things returned no images")
        png = pngs[0]
        layout["artifact_path"].write_bytes(png)
        with Image.open(BytesIO(png)) as img:
            width, height = img.size
        output_meta = {"width": width, "height": height, "source": "drawthings_prompt"}
        layout["artifact_metadata_path"].write_text(json.dumps(output_meta, sort_keys=True), encoding="utf-8")
        artifact = ImageRef(
            artifact_id=_artifact_id(run_id, step_id, cache_key),
            kind="image",
            format=layout["artifact_path"].suffix.lstrip("."),
            path=str(layout["artifact_path"]),
            metadata_path=str(layout["artifact_metadata_path"]),
            created_by_step=step_id,
            parent_artifact_ids=parent_artifact_ids,
            width=width,
            height=height,
        )
        model = {
            "id": self.model_id,
            "sha256": self.model_sha256,
            "backend": self.backend,
            "fingerprint": self.model_fingerprint(),
        }
        metadata = {
            "mode": self.mode,
            "prompt": prompt,
            "negative_prompt": str(request.get("negative_prompt", "")),
            "output_meta": output_meta,
        }
        return ExecutorResult(artifact=artifact, model=model, metadata=metadata)
