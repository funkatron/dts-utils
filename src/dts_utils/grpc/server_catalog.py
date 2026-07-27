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
from dts_utils.model_index.local import _categorize_file, _clip, _human_size
from dts_utils.models_api import resolve_draw_things_models_dir

_OVERRIDE_FIELDS = ("models", "loras", "controlNets", "textualInversions", "upscalers")
_BYTES_PER_MB = 1024 * 1024
_FILE_COLUMN_WIDTH = 48
_CATEGORY_COLUMN_WIDTH = 12
_SIZE_COLUMN_WIDTH = 10


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


def local_model_file_sizes(models_dir: Path | str | None = None) -> dict[str, int]:
    """Map basenames under the Draw Things Models dir to on-disk size in bytes."""
    root = resolve_draw_things_models_dir(models_dir)
    sizes: dict[str, int] = {}
    if not root.is_dir():
        return sizes
    try:
        entries = root.iterdir()
    except OSError:
        return sizes
    for path in entries:
        if not path.is_file():
            continue
        try:
            sizes[path.name] = path.stat().st_size
        except OSError:
            continue
    return sizes


def size_bytes_to_mb(size_bytes: int) -> float:
    """Convert bytes to mebibytes (MiB)."""
    return size_bytes / _BYTES_PER_MB


def _format_file_size(size_bytes: int | None) -> str:
    """Adaptive B/KB/MB/GB label for the text table (``-`` when unknown)."""
    if size_bytes is None:
        return "-"
    return _human_size(size_bytes)


def _json_size_mb(size_bytes: int | None) -> float | None:
    if size_bytes is None:
        return None
    return round(size_bytes_to_mb(size_bytes), 3)


def _filter_catalog_files(
    catalog: ServerCatalog,
    *,
    category: str | None = None,
    limit: int | None = None,
) -> tuple[list[str], list[str]]:
    """Return (matching after category filter, matching after category+limit)."""
    matching = list(catalog.files)
    if category:
        matching = [name for name in matching if _categorize_file(name) == category]
    files = matching
    if limit is not None and limit > 0:
        files = files[:limit]
    return matching, files


def format_server_catalog(
    catalog: ServerCatalog,
    *,
    category: str | None = None,
    limit: int | None = None,
    file_sizes: dict[str, int] | None = None,
    models_dir: Path | None = None,
) -> str:
    """Human-readable table of server-offered files."""
    matching, files = _filter_catalog_files(catalog, category=category, limit=limit)
    sizes = file_sizes if file_sizes is not None else {}

    lines = [
        f"Server catalog: {len(catalog.files)} file(s)",
        f"Echo message: {catalog.message or '(empty)'}",
    ]
    if models_dir is not None:
        lines.append(f"Local sizes from: {models_dir}")
    if category:
        lines.insert(1, f"Category filter: {category} ({len(matching)} match(es))")
    if not files:
        lines.append("Files: (none)")
    else:
        lines.append("")
        lines.append(
            f"{'FILE':<{_FILE_COLUMN_WIDTH}} "
            f"{'CATEGORY':<{_CATEGORY_COLUMN_WIDTH}} "
            f"{'SIZE':>{_SIZE_COLUMN_WIDTH}}"
        )
        lines.append(
            f"{'-' * _FILE_COLUMN_WIDTH} "
            f"{'-' * _CATEGORY_COLUMN_WIDTH} "
            f"{'-' * _SIZE_COLUMN_WIDTH}"
        )
        for name in files:
            size_bytes = sizes.get(name)
            display_name = _clip(name, _FILE_COLUMN_WIDTH)
            lines.append(
                f"{display_name:<{_FILE_COLUMN_WIDTH}} "
                f"{_categorize_file(name):<{_CATEGORY_COLUMN_WIDTH}} "
                f"{_format_file_size(size_bytes):>{_SIZE_COLUMN_WIDTH}}"
            )
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
    file_sizes: dict[str, int] | None = None,
    models_dir: Path | None = None,
) -> dict[str, object]:
    _matching, files = _filter_catalog_files(catalog, category=category, limit=limit)
    sizes = file_sizes if file_sizes is not None else {}

    entries: list[dict[str, object]] = []
    for name in files:
        size_bytes = sizes.get(name)
        entry: dict[str, object] = {
            "name": name,
            "category": _categorize_file(name),
            "size_bytes": size_bytes,
            "size_mb": _json_size_mb(size_bytes),
            "size": None if size_bytes is None else _human_size(size_bytes),
        }
        entries.append(entry)
    grouped = _group_files_by_category(catalog.files)
    payload: dict[str, object] = {
        "message": catalog.message,
        "file_count": len(catalog.files),
        "model_browser_enabled": catalog.model_browser_enabled,
        "files": entries,
        "files_by_category": {key: grouped[key] for key in sorted(grouped)},
        "override_bytes": catalog.override_bytes,
    }
    if models_dir is not None:
        payload["models_dir"] = str(models_dir)
    return payload


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

    models_dir = resolve_draw_things_models_dir(getattr(args, "model_dir", None))
    file_sizes = local_model_file_sizes(models_dir)
    limit = None if args.limit == 0 else args.limit
    if args.json:
        print(
            json.dumps(
                catalog_to_json(
                    catalog,
                    category=args.category,
                    limit=limit,
                    file_sizes=file_sizes,
                    models_dir=models_dir,
                ),
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print(
            format_server_catalog(
                catalog,
                category=args.category,
                limit=limit,
                file_sizes=file_sizes,
                models_dir=models_dir,
            )
        )

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
        "--model-dir",
        type=Path,
        default=None,
        help=(
            "Local Draw Things Models directory for SIZE lookup "
            "(default: DRAW_THINGS_MODEL_PATH or macOS Draw Things Models path)."
        ),
    )
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
