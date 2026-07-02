"""List model files exposed by a Draw Things gRPCServerCLI via the Echo RPC."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import grpc

from dts_utils.grpc.connection import create_channel, is_loopback_host
from dts_utils.grpc.proto.upstream import imageService_pb2 as pb
from dts_utils.grpc.proto.upstream import imageService_pb2_grpc as grpc_stub
from dts_utils.model_index.local import _categorize_file

_OVERRIDE_FIELDS = ("models", "loras", "controlNets", "textualInversions", "upscalers")


@dataclass(slots=True)
class ServerCatalog:
    """Catalog payload returned by ``ImageGenerationService.Echo``."""

    message: str
    files: list[str] = field(default_factory=list)
    override_bytes: dict[str, int] = field(default_factory=dict)

    @property
    def model_browser_enabled(self) -> bool:
        return bool(self.files) or any(size > 0 for size in self.override_bytes.values())


def fetch_server_catalog(
    *,
    host: str = "localhost",
    port: int = 7859,
    timeout: float = 10.0,
    insecure: bool = False,
    root_cert: Path | None = None,
    trust_server_cert: bool = False,
    force_trust_server_cert: bool = False,
    shared_secret: str | None = None,
    client_name: str = "dts-utils",
) -> ServerCatalog:
    """Call ``Echo`` and return filenames plus override blob sizes."""
    channel = create_channel(
        host,
        port,
        insecure=insecure,
        root_cert=root_cert,
        trust_server_cert=trust_server_cert,
        force_trust_server_cert=force_trust_server_cert,
    )
    try:
        grpc.channel_ready_future(channel).result(timeout=timeout)
        stub = grpc_stub.ImageGenerationServiceStub(channel)
        request = pb.EchoRequest(name=client_name)
        if shared_secret:
            request.sharedSecret = shared_secret
        reply = stub.Echo(request, timeout=timeout)
    finally:
        channel.close()

    override_bytes: dict[str, int] = {}
    if reply.HasField("override"):
        override = reply.override
        for field_name in _OVERRIDE_FIELDS:
            override_bytes[field_name] = len(getattr(override, field_name))

    return ServerCatalog(
        message=reply.message or "",
        files=sorted(reply.files),
        override_bytes=override_bytes,
    )


def _group_files_by_category(files: list[str]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for name in files:
        category = _categorize_file(name)
        grouped.setdefault(category, []).append(name)
    return grouped


def format_server_catalog(
    catalog: ServerCatalog,
    *,
    category: str | None = None,
    limit: int | None = None,
) -> str:
    """Human-readable table of server-offered files."""
    matching = list(catalog.files)
    if category:
        matching = [name for name in matching if _categorize_file(name) == category]
    files = matching
    if limit is not None and limit > 0:
        files = files[:limit]

    lines = [
        f"Server catalog: {len(catalog.files)} file(s)",
        f"Echo message: {catalog.message or '(empty)'}",
    ]
    if category:
        lines.insert(1, f"Category filter: {category} ({len(matching)} match(es))")
    if not files:
        lines.append("Files: (none)")
    else:
        lines.append("")
        lines.append(f"{'FILE':<48} {'CATEGORY':<12}")
        lines.append(f"{'-' * 48} {'-' * 12}")
        for name in files:
            lines.append(f"{name:<48} {_categorize_file(name):<12}")
        if len(matching) > len(files):
            lines.append(f"... {len(matching) - len(files)} more (use --limit 0 to show all)")

    if catalog.override_bytes:
        lines.append("")
        lines.append("Metadata override blobs:")
        for field_name, size in catalog.override_bytes.items():
            lines.append(f"  {field_name}: {size} bytes")

    return "\n".join(lines)


def catalog_to_json(
    catalog: ServerCatalog,
    *,
    category: str | None = None,
    limit: int | None = None,
) -> dict[str, object]:
    files = list(catalog.files)
    if category:
        files = [name for name in files if _categorize_file(name) == category]
    if limit is not None and limit > 0:
        files = files[:limit]

    entries = [
        {"name": name, "category": _categorize_file(name)}
        for name in files
    ]
    grouped = _group_files_by_category(catalog.files)
    return {
        "message": catalog.message,
        "file_count": len(catalog.files),
        "model_browser_enabled": catalog.model_browser_enabled,
        "files": entries,
        "files_by_category": {key: grouped[key] for key in sorted(grouped)},
        "override_bytes": catalog.override_bytes,
    }


def _resolve_trust_flags(
    *,
    host: str,
    insecure: bool,
    root_cert: Path | None,
    trust_server_cert: bool,
    force_trust_server_cert: bool,
) -> tuple[bool, bool]:
    if insecure or root_cert or trust_server_cert or force_trust_server_cert:
        return trust_server_cert, force_trust_server_cert
    if is_loopback_host(host):
        return True, False
    return False, False


def list_server_catalog(args: argparse.Namespace) -> int:
    """CLI handler for ``dts-utils server list-models``."""
    trust_server_cert, force_trust_server_cert = _resolve_trust_flags(
        host=args.host,
        insecure=args.no_tls,
        root_cert=args.root_cert,
        trust_server_cert=args.trust_server_cert,
        force_trust_server_cert=args.force_trust_server_cert,
    )
    if (
        not args.no_tls
        and not args.root_cert
        and not trust_server_cert
        and not force_trust_server_cert
    ):
        print(
            "dts-utils: TLS requires --trust-server-cert (loopback), --root-cert PATH, "
            "or --force-trust-server-cert.",
            file=sys.stderr,
        )
        return 2

    try:
        catalog = fetch_server_catalog(
            host=args.host,
            port=args.port,
            timeout=args.timeout,
            insecure=args.no_tls,
            root_cert=args.root_cert,
            trust_server_cert=trust_server_cert,
            force_trust_server_cert=force_trust_server_cert,
            shared_secret=args.shared_secret,
        )
    except grpc.RpcError as exc:
        print(f"Server catalog error: {exc.code()} {exc.details()}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"Server catalog error: {exc}", file=sys.stderr)
        return 1

    limit = None if args.limit == 0 else args.limit
    if args.json:
        print(json.dumps(catalog_to_json(catalog, category=args.category, limit=limit), indent=2, sort_keys=True))
    else:
        print(format_server_catalog(catalog, category=args.category, limit=limit))

    if not catalog.model_browser_enabled:
        print(
            "\nNo catalog data returned. Restart the server with model browsing enabled:\n"
            "  dts-utils server restart",
            file=sys.stderr,
        )
        return 1

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "List model files the running gRPCServerCLI advertises via the ImageGenerationService Echo RPC."
        ),
        epilog=(
            "Examples:\n"
            "  dts-utils server list-models\n"
            "  dts-utils server list-models --category model --limit 20\n"
            "  dts-utils server list-models --json\n"
            "  dts-utils server list-models --host gpu.local --root-cert ./gpu.pem"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--host", default="localhost", help="gRPC server host (default: localhost).")
    parser.add_argument("--port", type=int, default=7859, help="gRPC server port (default: 7859).")
    parser.add_argument("--timeout", type=float, default=10.0, help="RPC timeout in seconds (default: 10).")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument(
        "--category",
        choices=["model", "lora", "vae", "encoder", "controlnet", "textual-inversion", "config", "partial", "other"],
        help="Filter output to one file category.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        metavar="N",
        help="Show at most N files (default: 0 = show all).",
    )
    parser.add_argument(
        "--no-tls",
        action="store_true",
        help="Connect without TLS. Use only when the server was installed with --no-tls.",
    )
    parser.add_argument("--root-cert", type=Path, help="Root certificate PEM to trust for TLS.")
    parser.add_argument(
        "--trust-server-cert",
        action="store_true",
        help="Trust the presented certificate for localhost/loopback (default on loopback when TLS is on).",
    )
    parser.add_argument(
        "--force-trust-server-cert",
        action="store_true",
        help="Trust the presented certificate for any host (MITM risk).",
    )
    parser.add_argument(
        "-s",
        "--shared-secret",
        dest="shared_secret",
        default=None,
        help="Shared secret when the server requires authentication.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return list_server_catalog(args)
