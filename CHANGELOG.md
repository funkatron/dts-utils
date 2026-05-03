# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Documenting `gRPCServerCLI` for each release

When you **cut a release** (promote items from `[Unreleased]` into `## [x.y.z] - YYYY-MM-DD`), add a **Tested with** subsection under that version. Record the Draw Things **`gRPCServerCLI`** build you used for **manual** smoke against a live server—normally the GitHub release **`tag_name`** from [draw-things-community](https://github.com/drawthingsai/draw-things-community/releases) (for example `v1.20250225.0`, the same sort of tag `dts-util server install` resolves when it prints “Found latest version”). If you ship without running a real server, say so explicitly (for example “unit tests only; not smoke-tested against gRPCServerCLI”) so downstream can gauge compatibility. **Concrete smoke commands:** see [tests/README.md](tests/README.md#manual-release-smoke).

Example:

```markdown
## [0.4.0] - YYYY-MM-DD

### Tested with

- **gRPCServerCLI:** `v…` — smoke on macOS: `server check`, `generate` (saved config), `reflect`

### Added
- …
```

## [Unreleased]

### Fixed

- **`server check` / `server test`:** probe loopback with **TLS** using the server-presented certificate (same idea as `--trust-server-cert`), then fall back to plaintext, so the check matches default Draw Things `gRPCServerCLI`. Use `server test --no-tls` when the server runs without TLS.

### Changed

- **Implicit shorthand profile:** default saved name is **`zit`** (`zit.json`). If missing, a starter JSON is created there. **`os.environ.setdefault("DTS_UTIL_DEFAULT_CONFIGURATION", "zit")`** replaces **`"default"`**.
- **Docs / smoke:** [README.md](README.md) troubleshooting and [tests/README.md](tests/README.md) note that `reflect` is often `UNIMPLEMENTED` on Draw Things; [tests/README.md](tests/README.md) describes TLS-first check behavior.
- **Docs:** [AGENTS.md](AGENTS.md) and [docs/README.md](docs/README.md) — agent conventions and operator documentation map; README shorthand section renamed to **Shorthand profile (zit)**.

### Removed

- **Console scripts:** `dtsutils` and `dts-utils` removed from `[project.scripts](pyproject.toml)`; use `dts-util` only (shorthand behavior unchanged).

## [0.3.3] - 2026-05-03

### Tested with

- **gRPCServerCLI:** not smoke-tested for this tag. **pytest:** 124 passed, 6 skipped (maintainer, local). **CI:** `pytest` on Ubuntu (`ci.yml`).

### Added

- **Generate shorthand:** `dts-util "PROMPT" [PROFILE] [flags…]` runs `generate` with `--trust-server-cert` and `--open` (flags after optional profile).
- **Default profile bootstrap:** first shorthand use without `DTS_UTIL_DEFAULT_CONFIGURATION` creates **`default.json`** in the saved-config directory (starter 512² JSON; **`model`** from first `.ckpt` / `.safetensors` in Draw Things Models, **`DTS_UTIL_DEFAULT_MODEL`**, or empty with a stderr hint). **`os.environ.setdefault("DTS_UTIL_DEFAULT_CONFIGURATION", "default")`** documents the default for the process unless already exported. *(0.3.3 file name; current `main` uses **`zit.json`** / profile **`zit`** only—see [Unreleased].)*

## [0.3.2] - 2026-05-03

### Tested with

- **gRPCServerCLI:** not smoke-tested for this tag. **pytest:** 113 passed, 6 skipped (maintainer, local). **CI:** `pytest` on Ubuntu (`ci.yml`).

### Changed

- **[PROTOBUF.md](PROTOBUF.md):** cross-link to [DRAW-THINGS-GRPC-API.md](DRAW-THINGS-GRPC-API.md) for client/streaming notes.
- Renamed **`API.md`** → **`DRAW-THINGS-GRPC-API.md`** so it is obvious the doc is Draw Things' gRPC surface (not the Python `dts_util` module API).

### Added

- **Manual release smoke:** [tests/README.md § Manual release smoke](tests/README.md#manual-release-smoke) defines the live-server CLI checklist (`server check`, `reflect`, `generate`); linked from [CHANGELOG.md](CHANGELOG.md#documenting-grpcservercli-for-each-release) and [PROTOBUF.md](PROTOBUF.md).

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

