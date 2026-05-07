# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## Reading this file

| Audience | What to do |
| --- | --- |
| **Users / downstream** | Read **`[Unreleased]`** (upcoming) and the latest **`## [version]`** block for shipped behavior. |
| **Maintainers cutting a tag** | Move bullets from **`[Unreleased]`** into a dated **`## [x.y.z] - YYYY-MM-DD`** section, add **`### Tested with`** (below), sync **`pyproject.toml`** `version`, then open an empty **`[Unreleased]`**. |

---

## Maintainer release checklist (`gRPCServerCLI`)

Record which Draw Things **`gRPCServerCLI`** build you used for **manual** smoke (GitHub **`tag_name`** from [draw-things-community releases](https://github.com/drawthingsai/draw-things-community/releases), same sort of tag `dts-util server install` prints as “Found latest version”). If you ship **without** a live server, say so (e.g. “pytest + CI only; not smoke-tested against gRPCServerCLI”). Commands: [tests/README.md § Manual release smoke](tests/README.md#manual-release-smoke).

Example snippet for the next release:

```markdown
## [0.5.0] - YYYY-MM-DD

### Tested with

- **gRPCServerCLI:** `v…` — smoke on macOS: `server check`, `generate` (saved config), `reflect`
- Or: **pytest:** … passed; **CI:** … ; **gRPCServerCLI:** not smoke-tested.

### Added

- …
```

---

## [Unreleased]

### Changed

- **`dts-util web`:** history PNGs are now saved by the web server under the dts-util config directory instead of relying on browser `localStorage`; legacy `localStorage` rows import on first History open.
- **`dts-util web`:** result cards use a wider responsive grid, the composer is more compact, and expanded prompt details are shown as a slimmer scrollable log.
- **`dts-util web`:** results area scrolls reliably (including Safari): `#resultPane` is the scroll container with a proper flex `min-height` chain instead of `#stage` scrolling a `height: 100%` pane that failed to extend scroll height.
- **`dts-util server`:** `start` and `stop` subcommands manage the LaunchAgent without uninstalling; lifecycle prefers `launchctl bootstrap` / `bootout` (with `kickstart` and legacy `load`/`unload` fallbacks). `restart` is stop-then-start.
- **`dts-utils` CLI:** Console scripts **`dts-utils`** and **`dts-util`** both call [`dts_util.cli_router:main`](src/dts_util/cli_router.py); stderr examples follow the basename you invoked. Primary docs examples use **`dts-utils`** (repository name). User config paths stay under the **`dts-util`** application slug (`configs.APP_NAME`).
- **`dts-util server restart`:** Clarified in [CLI.md](CLI.md) — settings come from the existing LaunchAgent plist; `restart` does not accept fresh `install` flags, only optional `--model-browser` (mutates `ProgramArguments` before stop/start).
- **`dts-util web`:** Results layout — fixed missing **`img`** constraints (CSS), card-style thumbnails, bounded image height; expanded prompts shown **per run** in a scrollable panel instead of one wall of text; idle/busy centering when no thumbnails yet; slightly taller prompt textarea.
- **Docs:** [CLI.md](CLI.md) — removed redundant “If you only run one command…” lines before example blocks.
- **`dts-util web`:** Generation **history** persists **`configuration`** (same saved-profile value as **`POST /api/generate`**) with each PNG batch; History rows show it in the subtitle, and **Reuse** restores profile (dropdown or custom field), **runs**, and **negative prompt** with the prompt for a consistent redo.
- **`dts-utils` shorthand / web:** Implicit saved profile is **`default`** (**`default.json`** under `configs path`). Legacy **`zit.json`** there is renamed to **`default.json`** when **`default.json`** is missing. **`os.environ.setdefault("DTS_UTILS_DEFAULT_CONFIGURATION", "default")`** after materialization.

### Added

- **`dts_utils.configuration_build.configurations_equivalent_for_flatbuffer`:** returns whether two JSON configs normalize to the same **`flatc`** input (aliases, dropped empties, dimensions, `_dts_utils*` stripping); also bound on **`dts_utils.generate`** for callers/tests.
- **`dts-utils configs import-draw-things`:** Import Draw Things **Local** presets (`custom_configs.json` → **`NAME.json`** for **`generate --configuration`**, copied as-is — validate if **`flatc`** rejects fields). **`--mirror-app-json`** copies **`Models/custom*.json`** and related app JSON into **`draw-things-app/`** only (not **`--configuration`** targets).
- **`dts-utils configs scaffold-from-metadata`:** Create starter saved profile JSON from **`community-models`** **`metadata.json`** (checkpoint name plus optional **note**-based size/step guesses). **`--scan DIR`** walks the tree and writes one profile per eligible local model (`apis/` skipped). Skips remote/API-only models. **`--limit`**, **`--verbose`**, **`--dry-run`**, **`--force`** apply to batch mode as documented in [CLI.md](CLI.md).
- **`dts-utils web`:** Fullscreen minimalist image viewer — click a thumbnail in the results grid or History; **Escape** or backdrop closes; **←** / **→**, side strips, or swipe within that batch; **F** toggles **Fit** (whole image, letterboxed) vs **Fill** (fills the frame, crops edges — sharper on-screen detail); caption shows **Fit** / **Fill**.
- **Docs:** [docs/setup-clean-install-z-image-turbo.md](docs/setup-clean-install-z-image-turbo.md) — operator walkthrough for a clean Mac: Draw Things Community **Z Image Turbo 1.0 (Exact)** weights, **`dts-utils`**, **`models build`**, **`configs scaffold-from-metadata`**, **`server install`**, first **`generate`** (cross-linked from [README.md](README.md) and [docs/README.md](docs/README.md)).

### Fixed

- **JSON → FlatBuffer:** **`fps`** in Draw Things JSON maps to **`fps_id`** so **`flatc`** does not fail with **`unknown field: fps`**.
- **JSON → FlatBuffer:** **`compressionArtifacts": "disabled"`** (Draw Things export style) maps to enum **`Disabled`** so **`flatc`** accepts configs that previously failed with **`unknown enum value: disabled`**.
- **`dts-util web`:** Closed image viewer `<dialog>` no longer covered the page and swallowed clicks (fullscreen flex layout is scoped to `[open]` only).
- **`dts-util web`:** Image viewer **×** stacks above the wide “next” side tap strip so the close control receives clicks.

## [0.4.1] - 2026-05-05

### Tested with

- **gRPCServerCLI:** not smoke-tested for this tag.
- **pytest:** 203 passed, 6 skipped (maintainer, local; unchanged from 0.4.0 expectation). **CI:** `pytest` on Ubuntu (`ci.yml`).

### Changed

- **Docs:** [CLI.md](CLI.md) — task-first navigation table; web HTTP/SSE as tables; removed duplicate generate section; **`DTS_WEB_*`** in environment table.
- **Docs:** [CHANGELOG.md](CHANGELOG.md) — reader vs maintainer framing; maintainer checklist anchor; tighter **0.4.0** notes.
- **Docs:** [README.md](README.md), [docs/README.md](docs/README.md), [PROTOBUF.md](PROTOBUF.md) — updated cross-links.
- **Docstrings:** clearer wording for prompt wildcard preview (`expand_prompt_templates_for_batch`, `/api/prompt/expand` handler).

## [0.4.0] - 2026-04-28

### Tested with

- **gRPCServerCLI:** not smoke-tested for this tag.
- **pytest:** 203 passed, 6 skipped (maintainer, local).
- **CI:** `pytest` on Ubuntu (`ci.yml`).

### Added

- **`dts-util web`:** Loopback HTTP UI for prompt-first generation (Starlette, Jinja2, uvicorn). Optional **`DTS_WEB_TOKEN`** on `/api/*` except **`GET /api/health`**; optional **`DTS_WEB_GENERATE_TIMEOUT`**. Details: [CLI.md § web](CLI.md#web-dts-util-web).
- **`POST /api/generate/stream`:** Server-sent events for thumbnails and batch progress; multipart **`POST /api/generate`** unchanged for batch/script clients.
- **`POST /api/prompt/expand`:** Preview **`count`** wildcard expansions without generating (same rules as generate; each preview is an independent random pass—not locked to your next batch).
- **Docs:** [CLI.md](CLI.md) — SSE vs multipart, cancel/timeout, queue/backpressure; [docs/web-ui-layout.md](docs/web-ui-layout.md) — UI wireframe and Canvas mockup ([docs/design/](docs/design/dts-util-web-humane-layout.canvas.tsx)).

### Fixed

- **`dts-util web`:** Profile dropdown referenced an undefined JS binding; config load uses `default_profile` and fails closed on errors/`401`.
- **`server check` / `server test`:** TLS-first loopback probe (trust presented cert), then plaintext fallback—aligned with default Draw Things installs; use **`--no-tls`** when the server has no TLS.
- **Tests:** gRPC tests close channels cleanly ([test_grpc_server.py](tests/test_grpc_server.py)) to avoid teardown races.

### Changed

- **`dts-util web`:** Setup FAB (connection/profile); ⌘↵ / Ctrl+Enter to generate; History FAB (**localStorage**, downloads, clear).
- **`DTS_WEB_GENERATE_TIMEOUT`:** Applies to streaming SSE as well as multipart; timeout drains the SSE queue so workers do not wedge.
- **Implicit shorthand profile:** Saved name **`zit`** / **`zit.json`** (replaces historical **`default`**); **`setdefault(..., "zit")`** for env visibility.
- **Docs:** README / tests README — `reflect` often **`UNIMPLEMENTED`**; TLS-first check; optional **`dts-util web`** in manual smoke. [AGENTS.md](AGENTS.md), [docs/README.md](docs/README.md) map updates.

### Removed

- **Console scripts:** **`dtsutils`** and **`dts-utils`** removed; entrypoint **`dts-util`** only.

## [0.3.3] - 2026-05-03

### Tested with

- **gRPCServerCLI:** not smoke-tested for this tag. **pytest:** 124 passed, 6 skipped (maintainer, local). **CI:** `pytest` on Ubuntu (`ci.yml`).

### Added

- **Generate shorthand:** `dts-util "PROMPT" [PROFILE] [flags…]` runs `generate` with `--trust-server-cert` and `--open` (flags after optional profile).
- **Default profile bootstrap:** first shorthand use without `DTS_UTIL_DEFAULT_CONFIGURATION` creates **`default.json`** in the saved-config directory (starter 512² JSON; **`model`** from first `.ckpt` / `.safetensors` in Draw Things Models, **`DTS_UTIL_DEFAULT_MODEL`**, or empty with a stderr hint). **`os.environ.setdefault("DTS_UTIL_DEFAULT_CONFIGURATION", "default")`** documents the default for the process unless already exported. *(Later releases used **`zit`** / **`zit.json`**; current **`main`** uses **`default`** again with rename migration from **`zit.json`** — see [Unreleased].)*

## [0.3.2] - 2026-05-03

### Tested with

- **gRPCServerCLI:** not smoke-tested for this tag. **pytest:** 113 passed, 6 skipped (maintainer, local). **CI:** `pytest` on Ubuntu (`ci.yml`).

### Changed

- **[PROTOBUF.md](PROTOBUF.md):** cross-link to [DRAW-THINGS-GRPC-API.md](DRAW-THINGS-GRPC-API.md) for client/streaming notes.
- Renamed **`API.md`** → **`DRAW-THINGS-GRPC-API.md`** so it is obvious the doc is Draw Things' gRPC surface (not the Python `dts_util` module API).

### Added

- **Manual release smoke:** [tests/README.md § Manual release smoke](tests/README.md#manual-release-smoke) defines the live-server CLI checklist (`server check`, `reflect`, `generate`); linked from [CHANGELOG.md](CHANGELOG.md#maintainer-release-checklist-grpcservercli) and [PROTOBUF.md](PROTOBUF.md).

### Removed

- **PyPI publishing:** removed `.github/workflows/publish.yml` and README trusted-publishing instructions. The project is **not** on PyPI; install from a [git checkout](README.md#install) (or a local path / fork) until publishing is turned on deliberately.

### Fixed

- **Docs:** restore proper Markdown for [`flatc`](https://github.com/google/flatbuffers) links and for nested `` `**…**` `` emphasis in [CLI.md](CLI.md), [PROTOBUF.md](PROTOBUF.md), and [DRAW-THINGS-GRPC-API.md](DRAW-THINGS-GRPC-API.md).

## [0.3.1] - 2026-05-03

### Tested with

- **gRPCServerCLI:** not smoke-tested for this tag. **pytest:** 113 passed, 6 skipped (maintainer, local). **CI:** `pytest` on Ubuntu (`ci.yml`).

### Added

- **[`project.urls`](pyproject.toml)** `Repository` link (metadata / future packaging).

### Changed

- **CI:** `actions/checkout@v6` and `astral-sh/setup-uv@v8.1.0` (Node 24–aligned action runtimes; clears GitHub’s Node 20 deprecation noise on `ubuntu-latest`).

### Fixed

- **CI (Linux):** Installer/CLI tests use a fake `HOME` with the default Draw Things `Models` container path, order `installer` fixture after `mock_home_dir`, and make mocked `sys.exit` raise `SystemExit` so `parse_args` does not fall through to interactive `get_default_model_path()` (those failures only surfaced when the macOS default path was absent).

## [0.3.0] - 2026-05-02

### Tested with

- **gRPCServerCLI:** not smoke-tested for this tag. **pytest:** 113 passed, 6 skipped (maintainer, local). **CI:** `.github/workflows/ci.yml` runs `uv sync --dev` and `pytest` on Ubuntu for pushes and pull requests to `main`.

### Removed

- `**dt_model_index` package** (compatibility shim). Import `dts_util.model_index` or use `dts-util models`.
- `scripts/generate_image.py`; use `uv run dts-util generate` instead.

### Changed

- README and `pyproject.toml` classifiers state **alpha** 0.x expectations (breaking changes OK).
- **CLI routing:** New `[dts_util/cli_router.py](src/dts_util/cli_router.py)` owns top-level dispatch (`generate`, `configs`, `reflect`, `tls`, `models`) and `prepare_argv_for_installer_dispatch`; `[server_installer](src/dts_util/installer/server_installer.py)` stays LaunchAgent / installer only. Console script entry: `dts_util.cli_router:main`.
- **Model index package:** Implementation lives under `[dts_util.model_index](src/dts_util/model_index/)`.
- Raise `**grpcio`**, `**grpcio-reflection**`, and `**grpcio-tools**` lower bound to **1.80.0** so dependency resolution skips **1.78.1** (yanked; see [grpc#41725](https://github.com/grpc/grpc/issues/41725)).
- `dts-util generate` default `--output` is `**output/generated.png`** (under `./output`). The `output/` directory is gitignored except `**output/.gitkeep**`.
- `dts-util generate --output` inserts `-<unix_ms>` before the extension on every run (for example `output/generated.png` → `output/generated-1735123456789.png`) so successive invocations never clobber earlier PNGs; multiple images in one response use `-2`, `-3`, … after the timestamped stem.
- LaunchAgent lifecycle verbs must use the `**dts-util server …**` prefix. Bare `**dts-util install**`, `**uninstall**`, `**restart**`, `**test**`, and `**check**` exit with usage on stderr (**exit code `2`**).

### Added

- GitHub Actions **CI** workflow (`pytest` via `uv` on Ubuntu) on `main` pushes and PRs.
- `dts-util server restart --model-browser` to enable model browsing for an existing LaunchAgent service before restart.
- `dts-util generate` for sending a prompt to the upstream Draw Things gRPC streaming API and writing returned images to PNG, including JSON-to-FlatBuffer configuration, local certificate trust options, and `--open` viewer launch support.
- Clear prompt-only failure for `dts-util generate` when no generation configuration is provided.
- Documentation for the upstream Draw Things proto/FlatBuffer split, chunked image streaming, local TLS trust options, and the task-first prompt-to-image command.
- `dts-util reflect` to list services and methods from gRPC server reflection, with JSON output for scripts.
- Shared gRPC channel setup that restricts `--trust-server-cert` to localhost/loopback and directs remote or LAN usage to pinned `--root-cert` certificates.
- `--force-trust-server-cert` for explicit remote trust-on-first-use diagnostics when users accept the MITM risk.
- `dts-util configs path/list` and `dts-util generate --configuration` support for saved JSON config names and `.json` auto-conversion.
- Client commands now use `--no-tls` instead of `--insecure` for plaintext connections to servers installed with `**--no-tls`**.
- `dts-util tls path` and `dts-util tls export` to fetch the server's **presented** certificate over TLS (Python `ssl.get_server_certificate`) and save PEM for `**--root-cert`** on `**generate**` / `**reflect**`. `**server install**` can take `**--export-tls-cert**` (with optional `**--export-tls-cert-path**`, `**--export-tls-cert-force**`) after a successful TLS install on macOS. This pins what the binary serves; `**gRPCServerCLI**` keystores are not altered from `**dts-util**`.
- `dts-util server <install|uninstall|restart|test|check>` for LaunchAgent lifecycle (bare `dts-util server` prints help). `**check**` aliases `**test**` for the localhost listener probe.
- Comprehensive test suite for gRPC utilities
  - Server availability checking
  - Error handling for various gRPC scenarios
  - Channel creation with different configurations
- Improved error handling in `handle_grpc_error`
  - Simplified error code checking
  - Better handling of missing `code()` methods
