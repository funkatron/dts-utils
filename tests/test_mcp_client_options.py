"""Tests for MCP gRPC client option builder."""

from __future__ import annotations

from pathlib import Path

import pytest

from dts_utils.exceptions import ConfigurationError
from dts_utils.mcp.client_options import build_grpc_client_options


def test_build_grpc_client_options_clears_trust_when_root_cert_set(tmp_path: Path) -> None:
    cert = tmp_path / "root.pem"
    cert.write_text("pem", encoding="utf-8")
    opts = build_grpc_client_options(
        host="192.168.1.10",
        root_cert=str(cert),
        trust_server_cert=True,
    )
    assert opts.root_cert == cert
    assert opts.trust_server_cert is False
    assert opts.force_trust_server_cert is False


def test_build_grpc_client_options_clears_trust_when_force_trust_set() -> None:
    opts = build_grpc_client_options(
        host="192.168.1.10",
        trust_server_cert=True,
        force_trust_server_cert=True,
    )
    assert opts.trust_server_cert is False
    assert opts.force_trust_server_cert is True


def test_build_grpc_client_options_rejects_non_loopback_without_tls_path() -> None:
    with pytest.raises(ConfigurationError, match="non-loopback"):
        build_grpc_client_options(host="192.168.1.10", trust_server_cert=True)
