# Roadmap: `dts-utils models fetch` (weights orchestration)

Operator-facing behavior stays in [CLI.md](../CLI.md) and [setup-clean-install-z-image-turbo.md](setup-clean-install-z-image-turbo.md). This document is for **maintainers and contributors**: what shipped in MVP, what is queued, and acceptance hints.

---

## Shipped (baseline)

| Area | Status |
| --- | --- |
| Bundled recipes + `registry.json` default id | `dts_utils/model_fetch/recipe_files/` |
| Resolver | `DTS_UTILS_DEFAULT_FETCH_RECIPE` → `default_recipe_id` |
| Consent | `--yes` for writes; `--dry-run` is zero network / zero `--model-dir` writes |
| Backends | `https://` only (TLS verify on); optional `huggingface` via `huggingface_hub` (`uv sync --extra download`) |
| Integrity | `sha256` on artifact when set → mandatory verify after download |
| Optional integrity | `expected_size_bytes` on artifact → skip/idempotency + verify after download when **no** `sha256` |
| Metadata parity | `--from-metadata`, `--manifest` (compact TSV + stderr hints), `--manifest-wide` |
| Shared index logic | `metadata_fetch_hints` reused by `models build`; manifest SHA from `converted` |

---

## Phase A — Verified sources for reference recipes

**Status:** Landed for smoke targets **`sdxl-turbo`**, **`z-image-turbo-1.0-exact`**, and **`ltx-2.3-22b-distilled-exact`** via bundled recipe sources.

**Goal:** Expand source-backed coverage beyond those smoke presets only after **manual** confirmation that each source resolves to the **Draw Things–compatible** blob matching community filenames / hashes.

**Acceptance**

- Each artifact either has working `sources` or an explicit maintainer note in the recipe `description` explaining why URLs are omitted.
- Prefer pinned `revision` (commit/tag) where Hub `main` moves.
- Update [CHANGELOG.md](../CHANGELOG.md) when URLs land.

**Risk:** Hugging Face “model cards” often point at diffusers layouts, not `.ckpt` exports — validate against real files, not filenames alone.

---

## Phase B — `configs` integration (`bootstrap --pull-weights` or equivalent)

**Goal:** One-shot path: optional fetch (default recipe) + scaffold saved profile (+ optional `default.json` copy), as sketched in the original HF/Civitai plan.

**Acceptance**

- Non-interactive flags only (`--dry-run`, `--yes`, `--force`, `--model-dir`).
- Document next to `configs scaffold-from-metadata` in [CLI.md](../CLI.md).

---

## Phase C — Civitai / URL polish

**Goal:** When README or metadata lacks stable HTTPS blobs, optional Civitai GraphQL/API resolution (`CIVITAI_API_TOKEN`) behind explicit flags — **not** silent network.

**Acceptance**

- Document token, rate limits, and “direct HTTPS preferred” in CLI + this roadmap.

---

## Phase D — Integration smoke

**Goal:** `@pytest.mark.integration` test behind **`DTS_UTILS_FETCH_INTEGRATION=1`** hitting a **tiny** public `https://` fixture (or ephemeral server), documented in [tests/README.md](../tests/README.md).

**Acceptance**

- CI unchanged (test skips by default); maintainer can opt in locally.

---

## Phase E — Recipe ergonomics

| Idea | Notes |
| --- | --- |
| Partial `.part` cleanup | Align with local model doctor semantics where practical |
| ToS / license stderr reminder | Short line when `--yes` mutates disk |
| More bundled presets | Only after Phase A discipline (Turbo Exact stays reference) |

---

## See also

- [AGENTS.md](../AGENTS.md) — layout and pytest constraints
- [DRAW-THINGS-GRPC-API.md](../DRAW-THINGS-GRPC-API.md) — weights on disk vs `UploadFile`
