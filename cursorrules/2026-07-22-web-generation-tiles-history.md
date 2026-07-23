# Web generation tiles and metadata-only history

- Replaced result/history image rows with reusable generation tiles.
- Thumbnail clicks continue to use the fullscreen lightbox; each tile now has an accessible info button for prompt, configuration, run, timing, dimensions, and wildcard expansion details.
- Streaming generation now writes completed PNGs directly to the server history directory.
- `index.json` is uncapped and contains metadata only; image URLs come from `GET /api/history/{item_id}/artifacts`.
- Removed browser-side base64 history uploads and disabled `POST /api/history`.
- Updated web API/UI/CLI documentation and changelog.
- Initial implementation verified with `uv run pytest`: 469 passed, 1 skipped, 7 deselected.
- Follow-up layout correction: shared tile CSS now applies in History, whose wide responsive grid has one download action per thumbnail, a fixed footer, and reset scroll position.
- Follow-up verified with `uv run pytest`: 470 passed, 1 skipped, 7 deselected; browser inspection confirmed six responsive columns at the current viewport and a working details dialog.
