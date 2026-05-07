# Clean install: server + Z Image Turbo (community-models)

Use this when you want a **from-zero** path on macOS: **`dts-utils`**, **`gRPCServerCLI`**, and **one community preset** — **Z Image Turbo 1.0 (Exact)** (`drawthingsai/community-models` → **`models/z-image-turbo-1.0-exact`**).

This doc is **operator prose**, not an automated installer. Getting weights onto disk is still your responsibility; the most reliable route for Draw Things–compatible **`*.ckpt`** names is usually the **Draw Things app** Community catalog.

---

## What “one model” means here

[`metadata.json` for this preset](https://github.com/drawthingsai/community-models/blob/main/models/z-image-turbo-1.0-exact/metadata.json) references **several** files under the server model root (not a single blob):

| Role | Filename (must exist where the server looks for models) |
| --- | --- |
| Checkpoint | `z_image_turbo_1.0_f16.ckpt` |
| Text encoder | `qwen_3_vl_4b_instruct_f16.ckpt` |
| Autoencoder (VAE) | `flux_1_vae_f16.ckpt` |

Sha256 expectations for the main checkpoint and text encoder are listed under **`converted`** in that metadata file.

Until those files exist, **`server check`** may succeed while **`generate`** fails (empty or misleading errors depending on the server build).

---

## Default model directory

With **`dts-utils server install`** and **no** `-m/--model-path`, **`gRPCServerCLI`** uses Draw Things’ models folder:

`~/Library/Containers/com.liuliu.draw-things/Data/Documents/Models`

Grant **Terminal (or iTerm) Full Disk Access** if macOS blocks reads/writes under **`Library/Containers`** ([CLI.md § configs import-draw-things](../CLI.md) mentions the same constraint).

---

## Path A (recommended): Draw Things app installs the weights

1. Install **[Draw Things](https://drawthings.ai/)** and open it once.
2. In the app, use **Community** (or equivalent) to install **“Z Image Turbo 1.0 (Exact)”** so the **`*.ckpt`** files above land under the container **`Models`** tree.
3. Install **`dts-utils`** ([README.md § Install](../README.md#install)): clone this repo, `cd` into it, **`uv sync`**.
4. Sync metadata used by scaffolding (default clone dir **`~/.cache/community-models`**):

   ```bash
   uv run dts-utils models build --skip-hf
   ```

5. Scaffold the saved profile:

   ```bash
   META="$HOME/.cache/community-models/models/z-image-turbo-1.0-exact/metadata.json"
   uv run dts-utils configs scaffold-from-metadata "$META"
   ```

6. Follow **Install and verify the server** and **First generation** below.

Optional: copy **`z-image-turbo-1.0-exact.json`** → **`default.json`** under **`dts-utils configs path`** so shorthand picks this preset without a second argument (see Path B step 4).

You still use **`dts-utils`** for **`gRPCServerCLI`** + **`generate`** / **`web`**; the Draw Things app step is only to place Draw Things–compatible weights with the expected basenames.

---

## Path B: Clone repo + scaffold JSON only (weights unchanged)

If you already copied the three **`*.ckpt`** files into the model directory by hand (another Mac, backup, etc.):

1. Install **`dts-utils`** ([README.md § Install](../README.md#install)).
2. Sync community metadata (builds **`~/.cache/community-models`** by default):

   ```bash
   uv run dts-utils models build --skip-hf
   ```

3. Write a **starter saved profile** next to your other configs:

   ```bash
   META="$HOME/.cache/community-models/models/z-image-turbo-1.0-exact/metadata.json"
   uv run dts-utils configs scaffold-from-metadata "$META"
   ```

   That creates **`z-image-turbo-1.0-exact.json`** under **`dts-utils configs path`** (stem matches the folder name).

4. (Optional) Make shorthand use it without a second argument:

   ```bash
   CFG="$(uv run dts-utils configs path)"
   cp "$CFG/z-image-turbo-1.0-exact.json" "$CFG/default.json"
   ```

   Adjust **`model`** / sizes in **`default.json`** if anything still mismatches your disk.

---

## Install and verify the server

```bash
uv run dts-utils server install
uv run dts-utils server check
```

Use **`server check --no-tls`** only if you installed with **`--no-tls`**.

---

## First generation

Explicit profile (no **`default.json`** copy):

```bash
uv run dts-utils generate \
  --prompt "a simple product photo of a ceramic mug on white" \
  --configuration z-image-turbo-1.0-exact \
  --trust-server-cert \
  --output output/z-image-turbo-first-run.png
```

Shorthand (if **`default.json`** points at this preset):

```bash
uv run dts-utils "a simple product photo of a ceramic mug on white" \
  --output output/z-image-turbo-first-run.png
```

Requires **`flatc`** on **`PATH`** when using JSON saved configs ([README.md § Requirements](../README.md#requirements)).

---

## If something fails

| Symptom | Likely cause |
| --- | --- |
| **`generate`** fails immediately | Missing **`*.ckpt`** above, wrong **`model`** field in JSON, or **`flatc`** missing for JSON configs. |
| **`server check`** OK, **`generate`** not | Server listening but model weights not visible at the **installed** model path (`-m` overrides defaults). |
| Cannot see **`Models`** from Terminal | Full Disk Access / sandbox path permissions. |

Upstream issue discussion around remote uploads vs local files: [draw-things-community#40](https://github.com/drawthingsai/draw-things-community/issues/40). The **`dts-utils` `generate`** path does not call **`UploadFile`** today ([DRAW-THINGS-GRPC-API.md](../DRAW-THINGS-GRPC-API.md)).

---

## Skippable: canonical metadata URL

- Repo folder: `https://github.com/drawthingsai/community-models/tree/main/models/z-image-turbo-1.0-exact`
- Raw metadata: `https://raw.githubusercontent.com/drawthingsai/community-models/main/models/z-image-turbo-1.0-exact/metadata.json`
