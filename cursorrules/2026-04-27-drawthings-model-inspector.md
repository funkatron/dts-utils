# 2026-04-27 Draw Things Uncurated Model Inspector

- Added a `dts-utils models` workflow for local indexing, search, show, and report commands.
- Implemented standard-library-only parsing, export, SQLite output, and optional Hugging Face enrichment with local caching.
- Kept the existing installer CLI intact by routing only the `models` subcommand into the new package.
