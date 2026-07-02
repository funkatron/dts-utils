# Draw Things gRPC API Notes

This document describes the Draw Things gRPC RPCs and messages that `dts-utils` calls. It does not replace [CLI.md](CLI.md) for command-line usage or [README.md](README.md) for install and TLS.

The server binary is Draw Things `gRPCServerCLI`. This repo ships a client and installer, not the server implementation.

Authoritative references in this repository:

- Live upstream proto copy: `src/dts_utils/grpc/proto/upstream/imageService.proto`
- Python generated upstream stubs: `src/dts_utils/grpc/proto/upstream/imageService_pb2.py` and `src/dts_utils/grpc/proto/upstream/imageService_pb2_grpc.py`
- Draw Things generation config schema: `src/dts_utils/grpc/proto/upstream/config.fbs`
- Legacy local proto kept for older tests/docs history: `src/dts_utils/grpc/proto/image_generation.proto`

## Main Service

The upstream service is `ImageGenerationService`.

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

## Endpoint Summary

| Endpoint | Purpose | Notes |
| --- | --- | --- |
| `Echo` | Connectivity and server metadata | Handy when TLS or shared-secret setup is unclear. |
| `FilesExist` | Model files present on the server | Paths are relative to the server model directory (for example `*.ckpt`). |
| `GenerateImage` | Stream progress and image tensors | Request `configuration` must be FlatBuffer `GenerationConfiguration` bytes. |
| `UploadFile` | Stream file chunks | Not used by the current `dts-utils generate` path. |
| `Pubkey` / `Hours` | Other upstream RPCs | In the proto; not part of the usual CLI flow. |

## Image Generation Contract

`GenerateImage` is a server-streaming RPC. A request contains prompt text plus a binary Draw Things generation configuration:

```protobuf
message ImageGenerationRequest {
  optional bytes image = 1;
  int32 scaleFactor = 2;
  optional bytes mask = 3;
  repeated HintProto hints = 4;
  string prompt = 5;
  string negativePrompt = 6;
  bytes configuration = 7;       // FlatBuffer GenerationConfiguration bytes.
  MetadataOverride override = 8;
  repeated string keywords = 9;
  string user = 10;
  DeviceType device = 11;
  repeated bytes contents = 12;
  optional string sharedSecret = 13;
  bool chunked = 14;
}
```

The `configuration` field is not JSON. It is a FlatBuffer encoded from `GenerationConfiguration` in `src/dts_utils/grpc/proto/upstream/config.fbs`. The `dts-utils generate --configuration config.json` path accepts Draw Things JSON and converts it with [`flatc`](https://github.com/google/flatbuffers) before sending the RPC. For a prompt-first invocation without writing `generate`, see [CLI.md § Generate shorthand](CLI.md#generate-shorthand-prompt-first).

Responses contain progress, previews, and generated image tensors:

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

`generatedImages` are Draw Things tensor bytes, not PNG files. The `dts-utils generate` client decodes those tensors with `fpzip`, `numpy`, and `Pillow`, then writes PNG output. Some `gRPCServerCLI` builds stream progress in `previewImage` and leave `generatedImages` empty; in that case `dts-utils` uses the **largest** streamed `previewImage` payload that successfully decodes as the same tensor format.

## Examples (dts-utils)

Explicit `generate` (local TLS trust, JSON on disk):

```bash
uv run dts-utils generate \
  --prompt "a small robot painting clouds" \
  --configuration-json tmp_models/config.json \
  --output output/generated.png \
  --trust-server-cert \
  --open
```

Prompt-first shorthand (uses or creates `default.json` by default; opens the PNG):

```bash
uv run dts-utils "a small robot painting clouds"
```

Details: [CLI.md](CLI.md) and [README.md](README.md).

### Requirements

- [`flatc`](https://github.com/google/flatbuffers) on `PATH` when you pass JSON configuration (conversion uses `config.fbs`).
- A running Draw Things `gRPCServerCLI` on `localhost:7859` unless you pass `--host` / `--port`.
- `--trust-server-cert` for local TLS when Python does not trust the Draw Things root (shorthand adds this for you).
- `--shared-secret` when the server was installed with one.

## Server Management

Use `dts-utils` for installing and restarting the Draw Things server process:

```bash
uv run dts-utils server install
uv run dts-utils server stop
uv run dts-utils server start
uv run dts-utils server restart
uv run dts-utils server restart --no-model-browser
uv run dts-utils server test
uv run dts-utils server list-models
```

With **`--model-browser`**, the **`Echo`** gRPC RPC returns checkpoint / LoRA / VAE basenames in **`EchoReply.files`** plus optional **`MetadataOverride`** blobs. **`dts-utils server list-models`** wraps that endpoint. It is not the same as **`dts-utils models installed`**, which scans the Models directory on disk — see [CLI.md § Listing local weights](CLI.md#listing-local-weights-server-list-models-vs-models-installed).

For command details, see [CLI.md](CLI.md). For install, shorthand, and configuration files, see [README.md](README.md).

## Security and connection notes

- The server uses TLS by default.
- Local Draw Things servers commonly present a certificate issued by `Draw Things Root CA`. Python does not automatically trust that root certificate.
- `--trust-server-cert` fetches and trusts the presented server certificate only for `localhost` and loopback addresses. This is a local development convenience, not a remote trust model.
- Use `--root-cert PATH` when you have a pinned PEM certificate file.
- Use `--force-trust-server-cert` only when a remote or LAN diagnostic requires trusting the presented certificate and you accept the man-in-the-middle risk for that connection.
- Use `--no-tls` on the client only when the server was started with `--no-tls`.

