# Protocol And Schema Reference

This repository contains two protocol definitions:

- `src/dts_utils/grpc/proto/upstream/imageService.proto` is the live Draw Things gRPC API copy used by `dts-utils generate`.
- `src/dts_utils/grpc/proto/image_generation.proto` is an older simplified local proto retained for legacy tests and documentation history. Do not use it for new Draw Things `gRPCServerCLI` client work.

The Draw Things generation configuration schema is separate from protobuf:

- `src/dts_utils/grpc/proto/upstream/config.fbs` defines the FlatBuffer `GenerationConfiguration` table.

See also [DRAW-THINGS-GRPC-API.md](DRAW-THINGS-GRPC-API.md) for client-oriented notes (RPC summary, streaming behavior, example commands).

## Upstream gRPC Service

The live service is `ImageGenerationService`.

```protobuf
service ImageGenerationService {
  rpc GenerateImage(ImageGenerationRequest) returns (stream ImageGenerationResponse);
  rpc FilesExist(FileListRequest) returns (FileExistenceResponse);
  rpc UploadFile(stream FileUploadRequest) returns (stream UploadResponse);
  rpc Echo(EchoRequest) returns (EchoReply);
  rpc Pubkey(PubkeyRequest) returns (PubkeyResponse);
  rpc Hours(HoursRequest) returns (HoursResponse);
}
```

## Request Shape For Image Generation

The generation RPC takes prompt fields from protobuf and generation parameters from FlatBuffer bytes:

```protobuf
message ImageGenerationRequest {
  optional bytes image = 1;
  int32 scaleFactor = 2;
  optional bytes mask = 3;
  repeated HintProto hints = 4;
  string prompt = 5;
  string negativePrompt = 6;
  bytes configuration = 7;
  MetadataOverride override = 8;
  repeated string keywords = 9;
  string user = 10;
  DeviceType device = 11;
  repeated bytes contents = 12;
  optional string sharedSecret = 13;
  bool chunked = 14;
}
```

Important details:

