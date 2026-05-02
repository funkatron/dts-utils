# 2026-04-29 gRPC Model Browser and Image Client

- Added restart-time model browser enablement with `dts-util restart --model-browser`.
- Preserved existing LaunchAgent settings by mutating only the installed service `ProgramArguments`.
- Added `scripts/generate_image.py` to call upstream streaming `GenerateImage` and write returned image bytes to disk.
- Added `--configuration-json` to convert Draw Things JSON config into FlatBuffer bytes with `flatc` and the bundled `config.fbs` schema.
- Added Draw Things tensor decoding so generated responses are written as PNG images instead of raw tensor bytes.
- Added `--open` to launch successfully written image files in the platform default viewer.
- Added fail-fast validation so prompt-only calls report that a generation configuration is required instead of opening a doomed gRPC stream.
- Added explicit TLS trust options after local testing showed Draw Things presents a localhost certificate issued by `Draw Things Root CA` without a system-trusted chain.
- Covered both paths with mocked functional tests instead of requiring a live Draw Things server.
- Updated `README.md`, `CLI.md`, `API.md`, and `PROTOBUF.md` to describe the live upstream proto, FlatBuffer configuration requirement, chunked response handling, and task-first helper command.
- Promoted the useful reflection scratch probe to `dts-util reflect`, then removed one-off scratch scripts.
- Restricted `--trust-server-cert` to localhost/loopback so remote and LAN servers require explicit pinned trust via `--root-cert`.

## Follow-up ideas

- If no generation configuration is provided, prompt the user interactively to choose or supply one instead of immediately failing. Keep a non-interactive escape hatch for scripts and agents.
