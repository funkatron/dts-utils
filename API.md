# Draw Things gRPC API Notes

This document describes the Draw Things gRPC API surface that this repository uses for client calls. The server process is Draw Things `gRPCServerCLI`; `dts-util` installs and manages that process but does not define the server API.

Authoritative references in this repository:

- Live upstream proto copy: `src/dts_util/grpc/proto/upstream/imageService.proto`
- Python generated upstream stubs: `src/dts_util/grpc/proto/upstream/imageService_pb2.py` and `src/dts_util/grpc/proto/upstream/imageService_pb2_grpc.py`
- Draw Things generation config schema: `src/dts_util/grpc/proto/upstream/config.fbs`
- Legacy local proto kept for older tests/docs history: `src/dts_util/grpc/proto/image_generation.proto`

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


| Endpoint           | Purpose                                                        | Notes                                                                                                   |
| ------------------ | -------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| `Echo`             | Check connectivity and return server metadata.                 | Useful before generation, especially when TLS or shared-secret setup is uncertain.                      |
| `FilesExist`       | Check whether model files exist in the server model directory. | File names are passed relative to the model directory, for example `pikon_realism_v2_alt_q6p_q8p.ckpt`. |
| `GenerateImage`    | Stream image generation progress and generated tensor bytes.   | Requires FlatBuffer `GenerationConfiguration` bytes in `configuration`.                                 |
| `UploadFile`       | Stream file chunks to the server.                              | Not wrapped by the current prompt-to-image helper.                                                      |
| `Pubkey` / `Hours` | Server support endpoints.                                      | Present in the upstream proto; not central to the current CLI workflow.                                 |


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

The `configuration` field is not JSON. It is a FlatBuffer encoded from `GenerationConfiguration` in `src/dts_util/grpc/proto/upstream/config.fbs`. `dts-util generate --configuration config.json` accepts Draw Things JSON and converts it with `flatc` before sending the RPC.

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

`generatedImages` are Draw Things tensor bytes, not PNG files. The `dts-util generate` client decodes those tensors with `fpzip`, `numpy`, and `Pillow`, then writes PNG output.

## Recommended Client Command

Use this for local development:

```bash
uv run dts-util generate \
  --prompt "a small robot painting clouds" \
  --configuration-json tmp_models/config.json \
  --output generated.png \
  --trust-server-cert \
  --open
```

Requirements for this command:

- `flatc` on `PATH` for JSON-to-FlatBuffer conversion.
- A running Draw Things `gRPCServerCLI` on `localhost:7859`, unless `--host` or `--port` is provided.
- `--trust-server-cert` for local TLS when the Draw Things root certificate is not trusted by Python.
- `--shared-secret` if the server was installed with a shared secret.

## Server Management

Use `dts-util` for installing and restarting the Draw Things server process:

```bash
uv run dts-util install --model-browser
uv run dts-util restart --model-browser
uv run dts-util test
```

For command details, see `CLI.md`. For the prompt-to-image workflow, see `README.md`.

## Security And Connection Notes

- The server uses TLS by default.
- Local Draw Things servers commonly present a certificate issued by `Draw Things Root CA`. Python does not automatically trust that root certificate.
- `--trust-server-cert` fetches and trusts the presented server certificate only for `localhost` and loopback addresses. This is a local development convenience, not a remote trust model.
- Use `--root-cert PATH` when you have a pinned PEM certificate file.
- Use `--force-trust-server-cert` only when a remote or LAN diagnostic requires trusting the presented certificate and you accept the man-in-the-middle risk for that connection.
- Use `--no-tls` on the client only when the server was started with `--no-tls`.
