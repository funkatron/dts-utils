"""Draw Things generation configuration: JSON, FlatBuffer, and saved names."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from dts_utils.configs import resolve_configuration_value
from dts_utils.exceptions import ConfigurationError

PACKAGE_ROOT = Path(__file__).resolve().parent
UPSTREAM_PROTO_PATH = PACKAGE_ROOT / "grpc" / "proto" / "upstream"
CONFIG_SCHEMA_PATH = UPSTREAM_PROTO_PATH / "config.fbs"

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
    "fps": "fps_id",
    "fpsId": "fps_id",
    "guidanceEmbed": "guidance_embed",
    "guidanceScale": "guidance_scale",
    "guidingFrameNoise": "guiding_frame_noise",
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
    "motionScale": "motion_scale",
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
    "stage2Guidance": "stage_2_guidance",
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

# Draw Things JSON may use lowercase strings; flatc expects ``CompressionMethod`` PascalCase labels.
_COMPRESSION_METHOD_JSON_ALIASES = {
    "disabled": "Disabled",
    "h264": "H264",
    "h265": "H265",
    "jpeg": "Jpeg",
}


def normalize_configuration_for_flatc(configuration: dict) -> dict:
    normalized = {}
    for key, value in configuration.items():
        if isinstance(key, str) and key.startswith("_dts_utils"):
            # UI-only metadata in saved JSON; not part of Draw Things schema / flatc input.
            continue
        mapped_key = CONFIG_KEY_MAP.get(key, key)
        if value == "" or (mapped_key in {"controls", "loras"} and value == []):
            continue
        if mapped_key in CONFIG_DIMENSION_KEYS:
            value = max(int(value) // 64, 1)
        if mapped_key == "compression_artifacts" and isinstance(value, str):
            aliased = _COMPRESSION_METHOD_JSON_ALIASES.get(value.strip().lower())
            if aliased is not None:
                value = aliased
        normalized[mapped_key] = value
    return normalized


def configurations_equivalent_for_flatbuffer(a: dict, b: dict) -> bool:
    """True when ``a`` and ``b`` yield the same normalized dict passed to flatc.

    Uses :func:`normalize_configuration_for_flatc` (key aliases, dropped empties,
    dimension scaling, ``compression_artifacts`` enum aliases, skipped ``_dts_utils*``).
    """
    return normalize_configuration_for_flatc(a) == normalize_configuration_for_flatc(b)


def json_configuration_to_flatbuffer(configuration: dict) -> bytes:
    flatc_path = shutil.which("flatc")
    if not flatc_path:
        raise ConfigurationError(
            "flatc is required for JSON configuration. Install FlatBuffers or pass raw FlatBuffer bytes."
        )

    flatc_configuration = normalize_configuration_for_flatc(configuration)
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        json_path = temp_path / "configuration.json"
        json_path.write_text(json.dumps(flatc_configuration, sort_keys=True), encoding="utf-8")
        try:
            subprocess.run(
                [flatc_path, "-b", "-o", str(temp_path), str(CONFIG_SCHEMA_PATH), str(json_path)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            raise ConfigurationError(f"flatc failed: {e.stderr or e}") from e
        return (temp_path / "configuration.bin").read_bytes()


def read_json_configuration_bytes(configuration_path: Path) -> bytes:
    try:
        with configuration_path.open(encoding="utf-8") as f:
            configuration = json.load(f)
    except OSError as e:
        raise ConfigurationError(str(e)) from e
    except json.JSONDecodeError as e:
        raise ConfigurationError(str(e)) from e
    if not isinstance(configuration, dict):
        raise ConfigurationError("JSON configuration must be an object.")

    return json_configuration_to_flatbuffer(configuration)


def read_configuration_bytes(
    *,
    configuration: str | Path | None = None,
    configuration_json: str | Path | None = None,
    config_dir: Path | None = None,
) -> bytes:
    try:
        if configuration:
            configuration_path = resolve_configuration_value(configuration, config_dir=config_dir)
            if configuration_path.suffix.lower() == ".json":
                return read_json_configuration_bytes(configuration_path)
            return configuration_path.read_bytes()
        if not configuration_json:
            raise ConfigurationError(
                "Generation configuration is required. Pass --configuration CONFIG_PATH_OR_NAME "
                "or --configuration-json JSON_PATH_OR_NAME."
            )

        configuration_path = resolve_configuration_value(configuration_json, config_dir=config_dir)
        return read_json_configuration_bytes(configuration_path)
    except ValueError as e:
        raise ConfigurationError(str(e)) from e
