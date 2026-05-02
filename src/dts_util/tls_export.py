"""Fetch the TLS certificate gRPC presents and save it as a PEM for ``--root-cert``.

``gRPCServerCLI`` terminates TLS internally; ``dts-util`` cannot change its keystores.
Clients can pin the **presented** certificate (trust-on-first-connect, written to disk)
instead of repeating ``--trust-server-cert``.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from dts_util.configs import user_config_dir
from dts_util.grpc.connection import fetch_server_certificate

TRUST_RELATIVE_DIR = Path("trusted")
DEFAULT_SERVER_PEM_NAME = "drawthings-grpc-server.pem"


def default_server_pem_path() -> Path:
    """Stable path for exported server PEM alongside other ``dts-util`` config."""
    return user_config_dir() / TRUST_RELATIVE_DIR / DEFAULT_SERVER_PEM_NAME


def fetch_presented_pem(host: str, port: int) -> bytes:
    data = fetch_server_certificate(host, port)
    pem = data if isinstance(data, bytes) else str(data).encode()
    return pem if pem.endswith(b"\n") else pem + b"\n"


def export_presented_certificate(
    host: str,
    port: int,
    destination: Path,
    *,
    force: bool = False,
) -> Path:
    expanded = destination.expanduser()
    if expanded.exists() and not force:
        raise FileExistsError(f"{expanded} already exists; pass --force to overwrite")
    expanded.parent.mkdir(parents=True, exist_ok=True)
    expanded.write_bytes(fetch_presented_pem(host, port))
    return expanded.resolve()


def export_presented_certificate_with_retries(
    host: str,
    port: int,
    destination: Path,
    *,
    force: bool = False,
    attempts: int = 8,
    delay_s: float = 1.25,
) -> Path:
    dest = destination.expanduser()
    if dest.exists() and not force:
        raise FileExistsError(f"{dest} already exists; pass --force to overwrite")
    dest.parent.mkdir(parents=True, exist_ok=True)
    last_err: BaseException | None = None
    n = max(1, attempts)
    for attempt in range(n):
        try:
            dest.write_bytes(fetch_presented_pem(host, port))
            return dest.resolve()
        except Exception as exc:
            last_err = exc
            if attempt + 1 < n:
                time.sleep(delay_s)
    raise RuntimeError(
        f"Could not fetch TLS certificate from {host!r}:{port} after {n} attempts "
        f"(is the server up with TLS enabled?). Last error: {last_err}"
    ) from last_err


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export the gRPC server's presented TLS certificate as a PEM.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""Examples:
  uv run dts-util tls path
  uv run dts-util tls export
  uv run dts-util tls export --output ./my-server.pem --force

Default output: {DEFAULT_SERVER_PEM_NAME} under ${{APP_CONFIG}}/trusted (see tls path).

Use the PEM with ``uv run dts-util generate --root-cert <file>``.

This stores **what the server presented** (pinning); it does not install CAs inside gRPCServerCLI.
""",
    )
    sub = parser.add_subparsers(dest="action", required=True)

    path_p = sub.add_parser("path", help="Print the default PEM destination path.")
    path_p.add_argument(
        "--no-create",
        action="store_true",
        help="Do not create parent directories before printing.",
    )

    export_p = sub.add_parser(
        "export",
        help="Fetch the server's presented certificate via TLS handshake and save PEM.",
    )
    export_p.add_argument("--host", default="localhost", help="Server host.")
    export_p.add_argument("--port", type=int, default=7859, help="Server port.")
    export_p.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help=f"Destination file (default: {DEFAULT_SERVER_PEM_NAME} under configs …/trusted).",
    )
    export_p.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Overwrite an existing PEM file.",
    )
    export_p.add_argument(
        "--retries",
        type=int,
        default=8,
        help="Connection attempts spaced by ~1.25 s (after install latency). Default: %(default)s",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.action == "path":
            path = default_server_pem_path()
            if not args.no_create:
                path.parent.mkdir(parents=True, exist_ok=True)
            print(path)
            return 0

        destination = args.output or default_server_pem_path()
        export_presented_certificate_with_retries(
            args.host,
            args.port,
            destination,
            force=args.force,
            attempts=max(1, args.retries),
        )
        print(f"Wrote presented server certificate PEM to {destination.expanduser().resolve()}")
        print(f"Try: uv run dts-util generate --root-cert {destination.expanduser().resolve()} ...")
        return 0
    except (FileExistsError, OSError, ValueError, RuntimeError) as e:
        print(f"tls export error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
