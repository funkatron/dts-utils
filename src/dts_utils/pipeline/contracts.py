"""Contracts for pipeline step runs and artifact handoffs."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal


ArtifactKind = Literal["image", "video"]
ArtifactFormat = Literal["png", "tiff", "mp4", "mov"]
StepStatus = Literal["completed", "failed", "cached"]


@dataclass(slots=True)
class ArtifactRef:
    """Typed reference to an immutable run artifact."""

    artifact_id: str
    kind: ArtifactKind
    format: ArtifactFormat
    path: str
    metadata_path: str
    created_by_step: str
    parent_artifact_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ImageRef(ArtifactRef):
    width: int = 0
    height: int = 0


@dataclass(slots=True)
class VideoRef(ArtifactRef):
    width: int = 0
    height: int = 0
    fps: int = 0
    seconds: float = 0.0


@dataclass(slots=True)
class StepRun:
    """Manifest for one step execution attempt."""

    run_id: str
    step_id: str
    step_kind: str
    status: StepStatus
    executor: str
    executor_version: str
    cache_namespace: str
    cache_key: str
    input_hash: str
    started_at: str
    finished_at: str
    platform: dict[str, str]
    model: dict[str, Any]
    outputs: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PipelineRunManifest:
    run_id: str
    run_root: str
    steps: list[dict[str, Any]]
    artifacts: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def run_layout_paths(run_root: Path, run_id: str, step_id: str, artifact_basename: str) -> dict[str, Path]:
    """Canonical on-disk layout for run/step artifact + sidecars."""
    step_dir = run_root / run_id / step_id
    artifact_path = step_dir / artifact_basename
    artifact_json = artifact_path.with_suffix(f"{artifact_path.suffix}.json")
    step_run_json = step_dir / "step_run.json"
    return {
        "step_dir": step_dir,
        "artifact_path": artifact_path,
        "artifact_metadata_path": artifact_json,
        "step_run_path": step_run_json,
    }


def image_ref_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["artifact_id", "kind", "format", "path", "metadata_path", "created_by_step", "width", "height"],
        "properties": {
            "artifact_id": {"type": "string"},
            "kind": {"const": "image"},
            "format": {"enum": ["png", "tiff"]},
            "path": {"type": "string"},
            "metadata_path": {"type": "string"},
            "created_by_step": {"type": "string"},
            "parent_artifact_ids": {"type": "array", "items": {"type": "string"}},
            "width": {"type": "integer", "minimum": 1},
            "height": {"type": "integer", "minimum": 1},
        },
        "additionalProperties": False,
    }


def video_ref_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": [
            "artifact_id",
            "kind",
            "format",
            "path",
            "metadata_path",
            "created_by_step",
            "width",
            "height",
            "fps",
            "seconds",
        ],
        "properties": {
            "artifact_id": {"type": "string"},
            "kind": {"const": "video"},
            "format": {"enum": ["mp4", "mov"]},
            "path": {"type": "string"},
            "metadata_path": {"type": "string"},
            "created_by_step": {"type": "string"},
            "parent_artifact_ids": {"type": "array", "items": {"type": "string"}},
            "width": {"type": "integer", "minimum": 1},
            "height": {"type": "integer", "minimum": 1},
            "fps": {"type": "integer", "minimum": 1},
            "seconds": {"type": "number", "exclusiveMinimum": 0},
        },
        "additionalProperties": False,
    }


def step_run_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": [
            "run_id",
            "step_id",
            "step_kind",
            "status",
            "executor",
            "executor_version",
            "cache_namespace",
            "cache_key",
            "input_hash",
            "started_at",
            "finished_at",
            "platform",
            "model",
            "outputs",
            "metadata",
        ],
        "properties": {
            "run_id": {"type": "string"},
            "step_id": {"type": "string"},
            "step_kind": {"type": "string"},
            "status": {"enum": ["completed", "failed", "cached"]},
            "executor": {"type": "string"},
            "executor_version": {"type": "string"},
            "cache_namespace": {"type": "string"},
            "cache_key": {"type": "string"},
            "input_hash": {"type": "string"},
            "started_at": {"type": "string"},
            "finished_at": {"type": "string"},
            "platform": {"type": "object"},
            "model": {"type": "object"},
            "outputs": {"type": "array", "items": {"type": "object"}},
            "metadata": {"type": "object"},
        },
        "additionalProperties": False,
    }


def pipeline_run_manifest_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["run_id", "run_root", "steps", "artifacts"],
        "properties": {
            "run_id": {"type": "string"},
            "run_root": {"type": "string"},
            "steps": {"type": "array", "items": step_run_schema()},
            "artifacts": {"type": "array", "items": {"type": "object"}},
        },
        "additionalProperties": False,
    }
