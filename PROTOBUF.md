# Protocol And Schema Reference

This repository contains two protocol definitions:

- `src/dts_util/grpc/proto/upstream/imageService.proto` is the live Draw Things gRPC API copy used by `dts-util generate`.
- `src/dts_util/grpc/proto/image_generation.proto` is an older simplified local proto retained for legacy tests and documentation history. Do not use it for new Draw Things `gRPCServerCLI` client work.

The Draw Things generation configuration schema is separate from protobuf:

- `src/dts_util/grpc/proto/upstream/config.fbs` defines the FlatBuffer `GenerationConfiguration` table.

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
- `--configuration` in `dts-util generate` converts Draw Things JSON to those FlatBuffer bytes using `flatc`.
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

The root FlatBuffer type is `GenerationConfiguration` in `src/dts_util/grpc/proto/upstream/config.fbs`.

Common JSON fields from Draw Things use camelCase, while `config.fbs` uses snake_case. The helper script maps common fields before running `flatc`. Examples:

| Draw Things JSON | `config.fbs` field | Notes |
| --- | --- | --- |
| `width` | `start_width` | Converted from pixels to 64-pixel units. |
| `height` | `start_height` | Converted from pixels to 64-pixel units. |
| `batchCount` | `batch_count` | Must be at least `1` for practical generation. |
| `guidanceScale` | `guidance_scale` | Float. |
| `hiresFix` | `hires_fix` | Boolean. |
| `zeroNegativePrompt` | `zero_negative_prompt` | Boolean. |

The script also drops empty `controls`, empty `loras`, and empty string values before conversion. This matches how Draw Things treats omitted optional fields more closely than serializing empty strings everywhere.

## Regenerating Python gRPC Code

Use this only when `src/dts_util/grpc/proto/upstream/imageService.proto` changes:

```bash
uv run python -m grpc_tools.protoc \
  -Isrc/dts_util/grpc/proto/upstream \
  --python_out=src/dts_util/grpc/proto/upstream \
  --grpc_python_out=src/dts_util/grpc/proto/upstream \
  src/dts_util/grpc/proto/upstream/imageService.proto
```

The generated upstream Python file imports `imageService_pb2` as a top-level module. `dts_util.generate` adds `src/dts_util/grpc/proto/upstream` to `sys.path` before importing the generated stub.

## Practical Client Command

```bash
uv run dts-util generate \
  --prompt "a small robot painting clouds" \
  --configuration-json tmp_models/config.json \
  --output generated.png \
  --trust-server-cert \
  --open
```

Use `uv run python` for project code so imports and dependencies come from the uv-managed environment. Use `python3` only for system-level one-off snippets that do not need the project environment.