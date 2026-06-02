"""Run prompt-to-video pipelines from ``dts-utils generate --profile``."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from dts_utils.exceptions import ConfigurationError, GenerationRpcError
from dts_utils.pipeline.profile import PIPELINE_METADATA_KEY, is_pipeline_profile
from dts_utils.pipeline.run_plan import (
    PipelineRunRequest,
    default_run_id,
    default_run_root,
    execute_pipeline_run,
)


def resolve_generate_profile_name(profile: str | None) -> str | None:
    stem = (profile or "").strip()
    return stem or None


def generate_uses_pipeline_profile(profile: str | None) -> bool:
    name = resolve_generate_profile_name(profile)
    return bool(name and is_pipeline_profile(name))


def pipeline_request_from_generate_args(args: argparse.Namespace) -> PipelineRunRequest:
    profile = resolve_generate_profile_name(getattr(args, "profile", None))
    if not profile:
        raise ConfigurationError("--profile is required for pipeline generation.")
    if not generate_uses_pipeline_profile(profile):
        raise ConfigurationError(
            f"Profile {profile!r} is not a pipeline profile (no {PIPELINE_METADATA_KEY} block). "
            "Use --configuration for single-image generate, or "
            "dts-utils configs scaffold-pipeline prompt-to-video."
        )
    prompt = (getattr(args, "prompt", None) or "").strip()
    image_path = getattr(args, "image", None)
    if not prompt and not image_path:
        raise ConfigurationError("Pipeline generate requires --prompt or --image.")
    return PipelineRunRequest(
        profile=profile,
        prompt=prompt or None,
        image_path=image_path,
        run_root=getattr(args, "run_root", None) or default_run_root(),
        run_id=getattr(args, "run_id", None) or default_run_id(),
        allow_cache=not bool(getattr(args, "no_cache", False)),
        fps=getattr(args, "fps", None),
        seconds=getattr(args, "seconds", None),
        negative_prompt=getattr(args, "negative_prompt", None) or "",
        host=getattr(args, "host", None),
        port=getattr(args, "port", None),
        no_tls=getattr(args, "no_tls", None),
        trust_server_cert=getattr(args, "trust_server_cert", None),
        force_trust_server_cert=getattr(args, "force_trust_server_cert", None),
        root_cert=getattr(args, "root_cert", None),
        max_message_mb=getattr(args, "max_message_mb", None),
        user=getattr(args, "user", None),
        shared_secret=getattr(args, "shared_secret", None),
        video_width=getattr(args, "video_width", None),
        video_height=getattr(args, "video_height", None),
    )


def print_pipeline_run_summary(manifest, *, profile: str | None) -> None:
    run_root = Path(manifest.run_root)
    print(f"run_id: {manifest.run_id}")
    print(f"run_root: {manifest.run_root}")
    print(f"profile: {profile or '(none)'}")
    print(f"pipeline_manifest: {run_root / manifest.run_id / 'pipeline_run.json'}")
    for i, artifact in enumerate(manifest.artifacts, start=1):
        print(f"artifact_{i}: {artifact['path']}")


def open_pipeline_artifacts(manifest) -> None:
    if sys.platform == "darwin":
        command = ["open"]
    elif sys.platform.startswith("linux"):
        command = ["xdg-open"]
    elif sys.platform.startswith("win"):
        command = ["cmd", "/c", "start", ""]
    else:
        raise ValueError(f"Unsupported platform for --open: {sys.platform}")

    for artifact in manifest.artifacts:
        path = Path(str(artifact["path"]))
        if path.is_file():
            subprocess.run([*command, str(path)], check=True)


def run_generate_pipeline(args: argparse.Namespace) -> int:
    if int(getattr(args, "generations", 1) or 1) != 1:
        print(
            "Pipeline profiles do not support --generations > 1; run separate generate commands.",
            file=sys.stderr,
        )
        return 2
    try:
        request = pipeline_request_from_generate_args(args)
        manifest = execute_pipeline_run(request)
    except ConfigurationError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except GenerationRpcError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    profile = resolve_generate_profile_name(getattr(args, "profile", None))
    print_pipeline_run_summary(manifest, profile=profile)
    if getattr(args, "open", False):
        try:
            open_pipeline_artifacts(manifest)
        except (OSError, subprocess.CalledProcessError, ValueError) as exc:
            print(f"Open error: {exc}", file=sys.stderr)
            return 1
    return 0
