"""CLI entrypoints for pipeline execution and Apple runtime checks."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from dts_utils.configs import DEFAULT_PROFILE_NAME
from dts_utils.exceptions import ConfigurationError
from dts_utils.pipeline import (
    collect_apple_runtime_checks,
)
from dts_utils.pipeline.profile import (
    DEFAULT_PIPELINE_PROFILE_ENV,
    list_pipeline_profile_names,
)
from dts_utils.pipeline.run_plan import (
    PipelineRunRequest,
    default_run_root,
    execute_pipeline_run,
)


def _default_pipeline_profile() -> str | None:
    env = os.environ.get(DEFAULT_PIPELINE_PROFILE_ENV, "").strip()
    return env or None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dts-utils pipeline",
        description="Run Apple-first media pipelines and environment checks.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="Validate Apple runtime prerequisites for pipeline runs.")
    check.add_argument("--run-root", type=Path, default=default_run_root())
    check.add_argument("--json", action="store_true", help="Print machine-readable JSON.")

    profiles = sub.add_parser("profiles", help="List saved profiles that include pipeline defaults.")
    profiles.add_argument("--json", action="store_true", help="Print machine-readable JSON.")

    run = sub.add_parser(
        "run",
        help="Run a pipeline. Prefer --profile (saved JSON with _dts_utils_pipeline) plus --prompt.",
    )
    run.add_argument(
        "--profile",
        default=None,
        help=(
            "Saved profile with a _dts_utils_pipeline block. "
            f"Default: ${DEFAULT_PIPELINE_PROFILE_ENV} when set."
        ),
    )
    run.add_argument("--run-root", type=Path, default=None)
    run.add_argument("--run-id", default=None)
    input_group = run.add_mutually_exclusive_group()
    input_group.add_argument("--image", type=Path, help="Existing image for image-to-video only.")
    input_group.add_argument("--prompt", help="Prompt for Draw Things T2I and/or I2V.")
    run.add_argument("--preset", choices=["stub-to-ltx", "sdxl-to-ltx", "z-to-ltx"], default=None)
    run.add_argument("--no-cache", action="store_true")
    run.add_argument("--max-oom-retries", type=int, default=None)
    run.add_argument("--seed", type=int, default=None)
    run.add_argument("--width", type=int, default=None)
    run.add_argument("--height", type=int, default=None)
    run.add_argument("--video-width", type=int, default=None)
    run.add_argument("--video-height", type=int, default=None)
    run.add_argument("--fps", type=int, default=None)
    run.add_argument("--seconds", type=float, default=None)
    run.add_argument("--simulate-oom", action="store_true")
    run.add_argument("--negative-prompt", default=None)
    run.add_argument("--configuration", default=None)
    run.add_argument("--configuration-json", default=None)
    run.add_argument("--host", default=None)
    run.add_argument("--port", type=int, default=None)
    run.add_argument("--no-tls", action=argparse.BooleanOptionalAction, default=None)
    run.add_argument("--trust-server-cert", action=argparse.BooleanOptionalAction, default=None)
    run.add_argument("--force-trust-server-cert", action=argparse.BooleanOptionalAction, default=None)
    run.add_argument("--root-cert", type=Path, default=None)
    run.add_argument("--max-message-mb", type=int, default=None)
    run.add_argument("--user", default=None)
    run.add_argument("--shared-secret", default=None)
    run.add_argument("--sdxl-runtime", choices=["pytorch-mps", "mlx"], default=None)
    run.add_argument("--sdxl-model-id", default=None)
    run.add_argument("--sdxl-model-sha256", default=None)
    run.add_argument("--z-model-sha256", default=None)
    run.add_argument("--ltx-model-sha256", default=None)
    run.add_argument("--i2v-backend", choices=["auto", "placeholder", "drawthings"], default=None)
    run.add_argument("--video-configuration", default=None)
    run.add_argument("--video-configuration-json", default=None)
    run.add_argument("--video-prompt", default=None)
    run.add_argument("--video-negative-prompt", default=None)

    return parser


def _args_to_request(args: argparse.Namespace) -> PipelineRunRequest:
    profile = (str(args.profile).strip() if args.profile else None) or _default_pipeline_profile()
    return PipelineRunRequest(
        profile=profile,
        prompt=args.prompt,
        image_path=args.image,
        run_root=args.run_root,
        run_id=args.run_id,
        allow_cache=not args.no_cache,
        max_oom_retries=args.max_oom_retries,
        preset=args.preset,
        seed=args.seed,
        width=args.width,
        height=args.height,
        video_width=args.video_width,
        video_height=args.video_height,
        fps=args.fps,
        seconds=args.seconds,
        simulate_oom=args.simulate_oom,
        negative_prompt=args.negative_prompt,
        configuration=args.configuration,
        configuration_json=args.configuration_json,
        host=args.host,
        port=args.port,
        no_tls=args.no_tls,
        trust_server_cert=args.trust_server_cert,
        force_trust_server_cert=args.force_trust_server_cert,
        root_cert=args.root_cert,
        max_message_mb=args.max_message_mb,
        user=args.user,
        shared_secret=args.shared_secret,
        sdxl_runtime=args.sdxl_runtime,
        sdxl_model_id=args.sdxl_model_id,
        sdxl_model_sha256=args.sdxl_model_sha256,
        z_model_sha256=args.z_model_sha256,
        ltx_model_sha256=args.ltx_model_sha256,
        i2v_backend=args.i2v_backend,
        video_configuration=args.video_configuration,
        video_configuration_json=args.video_configuration_json,
        video_prompt=args.video_prompt,
        video_negative_prompt=args.video_negative_prompt,
    )


def handle_profiles(args: argparse.Namespace) -> int:
    names = list_pipeline_profile_names()
    payload = {"profiles": names, "default_profile": DEFAULT_PROFILE_NAME}
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        if not names:
            print("No pipeline profiles found (JSON files with _dts_utils_pipeline under configs path).")
            print("Run: dts-utils configs path")
            return 0
        for name in names:
            print(name)
    return 0


def handle_check(args: argparse.Namespace) -> int:
    checks = collect_apple_runtime_checks(args.run_root)
    payload = {
        "run_root": str(args.run_root),
        "ffmpeg_path": checks.ffmpeg_path,
        "run_root_writable": checks.run_root_writable,
        "gatekeeper_note": checks.gatekeeper_note,
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"run_root: {payload['run_root']}")
        print(f"run_root_writable: {payload['run_root_writable']}")
        print(f"ffmpeg_path: {payload['ffmpeg_path'] or 'missing'}")
        print(f"note: {payload['gatekeeper_note']}")
    return 0 if (checks.run_root_writable and checks.ffmpeg_path) else 1


def handle_run(args: argparse.Namespace) -> int:
    try:
        manifest = execute_pipeline_run(_args_to_request(args))
    except ConfigurationError as exc:
        raise SystemExit(str(exc)) from exc
    run_root = Path(manifest.run_root)
    print(f"run_id: {manifest.run_id}")
    print(f"run_root: {manifest.run_root}")
    print(f"profile: {args.profile or _default_pipeline_profile() or '(none)'}")
    print(f"pipeline_manifest: {run_root / manifest.run_id / 'pipeline_run.json'}")
    for i, artifact in enumerate(manifest.artifacts, start=1):
        print(f"artifact_{i}: {artifact['path']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "check":
        return handle_check(args)
    if args.command == "profiles":
        return handle_profiles(args)
    if args.command == "run":
        return handle_run(args)
    parser.error(f"Unknown command: {args.command}")
    return 2
