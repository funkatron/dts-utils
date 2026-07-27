"""Saved Draw Things generation configuration helpers."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

from dts_utils.cli_prog import cli_command_name
from dts_utils.exceptions import ConfigurationError


APP_NAME = "dts-utils"
CONFIG_SUBDIR = "configurations"

# Shorthand ``dts-utils "prompt"`` uses this saved profile when no second positional is given.
DEFAULT_PROFILE_NAME = "default"
# Set by :func:`ensure_default_generation_json_config` via ``os.environ.setdefault`` so subprocesses
# and later tools see the same default (user-exported env wins).
DEFAULT_CONFIGURATION_ENV = "DTS_UTILS_DEFAULT_CONFIGURATION"
# Optional override for the ``model`` field when auto-creating implicit profile JSON.
DEFAULT_MODEL_ENV = "DTS_UTILS_DEFAULT_MODEL"


def _xdg_config_app_dir(app_part: str) -> Path:
    """Config root under XDG conventions: ``$XDG_CONFIG_HOME/<app_part>`` or ``~/.config/<app_part>``."""
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config_home:
        return Path(xdg_config_home).expanduser() / app_part
    return Path.home() / ".config" / app_part


def _windows_roaming_app_dir(app_part: str) -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / app_part
    return Path.home() / "AppData" / "Roaming" / app_part


def user_config_dir() -> Path:
    """Return the platform-appropriate configuration directory for this tool (``…/dts-utils``).

    macOS uses the same XDG-style layout as Linux (``~/.config/dts-utils`` by default), not
    ``~/Library/Application Support``.
    """
    if sys.platform.startswith("win"):
        return _windows_roaming_app_dir(APP_NAME)
    return _xdg_config_app_dir(APP_NAME)


def configurations_dir() -> Path:
    """Return the directory for saved Draw Things JSON configurations."""
    return user_config_dir() / CONFIG_SUBDIR


def legacy_configurations_dirs() -> tuple[Path, ...]:
    """Older layout paths to merge into listings and name resolution (no writes).

    macOS previously used ``~/Library/Application Support/dts-utils``; some installs used
    the ``dts-util`` folder name. Listing merges stems from these when present so ``dts-utils web``
    and ``configs list`` still see profiles until files are moved under :func:`configurations_dir`.
    """
    if sys.platform.startswith("win"):
        return ()
    home = Path.home()
    return (
        home / "Library" / "Application Support" / "dts-utils" / CONFIG_SUBDIR,
        home / "Library" / "Application Support" / "dts-util" / CONFIG_SUBDIR,
        home / ".config" / "dts-util" / CONFIG_SUBDIR,
    )


def configuration_search_directories(config_dir: Path | None = None) -> tuple[Path, ...]:
    """Directories to scan for ``*.json`` profiles (primary first, then legacy when using defaults)."""
    primary = configurations_dir() if config_dir is None else config_dir
    if config_dir is not None:
        return (primary,)
    return (primary, *legacy_configurations_dirs())


def list_configuration_names(config_dir: Path | None = None) -> list[str]:
    """List saved JSON configuration names without the .json suffix."""
    stems: set[str] = set()
    for directory in configuration_search_directories(config_dir):
        if not directory.exists():
            continue
        stems.update(path.stem for path in directory.glob("*.json") if path.is_file())
    return sorted(stems)


def resolve_configuration_value(value: str | Path, config_dir: Path | None = None) -> Path:
    """Resolve a path or saved JSON config name to an on-disk file."""
    raw_value = str(value)
    explicit_path = Path(raw_value).expanduser()
    if explicit_path.exists():
        return explicit_path

    if explicit_path.is_absolute():
        raise ValueError(f"Configuration file not found: {explicit_path}")

    if explicit_path.parent != Path("."):
        raise ValueError(f"Configuration file not found: {explicit_path}")

    # Single path component: either a saved profile stem or a raw FlatBuffer next to cwd.
    # Pathlib treats the last dotted segment as ``suffix`` (e.g. ``dreamshaper-v6.31`` → ``.31``),
    # so we cannot reject "unknown extensions" without breaking community preset stems.
    suffix_lower = explicit_path.suffix.lower()
    raw_flatbuffer_suffixes = frozenset({".fb", ".bin"})
    if suffix_lower in raw_flatbuffer_suffixes:
        raise ValueError(f"Configuration file not found: {explicit_path}")

    saved_name = explicit_path.name if suffix_lower == ".json" else f"{explicit_path.name}.json"
    searched: list[Path] = []
    for directory in configuration_search_directories(config_dir):
        saved_path = directory / saved_name
        searched.append(saved_path)
        if saved_path.exists():
            return saved_path

    hint_dir = configurations_dir() if config_dir is None else config_dir
    raise ValueError(
        "Could not resolve generation configuration "
        f"{raw_value!r}. Looked for {explicit_path} and tried {saved_name} at: "
        + ", ".join(str(p) for p in searched)
        + ". "
        f"Save named JSON configs in {hint_dir} or run `uv run dts-utils configs path`."
    )


def guess_default_model_basename() -> str:
    """Pick a checkpoint file name for auto-created implicit profile JSON, or return ``\"\"``."""
    explicit = os.environ.get(DEFAULT_MODEL_ENV, "").strip()
    if explicit:
        return explicit
    raw = os.environ.get("DRAW_THINGS_MODEL_PATH", "").strip()
    if raw:
        models_dir = Path(raw).expanduser()
    else:
        from dts_utils.model_index.local import default_models_dir

        models_dir = default_models_dir()
    if not models_dir.is_dir():
        return ""
    for pattern in ("*.ckpt", "*.safetensors"):
        candidates = sorted(models_dir.glob(pattern))
        if candidates:
            return candidates[0].name
    return ""


