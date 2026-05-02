"""Generate images through Draw Things gRPCServerCLI."""

from __future__ import annotations

import argparse
import io
import json
import shutil
import struct
import subprocess
import sys
import tempfile
import time
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
UPSTREAM_PROTO_PATH = PACKAGE_ROOT / "grpc" / "proto" / "upstream"
CONFIG_SCHEMA_PATH = UPSTREAM_PROTO_PATH / "config.fbs"
sys.path.insert(0, str(UPSTREAM_PROTO_PATH))

import grpc
import fpzip
import numpy as np
from PIL import Image
from dts_util.configs import resolve_configuration_value
from dts_util.grpc.connection import create_channel
from dts_util.grpc.proto.upstream import imageService_pb2 as up_pb2
from dts_util.grpc.proto.upstream import imageService_pb2_grpc as up_grpc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Send a prompt to Draw Things gRPCServerCLI and save the returned image.",
    )
    parser.add_argument("--prompt", required=True, help="Prompt to generate.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("generated.png"),
        help=(
            "Output path; inserts -<unix_ms> before the extension so repeated runs do not overwrite "
            "prior files (e.g. out/foo.png → out/foo-1735123456789.png). "
            "Additional images from the same run append -2, -3, ... before the extension."
        ),
    )
    parser.add_argument("--host", default="localhost", help="gRPC server host.")
    parser.add_argument("--port", type=int, default=7859, help="gRPC server port.")
    parser.add_argument("--negative-prompt", default="", help="Negative prompt.")
    parser.add_argument("--open", action="store_true", help="Open generated image files in the default viewer.")
    parser.add_argument("--user", default="dts-util", help="Client name sent to the server.")
    parser.add_argument("--shared-secret", help="Shared secret, if the server requires one.")
    parser.add_argument(
        "--max-message-mb",
        type=int,
        default=64,
        help="Maximum gRPC send/receive message size in MiB.",
    )
    config_group = parser.add_mutually_exclusive_group()
    config_group.add_argument(
        "--configuration",
        help=(
            "Draw Things configuration. Existing .json files are converted to FlatBuffer bytes; "
            "other existing files are sent as raw FlatBuffer bytes; names resolve to saved JSON configs."
        ),
    )
    config_group.add_argument("--configuration-json", help="Draw Things JSON configuration file or saved config name.")
    parser.add_argument(
        "--no-tls",
        action="store_true",
        help="Connect without TLS. Use only when the server was installed with --no-tls.",
    )
    parser.add_argument("--root-cert", type=Path, help="Root certificate PEM to trust for TLS.")
    parser.add_argument(
        "--trust-server-cert",
        action="store_true",
        help="Fetch and trust the presented certificate for this localhost connection. Use --root-cert for remote or LAN servers.",
    )
    parser.add_argument(
        "--force-trust-server-cert",
        action="store_true",
        help=(
            "Fetch and trust the presented certificate for any host. "
            "This is vulnerable to MITM attacks; prefer --root-cert for remote or LAN servers."
        ),
    )
    return parser


def build_request(args: argparse.Namespace) -> up_pb2.ImageGenerationRequest:
    configuration = read_configuration_bytes(args)
    request = up_pb2.ImageGenerationRequest(
        prompt=args.prompt,
        negativePrompt=args.negative_prompt,
        scaleFactor=1,
        configuration=configuration,
        chunked=True,
        user=args.user,
        device=up_pb2.LAPTOP,
    )
    if args.shared_secret:
        request.sharedSecret = args.shared_secret
    return request


def read_configuration_bytes(args: argparse.Namespace) -> bytes:
    if args.configuration:
        configuration_path = resolve_configuration_value(args.configuration)
        if configuration_path.suffix.lower() == ".json":
            return read_json_configuration_bytes(configuration_path)
        return configuration_path.read_bytes()
    if not args.configuration_json:
        raise ValueError(
            "Generation configuration is required. Pass --configuration CONFIG_PATH_OR_NAME "
            "or --configuration-json JSON_PATH_OR_NAME."
        )

    configuration_path = resolve_configuration_value(args.configuration_json)
    return read_json_configuration_bytes(configuration_path)


def read_json_configuration_bytes(configuration_path: Path) -> bytes:
    with configuration_path.open(encoding="utf-8") as f:
        configuration = json.load(f)
    if not isinstance(configuration, dict):
        raise ValueError("JSON configuration must be an object.")

    return json_configuration_to_flatbuffer(configuration)