- `configuration` must contain `GenerationConfiguration` FlatBuffer bytes.
- `--configuration` in `dts-utils generate` converts Draw Things JSON to those FlatBuffer bytes using [`flatc`](https://github.com/google/flatbuffers).
- `chunked = true` allows large generated image tensors to arrive in multiple streamed messages.
- `contents` carries content-addressed tensor payloads for image, mask, and hints when those fields are used.

## Response Shape For Image Generation

```protobuf
message ImageGenerationResponse {
  repeated bytes generatedImages = 1;
  optional ImageGenerationSignpostProto currentSignpost = 2;
  repeated ImageGenerationSignpostProto signposts = 3;
  optional bytes previewImage = 4;
  optional int32 scaleFactor = 5;
  repeated string tags = 6;
  optional int64 downloadSize = 7;
  ChunkState chunkState = 8;
  optional RemoteDownloadResponse remoteDownload = 9;
}
```

`generatedImages` contains Draw Things tensor bytes. The helper script decodes those bytes to PNG using `fpzip`, `numpy`, and `Pillow`.

## FlatBuffer Configuration

The root FlatBuffer type is `GenerationConfiguration` in `src/dts_utils/grpc/proto/upstream/config.fbs`.

Common JSON fields from Draw Things use camelCase, while `config.fbs` uses snake_case. The helper script maps common fields before running [`flatc`](https://github.com/google/flatbuffers). Examples:


| Draw Things JSON     | `config.fbs` field     | Notes                                          |
| -------------------- | ---------------------- | ---------------------------------------------- |
| `width`              | `start_width`          | Converted from pixels to 64-pixel units.       |
| `height`             | `start_height`         | Converted from pixels to 64-pixel units.       |
| `batchCount`         | `batch_count`          | Must be at least `1` for practical generation. |
| `guidanceScale`      | `guidance_scale`       | Float.                                         |
| `hiresFix`           | `hires_fix`            | Boolean.                                       |
| `zeroNegativePrompt` | `zero_negative_prompt` | Boolean.                                       |
| `compressionArtifacts` | `compression_artifacts` | Enum `CompressionMethod`; lowercase aliases (`disabled` → `Disabled`, etc.) before flatc. |
| `fps` | `fps_id` | App JSON sometimes uses `fps`; schema field is `fps_id`. |

The script also drops empty `controls`, empty `loras`, and empty string values before conversion. This matches how Draw Things treats omitted optional fields more closely than serializing empty strings everywhere. This matches how Draw Things treats omitted optional fields more closely than serializing empty strings everywhere.

## Regenerating Python gRPC Code

Use this only when `src/dts_utils/grpc/proto/upstream/imageService.proto` changes:

```bash
uv run python -m grpc_tools.protoc \
  -Isrc/dts_utils/grpc/proto/upstream \
  --python_out=src/dts_utils/grpc/proto/upstream \
  --grpc_python_out=src/dts_utils/grpc/proto/upstream \
  src/dts_utils/grpc/proto/upstream/imageService.proto
```

The `grpc_tools` plugin emits `import imageService_pb2` in `imageService_pb2_grpc.py`. That only works if the upstream directory is on `sys.path`; this repo instead uses a **relative import** (`from . import imageService_pb2 as …`) so the package loads as part of `dts_utils`. After regenerating, replace the top-level import line with that relative form (or adjust via proto `option` / tooling if you automate it).

## gRPC integration tests

**Audience:** contributors and automation agents touching `tests/test_grpc_server.py`, protobuf, or Draw Things server releases.

### Current behavior

- **`tests/test_grpc_server.py`** uses the **legacy** `image_generation.proto` stack and assumes plaintext on **`localhost:7859`** (different message shapes than production). Some tests **skip** if nothing is listening, or are marked `@pytest.mark.skip` (models / TODO). Prefer treating this file as **historical** unless you are refreshing it onto upstream.
- **`tests/test_grpc_live_cli.py`** (`@pytest.mark.integration`, `@pytest.mark.live_grpc_cli`) uses **`imageService.proto`** (same as `dts-utils generate`). By default these tests **skip**; opt in by spawning a subprocess server — see [tests/README.md § Ephemeral server](tests/README.md#ephemeral-grpcservercli-pytest) and **Ephemeral subprocess** below.
- **`tests/test_generate_functional_live.py`** runs **`dts_utils.generate.main`** against that same ephemeral server (**`--configuration-json`**, **`flatc`**, first checkpoint under the models tree); still **`live_grpc_cli`** / **`DTS_GRPC_TEST_SPAWN_SERVER`** opt-in.

### Intended direction (hermetic by default)

When implementing or refactoring these tests:

1. **No fixed port by default.** Prefer binding an in-process test server to **127.0.0.1:0** and passing the resolved host/port into fixtures so local developers can run the real `gRPCServerCLI` on a well-known port (for example `7859`) without colliding with pytest.
2. **In-process fake first.** Use `grpc.server()` plus a small servicer that implements only the RPCs the tests need (for example Echo / FilesExist) with canned responses. That keeps CI fast and independent of Draw Things binaries.
3. **Optional real binary (no LaunchAgent).** Set **`DTS_GRPC_TEST_SPAWN_SERVER=1`** to run **`tests/test_grpc_live_cli.py`** and **`tests/test_generate_functional_live.py`**, which share a session-scoped fixture that starts **`gRPCServerCLI MODEL_DIR --port <ephemeral> --address 127.0.0.1 --no-tls`** via **`tests/ephemeral_grpc_server.py`**, probes readiness with **`is_server_running(..., prefer_plaintext=True)`**, then terminates the process when the pytest session ends. Requires the **`gRPCServerCLI`** binary (install path, **`PATH`**, or **`DTS_GRPC_TEST_SERVER_BINARY`**) and a **models directory** (Draw Things default container path or **`DTS_GRPC_TEST_MODEL_PATH`**). CI stays green without these; macOS maintainers use this to validate wire assumptions and full **`generate`** without **`server install`**.

### Staying aligned when `gRPCServerCLI` changes

The fake is a **mirror of a wire contract**, not the product. When Draw Things updates the server:

- Refresh **`src/dts_utils/grpc/proto/upstream/*.proto`**, **regenerate** Python stubs (`grpc_tools.protoc` as above), and fix any call sites (CLI, clients, tests).
- Update the **test servicer** so its behavior and types still match the messages clients send. Otherwise tests can stay green while real usage breaks.
- Use the **optional real-server** run occasionally or on release branches to catch drift the fake cannot see (timing, TLS, streaming quirks, etc.).
- **Pin or note** the Draw Things / proto revision you copied from (in commit messages or this doc) so the next bump is a deliberate step, not guesswork.
- **Shipping `dts-utils`:** each versioned release should list the **gRPCServerCLI** tag used for manual smoke in [CHANGELOG.md](CHANGELOG.md) (see [Maintainer release checklist](CHANGELOG.md#maintainer-release-checklist-grpcservercli)). A concrete **manual smoke** command list lives in [tests/README.md § Manual release smoke](tests/README.md#manual-release-smoke).

## Practical Client Command

```bash
uv run dts-utils generate \
  --prompt "a small robot painting clouds" \
  --configuration-json tmp_models/config.json \
  --output output/generated.png \
  --trust-server-cert \
  --open
```

Use `uv run python` for project code so imports and dependencies come from the uv-managed environment. Use `python3` only for system-level one-off snippets that do not need the project environment.

Prompt-first CLI shorthand (`dts-utils "…"` with no `generate` subcommand) is documented in [CLI.md](CLI.md) and [README.md](README.md); it still sends the same `ImageGenerationRequest` shape over the wire.