def default_generation_config_template_dict() -> dict:
    """Minimal Draw Things JSON shape for a new implicit profile file (camelCase; normalized by flatc)."""
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


def _parse_resolution_hint_for_scaffold(text: str) -> tuple[int, int] | None:
    m = re.search(r"(\d+)\s*[×xX]\s*(\d+)", text)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def _parse_steps_hint_for_scaffold(text: str) -> int | None:
    stripped = text.strip()
    m = re.search(r"(\d+)\s*[–—-]\s*(\d+)", stripped)
    if m:
        lo, hi = int(m.group(1)), int(m.group(2))
        return round((lo + hi) / 2)
    m = re.search(r"(?:^|\s)(\d+)\s*(?:steps|step)\b", stripped, re.IGNORECASE)
    if m:
        return int(m.group(1))
    if stripped.isdigit():
        return int(stripped)
    return None


def scaffold_generation_json_from_community_metadata(metadata: dict[str, object]) -> dict[str, object]:
    """Build starter Draw Things generation JSON from a ``community-models`` ``metadata.json`` dict.

    Copies the checkpoint name from ``file``. Width, height, and steps are prefilled only when the
    ``note`` text contains wording this tool understands (same source material as ``dts-utils models build``).
    Entries with ``remote_api_model_config`` are skipped — those models are not local checkpoints.
    """
    if "remote_api_model_config" in metadata:
        raise ValueError(
            "This metadata.json is for a cloud/API model, not a downloaded checkpoint — "
            "there is no local preset to scaffold."
        )
    file_val = metadata.get("file")
    if not isinstance(file_val, str) or not file_val.strip():
        raise ValueError("metadata missing non-empty string field 'file' (checkpoint basename).")

    from dts_utils.model_index.parse import extract_suggested_config

    model = file_val.strip()
    if not model.endswith((".ckpt", ".safetensors")):
        model = f"{model}.ckpt"

    base: dict[str, object] = dict(default_generation_config_template_dict())
    base["model"] = model

    suggested = extract_suggested_config(metadata)
    rt_raw = suggested.get("recommended_tuning") if isinstance(suggested, dict) else None
    rt: dict[str, object] = rt_raw if isinstance(rt_raw, dict) else {}

    res_text = rt.get("resolution")
    if isinstance(res_text, str):
        wh = _parse_resolution_hint_for_scaffold(res_text)
        if wh:
            base["width"], base["height"] = wh[0], wh[1]

    steps_text = rt.get("steps")
    if isinstance(steps_text, str):
        steps = _parse_steps_hint_for_scaffold(steps_text)
        if steps is not None:
            base["steps"] = steps

    return base


