# Protocol Buffer Definitions

This document details the protocol buffer definitions used by the Draw Things gRPC server. The definitions are located in `src/dts_util/grpc/proto/image_generation.proto`.

## Service Definition

```protobuf
syntax = "proto3";

package drawthings;

service ImageGenerationService {
    // Echo endpoint for health check
    rpc Echo(EchoRequest) returns (EchoResponse);

    // Check if model files exist
    rpc FilesExist(FilesExistRequest) returns (FilesExistResponse);

    // Generate images based on parameters
    rpc GenerateImage(ImageGenerationRequest) returns (ImageGenerationResponse);

    // Upload model files
    rpc UploadFile(stream UploadFileRequest) returns (UploadFileResponse);
}
```

## Message Definitions

### Echo Messages

```protobuf
message EchoRequest {
}

message EchoResponse {
    string message = 1;  // Returns "HELLO" when server is running
}
```

### File Existence Check Messages

```protobuf
message FilesExistRequest {
    repeated string files = 1;  // List of files to check
}

message FilesExistResponse {
    repeated string files = 1;   // List of checked files
    repeated bool exists = 2;    // Existence status for each file
    repeated string errors = 3;  // Error messages if any
}
```

### Image Generation Messages

```protobuf
message ImageGenerationRequest {
    string prompt = 1;              // Generation prompt
    string negative_prompt = 2;     // Negative prompt
    int32 width = 3;               // Image width
    int32 height = 4;              // Image height
    int32 steps = 5;               // Number of steps
    float cfg_scale = 6;           // CFG scale
    int64 seed = 7;                // Random seed (-1 for random)
    string sampler = 8;            // Sampler name
    bool restore_faces = 9;        // Face restoration
    bool enable_hr = 10;           // High-res fix
    float denoising_strength = 11; // Denoising strength
    int32 batch_size = 12;         // Images per batch
    int32 batch_count = 13;        // Number of batches
}

message ImageGenerationResponse {
    repeated bytes images = 1;     // Generated images (PNG format)
    repeated string info = 2;      // Generation parameters
    repeated SignpostEvent events = 3; // Progress events with timestamps/types
}
```

### File Upload Messages

```protobuf
message UploadFileRequest {
    string filename = 1;   // Target filename
    bytes chunk_data = 2;  // File data chunk
}

message UploadFileResponse {
    bool success = 1;   // Indicates whether upload succeeded
    string message = 2; // Status message
}
```

### Signpost Event Messages

```protobuf
message SignpostEvent {
    string name = 1;      // Event label
    int64 timestamp = 2;  // Event timestamp
    EventType type = 3;   // Categorized event type
}
```

## Using Protocol Buffers

### Generating Code

The protocol buffer code can be generated using:

```bash
cd src/dts_util/grpc/proto
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. image_generation.proto
```

### Python Usage

```python
from dts_util.grpc.proto import image_generation_pb2, image_generation_pb2_grpc

# Create a request
request = image_generation_pb2.ImageGenerationRequest(
    prompt="a beautiful landscape",
    width=512,
    height=512,
    steps=20,
    cfg_scale=7.0
)

# Use with gRPC channel
with grpc.insecure_channel('localhost:7859') as channel:
    stub = image_generation_pb2_grpc.ImageGenerationServiceStub(channel)
    response = stub.GenerateImage(request)
```

## Server Management

The server can be managed using the `dts-util` command-line tool:

```bash
# Install with default settings
dts-util install

# Install with custom port
dts-util install --port 7860

# Check server status
dts-util test

# Restart the server
dts-util restart

# Uninstall the server
dts-util uninstall
```

For more details on server management, see the [README.md](README.md).