# 2026-05-02 — generate output filenames include Unix milliseconds

## Trigger

User asked to add millisecond timestamps to output filenames so repeated `dts-util generate` runs do not collide / overwrite prior PNGs.

## Implementation

- `src/dts_util/generate.py`: `unique_ms_timestamp_output_path()` uses `time.time_ns() // 1_000_000` and rewrites the stem to `{stem}-{ms}` before `write_images()`.
- Multi-image responses keep existing indexing: first file `{stem}-{ms}.png`, then `{stem}-{ms}-2.png`, etc.
- `--help` text documents the suffix behavior.

## Tests

- Patched `time.time_ns` in tests that asserted exact paths.
- Added `test_unique_ms_timestamp_output_path` for stem + multi-dot filenames.

## Docs

- README quickstart step 3 + Generation tasks note; fixed broken `uv` link formatting on Requirements line.
- CLI.md: `--output` bullet under Important options; paragraph before Common tasks table; table "What you get" column mentions `generated-<unix_ms>.png`.
- CHANGELOG.md under [Unreleased] Changed.