def default_profile_stem_for_community_metadata(metadata_path: Path, metadata: dict[str, object]) -> str:
    """Prefer community folder slug; fall back to checkpoint stem."""
    parent = metadata_path.resolve().parent.name.strip()
    if parent and parent not in {".", ".."}:
        return parent
    file_val = metadata.get("file")
    if isinstance(file_val, str) and file_val.strip():
        return Path(file_val.strip()).stem
    return "profile"


def iter_scannable_community_metadata_files(scan_root: Path) -> list[Path]:
    """Sorted paths to ``metadata.json`` under *scan_root*, skipping ``apis/`` subtrees."""
    root = scan_root.expanduser().resolve()
    if not root.is_dir():
        return []
    out: list[Path] = []
    for path in sorted(root.rglob("metadata.json")):
        if not path.is_file():
            continue
        try:
            rel_parts = path.parent.resolve().relative_to(root).parts
        except ValueError:
            rel_parts = ()
        if "apis" in rel_parts:
            continue
        out.append(path)
    return out


def _load_metadata_object(path: Path) -> dict[str, object] | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


def run_scaffold_scan(
    scan_root: Path,
    *,
    out_dir: Path,
    dry_run: bool,
    force: bool,
    limit: int | None,
    verbose: bool,
) -> int:
    """Batch scaffold from all eligible ``metadata.json`` files under *scan_root*. Returns exit code."""
    root = scan_root.expanduser().resolve()
    if not root.is_dir():
        print(f"Not a directory: {scan_root}", file=sys.stderr)
        return 2

    paths = iter_scannable_community_metadata_files(root)
    if limit is not None and limit >= 0:
        paths = paths[:limit]

    wrote = 0
    skipped_existing = 0
    skipped_unusable = 0
    invalid_json = 0

    for meta_path in paths:
        payload = _load_metadata_object(meta_path)
        if payload is None:
            invalid_json += 1
            if verbose:
                print(f"skip (invalid JSON): {meta_path}", file=sys.stderr)
            continue
        try:
            body = scaffold_generation_json_from_community_metadata(payload)
        except ValueError as exc:
            skipped_unusable += 1
            if verbose:
                print(f"skip: {meta_path} ({exc})", file=sys.stderr)
            continue

        stem = default_profile_stem_for_community_metadata(meta_path, payload)
        out_path = out_dir / f"{stem}.json"
        text = json.dumps(body, indent=2, sort_keys=True) + "\n"

        if dry_run:
            print(f"would write {out_path.name}\t{meta_path}")
            wrote += 1
            continue

        if out_path.exists() and not force:
            skipped_existing += 1
            if verbose:
                print(f"skip (exists): {out_path}", file=sys.stderr)
            continue

        try:
            out_path.write_text(text, encoding="utf-8")
        except OSError as exc:
            print(f"Could not write {out_path}: {exc}", file=sys.stderr)
            return 2
        wrote += 1
        if verbose:
            print(out_path)

    parts = [
        f"wrote {wrote}" if not dry_run else f"would write {wrote}",
        f"skipped {skipped_existing} existing",
        f"skipped {skipped_unusable} (cloud/API or missing checkpoint)",
        f"{invalid_json} invalid JSON",
    ]
    print(f"scaffold-from-metadata --scan: {', '.join(parts)}.", file=sys.stderr)
    return 0