CONFIG_KEY_MAP = {
    "aestheticScore": "aesthetic_score",
    "batchCount": "batch_count",
    "batchSize": "batch_size",
    "causalInference": "causal_inference",
    "causalInferenceEnabled": "causal_inference_enabled",
    "causalInferencePad": "causal_inference_pad",
    "cfgZeroInitSteps": "cfg_zero_init_steps",
    "cfgZeroStar": "cfg_zero_star",
    "clipLText": "clip_l_text",
    "clipSkip": "clip_skip",
    "clipWeight": "clip_weight",
    "compressionArtifacts": "compression_artifacts",
    "compressionArtifactsQuality": "compression_artifacts_quality",
    "condAug": "cond_aug",
    "cropLeft": "crop_left",
    "cropTop": "crop_top",
    "decodingTileHeight": "decoding_tile_height",
    "decodingTileOverlap": "decoding_tile_overlap",
    "decodingTileWidth": "decoding_tile_width",
    "diffusionTileHeight": "diffusion_tile_height",
    "diffusionTileOverlap": "diffusion_tile_overlap",
    "diffusionTileWidth": "diffusion_tile_width",
    "faceRestoration": "face_restoration",
    "fpsId": "fps_id",
    "guidanceEmbed": "guidance_embed",
    "guidanceScale": "guidance_scale",
    "height": "start_height",
    "hiresFix": "hires_fix",
    "hiresFixHeight": "hires_fix_start_height",
    "hiresFixStartHeight": "hires_fix_start_height",
    "hiresFixStartWidth": "hires_fix_start_width",
    "hiresFixStrength": "hires_fix_strength",
    "hiresFixWidth": "hires_fix_start_width",
    "imageGuidanceScale": "image_guidance_scale",
    "imagePriorSteps": "image_prior_steps",
    "maskBlur": "mask_blur",
    "maskBlurOutset": "mask_blur_outset",
    "motionBucketId": "motion_bucket_id",
    "negativeAestheticScore": "negative_aesthetic_score",
    "negativeOriginalImageHeight": "negative_original_image_height",
    "negativeOriginalImageWidth": "negative_original_image_width",
    "negativePromptForImagePrior": "negative_prompt_for_image_prior",
    "numFrames": "num_frames",
    "openClipGText": "open_clip_g_text",
    "originalImageHeight": "original_image_height",
    "originalImageWidth": "original_image_width",
    "preserveOriginalAfterInpaint": "preserve_original_after_inpaint",
    "refinerModel": "refiner_model",
    "refinerStart": "refiner_start",
    "resolutionDependentShift": "resolution_dependent_shift",
    "seedMode": "seed_mode",
    "separateClipL": "separate_clip_l",
    "separateOpenClipG": "separate_open_clip_g",
    "separateT5": "separate_t5",
    "speedUpWithGuidanceEmbed": "speed_up_with_guidance_embed",
    "stage2Cfg": "stage_2_cfg",
    "stage2Shift": "stage_2_shift",
    "stage2Steps": "stage_2_steps",
    "startFrameCfg": "start_frame_cfg",
    "stochasticSamplingGamma": "stochastic_sampling_gamma",
    "t5Text": "t5_text",
    "t5TextEncoder": "t5_text_encoder",
    "targetImageHeight": "target_image_height",
    "targetImageWidth": "target_image_width",
    "teaCache": "tea_cache",
    "teaCacheEnd": "tea_cache_end",
    "teaCacheMaxSkipSteps": "tea_cache_max_skip_steps",
    "teaCacheStart": "tea_cache_start",
    "teaCacheThreshold": "tea_cache_threshold",
    "tiledDecoding": "tiled_decoding",
    "tiledDiffusion": "tiled_diffusion",
    "upscalerScaleFactor": "upscaler_scale_factor",
    "width": "start_width",
    "zeroNegativePrompt": "zero_negative_prompt",
}

CONFIG_DIMENSION_KEYS = {
    "decoding_tile_height",
    "decoding_tile_overlap",
    "decoding_tile_width",
    "diffusion_tile_height",
    "diffusion_tile_overlap",
    "diffusion_tile_width",
    "hires_fix_start_height",
    "hires_fix_start_width",
    "start_height",
    "start_width",
}


