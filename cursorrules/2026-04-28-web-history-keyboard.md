# Web UI: generation history + ⌘↵ / Ctrl+Enter

## Implemented

- **`index.html.j2`:** History FAB (`#btnOpenHistory`) opens `#historyDialog` with `#historyList`; successful multipart PNG responses append to `localStorage` key `dts_web_gen_history_v1` (cap ~30 entries, soft trim ~4M chars); Clear all; per-row PNG downloads via `data:` URLs.
- **Keyboard:** `#prompt` listens for meta/Ctrl+Enter → `runGenerate()`.
- **Docs:** `CLI.md` § web, `CHANGELOG.md` Unreleased Changed, `docs/web-ui-layout.md` wireframe + DOM table.
- **Tests:** `test_index_loads` asserts `historyDialog` and shortcut hint text.

## Verified

- `uv run pytest tests/test_web_app.py` — 12 passed.
