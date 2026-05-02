"""Inspect gRPC reflection metadata from a Draw Things server."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import grpc
from google.protobuf import descriptor_pb2
from grpc_reflection.v1alpha import reflection_pb2, reflection_pb2_grpc

from .connection import create_channel


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="List services and methods exposed through gRPC server reflection.",
        epilog="""Examples:
  dts-util reflect --trust-server-cert
  dts-util reflect --insecure
  dts-util reflect --json --root-cert cert.pem
""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--host", default="localhost", help="gRPC server host.")
    parser.add_argument("--port", type=int, default=7859, help="gRPC server port.")
    parser.add_argument("--timeout", type=float, default=2.0, help="Connection timeout in seconds.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument("--insecure", action="store_true", help="Use an insecure channel instead of TLS.")
    parser.add_argument("--root-cert", type=Path, help="Root certificate PEM to trust for TLS.")
    parser.add_argument(
        "--trust-server-cert",
        action="store_true",
        help=(
            "Fetch and trust the presented certificate for this localhost connection. "
            "Use --root-cert for remote or LAN servers."
        ),
    )
    return parser


def list_services(channel: grpc.Channel) -> list[str]:
    stub = reflection_pb2_grpc.ServerReflectionStub(channel)
    responses = stub.ServerReflectionInfo(
        iter([reflection_pb2.ServerReflectionRequest(list_services="")])
    )
    for response in responses:
        if response.WhichOneof("message_response") == "list_services_response":
            return [service.name for service in response.list_services_response.service]
    return []


def describe_service(channel: grpc.Channel, service_name: str) -> list[str]:
    stub = reflection_pb2_grpc.ServerReflectionStub(channel)
    responses = stub.ServerReflectionInfo(
        iter([reflection_pb2.ServerReflectionRequest(file_containing_symbol=service_name)])
    )
    methods: list[str] = []
    for response in responses:
        if response.WhichOneof("message_response") != "file_descriptor_response":
            continue
        for descriptor_bytes in response.file_descriptor_response.file_descriptor_proto:
            descriptor = descriptor_pb2.FileDescriptorProto()
            descriptor.ParseFromString(descriptor_bytes)
            for service in descriptor.service:
                full_name = f"{descriptor.package}.{service.name}" if descriptor.package else service.name
                if service_name in {full_name, service.name} or service_name.endswith(f".{service.name}"):
                    methods.extend(method.name for method in service.method)
    return methods


def reflect_server(channel: grpc.Channel) -> list[dict[str, object]]:
    return [
        {"name": service_name, "methods": describe_service(channel, service_name)}
        for service_name in list_services(channel)
    ]


def print_text(target: str, services: list[dict[str, object]]) -> None:
    print(f"Reflected services from {target}:")
    if not services:
        print("  (no services reported)")
        return

    for service in services:
        print(f"  - {service['name']}")
        for method in service["methods"]:
            print(f"      - {method}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    target = f"{args.host}:{args.port}"

    try:
        channel = create_channel(
            args.host,
            args.port,
            args.insecure,
            root_cert=args.root_cert,
            trust_server_cert=args.trust_server_cert,
        )
    except (OSError, ValueError) as exc:
        print(f"Connection setup error: {exc}", file=sys.stderr)
        return 1

    try:
        grpc.channel_ready_future(channel).result(timeout=args.timeout)
        services = reflect_server(channel)
    except grpc.FutureTimeoutError:
        print(f"Unable to connect to {target} within {args.timeout:g}s.", file=sys.stderr)
        return 1
    except grpc.RpcError as exc:
        print(f"Reflection error: {exc.code()} {exc.details()}", file=sys.stderr)
        return 1
    finally:
        close = getattr(channel, "close", None)
        if close:
            close()

    if args.json:
        print(json.dumps({"target": target, "services": services}, sort_keys=True))
    else:
        print_text(target, services)
    return 0
