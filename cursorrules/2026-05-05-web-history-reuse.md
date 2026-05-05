# Web UI: reusable generation history

## Implemented

- **`index.html.j2`:** History rows now include a Reuse button. Reuse always restores the saved prompt to `#prompt`, then focuses the composer.
- **History metadata:** New `dts_web_gen_history_v1` entries may include `negative_prompt` and `generations` alongside the existing `{ id, ts, prompt, images }` shape. Legacy entries remain valid and restore prompt-only.
- **Clean restore rule:** Reuse fills `#neg` only when it is blank, and changes `#generations` only when it is still `1`.
- **Docs:** `CLI.md`, `docs/web-ui-layout.md`, and `CHANGELOG.md` describe the Reuse action and optional metadata.
- **Tests:** `tests/test_web_app.py` asserts the shipped page includes the Reuse flow and the clean-field contract.

## Verified

- `uv run pytest tests/test_web_app.py` — 33 passed.
- `uv run pytest` — 205 passed, 6 skipped.
