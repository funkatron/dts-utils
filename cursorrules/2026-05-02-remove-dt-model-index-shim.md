# 2026-05-02 — remove dt_model_index shim

## Trigger

Single-user repo: drop `dt_model_index` compatibility package; use `dts_util.model_index` / `dts-util models` only.

## Changes

- Removed `src/dt_model_index/`.
- Removed `test_dt_model_index_shim_aliases_canonical_main` from `tests/test_model_index.py`.
- `CHANGELOG.md` [Unreleased]: **Removed** bullet + trimmed model-index line under **Changed**.

## Tests

`uv run pytest -q` — 113 passed, 6 skipped.
