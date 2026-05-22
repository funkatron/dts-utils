"""CLI entrypoints for pipeline execution and Apple runtime checks."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from dts_utils.pipeline import (
    DrawThingsPromptTextToImageExecutor,
    LtxImageToVideoExecutor,
    PipelineRunner,
    PipelineStep,
    SdxlTextToImageExecutor,
    StubTextToImageExecutor,
    ZImageTurboTextToImageExecutor,
    collect_apple_runtime_checks,
)


def _default_run_root() -> Path:
    return Path.home() / "Movies" / "infomux-runs"


def _default_run_id() -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"pipeline-{stamp}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dts-utils pipeline",
        description="Run Apple-first media pipelines and environment checks.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="Validate Apple runtime prerequisites for pipeline runs.")
    check.add_argument("--run-root", type=Path, default=_default_run_root())
    check.add_argument("--json", action="store_true", help="Print machine-readable JSON.")

    run = sub.add_parser("run", help="Run a local text-to-image to image-to-video pipeline.")
    run.add_argument("--run-root", type=Path, default=_default_run_root())
    run.add_argument("--run-id", default=_default_run_id())
    input_group = run.add_mutually_exclusive_group()
    input_group.add_argument(
        "--image",
        type=Path,
        help="Use an existing input image and run image_to_video only.",
    )
    input_group.add_argument(
        "--prompt",
        help="Generate a prompt image via Draw Things before image_to_video.",
    )
    run.add_argument(
        "--preset",
        choices=["stub-to-ltx", "sdxl-to-ltx", "z-to-ltx"],
        default="sdxl-to-ltx",
        help="Choose the text-to-image executor before the LTX video step.",
    )
    run.add_argument("--no-cache", action="store_true", help="Disable cache hits for this run.")
    run.add_argument("--max-oom-retries", type=int, default=1)
    run.add_argument("--seed", type=int, default=42)
    run.add_argument("--width", type=int, default=1024)
    run.add_argument("--height", type=int, default=1024)
    run.add_argument("--video-width", type=int, default=1024)
    run.add_argument("--video-height", type=int, default=576)
    run.add_argument("--fps", type=int, default=12)
    run.add_argument("--seconds", type=float, default=2.0)
    run.add_argument("--simulate-oom", action="store_true", help="Simulate one OOM retry in the LTX step.")
    run.add_argument("--negative-prompt", default="")
    run.add_argument("--configuration", help="Saved profile name or config path for Draw Things prompt generation.")
    run.add_argument("--configuration-json", help="JSON config path for Draw Things prompt generation.")
    run.add_argument("--host", default="localhost")
    run.add_argument("--port", type=int, default=7859)
    run.add_argument("--no-tls", action="store_true")
    run.add_argument("--trust-server-cert", action="store_true")
    run.add_argument("--force-trust-server-cert", action="store_true")
    run.add_argument("--root-cert", type=Path)
    run.add_argument("--max-message-mb", type=int, default=64)
    run.add_argument("--user", default="dts-utils")
    run.add_argument("--shared-secret")
    run.add_argument("--sdxl-runtime", choices=["pytorch-mps", "mlx"], default="pytorch-mps")
    run.add_argument("--sdxl-model-id", default="sdxl-turbo")
    run.add_argument("--sdxl-model-sha256", default="unknown")
    run.add_argument("--z-model-sha256", default="unknown")
    run.add_argument("--ltx-model-sha256", default="unknown")

    return parser


def _build_t2i_executor(args: argparse.Namespace):
    if args.preset == "stub-to-ltx":
        return StubTextToImageExecutor()
    if args.preset == "z-to-ltx":
        return ZImageTurboTextToImageExecutor(model_sha256=args.z_model_sha256)
    return SdxlTextToImageExecutor(
        runtime=args.sdxl_runtime,
        model_id=args.sdxl_model_id,
        model_sha256=args.sdxl_model_sha256,
    )


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
    runner = PipelineRunner(
        run_root=args.run_root,
        allow_cache=not args.no_cache,
        max_oom_retries=max(0, args.max_oom_retries),
    )
    if args.prompt and not args.configuration and not args.configuration_json:
        raise SystemExit("pipeline run --prompt requires --configuration or --configuration-json")

    steps: list[PipelineStep] = []
    i2v_input_from: str | None = None
    i2v_request = {
        "fps": args.fps,
        "seconds": args.seconds,
        "width": args.video_width,
        "height": args.video_height,
        "simulate_oom": args.simulate_oom,
    }
    if args.image:
        i2v_request["image_path"] = str(args.image)
    elif args.prompt:
        steps.append(
            PipelineStep(
                step_id="t2i",
                executor=DrawThingsPromptTextToImageExecutor(
                    host=args.host,
                    port=args.port,
                    no_tls=args.no_tls,
                    root_cert=args.root_cert,
                    trust_server_cert=args.trust_server_cert,
                    force_trust_server_cert=args.force_trust_server_cert,
                    max_message_mb=args.max_message_mb,
                    user=args.user,
                    shared_secret=args.shared_secret,
                ),
                request={
                    "prompt": args.prompt,
                    "negative_prompt": args.negative_prompt,
                    "configuration": args.configuration,
                    "configuration_json": args.configuration_json,
                    "user": args.user,
                    "shared_secret": args.shared_secret,
                },
            )
        )
        i2v_input_from = "t2i"
    else:
        steps.append(
            PipelineStep(
                step_id="t2i",
                executor=_build_t2i_executor(args),
                request={"seed": args.seed, "width": args.width, "height": args.height},
            )
        )
        i2v_input_from = "t2i"

    steps.append(
        PipelineStep(
            step_id="i2v",
            executor=LtxImageToVideoExecutor(model_sha256=args.ltx_model_sha256),
            input_from_step=i2v_input_from,
            request=i2v_request,
        )
    )
    manifest = runner.run(run_id=args.run_id, steps=steps)
    print(f"run_id: {manifest.run_id}")
    print(f"run_root: {manifest.run_root}")
    print(f"pipeline_manifest: {args.run_root / args.run_id / 'pipeline_run.json'}")
    for i, artifact in enumerate(manifest.artifacts, start=1):
        print(f"artifact_{i}: {artifact['path']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "check":
        return handle_check(args)
    if args.command == "run":
        return handle_run(args)
    parser.error(f"Unknown command: {args.command}")
    return 2
