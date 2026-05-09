"""Recipe loading and default recipe resolution.

Bundled recipe objects are JSON dicts with:

- ``id`` (optional echo), optional human ``description``.
- ``artifacts``: non-empty list of objects::

    {"filename": "<DrawThings basename>", "sha256": "<64-char hex, optional>",
     "expected_size_bytes": <int, optional>, "sources": [<source>, ...]}

  When ``sha256`` is present it is verified after download (no bypass flag).
  When ``sha256`` is absent but ``expected_size_bytes`` is set, that exact size is used for
  skip/idempotency and verified after download.

- Each ``source`` is either::

    {"type": "https", "url": "https://..."}

  or::

    {"type": "huggingface", "repo_id": "...", "path_in_repo": "...",
     "revision": "<optional>"}

  Only ``https://`` URLs are accepted for HTTP sources; TLS verification stays on.
"""

from __future__ import annotations

import json
import os
from importlib import resources
from typing import Any

from dts_utils.model_fetch.errors import FetchRecipeError

DEFAULT_FETCH_RECIPE_ENV = "DTS_UTILS_DEFAULT_FETCH_RECIPE"


def _recipe_traversable():
    return resources.files("dts_utils.model_fetch.recipe_files")


def load_registry_dict() -> dict[str, Any]:
    raw = _recipe_traversable().joinpath("registry.json").read_text(encoding="utf-8")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise FetchRecipeError("registry.json must contain a JSON object.")
    return payload


def resolve_default_recipe_id() -> str:
    """Recipe id when ``models fetch`` omits a positional.

    Precedence: ``DTS_UTILS_DEFAULT_FETCH_RECIPE`` → ``registry.json`` ``default_recipe_id``.
    """
    env_val = os.environ.get(DEFAULT_FETCH_RECIPE_ENV, "").strip()
    if env_val:
        return env_val
    try:
        registry = load_registry_dict()
    except (OSError, json.JSONDecodeError) as exc:
        raise FetchRecipeError(f"Could not read bundled registry.json: {exc}") from exc
    rid = registry.get("default_recipe_id")
    if not isinstance(rid, str) or not rid.strip():
        raise FetchRecipeError(
            "Bundled registry.json missing non-empty string field default_recipe_id "
            f"(override with {DEFAULT_FETCH_RECIPE_ENV}).",
        )
    return rid.strip()


def load_recipe_dict(recipe_id: str) -> dict[str, Any]:
    stem = recipe_id.strip()
    if not stem:
        raise FetchRecipeError("Recipe id is empty.")
    path = _recipe_traversable().joinpath(f"{stem}.json")
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise FetchRecipeError(f"No bundled recipe {stem!r} ({exc}).") from exc
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise FetchRecipeError(f"Recipe {stem!r}: expected JSON object.")
    return payload
