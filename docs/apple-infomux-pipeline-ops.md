# Apple infomux pipeline ops

This note documents Apple-specific runtime expectations for the new pipeline primitives in `dts_utils.pipeline`.

## Runtime checks

- Use `collect_apple_runtime_checks(run_root)` to snapshot:
  - detected `ffmpeg` path (or missing),
  - writability of your run root,
  - Gatekeeper/notarization reminder for distributed executables.

## Writable run roots

- Prefer user-writable roots such as:
  - `~/Movies/infomux-runs`
  - `~/Library/Application Support/infomux/runs`
- Avoid app-container or protected paths unless explicitly required.

## Heartbeats for long I2V runs

- `PipelineRunner` writes `heartbeat.json` under each run directory.
- The heartbeat updates at step start/end with:
  - active step id,
  - index + total step count,
  - coarse remaining-step estimate.

This supports lightweight progress polling for long video steps.

## ffmpeg behavior

- Video steps call `ffmpeg` to mux frames (Draw Things gRPC image-to-video) or to render placeholder motion (subprocess worker).
- If `ffmpeg` is missing, `pipeline run` fails with an actionable error (run `dts-utils pipeline check` first).
- Tests may set `DTS_PIPELINE_ALLOW_FFMPEG_STUB=1` to write a deterministic placeholder `.mp4` when `ffmpeg` is unavailable.

## Pipeline profiles

- Store run defaults in saved JSON under the configs directory as `_dts_utils_pipeline` (see [CLI.md](../CLI.md#pipeline-dts-utils-pipeline)).
- Quick install bundled manifest: `dts-utils configs scaffold-pipeline infomux` (references **`default`** and **`ltx-2.3-22b-distilled-exact`** — create those Draw Things JSON profiles separately).
- List profiles: `dts-utils pipeline profiles`.
- Typical run: `dts-utils pipeline run --profile YOUR_PROFILE --prompt "..."`.
- Web UI: select a profile marked **(pipeline)** and use **Run pipeline**.
- Set `DTS_UTILS_DEFAULT_PIPELINE_PROFILE` to omit `--profile` on repeat runs.

## Run-root cleanup (disk control)

- Use `dts-utils pipeline cleanup` to prune old run directories under your run root.
- Common preview pass:
  - `dts-utils pipeline cleanup --older-than 7 --keep-last 20 --dry-run`
- Common bounded-size pass:
  - `dts-utils pipeline cleanup --max-run-root-gb 25 --keep-last 10`
- The cleaner only targets directories that contain `pipeline_run.json`.
- Use `--json` for machine-readable output in scripts.

## Draw Things image-to-video

- Real I2V uses the same `ImageGenerationService.GenerateImage` RPC as text-to-image: pass an input image tensor on `request.image`, a video-oriented saved JSON profile (from the pipeline profile’s `video_configuration`), and mux all returned frame tensors to `video.mp4`.
- Placeholder I2V (`i2v_backend: placeholder` in the profile, or legacy flags) does not call Draw Things; it animates the input still with ffmpeg for fast local tests.

## Gatekeeper and quarantine

- Downloaded binaries can be blocked by `com.apple.quarantine`.
- For distributed adapters, prefer signed/notarized binaries.
- Local dev fallback can clear quarantine explicitly when policy allows.
