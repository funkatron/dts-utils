"""Shared gRPC channel helpers for Draw Things local tooling."""

from __future__ import annotations

import ipaddress
import ssl
from pathlib import Path

import grpc


LOCAL_TRUST_HOSTS = {"localhost", "localhost."}


def is_loopback_host(host: str) -> bool:
    """Return True when a host string is explicitly local loopback."""
    normalized_host = host.strip().lower()
    if normalized_host in LOCAL_TRUST_HOSTS:
        return True

    try:
        return ipaddress.ip_address(normalized_host).is_loopback
    except ValueError:
        return False


def fetch_server_certificate(host: str, port: int) -> bytes:
    """Fetch the server's presented certificate as PEM bytes."""
    return ssl.get_server_certificate((host, port)).encode()


def create_channel(
    host: str,
    port: int,
    insecure: bool,
    root_cert: Path | None = None,
    trust_server_cert: bool = False,
    force_trust_server_cert: bool = False,
    max_message_mb: int = 64,
) -> grpc.Channel:
    """Create a gRPC channel with consistent local TLS handling."""
    target = f"{host}:{port}"
    max_message_bytes = max_message_mb * 1024 * 1024
    options: list[tuple[str, int | str]] = [
        ("grpc.max_send_message_length", max_message_bytes),
        ("grpc.max_receive_message_length", max_message_bytes),
    ]
    if insecure:
        return grpc.insecure_channel(target, options=options)

    # gRPCServerCLI presents CN=localhost even when bound to LAN/Tailscale addresses.
    if not is_loopback_host(host):
        options.append(("grpc.ssl_target_name_override", "localhost"))

    trust_presented_cert = trust_server_cert or force_trust_server_cert
    if root_cert and trust_presented_cert:
        raise ValueError("Use either --root-cert or a trust-server-cert option, not both.")
    if trust_server_cert and force_trust_server_cert:
        raise ValueError("Use either --trust-server-cert or --force-trust-server-cert, not both.")

    root_certificates = None
    if root_cert:
        root_certificates = root_cert.read_bytes()
    elif trust_presented_cert:
        if trust_server_cert and not is_loopback_host(host):
            raise ValueError(
                "--trust-server-cert is only allowed for localhost or loopback addresses. "
                "Use --root-cert PATH for remote/LAN servers, or --force-trust-server-cert "
                "if you understand the MITM risk."
            )
        root_certificates = fetch_server_certificate(host, port)

    return grpc.secure_channel(
        target,
        grpc.ssl_channel_credentials(root_certificates=root_certificates),
        options=options,
    )
