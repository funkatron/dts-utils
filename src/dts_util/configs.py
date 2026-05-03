"""Saved Draw Things generation configuration helpers."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


APP_NAME = "dts-util"
CONFIG_SUBDIR = "configurations"

# Shorthand ``dts-util "prompt"`` uses this profile name when no second positional is given.
DEFAULT_PROFILE_NAME = "default"
# Set by :func:`ensure_default_generation_json_config` via ``os.environ.setdefault`` so subprocesses
# and later tools see the same default (user-exported env wins).
DEFAULT_CONFIGURATION_ENV = "DTS_UTIL_DEFAULT_CONFIGURATION"
# Optional override for the ``model`` field when auto-creating ``default.json``.
DEFAULT_MODEL_ENV = "DTS_UTIL_DEFAULT_MODEL"


def user_config_dir() -> Path:
    """Return the platform-appropriate dts-util configuration directory."""
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    if sys.platform.startswith("win"):
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / APP_NAME
        return Path.home() / "AppData" / "Roaming" / APP_NAME

    xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config_home:
        return Path(xdg_config_home) / APP_NAME
    return Path.home() / ".config" / APP_NAME


def configurations_dir() -> Path:
    """Return the directory for saved Draw Things JSON configurations."""
    return user_config_dir() / CONFIG_SUBDIR


def list_configuration_names(config_dir: Path | None = None) -> list[str]:
    """List saved JSON configuration names without the .json suffix."""
    directory = config_dir or configurations_dir()
    if not directory.exists():
        return []
    return sorted(path.stem for path in directory.glob("*.json") if path.is_file())


def resolve_configuration_value(value: str | Path, config_dir: Path | None = None) -> Path:
    """Resolve a path or saved JSON config name to an on-disk file."""
    raw_value = str(value)
    explicit_path = Path(raw_value).expanduser()
    if explicit_path.exists():
        return explicit_path

    if explicit_path.is_absolute() or explicit_path.parent != Path("."):
        raise ValueError(f"Configuration file not found: {explicit_path}")

    if explicit_path.suffix and explicit_path.suffix.lower() != ".json":
        raise ValueError(f"Configuration file not found: {explicit_path}")

    directory = config_dir or configurations_dir()
    saved_name = explicit_path.name if explicit_path.suffix.lower() == ".json" else f"{explicit_path.name}.json"
    saved_path = directory / saved_name
    if saved_path.exists():
        return saved_path

    raise ValueError(
        "Could not resolve generation configuration "
        f"{raw_value!r}. Looked for {explicit_path} and {saved_path}. "
        f"Save named JSON configs in {directory} or run `uv run dts-util configs path`."
    )


def guess_default_model_basename() -> str:
    """Pick a checkpoint file name for auto-generated ``default.json``, or return ``\"\"``."""
    explicit = os.environ.get(DEFAULT_MODEL_ENV, "").strip()
    if explicit:
        return explicit
    raw = os.environ.get("DRAW_THINGS_MODEL_PATH", "").strip()
    if raw:
        models_dir = Path(raw).expanduser()
    else:
        from dts_util.model_index.local import default_models_dir

        models_dir = default_models_dir()
    if not models_dir.is_dir():
        return ""
    for pattern in ("*.ckpt", "*.safetensors"):
        candidates = sorted(models_dir.glob(pattern))
        if candidates:
            return candidates[0].name
    return ""


def default_generation_config_template_dict() -> dict:
    """Minimal Draw Things JSON shape for ``default.json`` (camelCase; normalized by flatc pipeline)."""
    model = guess_default_model_basename()
    return {
        "width": 512,
        "height": 512,
        "batchCount": 1,
        "steps": 28,
        "guidanceScale": 7.5,
        "hiresFix": False,
        "model": model,
        "controls": [],
        "faceRestoration": "",
    }


def ensure_default_generation_json_config() -> Path:
    """Ensure ``configurations/default.json`` exists; set ``DEFAULT_CONFIGURATION_ENV`` if unset.

    Creates the configurations directory, writes a starter JSON when the file is missing
    (model guessed from the Draw Things models directory when possible), and runs
    ``os.environ.setdefault(DEFAULT_CONFIGURATION_ENV, DEFAULT_PROFILE_NAME)``.
    """
    directory = configurations_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{DEFAULT_PROFILE_NAME}.json"
    if not path.is_file():
        payload = default_generation_config_template_dict()
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if not (str(payload.get("model") or "")).strip():
            print(
                "dts-util: created default.json with an empty model name. "
                f"Set {DEFAULT_MODEL_ENV}, put a .ckpt in your Draw Things Models folder, or edit:\n"
                f"  {path}",
                file=sys.stderr,
            )
    os.environ.setdefault(DEFAULT_CONFIGURATION_ENV, DEFAULT_PROFILE_NAME)
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manage saved Draw Things JSON generation configurations.",
        epilog="""Examples:
  dts-util configs path
  dts-util configs list
  dts-util configs list --directory ./configs
""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="action", required=True)

    path_parser = subparsers.add_parser("path", help="Print the saved configuration directory.")
    path_parser.add_argument("--no-create", action="store_true", help="Do not create the directory before printing it.")

    list_parser = subparsers.add_parser("list", help="List saved JSON configuration names.")
    list_parser.add_argument("--directory", type=Path, help="Directory to list instead of the default config directory.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.action == "path":
        directory = configurations_dir()
        if not args.no_create:
            directory.mkdir(parents=True, exist_ok=True)
        print(directory)
        return 0

    if args.action == "list":
        directory = args.directory or configurations_dir()
        names = list_configuration_names(directory)
        if not names:
            print(f"No saved JSON configurations in {directory}.")
            return 0
        for name in names:
            print(name)
        return 0

    parser.error(f"Unsupported action: {args.action}")
    return 2
