"""gRPC client options for MCP tools."""

from __future__ import annotations

from pathlib import Path

from dts_utils.exceptions import ConfigurationError
from dts_utils.generate_api import GrpcClientOptions
from dts_utils.grpc.connection import is_loopback_host


def non_loopback_warning(host: str) -> str | None:
    if is_loopback_host(host):
        return None
    return (
        "Target host is not loopback. Ensure root_cert or force_trust_server_cert is set when using TLS, "
        "or set no_tls=true for plaintext servers."
    )


def build_grpc_client_options(
    *,
    host: str = "localhost",
    port: int = 7859,
    no_tls: bool = False,
    trust_server_cert: bool = True,
    force_trust_server_cert: bool = False,
    root_cert: str | None = None,
    max_message_mb: int = 64,
) -> GrpcClientOptions:
    """Build :class:`GrpcClientOptions` with the same defaults as the web UI happy path."""
    host = host.strip() or "localhost"
    root_path: Path | None = None
    if root_cert and root_cert.strip():
        root_path = Path(root_cert).expanduser()

    if (
        not is_loopback_host(host)
        and not no_tls
        and trust_server_cert
        and not force_trust_server_cert
        and root_path is None
    ):
        raise ConfigurationError(
            "For non-loopback hosts, set root_cert or force_trust_server_cert=true, "
            "or disable TLS with no_tls=true for plaintext servers."
        )

    # create_channel rejects root_cert combined with trust_server_cert / force_trust_server_cert.
    effective_trust_server_cert = trust_server_cert
    if root_path is not None or force_trust_server_cert:
        effective_trust_server_cert = False

    return GrpcClientOptions(
        host=host,
        port=port,
        no_tls=no_tls,
        root_cert=root_path,
        trust_server_cert=effective_trust_server_cert,
        force_trust_server_cert=force_trust_server_cert,
        max_message_mb=max_message_mb,
    )
