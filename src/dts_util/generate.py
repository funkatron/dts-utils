"""Generate images through Draw Things gRPCServerCLI."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from dts_util.configuration_build import (
    json_configuration_to_flatbuffer,
    normalize_configuration_for_flatc,
)
from dts_util.exceptions import (
    ChannelSetupError,
    ConfigurationError,
    GenerationEmptyError,
    GenerationRpcError,
)
from dts_util.generate_api import (
    GrpcClientOptions,
    ImageGenerationRequestOptions,
    build_image_generation_request,
    generate_to_paths,
)
from dts_util.generation_stream import collect_generated_images
from dts_util.image_output import unique_ms_timestamp_output_path
from dts_util.grpc.proto.upstream import imageService_pb2 as up_pb2
from dts_util.grpc.proto.upstream import imageService_pb2_grpc as up_grpc

# Legacy layout constants (some callers/tests expect these on this module).
PACKAGE_ROOT = Path(__file__).resolve().parent
UPSTREAM_PROTO_PATH = PACKAGE_ROOT / "grpc" / "proto" / "upstream"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Send a prompt to Draw Things gRPCServerCLI and save the returned image.",
    )
    parser.add_argument("--prompt", required=True, help="Prompt to generate.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output/generated.png"),
        help=(
            "Output path (default: output/generated.png under ./output); inserts -<unix_ms> before the extension so repeated runs do not overwrite "
            "prior files (e.g. out/foo.png → out/foo-1735123456789.png). "
            "Additional images from the same run append -2, -3, ... before the extension."
        ),
    )
    parser.add_argument("--host", default="localhost", help="gRPC server host.")
    parser.add_argument("--port", type=int, default=7859, help="gRPC server port.")
    parser.add_argument("--negative-prompt", default="", help="Negative prompt.")
    parser.add_argument("--open", action="store_true", help="Open generated image files in the default viewer.")
    parser.add_argument("--user", default="dts-util", help="Client name sent to the server.")
    parser.add_argument("--shared-secret", help="Shared secret, if the server requires one.")
    parser.add_argument(
        "--max-message-mb",
        type=int,
        default=64,
        help="Maximum gRPC send/receive message size in MiB.",
    )
    config_group = parser.add_mutually_exclusive_group()
    config_group.add_argument(
        "--configuration",
        help=(
            "Draw Things configuration. Existing .json files are converted to FlatBuffer bytes; "
            "other existing files are sent as raw FlatBuffer bytes; names resolve to saved JSON configs."
        ),
    )
    config_group.add_argument("--configuration-json", help="Draw Things JSON configuration file or saved config name.")
    parser.add_argument(
        "--no-tls",
        action="store_true",
        help="Connect without TLS. Use only when the server was installed with --no-tls.",
    )
    parser.add_argument("--root-cert", type=Path, help="Root certificate PEM to trust for TLS.")
    parser.add_argument(
        "--trust-server-cert",
        action="store_true",
        help="Fetch and trust the presented certificate for this localhost connection. Use --root-cert for remote or LAN servers.",
    )
    parser.add_argument(
        "--force-trust-server-cert",
        action="store_true",
        help=(
            "Fetch and trust the presented certificate for any host. "
            "This is vulnerable to MITM attacks; prefer --root-cert for remote or LAN servers."
        ),
    )
    return parser


def build_request(args: argparse.Namespace) -> up_pb2.ImageGenerationRequest:
    """Build a protobuf request from CLI-parse results (for tests and advanced callers)."""
    return build_image_generation_request(
        ImageGenerationRequestOptions(
            prompt=args.prompt,
            negative_prompt=args.negative_prompt,
            configuration=args.configuration,
            configuration_json=args.configuration_json,
            user=args.user,
            shared_secret=args.shared_secret,
        )
    )


def open_images(paths: list[Path]) -> None:
    if sys.platform == "darwin":
        command = ["open"]
    elif sys.platform.startswith("linux"):
        command = ["xdg-open"]
    elif sys.platform.startswith("win"):
        command = ["cmd", "/c", "start", ""]
    else:
        raise ValueError(f"Unsupported platform for --open: {sys.platform}")

    for path in paths:
        subprocess.run([*command, str(path)], check=True)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    client_opts = GrpcClientOptions(
        host=args.host,
        port=args.port,
        no_tls=args.no_tls,
        root_cert=args.root_cert,
        trust_server_cert=args.trust_server_cert,
        force_trust_server_cert=args.force_trust_server_cert,
        max_message_mb=args.max_message_mb,
    )
    gen_opts = ImageGenerationRequestOptions(
        prompt=args.prompt,
        negative_prompt=args.negative_prompt,
        configuration=args.configuration,
        configuration_json=args.configuration_json,
        user=args.user,
        shared_secret=args.shared_secret,
    )
    try:
        written_paths = generate_to_paths(client_opts, gen_opts, args.output)
    except ConfigurationError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        return 1
    except ChannelSetupError as e:
        print(f"Connection setup error: {e}", file=sys.stderr)
        return 1
    except GenerationRpcError as e:
        print(str(e), file=sys.stderr)
        if "CERTIFICATE_VERIFY_FAILED" in (e.details or ""):
            print(
                "TLS certificate verification failed. For a local Draw Things server, retry with --trust-server-cert.",
                file=sys.stderr,
            )
        return 1
    except GenerationEmptyError as e:
        print(str(e), file=sys.stderr)
        return 1
    except (OSError, ValueError, subprocess.CalledProcessError) as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        return 1

    for path in written_paths:
        print(f"Wrote {path}")
    if args.open:
        try:
            open_images(written_paths)
        except (OSError, subprocess.CalledProcessError, ValueError) as e:
            print(f"Open error: {e}", file=sys.stderr)
            return 1
    return 0