def ensure_default_generation_json_config() -> Path:
    """Ensure ``configurations/default.json`` exists; set ``DEFAULT_CONFIGURATION_ENV`` if unset.

    If ``default.json`` is missing but a legacy ``zit.json`` exists in the same directory,
    renames ``zit.json`` → ``default.json`` so older installs keep their profile.

    Creates the configurations directory and writes a starter JSON when the implicit profile file is still missing,
    then runs ``os.environ.setdefault(DEFAULT_CONFIGURATION_ENV, DEFAULT_PROFILE_NAME)``.
    """
    directory = configurations_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{DEFAULT_PROFILE_NAME}.json"
    legacy_zit = directory / "zit.json"
    if not path.is_file() and legacy_zit.is_file():
        try:
            legacy_zit.rename(path)
        except OSError:
            path.write_bytes(legacy_zit.read_bytes())
            try:
                legacy_zit.unlink()
            except OSError:
                pass
    if not path.is_file():
        payload = default_generation_config_template_dict()
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if not (str(payload.get("model") or "")).strip():
            print(
                f"dts-utils: created {path.name} with an empty model name. "
                f"Set {DEFAULT_MODEL_ENV}, put a .ckpt in your Draw Things Models folder, or edit:\n"
                f"  {path}",
                file=sys.stderr,
            )
    os.environ.setdefault(DEFAULT_CONFIGURATION_ENV, DEFAULT_PROFILE_NAME)
    return path


def draw_things_container_documents() -> Path:
    """macOS sandbox root for Draw Things user files (Documents inside the container)."""
    return Path.home() / "Library/Containers/com.liuliu.draw-things/Data/Documents"


def draw_things_custom_configs_path() -> Path:
    """Draw Things ``Local`` configuration presets (array of ``name`` + ``configuration`` objects)."""
    return draw_things_container_documents() / "Models" / "custom_configs.json"


# App metadata mirrored by ``import-draw-things --mirror-app-json`` (not FlatBuffer generation configs).
DRAW_THINGS_APP_MIRROR_SUBDIR = "draw-things-app"


def normalize_profile_stem(stem: str, *, fallback: str = "profile") -> str:
    """Normalize a saved profile stem to lowercase kebab-case (``a-z``, digits, ``-``, ``.``)."""
    parts: list[str] = []
    for ch in stem.strip():
        if ch.isalnum() or ch in "-.":
            parts.append(ch.lower() if ch.isalpha() else ch)
        elif ch.isspace() or ch == "_":
            parts.append("-")
        else:
            parts.append("-")
    normalized = re.sub(r"-+", "-", "".join(parts)).strip("._-")
    return (normalized or fallback)[:120]


_MODEL_QUANT_SUFFIX_RE = re.compile(
    r"(?:_(?:q\d+p(?:_q\d+p)?|f16|f32|bf16|fp8|fp16|fp32))+$",
    re.IGNORECASE,
)


def _model_stem_for_profile_name(model: object) -> str:
    if not isinstance(model, str) or not model.strip():
        return ""
    stem = Path(model.strip()).name
    if stem.lower().endswith(".ckpt"):
        stem = stem[: -len(".ckpt")]
    elif "." in stem:
        stem = Path(stem).stem
    stem = _MODEL_QUANT_SUFFIX_RE.sub("", stem)
    return normalize_profile_stem(stem, fallback="")


def _stem_from_draw_things_preset_name(name: object | None, idx: int) -> str:
    raw = name if isinstance(name, str) else ""
    base = raw.strip() or f"draw-things-{idx}"
    return normalize_profile_stem(base, fallback=f"draw-things-{idx}")


def stem_for_draw_things_import(
    preset_name: object | None,
    configuration: dict,
    *,
    used: set[str],
    index: int,
) -> str:
    """Build a human-useful kebab stem from a Draw Things preset name and model."""
    raw_name = preset_name.strip() if isinstance(preset_name, str) else ""
    base = normalize_profile_stem(raw_name, fallback="") if raw_name else ""
    model_part = _model_stem_for_profile_name(configuration.get("model"))
    if not base or base.startswith("draw-things-"):
        base = model_part or f"draw-things-{index}"

    candidate = base
    if candidate in used and model_part and model_part not in candidate:
        candidate = f"{base}-{model_part}"

    stem = candidate
    suffix = 2
    while stem in used:
        stem = f"{candidate}-{suffix}"
        suffix += 1
    used.add(stem)
    return stem


