# Draw Things gRPC Server API

This document describes the gRPC API endpoints provided by the Draw Things gRPC server. These endpoints can be managed using the `dts-util` tool.

## Service Definition

The service is defined in `src/dts_util/grpc/proto/image_generation.proto`.

## Endpoints

### Echo

Health check endpoint that returns a simple response.

```protobuf
rpc Echo(EchoRequest) returns (EchoResponse);

message EchoRequest {
}

message EchoResponse {
    string message = 1;
}
```

### FilesExist

Check if model files exist in the server's model directory.

```protobuf
rpc FilesExist(FilesExistRequest) returns (FilesExistResponse);

message FilesExistRequest {
    repeated string files = 1;
}

message FilesExistResponse {
    repeated string files = 1;
    repeated bool exists = 2;
    repeated string errors = 3;
}
```

### GenerateImage

Generate images based on provided parameters.

```protobuf
rpc GenerateImage(ImageGenerationRequest) returns (ImageGenerationResponse);

message ImageGenerationRequest {
    string prompt = 1;
    string negative_prompt = 2;
    int32 width = 3;
    int32 height = 4;
    int32 steps = 5;
    float cfg_scale = 6;
    int64 seed = 7;
    string sampler = 8;
    bool restore_faces = 9;
    bool enable_hr = 10;
    float denoising_strength = 11;
    int32 batch_size = 12;
    int32 batch_count = 13;
}

message ImageGenerationResponse {
    repeated bytes images = 1;
    repeated string info = 2;
    repeated SignpostEvent events = 3;
}

message SignpostEvent {
    string name = 1;
    int64 timestamp = 2;
    EventType type = 3;
}
```

### UploadFile

Upload model files to the server.

```protobuf
rpc UploadFile(stream UploadFileRequest) returns (UploadFileResponse);

message UploadFileRequest {
    string filename = 1;
    bytes chunk_data = 2;
}

message UploadFileResponse {
    bool success = 1;
    string message = 2;
}
```

## Using the API

The API can be accessed using any gRPC client. The server can be managed using the `dts-util` command-line tool:

```bash
# Install the server
dts-util install

# Check server status
dts-util test

# Uninstall the server
dts-util uninstall
```

For more details on server management, see the [README.md](README.md).

## Security

- By default, the server uses TLS encryption
- Authentication can be enabled using the `--shared-secret` option
- Default bind address is `0.0.0.0` on port `7859`

## Error Handling

The server uses standard gRPC error codes:

- `UNAVAILABLE`: Server is not running or not accessible
- `INVALID_ARGUMENT`: Invalid request parameters
- `NOT_FOUND`: Requested resource not found
- `INTERNAL`: Server error during processing

## Monitoring

The server supports Datadog monitoring when configured with an API key:

```bash
dts-util install --datadog-api-key YOUR_API_KEY
```