# Web UI: filesystem-backed history images

## Implemented

- **Server history:** Added `/api/history` for list/save/clear and `/history/{item_id}/{filename}` for persisted PNG reads.
- **Storage:** History metadata and PNG files live under `web-history` in the dts-utils user config directory. `DTS_WEB_HISTORY_DIR` can override the location for tests or operators.
- **Migration:** The browser imports legacy `localStorage` history entries on first History open, then clears the old browser-only key.
- **UI cleanup:** Multi-run results use a wider responsive grid, the composer is more compact, and expanded prompt details are a slimmer scrollable log.
- **Docs:** Updated `CLI.md`, `docs/web-ui-layout.md`, and `CHANGELOG.md`.

## Verified

- `uv run pytest tests/test_web_app.py` — 35 passed.
- `uv run pytest` — 207 passed, 6 skipped.