def _smoke_imported_profile(path: Path, *, host: str = "localhost", port: int = 7859) -> str | None:
    """Return None on success, or an error string. Caller must ensure the server is up."""
    import grpc

    from dts_utils.configuration_build import read_json_configuration_bytes
    from dts_utils.grpc.connection import create_channel

    try:
        payload = read_json_configuration_bytes(path)
    except ConfigurationError as exc:
        return str(exc)
    if not payload:
        return "configuration FlatBuffer was empty"

    channel = create_channel(host, port, trust_server_cert=True)
    try:
        grpc.channel_ready_future(channel).result(timeout=2.0)
    except Exception as exc:  # noqa: BLE001
        return f"gRPC channel not ready: {exc}"
    finally:
        channel.close()
    return None


def import_draw_things_saved_configs(
    *,
    out_dir: Path,
    source: Path | None = None,
    force: bool = False,
    dry_run: bool = False,
    mirror_app_json: bool = False,
    raw: bool = False,
    no_smoke: bool = False,
    smoke_all: bool = False,
) -> int:
    """Split Draw Things ``custom_configs.json`` into ``OUT_DIR/<stem>.json`` profiles.

    By default each preset is normalized and repaired until ``flatc`` accepts it, then written
    under a human-useful kebab stem. Pass ``raw=True`` to copy the inner ``configuration`` as-is
    (legacy behavior).

    With ``mirror_app_json``, auxiliary ``Models/custom*.json`` (etc.) are copied under
    ``OUT_DIR/draw-things-app/`` only—they are **not** valid ``--configuration`` inputs for
    ``dts-utils generate``.
    """
    from dts_utils.configuration_build import prepare_configuration_for_generate, resolve_flatc_path
    from dts_utils.grpc.utils import is_server_running

    src = source.expanduser() if source else draw_things_custom_configs_path()
    if not src.is_file():
        print(f"Not found: {src}", file=sys.stderr)
        print(
            "Expected Draw Things Local configurations at Models/custom_configs.json in the app container.",
            file=sys.stderr,
        )
        return 2

    try:
        raw_json = json.loads(src.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"{src}: invalid JSON ({exc})", file=sys.stderr)
        return 2
    if not isinstance(raw_json, list):
        print(f"{src}: expected a JSON array", file=sys.stderr)
        return 2

    if not raw and resolve_flatc_path() is None:
        print(
            "flatc is required for one-step import (converts JSON for generate). "
            "Install FlatBuffers (e.g. brew install flatbuffers), or pass --raw to copy presets as-is.",
            file=sys.stderr,
        )
        return 2

    out_dir = out_dir.expanduser()
    if not dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)

    if raw:
        print(
            "Importing with --raw: presets are copied as-is and may need edits before generate.",
            file=sys.stderr,
        )
    else:
        print(
            "Importing for generate: normalizing presets and repairing until flatc accepts them.",
            file=sys.stderr,
        )

    used_stems: set[str] = set()
    stem_counts: dict[str, int] = {}

    def allocate_stem_legacy(base: str) -> str:
        n = stem_counts.get(base, 0) + 1
        stem_counts[base] = n
        return base if n == 1 else f"{base}-{n}"

    written = 0
    skipped = 0
    repaired = 0
    failed = 0
    smoke_candidates: list[Path] = []

    for i, item in enumerate(raw_json, start=1):
        if not isinstance(item, dict):
            skipped += 1
            continue
        cfg = item.get("configuration")
        if not isinstance(cfg, dict):
            print(f"skip entry {i}: missing configuration object", file=sys.stderr)
            skipped += 1
            continue

        source_name = item.get("name") if isinstance(item.get("name"), str) else ""
        if raw:
            stem = allocate_stem_legacy(_stem_from_draw_things_preset_name(item.get("name"), i))
            payload: dict = dict(cfg)
            notes: list[str] = []
        else:
            try:
                prepared, notes = prepare_configuration_for_generate(cfg)
            except ConfigurationError as exc:
                print(f"fail entry {i} ({source_name or 'unnamed'}): {exc}", file=sys.stderr)
                failed += 1
                continue
            stem = stem_for_draw_things_import(
                item.get("name"),
                cfg,
                used=used_stems,
                index=i,
            )
            payload = dict(prepared)
            import_meta: dict[str, object] = {}
            if source_name.strip():
                import_meta["source_name"] = source_name.strip()
            if notes:
                import_meta["notes"] = list(notes)
                repaired += 1
            if import_meta:
                payload["_dts_utils_import"] = import_meta

        out_path = out_dir / f"{stem}.json"
        text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        if out_path.exists() and not force:
            print(f"skip (exists): {out_path}", file=sys.stderr)
            skipped += 1
            continue
        if dry_run:
            print(out_path)
            written += 1
            smoke_candidates.append(out_path)
            continue
        out_path.write_text(text, encoding="utf-8")
        print(out_path)
        written += 1
        smoke_candidates.append(out_path)

    if mirror_app_json:
        aux_dir = out_dir / DRAW_THINGS_APP_MIRROR_SUBDIR
        print(
            f"Mirroring Draw Things app metadata under {aux_dir}/ "
            f"(not for generate --configuration; presets stay as *.json in {out_dir}).",
            file=sys.stderr,
        )
        doc = draw_things_container_documents()
        models_dir = doc / "Models"
        extra: list[Path] = []
        if models_dir.is_dir():
            extra.extend(sorted(models_dir.glob("custom*.json")))
        adv = doc / "advanced_sections.json"
        if adv.is_file():
            extra.append(adv)
        scripts_json = doc / "Scripts" / "custom_scripts.json"
        if scripts_json.is_file():
            extra.append(scripts_json)

        if not dry_run:
            aux_dir.mkdir(parents=True, exist_ok=True)

        for p in extra:
            dest = aux_dir / p.name
            if dest.exists() and not force:
                print(f"skip (exists): {dest}", file=sys.stderr)
                skipped += 1
                continue
            if dry_run:
                print(dest)
                written += 1
                continue
            dest.write_bytes(p.read_bytes())
            print(dest)
            written += 1

    if written == 0:
        print(
            f"No files written ({skipped} skipped, {failed} failed). "
            "Try --dry-run, or --force to overwrite existing profiles.",
            file=sys.stderr,
        )
        return 2

    print(
        f"Done: {written} written, {repaired} repaired, {failed} failed, {skipped} skipped.",
        file=sys.stderr,
    )

    if not raw and not no_smoke and not dry_run and smoke_candidates:
        if not is_server_running("localhost", 7859):
            print(
                "Smoke skipped: gRPC server not reachable on localhost:7859 "
                "(start with dts-utils server start, or pass --no-smoke).",
                file=sys.stderr,
            )
        else:
            targets = smoke_candidates if smoke_all else smoke_candidates[:1]
            for path in targets:
                err = _smoke_imported_profile(path)
                if err:
                    print(f"Smoke warning ({path.name}): {err}", file=sys.stderr)
                else:
                    print(f"Smoke ok: {path.name} (server reachable, flatc bytes ok).", file=sys.stderr)

    return 0 if failed == 0 else 1


