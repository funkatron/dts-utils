"""Pipeline defaults embedded in saved Draw Things JSON profiles."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dts_utils.configs import configuration_search_directories, resolve_configuration_value
from dts_utils.exceptions import ConfigurationError

PIPELINE_METADATA_KEY = "_dts_utils_pipeline"
DEFAULT_PIPELINE_PROFILE_ENV = "DTS_UTILS_DEFAULT_PIPELINE_PROFILE"

# Draw Things keys that indicate the file is a generation config (not manifest-only).
_GENERATION_CONFIG_HINT_KEYS = frozenset(
    {
        "model",
        "width",
        "height",
        "steps",
        "guidanceScale",
        "guidance_scale",
        "sampler",
    }
)


@dataclass(frozen=True)
class GrpcProfileSettings:
    host: str = "localhost"
    port: int = 7859
    no_tls: bool = False
    trust_server_cert: bool = False
    force_trust_server_cert: bool = False
    max_message_mb: int = 64
    user: str = "dts-utils"
    shared_secret: str | None = None
    root_cert: Path | None = None


@dataclass(frozen=True)
class PipelineProfileSettings:
    """Non-secret pipeline run defaults stored under ``_dts_utils_pipeline`` in a profile JSON file."""

    profile_stem: str
    profile_path: Path
    t2i_configuration: str | None = None
    video_configuration: str | None = None
    configuration_json: str | None = None
    video_configuration_json: str | None = None
    i2v_backend: str | None = None
    preset: str | None = None
    fps: int | None = None
    video_width: int | None = None
    video_height: int | None = None
    seconds: float | None = None
    width: int | None = None
    height: int | None = None
    seed: int | None = None
    negative_prompt: str | None = None
    video_negative_prompt: str | None = None
    video_prompt: str | None = None
    t2i_mode: str | None = None
    grpc: GrpcProfileSettings = field(default_factory=GrpcProfileSettings)
    run_root: Path | None = None

    def has_drawthings_video(self) -> bool:
        return bool(self.video_configuration or self.video_configuration_json)


def _coerce_bool(value: object, *, field_name: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    raise ConfigurationError(f"{field_name} must be a boolean.")


def _coerce_int(value: object, *, field_name: str) -> int:
    if isinstance(value, bool):
        raise ConfigurationError(f"{field_name} must be an integer.")
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    raise ConfigurationError(f"{field_name} must be an integer.")


def _coerce_float(value: object, *, field_name: str) -> float:
    if isinstance(value, bool):
        raise ConfigurationError(f"{field_name} must be a number.")
    if isinstance(value, (int, float)):
        return float(value)
    raise ConfigurationError(f"{field_name} must be a number.")


def _coerce_str(value: object, *, field_name: str) -> str:
    if isinstance(value, str):
        return value
    raise ConfigurationError(f"{field_name} must be a string.")


def is_drawthings_generation_config(raw: dict[str, Any]) -> bool:
    """True when *raw* looks like a Draw Things generation JSON object (not manifest-only)."""
    return any(key in raw for key in _GENERATION_CONFIG_HINT_KEYS)


def parse_pipeline_settings(*, profile_stem: str, profile_path: Path, raw: dict[str, Any]) -> PipelineProfileSettings | None:
    block = raw.get(PIPELINE_METADATA_KEY)
    if block is None:
        return None
    if not isinstance(block, dict):
        raise ConfigurationError(f"{PIPELINE_METADATA_KEY} must be a JSON object.")

    grpc_raw = block.get("grpc", {})
    if grpc_raw is None:
        grpc_raw = {}
    if not isinstance(grpc_raw, dict):
        raise ConfigurationError(f"{PIPELINE_METADATA_KEY}.grpc must be a JSON object.")

    root_cert: Path | None = None
    if "root_cert" in grpc_raw and grpc_raw["root_cert"] is not None:
        root_cert = Path(_coerce_str(grpc_raw["root_cert"], field_name="grpc.root_cert")).expanduser()

    grpc = GrpcProfileSettings(
        host=_coerce_str(grpc_raw.get("host", "localhost"), field_name="grpc.host"),
        port=_coerce_int(grpc_raw.get("port", 7859), field_name="grpc.port"),
        no_tls=_coerce_bool(grpc_raw.get("no_tls", False), field_name="grpc.no_tls"),
        trust_server_cert=_coerce_bool(
            grpc_raw.get("trust_server_cert", False),
            field_name="grpc.trust_server_cert",
        ),
        force_trust_server_cert=_coerce_bool(
            grpc_raw.get("force_trust_server_cert", False),
            field_name="grpc.force_trust_server_cert",
        ),
        max_message_mb=_coerce_int(grpc_raw.get("max_message_mb", 64), field_name="grpc.max_message_mb"),
        user=_coerce_str(grpc_raw.get("user", "dts-utils"), field_name="grpc.user"),
        shared_secret=(
            _coerce_str(grpc_raw["shared_secret"], field_name="grpc.shared_secret")
            if grpc_raw.get("shared_secret") is not None
            else None
        ),
        root_cert=root_cert,
    )

    run_root: Path | None = None
    if block.get("run_root") is not None:
        run_root = Path(_coerce_str(block["run_root"], field_name="run_root")).expanduser()

    def _optional_str(key: str) -> str | None:
        if key not in block or block[key] is None:
            return None
        return _coerce_str(block[key], field_name=key)

    def _optional_int(key: str) -> int | None:
        if key not in block or block[key] is None:
            return None
        return _coerce_int(block[key], field_name=key)

    def _optional_float(key: str) -> float | None:
        if key not in block or block[key] is None:
            return None
        return _coerce_float(block[key], field_name=key)

    t2i_configuration = _optional_str("t2i_configuration") or _optional_str("configuration")
    t2i_mode = _optional_str("t2i_mode")
    if t2i_mode is not None and t2i_mode not in {"auto", "drawthings", "preset"}:
        raise ConfigurationError("t2i_mode must be one of: auto, drawthings, preset.")

    return PipelineProfileSettings(
        profile_stem=profile_stem,
        profile_path=profile_path,
        t2i_configuration=t2i_configuration,
        video_configuration=_optional_str("video_configuration"),
        configuration_json=_optional_str("configuration_json"),
        video_configuration_json=_optional_str("video_configuration_json"),
        i2v_backend=_optional_str("i2v_backend"),
        preset=_optional_str("preset"),
        fps=_optional_int("fps"),
        video_width=_optional_int("video_width"),
        video_height=_optional_int("video_height"),
        seconds=_optional_float("seconds"),
        width=_optional_int("width"),
        height=_optional_int("height"),
        seed=_optional_int("seed"),
        negative_prompt=_optional_str("negative_prompt"),
        video_negative_prompt=_optional_str("video_negative_prompt"),
        video_prompt=_optional_str("video_prompt"),
        t2i_mode=t2i_mode,
        grpc=grpc,
        run_root=run_root,
    )


def pipeline_profile_template_dir() -> Path:
    return Path(__file__).resolve().parent / "profile_templates"


def list_pipeline_profile_templates() -> list[str]:
    directory = pipeline_profile_template_dir()
    if not directory.is_dir():
        return []
    return sorted(path.stem for path in directory.glob("*.json") if path.is_file())


def pipeline_profile_template_path(name: str) -> Path:
    stem = Path(str(name)).stem
    path = pipeline_profile_template_dir() / f"{stem}.json"
    if not path.is_file():
        known = ", ".join(list_pipeline_profile_templates()) or "(none bundled)"
        raise ConfigurationError(f"Unknown pipeline profile template {stem!r}. Known templates: {known}.")
    return path


def scaffold_pipeline_profile(
    name: str,
    *,
    out_dir: Path,
    dry_run: bool = False,
    force: bool = False,
) -> Path:
    """Copy a bundled pipeline profile manifest into the saved configs directory."""
    template_path = pipeline_profile_template_path(name)
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / f"{Path(name).stem}.json"
    text = template_path.read_text(encoding="utf-8")
    if dest.exists() and not force:
        raise ConfigurationError(f"Refusing to overwrite {dest} (pass --force).")
    if dry_run:
        print(dest)
        return dest
    dest.write_text(text, encoding="utf-8")
    return dest


def is_pipeline_profile(name: str, *, config_dir: Path | None = None) -> bool:
    """True when *name* is a saved profile stem with ``_dts_utils_pipeline`` metadata."""
    stem = Path(str(name)).stem
    return stem in list_pipeline_profile_names(config_dir=config_dir)


def list_pipeline_profile_names(*, config_dir: Path | None = None) -> list[str]:
    """Saved profile stems whose JSON includes a ``_dts_utils_pipeline`` block."""
    names: list[str] = []
    for directory in configuration_search_directories(config_dir):
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.json")):
            if not path.is_file():
                continue
            try:
                with path.open(encoding="utf-8") as handle:
                    loaded = json.load(handle)
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(loaded, dict) and PIPELINE_METADATA_KEY in loaded:
                names.append(path.stem)
    return sorted(set(names))


def uses_drawthings_t2i(
    *,
    has_prompt: bool,
    configuration: str | None,
    configuration_json: str | None,
    profile: PipelineProfileSettings | None,
) -> bool:
    if not has_prompt:
        return False
    if profile is not None and profile.t2i_mode == "preset":
        return False
    if profile is not None and profile.t2i_mode == "drawthings":
        return True
    return bool(configuration or configuration_json)


def load_profile_document(profile: str | Path, *, config_dir: Path | None = None) -> tuple[Path, dict[str, Any]]:
    """Resolve and load a saved profile JSON document."""
    profile_path = resolve_configuration_value(profile, config_dir=config_dir)
    if profile_path.suffix.lower() != ".json":
        raise ConfigurationError("Pipeline profiles must be JSON (.json) files.")
    try:
        with profile_path.open(encoding="utf-8") as handle:
            loaded = json.load(handle)
    except OSError as exc:
        raise ConfigurationError(str(exc)) from exc
    except json.JSONDecodeError as exc:
        raise ConfigurationError(str(exc)) from exc
    if not isinstance(loaded, dict):
        raise ConfigurationError("Profile JSON must be an object.")
    return profile_path, loaded


def load_pipeline_profile(profile: str | Path, *, config_dir: Path | None = None) -> PipelineProfileSettings:
    profile_path, raw = load_profile_document(profile, config_dir=config_dir)
    settings = parse_pipeline_settings(profile_stem=profile_path.stem, profile_path=profile_path, raw=raw)
    if settings is None:
        raise ConfigurationError(
            f"Profile {profile_path.name!r} has no {PIPELINE_METADATA_KEY} block. "
            f"Add pipeline defaults to the profile or pass explicit CLI flags."
        )
    return settings


def merge_profile_into_run_args(args: Any, *, config_dir: Path | None = None) -> PipelineProfileSettings:
    """Apply ``args.profile`` defaults onto *args*; explicit CLI values (non-``None``) win."""
    profile_name = getattr(args, "profile", None)
    if not profile_name:
        raise ValueError("merge_profile_into_run_args requires args.profile")

    profile_path, raw = load_profile_document(profile_name, config_dir=config_dir)
    settings = parse_pipeline_settings(profile_stem=profile_path.stem, profile_path=profile_path, raw=raw)
    if settings is None:
        raise ConfigurationError(
            f"Profile {profile_path.name!r} has no {PIPELINE_METADATA_KEY} block. "
            "Add pipeline defaults under that key (see CLI.md)."
        )

    t2i_cfg, t2i_json = resolve_t2i_configuration_name(
        settings,
        raw,
        cli_configuration=getattr(args, "configuration", None),
        cli_configuration_json=getattr(args, "configuration_json", None),
    )
    if getattr(args, "configuration", None) is None and t2i_cfg is not None:
        args.configuration = t2i_cfg
    if getattr(args, "configuration_json", None) is None and t2i_json is not None:
        args.configuration_json = t2i_json

    if getattr(args, "video_configuration", None) is None and settings.video_configuration:
        args.video_configuration = settings.video_configuration
    if getattr(args, "video_configuration_json", None) is None and settings.video_configuration_json:
        args.video_configuration_json = settings.video_configuration_json
    if getattr(args, "i2v_backend", None) is None and settings.i2v_backend:
        args.i2v_backend = settings.i2v_backend
    if getattr(args, "preset", None) is None and settings.preset:
        args.preset = settings.preset
    if getattr(args, "fps", None) is None and settings.fps is not None:
        args.fps = settings.fps
    if getattr(args, "video_width", None) is None and settings.video_width is not None:
        args.video_width = settings.video_width
    if getattr(args, "video_height", None) is None and settings.video_height is not None:
        args.video_height = settings.video_height
    if getattr(args, "seconds", None) is None and settings.seconds is not None:
        args.seconds = settings.seconds
    if getattr(args, "width", None) is None and settings.width is not None:
        args.width = settings.width
    if getattr(args, "height", None) is None and settings.height is not None:
        args.height = settings.height
    if getattr(args, "seed", None) is None and settings.seed is not None:
        args.seed = settings.seed
    if getattr(args, "negative_prompt", None) is None and settings.negative_prompt is not None:
        args.negative_prompt = settings.negative_prompt
    if getattr(args, "video_negative_prompt", None) is None and settings.video_negative_prompt is not None:
        args.video_negative_prompt = settings.video_negative_prompt
    if getattr(args, "video_prompt", None) is None and settings.video_prompt is not None:
        args.video_prompt = settings.video_prompt
    if getattr(args, "run_root", None) is None and settings.run_root is not None:
        args.run_root = settings.run_root

    grpc = settings.grpc
    if getattr(args, "host", None) is None:
        args.host = grpc.host
    if getattr(args, "port", None) is None:
        args.port = grpc.port
    if getattr(args, "no_tls", None) is None:
        args.no_tls = grpc.no_tls
    if getattr(args, "trust_server_cert", None) is None:
        args.trust_server_cert = grpc.trust_server_cert
    if getattr(args, "force_trust_server_cert", None) is None:
        args.force_trust_server_cert = grpc.force_trust_server_cert
    if getattr(args, "max_message_mb", None) is None:
        args.max_message_mb = grpc.max_message_mb
    if getattr(args, "user", None) is None:
        args.user = grpc.user
    if getattr(args, "shared_secret", None) is None and grpc.shared_secret is not None:
        args.shared_secret = grpc.shared_secret
    if getattr(args, "root_cert", None) is None and grpc.root_cert is not None:
        args.root_cert = grpc.root_cert

    return settings


def resolve_t2i_configuration_name(
    profile: PipelineProfileSettings,
    raw: dict[str, Any],
    *,
    cli_configuration: str | None,
    cli_configuration_json: str | None,
) -> tuple[str | None, str | None]:
    """Return ``(configuration, configuration_json)`` stems/paths for the T2I step."""
    if cli_configuration or cli_configuration_json:
        return cli_configuration, cli_configuration_json
    if profile.configuration_json:
        return None, profile.configuration_json
    if profile.t2i_configuration:
        return profile.t2i_configuration, None
    if is_drawthings_generation_config(raw):
        return profile.profile_stem, None
    return None, None