def json_configuration_to_flatbuffer(configuration: dict) -> bytes:
    flatc_path = shutil.which("flatc")
    if not flatc_path:
        raise ValueError("flatc is required for JSON configuration. Install FlatBuffers or pass raw FlatBuffer bytes.")

    flatc_configuration = normalize_configuration_for_flatc(configuration)
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        json_path = temp_path / "configuration.json"
        json_path.write_text(json.dumps(flatc_configuration, sort_keys=True), encoding="utf-8")
        subprocess.run(
            [flatc_path, "-b", "-o", str(temp_path), str(CONFIG_SCHEMA_PATH), str(json_path)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return (temp_path / "configuration.bin").read_bytes()


def normalize_configuration_for_flatc(configuration: dict) -> dict:
    normalized = {}
    for key, value in configuration.items():
        mapped_key = CONFIG_KEY_MAP.get(key, key)
        if value == "" or (mapped_key in {"controls", "loras"} and value == []):
            continue
        if mapped_key in CONFIG_DIMENSION_KEYS:
            value = max(int(value) // 64, 1)
        normalized[mapped_key] = value
    return normalized


def unique_ms_timestamp_output_path(output_path: Path) -> Path:
    """Insert Unix milliseconds before the suffix so repeated runs do not clobber prior files."""
    ms = time.time_ns() // 1_000_000
    return output_path.with_name(f"{output_path.stem}-{ms}{output_path.suffix}")


def indexed_output_path(output_path: Path, index: int) -> Path:
    if index == 0:
        return output_path
    return output_path.with_name(f"{output_path.stem}-{index + 1}{output_path.suffix}")


def write_images(images: list[bytes], output_path: Path) -> list[Path]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    written_paths = []
    for index, image in enumerate(images):
        image_path = indexed_output_path(output_path, index)
        image_path.write_bytes(decode_dt_tensor_to_png(image))
        written_paths.append(image_path)
    return written_paths


def open_images(paths: list[Path]) -> None:
    if sys.platform == "darwin":
        command = ["open"]
    elif sys.platform.startswith("linux"):
        command = ["xdg-open"]
    elif sys.platform.startswith("win"):
        command = ["cmd", "/c", "start", ""]
    else:
        raise ValueError(f"Unsupported platform for --open: {sys.platform}")

    for path in paths:
        subprocess.run([*command, str(path)], check=True)


def decode_dt_tensor_to_png(image_data: bytes) -> bytes:
    if len(image_data) < 68:
        raise ValueError("Generated image tensor is too small to contain a Draw Things header.")

    header = struct.unpack("<17I", image_data[:68])
    height, width, channels = header[6], header[7], header[8]
    if channels not in (1, 3, 4):
        raise ValueError(f"Unsupported generated image channel count: {channels}")

    is_compressed = header[0] == 1012247
    if is_compressed:
        tensor = fpzip.decompress(image_data[68:], order="C")
        tensor = np.asarray(tensor)
        if tensor.ndim == 4 and tensor.shape[0] == 1:
            tensor = tensor[0]
    else:
        tensor = np.frombuffer(image_data, dtype=np.float16, offset=68)
        tensor = tensor.reshape((height, width, channels))

    pixels = np.clip((tensor + 1) * 127, 0, 255).astype(np.uint8)
    if pixels.shape != (height, width, channels):
        pixels = pixels.reshape((height, width, channels))

    mode = {1: "L", 3: "RGB", 4: "RGBA"}[channels]
    output = io.BytesIO()
    Image.fromarray(pixels, mode=mode).save(output, format="PNG")
    return output.getvalue()


def collect_generated_images(stub: up_grpc.ImageGenerationServiceStub, request: up_pb2.ImageGenerationRequest) -> list[bytes]:
    images = []
    pending_chunk = b""
    for response in stub.GenerateImage(request):
        if not response.generatedImages:
            continue

        chunk_state = getattr(response, "chunkState", up_pb2.LAST_CHUNK)
        if chunk_state == up_pb2.MORE_CHUNKS:
            pending_chunk += response.generatedImages[0]
            continue

        response_images = list(response.generatedImages)
        if pending_chunk:
            response_images[0] = pending_chunk + response_images[0]
            pending_chunk = b""
        images.extend(response_images)
    return images


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        request = build_request(args)
    except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError) as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        return 1

    try:
        channel = create_channel(
            args.host,
            args.port,
            args.no_tls,
            root_cert=args.root_cert,
            trust_server_cert=args.trust_server_cert,
            force_trust_server_cert=args.force_trust_server_cert,
            max_message_mb=args.max_message_mb,
        )
    except (OSError, ValueError) as e:
        print(f"Connection setup error: {e}", file=sys.stderr)
        return 1
    try:
        stub = up_grpc.ImageGenerationServiceStub(channel)
        images = collect_generated_images(stub, request)
    except grpc.RpcError as e:
        print(f"RPC error: {e.code()} {e.details()}", file=sys.stderr)
        if "CERTIFICATE_VERIFY_FAILED" in (e.details() or ""):
            print(
                "TLS certificate verification failed. For a local Draw Things server, retry with --trust-server-cert.",
                file=sys.stderr,
            )
        return 1
    finally:
        close = getattr(channel, "close", None)
        if close:
            close()

    if not images:
        print("No generated images returned by the server.", file=sys.stderr)
        return 1

    written_paths = write_images(images, unique_ms_timestamp_output_path(args.output))
    for path in written_paths:
        print(f"Wrote {path}")
    if args.open:
        try:
            open_images(written_paths)
        except (OSError, subprocess.CalledProcessError, ValueError) as e:
            print(f"Open error: {e}", file=sys.stderr)
            return 1
    return 0
