"""HTTPS / Hugging Face artifact downloads for ``models fetch``."""

from __future__ import annotations

import hashlib
import os
import shutil
import ssl
import tempfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from dts_utils.model_fetch.errors import FetchRecipeError


def assert_https_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise FetchRecipeError(f"Only https:// URLs are allowed (got scheme {parsed.scheme!r}).")


def sha256_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def download_bytes_https(url: str, *, timeout: float = 600.0) -> bytes:
    """Fetch URL bytes with TLS verification enabled (default SSL context)."""
    assert_https_url(url)
    ctx = ssl.create_default_context()
    request = Request(url, headers={"User-Agent": "dts-utils-models-fetch"})
    try:
        with urlopen(request, timeout=timeout, context=ctx) as response:
            return response.read()
    except HTTPError as exc:
        raise FetchRecipeError(f"HTTP error downloading {url!r}: {exc}") from exc
    except URLError as exc:
        raise FetchRecipeError(f"Network error downloading {url!r}: {exc}") from exc


def download_hf_file(
    *,
    repo_id: str,
    path_in_repo: str,
    revision: str | None,
) -> Path:
    try:
        from huggingface_hub import hf_hub_download  # type: ignore[import-not-found]
    except ImportError as exc:
        raise FetchRecipeError(
            "Install optional dependency: uv sync --extra download "
            "(provides huggingface_hub for huggingface recipe sources).",
        ) from exc

    kwargs: dict[str, object] = {
        "repo_id": repo_id,
        "filename": path_in_repo,
        "local_files_only": False,
    }
    if revision:
        kwargs["revision"] = revision

    token = os.environ.get("HF_TOKEN")
    if token:
        kwargs["token"] = token

    try:
        return Path(hf_hub_download(**kwargs))
    except Exception as exc:
        raise FetchRecipeError(
            f"Hugging Face download failed for {repo_id} @ {path_in_repo!r}: {exc}",
        ) from exc


def atomic_write_bytes(dest: Path, payload: bytes) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="wb",
        dir=dest.parent,
        prefix=f".{dest.name}-",
        suffix=".dts-fetch-tmp",
        delete=False,
    ) as tmp:
        tmp.write(payload)
        tmp_path = Path(tmp.name)
    try:
        tmp_path.replace(dest)
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


def copy_hf_download_to_dest(source: Path, dest: Path) -> None:
    """Copy hub-downloaded file into Draw Things model dir basename."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(
        dir=str(dest.parent),
        prefix=f".{dest.name}-",
        suffix=".dts-fetch-tmp",
    )
    os.close(fd)
    tmp_path = Path(name)
    try:
        shutil.copy2(source, tmp_path)
        tmp_path.replace(dest)
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def verify_sha_required(dest: Path, expected_hex: str) -> None:
    actual = sha256_file(dest)
    expected = expected_hex.strip().lower()
    if actual.lower() != expected:
        raise FetchRecipeError(
            f"{dest.name}: SHA-256 mismatch after download "
            f"(expected {expected}, got {actual}).",
        )
