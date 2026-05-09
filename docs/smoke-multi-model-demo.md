# Smoke demo: server install + generation across presets

Use this when you want to **walk through** Draw Things **`gRPCServerCLI`** plus **`dts-utils generate`** for several representative checkpoints: **SD 1.5–class (quantized)**, **SDXL (with a lighter checkpoint option)**, **Z Image Turbo**, and **LTX‑2.3 distilled** (lighter than the dev weights).

This is **operator prose**, not CI. You still need **real weights** on disk (Draw Things Community is the most reliable source for Draw Things–compatible **`*.ckpt`** names). Maintainer notes on automated fetch: [models-fetch-roadmap.md](models-fetch-roadmap.md).

---

## Prerequisites

- macOS for **`dts-utils server install`** (LaunchAgent path used below).
- **`uv`** and this repo: [README.md § Install](../README.md#install).
- **`flatc`** on **`PATH`** when using JSON saved configs ([README.md § Requirements](../README.md#requirements)).
- Terminal **Full Disk Access** if macOS blocks **`~/Library/Containers/com.liuliu.draw-things/...`** ([CLI.md § configs import-draw-things](../CLI.md)).

---

## One-time: install server + sync community metadata

From the repo root:

```bash
uv sync
uv run dts-utils server install
uv run dts-utils server check
```

Use **`server check --no-tls`** only if you installed with **`--no-tls`**.

Clone or refresh the community index (default **`~/.cache/community-models`**):

```bash
uv run dts-utils models build --skip-hf
```

---

## Presets used in this smoke

| Goal | `community-models` folder | Saved profile (`configs path`) | Quantized / lighter choice |
| --- | --- | --- | --- |
| SD 1.5–class image | [`dreamshaper-v6.31`](https://github.com/drawthingsai/community-models/tree/main/models/dreamshaper-v6.31) | `dreamshaper-v6.31.json` | **`dreamshaper_v6.31_q6p_q8p.ckpt`** is the default **`file`** in metadata (8‑bit). |
| SDXL image | [`sdxl-turbo`](https://github.com/drawthingsai/community-models/tree/main/models/sdxl-turbo) | `sdxl-turbo.json` | Scaffold targets **`sd_xl_turbo_f16.ckpt`**. For a **smaller** checkpoint, install **`sd_xl_turbo_q6p_q8p.ckpt`** and set **`"model"`** in that JSON to match ([metadata `converted`](https://github.com/drawthingsai/community-models/blob/main/models/sdxl-turbo/metadata.json)). |
| Z Image Turbo | [`z-image-turbo-1.0-exact`](https://github.com/drawthingsai/community-models/tree/main/models/z-image-turbo-1.0-exact) | `z-image-turbo-1.0-exact.json` | Same preset as [setup-clean-install-z-image-turbo.md](setup-clean-install-z-image-turbo.md) (multiple files: checkpoint + text encoder + VAE). |
| LTX‑2.3 (lighter) | [`ltx-2.3-22b-distilled-exact`](https://github.com/drawthingsai/community-models/tree/main/models/ltx-2.3-22b-distilled-exact) | `ltx-2.3-22b-distilled-exact.json` | **Distilled** turbo checkpoint vs **`ltx-2.3-22b-dev-exact`**; text encoder **`gemma_3_12b_it_qat_f16.ckpt`** is QAT‑style. |

### LTX caveat (`dts-utils generate`)

LTX‑2.3 is an **audio‑video** foundation model ([upstream note in metadata](https://github.com/drawthingsai/community-models/blob/main/models/ltx-2.3-22b-distilled-exact/metadata.json)). **`dts-utils generate`** uses the **ImageGeneration** gRPC API ([DRAW-THINGS-GRPC-API.md](../DRAW-THINGS-GRPC-API.md)). Treat this step as **best‑effort**: your server build may accept or reject the preset for image RPCs—validate in the Draw Things app if gRPC fails while weights are present.

---

## Put weights on disk (recommended path)

For each preset, use **Draw Things → Community** (or equivalent) so **every basename** referenced in that folder’s **`metadata.json`** exists under:

`~/Library/Containers/com.liuliu.draw-things/Data/Documents/Models`

Inspect expected files anytime:

```bash
META="$HOME/.cache/community-models/models/<folder>/metadata.json"
uv run dts-utils models fetch --from-metadata "$META" --manifest
```

(`--manifest` lists basenames and hashes; use **`--yes`** only when you intend downloads — see [CLI.md § models](../CLI.md).)

---

## Scaffold saved profiles

Repeat per preset (adjust **`META`**):

```bash
META="$HOME/.cache/community-models/models/dreamshaper-v6.31/metadata.json"
uv run dts-utils configs scaffold-from-metadata "$META"

META="$HOME/.cache/community-models/models/sdxl-turbo/metadata.json"
uv run dts-utils configs scaffold-from-metadata "$META"
# Optional: edit configs path / sdxl-turbo.json → "model": "sd_xl_turbo_q6p_q8p.ckpt"

META="$HOME/.cache/community-models/models/z-image-turbo-1.0-exact/metadata.json"
uv run dts-utils configs scaffold-from-metadata "$META"

META="$HOME/.cache/community-models/models/ltx-2.3-22b-distilled-exact/metadata.json"
uv run dts-utils configs scaffold-from-metadata "$META"
```

Preview JSON without writing:

```bash
uv run dts-utils configs scaffold-from-metadata "$META" --dry-run
```

---

## Generation smoke (one image each)

Use **`--trust-server-cert`** for default TLS installs (`--no-tls` if the server is plaintext):

```bash
uv run dts-utils generate \
  --prompt "smoke test, simple geometric shapes on white" \
  --configuration dreamshaper-v6.31 \
  --trust-server-cert \
  --output output/smoke-dreamshaper.png

uv run dts-utils generate \
  --prompt "smoke test, simple geometric shapes on white" \
  --configuration sdxl-turbo \
  --trust-server-cert \
  --output output/smoke-sdxl-turbo.png

uv run dts-utils generate \
  --prompt "smoke test, simple geometric shapes on white" \
  --configuration z-image-turbo-1.0-exact \
  --trust-server-cert \
  --output output/smoke-z-image-turbo.png

uv run dts-utils generate \
  --prompt "smoke test, simple geometric shapes on white" \
  --configuration ltx-2.3-22b-distilled-exact \
  --trust-server-cert \
  --output output/smoke-ltx-distilled.png
```

Success lines look like **`Wrote …`** on stdout. If **`generate`** fails while **`server check`** passes, compare **`metadata.json`** filenames to what is actually on disk and re‑run **`--manifest`** for the mismatching preset.

---

## Skippable: canonical metadata URLs

| Preset | Raw metadata |
| --- | --- |
| DreamShaper v6.31 | `https://raw.githubusercontent.com/drawthingsai/community-models/main/models/dreamshaper-v6.31/metadata.json` |
| SDXL Turbo | `https://raw.githubusercontent.com/drawthingsai/community-models/main/models/sdxl-turbo/metadata.json` |
| Z Image Turbo 1.0 (Exact) | `https://raw.githubusercontent.com/drawthingsai/community-models/main/models/z-image-turbo-1.0-exact/metadata.json` |
| LTX‑2.3 distilled (Exact) | `https://raw.githubusercontent.com/drawthingsai/community-models/main/models/ltx-2.3-22b-distilled-exact/metadata.json` |

---

## See also

- [setup-clean-install-z-image-turbo.md](setup-clean-install-z-image-turbo.md) — deeper Z‑Turbo checklist (three‑file layout).
- [CLI.md § generate](../CLI.md#generate) — flags, shorthand, TLS.
- [README.md § Troubleshooting](../README.md#troubleshooting) — reflection **`UNIMPLEMENTED`**, TLS, missing weights.
