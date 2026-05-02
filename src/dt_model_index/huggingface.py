"""Hugging Face metadata enrichment with local caching."""

from __future__ import annotations

import hashlib
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

HF_HOSTS = {"huggingface.co", "www.huggingface.co", "hf.co"}
HF_API_ROOT = "https://huggingface.co/api/models"


class HuggingFaceError(RuntimeError):
    """Raised when Hugging Face enrichment fails."""


def extract_repo_id(value: str | None) -> str | None:
    """Extract `owner/repo` from a Hugging Face URL or identifier."""
    if not value:
        return None

    candidate = value.strip()
    if not candidate:
        return None

    if re.fullmatch(r"[\w.-]+/[\w.-]+", candidate):
        return candidate

    parsed = urllib.parse.urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() not in HF_HOSTS:
        return None

    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2:
        return None

    if parts[0] in {"models", "spaces", "datasets"} and len(parts) >= 3:
        return f"{parts[1]}/{parts[2]}"

    return f"{parts[0]}/{parts[1]}"


def _cache_prefix(repo_id: str) -> str:
    digest = hashlib.sha1(repo_id.encode("utf-8")).hexdigest()[:12]
    safe_id = repo_id.replace("/", "--")
    return f"{safe_id}-{digest}"


def _cache_paths(cache_dir: Path, repo_id: str) -> tuple[Path, Path]:
    prefix = _cache_prefix(repo_id)
    return cache_dir / f"{prefix}.json", cache_dir / f"{prefix}-README.md"


def _fetch_json(url: str, timeout: int = 20) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "dts-util/0.1.0"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, dict):
            raise HuggingFaceError(f"Unexpected JSON payload from {url}")
        return payload


def _fetch_text(url: str, timeout: int = 20) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "dts-util/0.1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def _extract_readme_excerpt(readme_text: str, limit: int = 500) -> str | None:
    cleaned_lines: list[str] = []
    for line in readme_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("---"):
            continue
        if stripped.startswith("#"):
            stripped = stripped.lstrip("#").strip()
        cleaned_lines.append(stripped)
        if len(" ".join(cleaned_lines)) >= limit:
            break

    excerpt = " ".join(cleaned_lines).strip()
    if not excerpt:
        return None
    return excerpt[:limit].rstrip()


def load_repo_data(
    repo_id: str,
    cache_dir: Path,
    refresh: bool = False,
    timeout: int = 20,
) -> dict[str, Any]:
    """Load cached or fresh metadata for a Hugging Face model repo."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    json_cache, readme_cache = _cache_paths(cache_dir, repo_id)

    if json_cache.exists() and not refresh:
        try:
            payload = json.loads(json_cache.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                return payload
        except json.JSONDecodeError:
            pass

    try:
        payload = _fetch_json(f"{HF_API_ROOT}/{repo_id}", timeout=timeout)
    except (urllib.error.URLError, TimeoutError) as exc:
        raise HuggingFaceError(f"Failed to fetch metadata for {repo_id}: {exc}") from exc

    readme_excerpt: str | None = None
    if readme_cache.exists() and not refresh:
        readme_excerpt = _extract_readme_excerpt(readme_cache.read_text(encoding="utf-8"))
    else:
        try:
            readme_url = f"https://huggingface.co/{repo_id}/raw/main/README.md"
            readme_text = _fetch_text(readme_url, timeout=timeout)
            readme_cache.write_text(readme_text, encoding="utf-8")
            readme_excerpt = _extract_readme_excerpt(readme_text)
        except (urllib.error.URLError, TimeoutError):
            readme_excerpt = None

    payload["readme_excerpt"] = readme_excerpt
    json_cache.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return payload
