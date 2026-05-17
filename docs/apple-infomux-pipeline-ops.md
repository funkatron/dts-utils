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

- Video steps call `ffmpeg` through the subprocess worker.
- In test/dev environments where `ffmpeg` is unavailable, the stub worker writes a placeholder artifact to keep contract tests deterministic.

## Gatekeeper and quarantine

- Downloaded binaries can be blocked by `com.apple.quarantine`.
- For distributed adapters, prefer signed/notarized binaries.
- Local dev fallback can clear quarantine explicitly when policy allows.