def build_parser() -> argparse.ArgumentParser:
    prog = cli_command_name()
    parser = argparse.ArgumentParser(
        prog=f"{prog} configs",
        description="Manage saved Draw Things JSON generation configurations.",
        epilog="""Examples:
  dts-utils configs path
  dts-utils configs list
  dts-utils configs list --directory ./configs
  dts-utils configs import-draw-things
  dts-utils configs import-draw-things --dry-run
  dts-utils configs import-draw-things --raw
  dts-utils configs import-draw-things --mirror-app-json --dry-run
  dts-utils configs scaffold-from-metadata ~/.cache/community-models/models/flux-2-klein-base-9b/metadata.json
  dts-utils configs scaffold-from-metadata ./metadata.json --dry-run
  dts-utils configs scaffold-from-metadata --scan ~/.cache/community-models/models --limit 20 --dry-run
  dts-utils configs scaffold-pipeline prompt-to-video
  dts-utils configs scaffold-pipeline --list
""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="action", required=True)

    path_parser = subparsers.add_parser("path", help="Print the saved configuration directory.")
    path_parser.add_argument("--no-create", action="store_true", help="Do not create the directory before printing it.")

    list_parser = subparsers.add_parser("list", help="List saved JSON configuration names.")
    list_parser.add_argument("--directory", type=Path, help="Directory to list instead of the default config directory.")

    scaffold_parser = subparsers.add_parser(
        "scaffold-from-metadata",
        help=(
            "Write starter saved JSON from a drawthingsai/community-models metadata.json "
            "(local checkpoints only)."
        ),
    )
    scaffold_parser.add_argument(
        "metadata",
        nargs="?",
        type=Path,
        default=None,
        help="Single metadata.json (omit when using --scan DIR).",
    )
    scaffold_parser.add_argument(
        "--scan",
        type=Path,
        metavar="DIR",
        default=None,
        help=(
            "Walk DIR recursively for metadata.json (skips apis/ trees). "
            "Writes one starter profile per local checkpoint."
        ),
    )
    scaffold_parser.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="With --scan: process at most N metadata files (sorted paths).",
    )
    scaffold_parser.add_argument(
        "--verbose",
        action="store_true",
        help="With --scan: print each output path written, and each skipped file.",
    )
    scaffold_parser.add_argument(
        "--name",
        type=str,
        help="Saved profile stem without .json (default: parent folder name, e.g. flux-2-klein-base-9b).",
    )
    scaffold_parser.add_argument(
        "--directory",
        type=Path,
        help="Directory to write NAME.json (default: same as ``dts-utils configs path``).",
    )
    scaffold_parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Single file: print JSON only. "
            "With --scan: list would-write paths instead of saving (see stderr summary)."
        ),
    )
    scaffold_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing NAME.json.",
    )

    pipeline_parser = subparsers.add_parser(
        "scaffold-pipeline",
        help="Install a bundled pipeline profile manifest (_dts_utils_pipeline) into saved configs.",
    )
    pipeline_parser.add_argument(
        "name",
        nargs="?",
        default="prompt-to-video",
        help="Template name (default: prompt-to-video). Use --list to see bundled templates.",
    )
    pipeline_parser.add_argument(
        "--list",
        action="store_true",
        help="List bundled pipeline profile templates and exit.",
    )
    pipeline_parser.add_argument(
        "--directory",
        type=Path,
        help="Directory to write NAME.json (default: ``dts-utils configs path``).",
    )
    pipeline_parser.add_argument("--dry-run", action="store_true", help="Print destination path only.")
    pipeline_parser.add_argument("--force", action="store_true", help="Overwrite an existing NAME.json.")

    import_dt_parser = subparsers.add_parser(
        "import-draw-things",
        help=(
            "Import Draw Things Local configurations from the macOS app sandbox "
            "(Models/custom_configs.json) into separate saved JSON profiles. "
            "Default: normalize/repair until flatc accepts each preset (one-step for generate). "
            "Use --raw to copy as-is."
        ),
    )
    import_dt_parser.add_argument(
        "--source",
        type=Path,
        default=None,
        help="Path to custom_configs.json (default: Draw Things container Models/custom_configs.json).",
    )
    import_dt_parser.add_argument(
        "--directory",
        type=Path,
        default=None,
        help="Directory for output .json files (default: same as ``dts-utils configs path``).",
    )
    import_dt_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing output files.",
    )
    import_dt_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print paths that would be written without creating files.",
    )
    import_dt_parser.add_argument(
        "--mirror-app-json",
        action="store_true",
        help=(
            "Also copy Models/custom*.json, Documents/advanced_sections.json, "
            "and Scripts/custom_scripts.json into OUTPUT/draw-things-app/ "
            "(app metadata only — not valid --configuration for generate)."
        ),
    )
    import_dt_parser.add_argument(
        "--raw",
        action="store_true",
        help="Copy preset configuration objects as-is (skip flatc normalize/repair).",
    )
    import_dt_parser.add_argument(
        "--no-smoke",
        action="store_true",
        help="Skip the optional localhost gRPC smoke after a successful import.",
    )
    import_dt_parser.add_argument(
        "--smoke-all",
        action="store_true",
        help="Smoke every written profile when the server is up (default: first only).",
    )
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

    if args.action == "scaffold-from-metadata":
        out_dir = (args.directory or configurations_dir()).expanduser()
        out_dir.mkdir(parents=True, exist_ok=True)

        if args.scan is None and args.limit is not None:
            print("--limit applies only with --scan DIR.", file=sys.stderr)
            return 2

        if args.scan is not None and args.metadata is not None:
            print("Use either a single METADATA.json path or --scan DIR, not both.", file=sys.stderr)
            return 2
        if args.scan is not None:
            if args.name:
                print("--name cannot be used with --scan.", file=sys.stderr)
                return 2
            if args.limit is not None and args.limit < 0:
                print("--limit must be >= 0.", file=sys.stderr)
                return 2
            return run_scaffold_scan(
                args.scan,
                out_dir=out_dir,
                dry_run=args.dry_run,
                force=args.force,
                limit=args.limit,
                verbose=args.verbose,
            )

        if args.metadata is None:
            print(
                "scaffold-from-metadata: pass METADATA.json or use --scan DIR.",
                file=sys.stderr,
            )
            return 2

        meta_path = args.metadata.expanduser()
        if not meta_path.is_file():
            print(f"Not a file: {meta_path}", file=sys.stderr)
            return 2
        try:
            payload = json.loads(meta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"{meta_path}: invalid JSON ({exc})", file=sys.stderr)
            return 2
        if not isinstance(payload, dict):
            print(f"{meta_path}: expected a JSON object", file=sys.stderr)
            return 2
        try:
            body = scaffold_generation_json_from_community_metadata(payload)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        stem = (args.name.strip() if args.name else "") or default_profile_stem_for_community_metadata(
            meta_path,
            payload,
        )
        text = json.dumps(body, indent=2, sort_keys=True) + "\n"
        if args.dry_run:
            print(text, end="")
            return 0
        out_path = out_dir / f"{stem}.json"
        if out_path.exists() and not args.force:
            print(f"Refusing to overwrite {out_path} (pass --force).", file=sys.stderr)
            return 2
        out_path.write_text(text, encoding="utf-8")
        print(out_path)
        return 0

    if args.action == "scaffold-pipeline":
        from dts_utils.exceptions import ConfigurationError
        from dts_utils.pipeline.profile import (
            list_pipeline_profile_templates,
            scaffold_pipeline_profile,
        )

        if args.list:
            names = list_pipeline_profile_templates()
            if not names:
                print("No bundled pipeline profile templates.")
                return 0
            for template_name in names:
                print(template_name)
            return 0

        out_dir = (args.directory or configurations_dir()).expanduser()
        try:
            dest = scaffold_pipeline_profile(
                args.name,
                out_dir=out_dir,
                dry_run=args.dry_run,
                force=args.force,
            )
        except ConfigurationError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        if not args.dry_run:
            print(dest)
            print(
                "Next: ensure referenced profiles exist (e.g. default, ltx-2.3-portrait). "
                "Then: dts-utils generate --profile "
                f"{Path(args.name).stem} --prompt \"…\" --trust-server-cert  "
                "or select it in dts-utils web.",
                file=sys.stderr,
            )
        return 0

    if args.action == "import-draw-things":
        out_dir = args.directory.expanduser() if args.directory else configurations_dir()
        src = args.source.expanduser() if args.source else None
        return import_draw_things_saved_configs(
            out_dir=out_dir,
            source=src,
            force=args.force,
            dry_run=args.dry_run,
            mirror_app_json=args.mirror_app_json,
            raw=args.raw,
            no_smoke=args.no_smoke,
            smoke_all=args.smoke_all,
        )

    parser.error(f"Unsupported action: {args.action}")
    return 2
