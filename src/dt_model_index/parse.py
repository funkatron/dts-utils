"""Parsing and normalization for Draw Things community model metadata."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import re
from pathlib import Path
from typing import Any

from .huggingface import extract_repo_id, load_repo_data, HuggingFaceError

ROOT_PRIORITY = {
    "uncurated_models": 0,
    "models": 1,
    "loras": 2,
}


@dataclass(slots=True)
class ModelRecord:
    """Normalized model record used across exports and CLI commands."""

    id: str
    name: str
    type: str | None
    model_family: str
    source_url: str | None
    huggingface_repo_id: str | None
    download_url: str | None
    author: str | None
    license: str | None
    tags: list[str]
    sha256: str | None
    metadata_path: str | None
    raw_metadata_json: dict[str, Any]
    likes: int | None = None
    downloads: int | None = None
    last_modified: str | None = None
    sibling_file_names: list[str] = field(default_factory=list)
    readme_excerpt: str | None = None
    suggested_config: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _safe_read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def load_uncurated_ids(path: Path) -> list[str]:
    """Load the uncurated model identifiers from a txt file."""
    text = _safe_read_text(path)
    tokens = [token.strip() for token in re.split(r"\s+", text) if token.strip()]
    seen: set[str] = set()
    ordered: list[str] = []
    for token in tokens:
        if token not in seen:
            seen.add(token)
            ordered.append(token)
    return ordered


def load_sha256_map(path: Path) -> dict[str, str]:
    """Load the sha256 mapping while tolerating malformed data."""
    try:
        payload = json.loads(_safe_read_text(path))
    except json.JSONDecodeError:
        return {}

    if not isinstance(payload, dict):
        return {}

    result: dict[str, str] = {}
    for key, value in payload.items():
        if isinstance(key, str) and isinstance(value, str) and value.strip():
            result[key] = value.strip()
    return result


def discover_metadata_files(repo_dir: Path) -> dict[str, list[Path]]:
    """Find candidate metadata.json files keyed by their directory name."""
    discovered: dict[str, list[Path]] = {}
    for root_name in ROOT_PRIORITY:
        root_dir = repo_dir / root_name
        if not root_dir.exists():
            continue
        for metadata_path in root_dir.rglob("metadata.json"):
            model_id = metadata_path.parent.name
            discovered.setdefault(model_id, []).append(metadata_path)
    return discovered


def _priority_for(path: Path) -> int:
    try:
        root_name = path.parts[-3]
    except IndexError:
        return 999
    return ROOT_PRIORITY.get(root_name, 999)


def _best_metadata_path(paths: list[Path]) -> Path:
    return sorted(paths, key=_priority_for)[0]


def _coerce_string(value: Any) -> str | None:
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None
    if isinstance(value, (int, float, bool)):
        return str(value)
    return None


def _coerce_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        items = [_coerce_string(item) for item in value]
        return sorted({item for item in items if item})
    if isinstance(value, str):
        parts = [part.strip() for part in re.split(r"[,|;/]", value) if part.strip()]
        return sorted(set(parts))
    return []


def _coerce_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    return None


def _coerce_int(value: Any) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return None


def _find_first_string(payload: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = payload.get(key)
        result = _coerce_string(value)
        if result:
            return result
    return None


def _find_nested_string(
    payload: dict[str, Any],
    dotted_paths: tuple[str, ...],
) -> str | None:
    for dotted_path in dotted_paths:
        current: Any = payload
        for part in dotted_path.split("."):
            if not isinstance(current, dict):
                current = None
                break
            current = current.get(part)
        result = _coerce_string(current)
        if result:
            return result
    return None


def _infer_type(metadata_path: Path, payload: dict[str, Any]) -> str:
    explicit = _find_first_string(payload, ("type", "kind", "category"))
    if explicit:
        return explicit

    root_name = metadata_path.parts[-3]
    if root_name == "loras":
        return "lora"
    return "model"


def _infer_license(metadata_path: Path, payload: dict[str, Any]) -> str | None:
    explicit = _find_first_string(payload, ("license", "licence"))
    if explicit:
        return explicit

    note_license = _infer_license_from_note(_coerce_string(payload.get("note")))
    if note_license:
        return note_license

    license_path = metadata_path.with_name("LICENSE")
    if not license_path.exists():
        return None

    first_line = _safe_read_text(license_path).splitlines()
    if not first_line:
        return None
    cleaned = first_line[0].strip()
    return cleaned or "LICENSE file present"


def _guess_hf_download_url(repo_id: str, payload: dict[str, Any]) -> str | None:
    file_name = _find_first_string(payload, ("file", "filename", "weights", "checkpoint"))
    if not file_name:
        return None
    return f"https://huggingface.co/{repo_id}/resolve/main/{file_name}"


def _extract_urls_from_text(value: str | None) -> list[str]:
    if not value:
        return []
    return re.findall(r"https?://[^\s)]+", value)


def _pick_preferred_url(urls: list[str]) -> str | None:
    if not urls:
        return None
    for url in urls:
        if "huggingface.co" in url:
            return url
    for url in urls:
        if "civitai.com" in url:
            return url
    return urls[0]


def _extract_source_url_from_sidecar_files(metadata_path: Path) -> str | None:
    for file_name in ("README.md", "LICENSE"):
        sidecar_path = metadata_path.with_name(file_name)
        if not sidecar_path.exists():
            continue
        preferred = _pick_preferred_url(_extract_urls_from_text(_safe_read_text(sidecar_path)))
        if preferred:
            return preferred
    return None


def _infer_license_from_note(note: str | None) -> str | None:
    if not note:
        return None
    patterns = [
        (r"\bApache 2\.0\b", "Apache 2.0"),
        (r"\bMIT-licensed\b|\bMIT license\b", "MIT"),
        (r"\bnon-commercial license\b", "Non-commercial"),
    ]
    for pattern, label in patterns:
        if re.search(pattern, note, re.IGNORECASE):
            return label
    return None


def _extract_step_hint(note: str | None) -> str | None:
    if not note:
        return None
    patterns = [
        r"(\d+\s*[–-]\s*\d+)\s+sampling steps",
        r"(\d+\s+to\s+\d+)\s+sampling steps",
        r"(\d+)\s+sampling steps",
        r"(\d+)\s+steps",
    ]
    for pattern in patterns:
        match = re.search(pattern, note, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def _extract_text_guidance_hint(note: str | None) -> str | None:
    if not note:
        return None
    patterns = [
        r"Text Guidance (?:should be somewhere )?between (\d+\s+to\s+\d+|\d+\s*[–-]\s*\d+)",
        r"Text Guidance value of (\d+(?:\.\d+)?)",
        r"CFG (\d+\s*[–-]\s*\d+|\d+\s+to\s+\d+|\d+(?:\.\d+)?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, note, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def _extract_resolution_hint(note: str | None) -> str | None:
    if not note:
        return None
    patterns = [
        r"recommended resolutions? (?:are|of) ([0-9×x]+(?:\s+or\s+[0-9×x]+)*)",
        r"recommended resolution of ([0-9×x]+)",
        r"trained at ([0-9×x]+) resolution",
        r"width is set to (\d+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, note, re.IGNORECASE)
        if match:
            value = match.group(1).strip()
            if pattern.endswith(r"(\d+)"):
                return f"{value}x{value}"
            return value
    return None


def _extract_shift_hint(note: str | None) -> str | None:
    if not note:
        return None
    match = re.search(r"recommended shift value of (\d+(?:\.\d+)?(?:\s+or higher)?)", note, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


def _extract_max_frames(note: str | None) -> int | None:
    if not note:
        return None
    match = re.search(r"supports up to (\d+) frames", note, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def _extract_sampler_hint(note: str | None) -> str | None:
    if not note:
        return None
    hints: list[str] = []
    if re.search(r"trailing samplers", note, re.IGNORECASE):
        hints.append("trailing")
    if re.search(r"heun", note, re.IGNORECASE):
        hints.append("heun")
    if not hints:
        return None
    return ", ".join(hints)


def _extract_prompt_format_hint(note: str | None) -> str | None:
    if not note:
        return None
    match = re.search(r"prompt format:\s*(.+)", note, re.IGNORECASE)
    if match:
        return match.group(1).strip().rstrip(".")
    return None


def extract_suggested_config(payload: dict[str, Any]) -> dict[str, Any]:
    note = _coerce_string(payload.get("note"))
    baseline_config: dict[str, Any] = {}
    recommended_tuning: dict[str, Any] = {}

    for field_name in ("default_scale", "hires_fix_scale", "padded_text_encoding_length", "frames_per_second"):
        value = _coerce_int(payload.get(field_name))
        if value is not None:
            baseline_config[field_name] = value

    for field_name in ("upcast_attention", "guidance_embed", "high_precision_autoencoder", "is_bf16"):
        value = _coerce_bool(payload.get(field_name))
        if value is not None:
            baseline_config[field_name] = value

    if isinstance(payload.get("tea_cache_coefficients"), list):
        baseline_config["has_tea_cache"] = True

    prefix = _coerce_string(payload.get("prefix"))
    if prefix:
        fps_match = re.search(r"FPS-(\d+)", prefix, re.IGNORECASE)
        if fps_match and "frames_per_second" not in baseline_config:
            baseline_config["frames_per_second"] = int(fps_match.group(1))

    resolution_hint = _extract_resolution_hint(note)
    if resolution_hint:
        recommended_tuning["resolution"] = resolution_hint

    step_hint = _extract_step_hint(note)
    if step_hint:
        recommended_tuning["steps"] = step_hint

    text_guidance_hint = _extract_text_guidance_hint(note)
    if text_guidance_hint:
        recommended_tuning["text_guidance"] = text_guidance_hint

    shift_hint = _extract_shift_hint(note)
    if shift_hint:
        recommended_tuning["shift"] = shift_hint

    max_frames = _extract_max_frames(note)
    if max_frames is not None:
        recommended_tuning["max_frames"] = max_frames

    sampler_hint = _extract_sampler_hint(note)
    if sampler_hint:
        recommended_tuning["sampler"] = sampler_hint

    prompt_format_hint = _extract_prompt_format_hint(note)
    if prompt_format_hint:
        recommended_tuning["prompt_format"] = prompt_format_hint

    if note and "Speedup w/ Guidance Embed" in note:
        recommended_tuning["guidance_embed_note"] = 'Consider disabling "Speedup w/ Guidance Embed"'

    config: dict[str, Any] = {}
    if baseline_config:
        config["baseline_config"] = baseline_config
    if recommended_tuning:
        config["recommended_tuning"] = recommended_tuning
    return config


def detect_model_family(model_id: str, payload: dict[str, Any]) -> str:
    """Best-effort model family detection."""
    haystack_parts = [model_id]
    for key in (
        "name",
        "version",
        "base",
        "architecture",
        "description",
        "file",
        "text_encoder",
        "clip_encoder",
        "autoencoder",
        "note",
    ):
        value = _coerce_string(payload.get(key))
        if value:
            haystack_parts.append(value)
    tags = _coerce_string_list(payload.get("tags"))
    haystack_parts.extend(tags)
    haystack = " ".join(haystack_parts).lower()

    if "flux" in haystack or "flux1" in haystack or "flux.1" in haystack:
        return "Flux"
    if "wan" in haystack or "wan2" in haystack:
        return "Wan"
    if "hunyuan" in haystack:
        return "Hunyuan"
    if "sdxl" in haystack or "stable diffusion xl" in haystack or "sdxl_base" in haystack:
        return "SDXL"
    if "sd3" in haystack or "sd 3" in haystack or "stable diffusion 3" in haystack:
        return "SD 3.x"
    if "1.5" in haystack or "sd15" in haystack or "stable diffusion 1.5" in haystack:
        return "SD 1.5"
    return "other / unknown"


def _basename_from_url(value: str | None) -> str | None:
    if not value or "://" not in value:
        return None
    return value.rsplit("/", 1)[-1].split("?", 1)[0] or None


def _extract_sha256(payload: dict[str, Any], sha_map: dict[str, str], download_url: str | None) -> str | None:
    file_name = _coerce_string(payload.get("file"))
    if file_name:
        match = sha_map.get(file_name)
        if match:
            return match

    nested_file_name = _find_nested_string(payload, ("download.file", "download.url"))
    basename = _basename_from_url(nested_file_name) or _basename_from_url(download_url)
    if basename:
        match = sha_map.get(basename)
        if match:
            return match

    converted = payload.get("converted")
    if isinstance(converted, dict):
        if file_name and isinstance(converted.get(file_name), str):
            return converted[file_name]
        if basename and isinstance(converted.get(basename), str):
            return converted[basename]
        if len(converted) == 1:
            only_value = next(iter(converted.values()))
            if isinstance(only_value, str):
                return only_value
    return None


def _choose_source_url(payload: dict[str, Any]) -> str | None:
    direct = _find_first_string(
        payload,
        (
            "source_url",
            "source",
            "sourceURL",
            "model_url",
            "url",
            "download_url",
            "downloadURL",
        ),
    )
    if direct:
        return direct

    nested = _find_nested_string(
        payload,
        (
            "download.file",
            "download.url",
            "source.file",
            "source.url",
        ),
    )
    if nested:
        return nested

    note = _coerce_string(payload.get("note"))
    if note:
        preferred = _pick_preferred_url(_extract_urls_from_text(note))
        if preferred:
            return preferred

    return None


def load_metadata_payload(path: Path) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    try:
        payload = json.loads(_safe_read_text(path))
    except json.JSONDecodeError as exc:
        return {}, [f"Malformed JSON: {exc}"]

    if not isinstance(payload, dict):
        return {}, ["Metadata JSON was not an object"]

    return payload, warnings


def build_records(repo_dir: Path) -> list[ModelRecord]:
    """Build normalized records for all ids listed in uncurated_models.txt."""
    ids = load_uncurated_ids(repo_dir / "uncurated_models.txt")
    sha_map = load_sha256_map(repo_dir / "uncurated_models_sha256.json")
    metadata_index = discover_metadata_files(repo_dir)

    records: list[ModelRecord] = []
    for model_id in ids:
        warnings: list[str] = []
        metadata_paths = metadata_index.get(model_id, [])
        raw_payload: dict[str, Any] = {}
        metadata_path_str: str | None = None
        record_type: str | None = None
        source_url: str | None = None
        huggingface_repo_id: str | None = None
        download_url: str | None = None
        author: str | None = None
        license_name: str | None = None
        tags: list[str] = []
        model_family = "other / unknown"
        name = model_id

        if not metadata_paths:
            warnings.append("No metadata.json file found")
        else:
            if len(metadata_paths) > 1:
                warnings.append(
                    "Multiple metadata.json files found; selected highest-priority path"
                )
            metadata_path = _best_metadata_path(metadata_paths)
            metadata_path_str = str(metadata_path.relative_to(repo_dir))
            raw_payload, metadata_warnings = load_metadata_payload(metadata_path)
            warnings.extend(metadata_warnings)

            if raw_payload:
                name = _find_first_string(raw_payload, ("name", "title")) or model_id
                record_type = _infer_type(metadata_path, raw_payload)
                source_url = _choose_source_url(raw_payload)
                huggingface_repo_id = (
                    _find_first_string(raw_payload, ("huggingface_repo_id", "huggingface"))
                    or extract_repo_id(source_url)
                )
                download_url = _find_first_string(
                    raw_payload,
                    ("download_url", "downloadURL", "source", "url"),
                )
                if not download_url:
                    download_url = _find_nested_string(
                        raw_payload,
                        (
                            "download.file",
                            "download.url",
                        ),
                    )
                if huggingface_repo_id and (not download_url or "huggingface.co" in download_url):
                    download_url = download_url or _guess_hf_download_url(huggingface_repo_id, raw_payload)
                author = _find_first_string(raw_payload, ("author", "creator", "publisher"))
                license_name = _infer_license(metadata_path, raw_payload)
                tags = _coerce_string_list(raw_payload.get("tags"))
                model_family = detect_model_family(model_id, raw_payload)
                if not source_url:
                    source_url = _extract_source_url_from_sidecar_files(metadata_path)
                    if source_url and not huggingface_repo_id:
                        huggingface_repo_id = extract_repo_id(source_url)

        record = ModelRecord(
            id=model_id,
            name=name,
            type=record_type,
            model_family=model_family,
            source_url=source_url,
            huggingface_repo_id=huggingface_repo_id,
            download_url=download_url,
            author=author,
            license=license_name,
            tags=tags,
            sha256=_extract_sha256(raw_payload, sha_map, download_url),
            metadata_path=metadata_path_str,
            raw_metadata_json=raw_payload,
            suggested_config=extract_suggested_config(raw_payload),
            warnings=warnings,
        )
        records.append(record)

    return records


def enrich_huggingface_records(
    records: list[ModelRecord],
    cache_dir: Path,
    refresh: bool = False,
) -> None:
    """Mutate records in-place with cached Hugging Face metadata."""
    for record in records:
        if not record.huggingface_repo_id:
            continue

        try:
            payload = load_repo_data(record.huggingface_repo_id, cache_dir=cache_dir, refresh=refresh)
        except HuggingFaceError as exc:
            record.warnings.append(str(exc))
            continue

        likes = payload.get("likes")
        downloads = payload.get("downloads")
        last_modified = payload.get("lastModified")
        siblings = payload.get("siblings")
        hf_tags = payload.get("tags")

        if isinstance(likes, int):
            record.likes = likes
        if isinstance(downloads, int):
            record.downloads = downloads
        if isinstance(last_modified, str):
            record.last_modified = last_modified
        if isinstance(siblings, list):
            record.sibling_file_names = sorted(
                {
                    sibling["rfilename"]
                    for sibling in siblings
                    if isinstance(sibling, dict) and isinstance(sibling.get("rfilename"), str)
                }
            )
        if isinstance(hf_tags, list):
            combined = set(record.tags)
            for tag in hf_tags:
                if isinstance(tag, str) and tag.strip():
                    combined.add(tag.strip())
            record.tags = sorted(combined)
            if not record.license:
                for tag in record.tags:
                    if tag.startswith("license:"):
                        record.license = tag.split(":", 1)[1]
                        break
        card_data = payload.get("cardData")
        if isinstance(card_data, dict) and not record.license:
            card_license = _coerce_string(card_data.get("license"))
            if card_license:
                record.license = card_license
        if not record.author:
            author = _coerce_string(payload.get("author"))
            if author:
                record.author = author
            elif "/" in record.huggingface_repo_id:
                record.author = record.huggingface_repo_id.split("/", 1)[0]
        readme_excerpt = payload.get("readme_excerpt")
        if isinstance(readme_excerpt, str) and readme_excerpt.strip():
            record.readme_excerpt = readme_excerpt.strip()
