"""Execute bundled fetch recipes."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from dts_utils.model_fetch.download import (
    copy_hf_download_to_dest,
    download_https_to_dest,
    download_hf_file,
    sha256_file,
    verify_sha_required,
    verify_size_required,
)
from dts_utils.model_fetch.errors import FetchRecipeError
from dts_utils.model_fetch.recipes import load_recipe_dict


def _normalize_artifacts(payload: dict[str, Any]) -> list[dict[str, Any]]:
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise FetchRecipeError("Recipe missing non-empty artifacts array.")
    normalized: list[dict[str, Any]] = []
    for i, raw in enumerate(artifacts):
        if not isinstance(raw, dict):
            raise FetchRecipeError(f"artifacts[{i}] must be an object.")
        fn = raw.get("filename")
        if not isinstance(fn, str) or not fn.strip():
            raise FetchRecipeError(f"artifacts[{i}].filename must be a non-empty string.")
        sha_val = raw.get("sha256")
        if sha_val is not None:
            if not isinstance(sha_val, str) or not sha_val.strip():
                raise FetchRecipeError(f"artifacts[{i}].sha256 must be non-empty when set.")
        size_raw = raw.get("expected_size_bytes")
        expected_size: int | None = None
        if size_raw is not None:
            if isinstance(size_raw, bool) or not isinstance(size_raw, int):
                raise FetchRecipeError(
                    f"artifacts[{i}].expected_size_bytes must be a non-negative integer when set.",
                )
            if size_raw < 0:
                raise FetchRecipeError(
                    f"artifacts[{i}].expected_size_bytes must be non-negative.",
                )
            expected_size = size_raw
        sources = raw.get("sources", [])
        if sources is None:
            sources = []
        if not isinstance(sources, list):
            raise FetchRecipeError(f"artifacts[{i}].sources must be an array.")
        for j, src in enumerate(sources):
            if not isinstance(src, dict):
                raise FetchRecipeError(f"artifacts[{i}].sources[{j}] must be an object.")
            stype = src.get("type")
            if not isinstance(stype, str) or not stype.strip():
                raise FetchRecipeError(f"artifacts[{i}].sources[{j}].type invalid.")
        normalized.append(
            {
                "filename": fn.strip(),
                "sha256": sha_val.strip() if isinstance(sha_val, str) else None,
                "expected_size_bytes": expected_size,
                "sources": sources,
            },
        )
    return normalized


def _artifact_satisfied(
    dest: Path,
    *,
    expected_sha: str | None,
    expected_size_bytes: int | None,
    force: bool,
) -> bool:
    if not dest.is_file():
        return False
    if force:
        return False
    if expected_sha:
        return sha256_file(dest).lower() == expected_sha.strip().lower()
    if expected_size_bytes is not None:
        try:
            return dest.stat().st_size == expected_size_bytes
        except OSError:
            return False
    # Recipe omitted SHA and size: treat existing non-empty file as satisfied (weak idempotency).
    try:
        return dest.stat().st_size > 0
    except OSError:
        return False


def _download_first_working_source(
    art: dict[str, Any],
    dest: Path,
    *,
    expected_sha: str | None,
    expected_size: int | None,
) -> None:
    sources: list[dict[str, Any]] = art["sources"]
    errors: list[str] = []
    for src in sources:
        stype = str(src.get("type", "")).strip().lower()
        try:
            if stype == "https":
                url = src.get("url")
                if not isinstance(url, str) or not url.strip():
                    raise FetchRecipeError("https source missing url.")
                download_https_to_dest(url=url.strip(), dest=dest)
            elif stype == "huggingface":
                repo_id = src.get("repo_id")
                path_in_repo = src.get("path_in_repo")
                if not isinstance(repo_id, str) or not repo_id.strip():
                    raise FetchRecipeError("huggingface source missing repo_id.")
                if not isinstance(path_in_repo, str) or not path_in_repo.strip():
                    raise FetchRecipeError("huggingface source missing path_in_repo.")
                revision = src.get("revision")
                rev = revision.strip() if isinstance(revision, str) and revision.strip() else None
                cached = download_hf_file(
                    repo_id=repo_id.strip(),
                    path_in_repo=path_in_repo.strip(),
                    revision=rev,
                )
                copy_hf_download_to_dest(cached, dest)
            else:
                raise FetchRecipeError(f"Unknown source type {stype!r}.")

            if expected_sha:
                verify_sha_required(dest, expected_sha)
            elif expected_size is not None:
                verify_size_required(dest, expected_size)
            return
        except FetchRecipeError as exc:
            try:
                dest.unlink(missing_ok=True)
            except OSError:
                pass
            errors.append(str(exc))
            continue
    detail = "; ".join(errors) if errors else "no sources"
    raise FetchRecipeError(f"All sources failed for {art['filename']}: {detail}")


def run_fetch_plan(
    *,
    recipe_id: str,
    model_dir: Path,
    dry_run: bool,
    yes: bool,
    force: bool,
) -> int:
    payload = load_recipe_dict(recipe_id)
    artifacts = _normalize_artifacts(payload)
    rid = payload.get("id", recipe_id)
    desc = payload.get("description")

    print(f"recipe={recipe_id!r} bundled_id={rid!r}")
    if isinstance(desc, str) and desc.strip():
        print(desc.strip())

    if dry_run:
        missing_urls = 0
        for art in artifacts:
            dest = model_dir / art["filename"]
            n_sources = len(art["sources"])
            sha_note = "sha256=" + ("set" if art["sha256"] else "none")
            sz = art["expected_size_bytes"]
            size_note = f" expected_size_bytes={sz}" if sz is not None else ""
            print(
                f"[dry-run] artifact={art['filename']} dest={dest} "
                f"sources={n_sources} {sha_note}{size_note}",
            )
            if not art["sources"]:
                missing_urls += 1
        if missing_urls:
            print(
                f"[dry-run] note: {missing_urls} artifact(s) have empty sources "
                "(bundled skeleton — see docs/models-fetch-roadmap.md; extend recipe JSON "
                "with https:// or huggingface entries when verified).",
                file=sys.stderr,
            )
        return 0

    if not yes:
        print(
            "Pass --dry-run to preview this recipe or --yes to download into --model-dir.",
            file=sys.stderr,
        )
        return 2

    skeleton = sum(1 for art in artifacts if not art["sources"])
    if skeleton:
        print(
            f"Note: {skeleton} artifact(s) in this recipe have no download URLs yet "
            "(bundled skeleton). Install weights via Draw Things Community or edit recipe JSON "
            "after verifying URLs — see docs/models-fetch-roadmap.md. "
            "Preview without writes: dts-utils models fetch [<recipe-id>] --dry-run",
            file=sys.stderr,
        )

    model_dir.mkdir(parents=True, exist_ok=True)
    failures = 0
    for art in artifacts:
        dest = model_dir / art["filename"]
        expected_sha = art["sha256"]
        expected_size = art["expected_size_bytes"]

        if _artifact_satisfied(
            dest,
            expected_sha=expected_sha,
            expected_size_bytes=expected_size,
            force=force,
        ):
            print(f"[skip] already satisfied {dest.name}")
            continue

        if not art["sources"]:
            print(
                f"[error] {art['filename']}: missing on disk and recipe has no sources.",
                file=sys.stderr,
            )
            failures += 1
            continue

        try:
            print(f"[fetch] {art['filename']} -> {dest}")
            _download_first_working_source(
                art,
                dest,
                expected_sha=expected_sha,
                expected_size=expected_size,
            )
        except FetchRecipeError as exc:
            print(f"[error] {art['filename']}: {exc}", file=sys.stderr)
            failures += 1

    return 2 if failures else 0
