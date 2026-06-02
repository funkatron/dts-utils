"""Build and execute pipeline runs (shared by CLI and web)."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from dts_utils.exceptions import ConfigurationError
from dts_utils.pipeline.contracts import PipelineRunManifest
from dts_utils.pipeline.executors import (
    DrawThingsGrpcImageToVideoExecutor,
    DrawThingsPromptTextToImageExecutor,
    PlaceholderImageToVideoExecutor,
    SdxlTextToImageExecutor,
    StubTextToImageExecutor,
    ZImageTurboTextToImageExecutor,
)
from dts_utils.pipeline.profile import (
    PipelineProfileSettings,
    merge_profile_into_run_args,
    uses_drawthings_t2i,
)
from dts_utils.pipeline.runner import PipelineRunner, PipelineStep


def default_run_root() -> Path:
    return Path.home() / "Movies" / "infomux-runs"


def default_run_id() -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"pipeline-{stamp}"


@dataclass(slots=True)
class PipelineRunRequest:
    profile: str | None = None
    prompt: str | None = None
    image_path: Path | None = None
    run_root: Path | None = None
    run_id: str | None = None
    allow_cache: bool = True
    max_oom_retries: int = 1
    preset: str | None = None
    seed: int | None = None
    width: int | None = None
    height: int | None = None
    video_width: int | None = None
    video_height: int | None = None
    fps: int | None = None
    seconds: float | None = None
    simulate_oom: bool = False
    negative_prompt: str | None = None
    configuration: str | None = None
    configuration_json: str | None = None
    host: str | None = None
    port: int | None = None
    no_tls: bool | None = None
    trust_server_cert: bool | None = None
    force_trust_server_cert: bool | None = None
    root_cert: Path | None = None
    max_message_mb: int | None = None
    user: str | None = None
    shared_secret: str | None = None
    sdxl_runtime: str | None = None
    sdxl_model_id: str | None = None
    sdxl_model_sha256: str | None = None
    z_model_sha256: str | None = None
    ltx_model_sha256: str | None = None
    i2v_backend: str | None = None
    video_configuration: str | None = None
    video_configuration_json: str | None = None
    video_prompt: str | None = None
    video_negative_prompt: str | None = None


def apply_run_defaults(args: argparse.Namespace) -> None:
    if getattr(args, "run_root", None) is None:
        args.run_root = default_run_root()
    if getattr(args, "run_id", None) is None:
        args.run_id = default_run_id()
    if getattr(args, "preset", None) is None:
        args.preset = "sdxl-to-ltx"
    if getattr(args, "max_oom_retries", None) is None:
        args.max_oom_retries = 1
    if getattr(args, "seed", None) is None:
        args.seed = 42
    if getattr(args, "width", None) is None:
        args.width = 1024
    if getattr(args, "height", None) is None:
        args.height = 1024
    if getattr(args, "video_width", None) is None:
        args.video_width = 1024
    if getattr(args, "video_height", None) is None:
        args.video_height = 576
    if getattr(args, "fps", None) is None:
        args.fps = 12
    if getattr(args, "seconds", None) is None:
        args.seconds = 2.0
    if getattr(args, "host", None) is None:
        args.host = "localhost"
    if getattr(args, "port", None) is None:
        args.port = 7859
    if getattr(args, "no_tls", None) is None:
        args.no_tls = False
    if getattr(args, "trust_server_cert", None) is None:
        args.trust_server_cert = False
    if getattr(args, "force_trust_server_cert", None) is None:
        args.force_trust_server_cert = False
    if getattr(args, "max_message_mb", None) is None:
        args.max_message_mb = 64
    if getattr(args, "user", None) is None:
        args.user = "dts-utils"
    if getattr(args, "negative_prompt", None) is None:
        args.negative_prompt = ""
    if getattr(args, "i2v_backend", None) is None:
        args.i2v_backend = "auto"
    if getattr(args, "sdxl_runtime", None) is None:
        args.sdxl_runtime = "pytorch-mps"
    if getattr(args, "sdxl_model_id", None) is None:
        args.sdxl_model_id = "sdxl-turbo"
    if getattr(args, "sdxl_model_sha256", None) is None:
        args.sdxl_model_sha256 = "unknown"
    if getattr(args, "z_model_sha256", None) is None:
        args.z_model_sha256 = "unknown"
    if getattr(args, "ltx_model_sha256", None) is None:
        args.ltx_model_sha256 = "unknown"


def request_to_namespace(request: PipelineRunRequest) -> argparse.Namespace:
    return argparse.Namespace(**{field: getattr(request, field) for field in request.__dataclass_fields__})


def prepare_pipeline_run(request: PipelineRunRequest) -> tuple[argparse.Namespace, PipelineProfileSettings | None]:
    args = request_to_namespace(request)
    profile_settings: PipelineProfileSettings | None = None
    if args.profile:
        profile_settings = merge_profile_into_run_args(args)
    apply_run_defaults(args)
    return args, profile_settings


def validate_pipeline_run(
    args: argparse.Namespace,
    profile_settings: PipelineProfileSettings | None,
) -> None:
    if not args.prompt and not args.image_path:
        if args.profile:
            raise ConfigurationError("Pipeline run with a profile requires a prompt or input image.")
        return

    if uses_drawthings_t2i(
        has_prompt=bool(args.prompt),
        configuration=args.configuration,
        configuration_json=args.configuration_json,
        profile=profile_settings,
    ):
        if not args.configuration and not args.configuration_json:
            raise ConfigurationError(
                "Draw Things text-to-image needs a configuration. "
                "Set t2i_configuration in the pipeline profile or pass configuration."
            )
    elif args.prompt and not args.profile:
        if not args.configuration and not args.configuration_json:
            raise ConfigurationError(
                "Pipeline run with a prompt requires configuration, configuration_json, or a profile."
            )


def resolve_i2v_backend(args: argparse.Namespace) -> str:
    if args.i2v_backend == "drawthings":
        return "drawthings"
    if args.i2v_backend == "placeholder":
        return "placeholder"
    if args.video_configuration or args.video_configuration_json:
        return "drawthings"
    return "placeholder"


def build_i2v_executor(args: argparse.Namespace):
    backend = resolve_i2v_backend(args)
    if backend == "drawthings":
        if not args.video_configuration and not args.video_configuration_json:
            raise ConfigurationError(
                "Draw Things image-to-video requires a video configuration. "
                "Set video_configuration in the pipeline profile."
            )
        return DrawThingsGrpcImageToVideoExecutor(
            host=args.host,
            port=args.port,
            no_tls=args.no_tls,
            root_cert=args.root_cert,
            trust_server_cert=args.trust_server_cert,
            force_trust_server_cert=args.force_trust_server_cert,
            max_message_mb=args.max_message_mb,
            user=args.user,
            shared_secret=args.shared_secret,
            video_configuration=args.video_configuration,
            video_configuration_json=args.video_configuration_json,
        )
    return PlaceholderImageToVideoExecutor(model_sha256=args.ltx_model_sha256)


def build_t2i_executor(args: argparse.Namespace):
    if args.preset == "stub-to-ltx":
        return StubTextToImageExecutor()
    if args.preset == "z-to-ltx":
        return ZImageTurboTextToImageExecutor(model_sha256=args.z_model_sha256)
    return SdxlTextToImageExecutor(
        runtime=args.sdxl_runtime,
        model_id=args.sdxl_model_id,
        model_sha256=args.sdxl_model_sha256,
    )


def build_pipeline_steps(
    args: argparse.Namespace,
    profile_settings: PipelineProfileSettings | None,
) -> list[PipelineStep]:
    steps: list[PipelineStep] = []
    i2v_backend = resolve_i2v_backend(args)
    i2v_request: dict[str, object] = {
        "fps": args.fps,
        "seconds": args.seconds,
        "width": args.video_width,
        "height": args.video_height,
    }
    if i2v_backend == "placeholder":
        i2v_request["simulate_oom"] = args.simulate_oom
    else:
        video_prompt = (args.video_prompt or args.prompt or "").strip()
        if not video_prompt and not args.image_path:
            raise ConfigurationError(
                "Draw Things image-to-video needs a prompt in the profile or request."
            )
        i2v_request.update(
            {
                "prompt": video_prompt,
                "negative_prompt": (args.video_negative_prompt or args.negative_prompt or ""),
                "configuration": args.video_configuration,
                "configuration_json": args.video_configuration_json,
                "user": args.user,
                "shared_secret": args.shared_secret,
            }
        )

    i2v_input_from: str | None = None
    if args.image_path:
        i2v_request["image_path"] = str(args.image_path)
    if not args.image_path and uses_drawthings_t2i(
        has_prompt=bool(args.prompt),
        configuration=args.configuration,
        configuration_json=args.configuration_json,
        profile=profile_settings,
    ):
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
    elif not args.image_path:
        steps.append(
            PipelineStep(
                step_id="t2i",
                executor=build_t2i_executor(args),
                request={"seed": args.seed, "width": args.width, "height": args.height},
            )
        )
        i2v_input_from = "t2i"

    steps.append(
        PipelineStep(
            step_id="i2v",
            executor=build_i2v_executor(args),
            input_from_step=i2v_input_from,
            request=i2v_request,
        )
    )
    if args.image_path and len(steps) != 1:
        raise ConfigurationError("image_path runs must only include the image_to_video step.")
    return steps


def execute_pipeline_run(request: PipelineRunRequest) -> PipelineRunManifest:
    args, profile_settings = prepare_pipeline_run(request)
    validate_pipeline_run(args, profile_settings)
    runner = PipelineRunner(
        Path(args.run_root),
        allow_cache=args.allow_cache,
        max_oom_retries=max(0, int(args.max_oom_retries)),
    )
    steps = build_pipeline_steps(args, profile_settings)
    return runner.run(run_id=str(args.run_id), steps=steps)
