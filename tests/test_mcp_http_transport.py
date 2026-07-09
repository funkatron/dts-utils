"""Tests for MCP Streamable HTTP transport (Phase 5)."""

from __future__ import annotations

import asyncio
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Iterator

import httpx
import pytest
import uvicorn
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.shared._httpx_utils import create_mcp_http_client

from dts_utils.mcp.env import MCP_TOKEN_ENV
from dts_utils.mcp.http_auth import warn_if_insecure_bind
from dts_utils.mcp.server import create_mcp_server, main
from dts_utils.mcp.tools import LIFECYCLE_TOOL_NAMES, MCP_TOOL_NAMES


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _dts_utils_mcp_argv(*args: str) -> list[str]:
    script = shutil.which("dts-utils-mcp")
    if script:
        return [script, *args]
    return [sys.executable, "-m", "dts_utils.mcp.server", *args]


def _wait_for_port(
    host: str,
    port: int,
    *,
    timeout: float = 5.0,
    proc: subprocess.Popen[bytes] | None = None,
) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc is not None and proc.poll() is not None:
            stderr = proc.stderr.read().decode() if proc.stderr else ""
            raise RuntimeError(f"dts-utils-mcp serve exited early ({proc.returncode}): {stderr}")
        try:
            with socket.create_connection((host, port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.05)
    raise RuntimeError(f"TCP server on {host}:{port} did not start within {timeout}s")


@asynccontextmanager
async def _authenticated_mcp_client(url: str, token: str) -> AsyncIterator[ClientSession]:
    async with create_mcp_http_client(
        headers={"Authorization": f"Bearer {token}"},
    ) as http_client:
        async with streamable_http_client(url, http_client=http_client) as (read, write, _get_session_id):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session


@pytest.fixture
def http_mcp_url(monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[str, str]]:
    """Start Streamable HTTP MCP on an ephemeral loopback port."""
    monkeypatch.delenv("DTS_MCP_ALLOW_SERVER_LIFECYCLE", raising=False)
    token = "phase5-test-token"
    port = _free_port()
    host = "127.0.0.1"
    path = "/mcp"
    server = create_mcp_server(
        transport_mode="http",
        host=host,
        port=port,
        streamable_http_path=path,
        token=token,
    )
    app = server.streamable_http_app()
    config = uvicorn.Config(app, host=host, port=port, log_level="error")
    uvicorn_server = uvicorn.Server(config)

    thread = threading.Thread(target=uvicorn_server.run, daemon=True)
    thread.start()

    _wait_for_port(host, port)

    yield f"http://{host}:{port}{path}", token

    uvicorn_server.should_exit = True
    thread.join(timeout=5.0)


@pytest.fixture
def serve_cli_url() -> Iterator[tuple[str, str]]:
    """Start ``dts-utils-mcp serve`` subprocess on an ephemeral loopback port."""
    token = "phase5-cli-test-token"
    port = _free_port()
    host = "127.0.0.1"
    path = "/mcp"
    env = os.environ.copy()
    env[MCP_TOKEN_ENV] = token
    env.pop("DTS_MCP_ALLOW_SERVER_LIFECYCLE", None)

    proc = subprocess.Popen(
        _dts_utils_mcp_argv(
            "serve",
            "--bind",
            host,
            "--port",
            str(port),
            "--path",
            path,
        ),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    try:
        _wait_for_port(host, port, timeout=10.0, proc=proc)
        yield f"http://{host}:{port}{path}", token
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5.0)
        if proc.stderr is not None:
            proc.stderr.close()


def test_mcp_http_requires_token_when_set(http_mcp_url: tuple[str, str]) -> None:
    _url, token = http_mcp_url
    server = create_mcp_server(
        transport_mode="http",
        host="127.0.0.1",
        port=80,
        token=token,
    )
    transport = httpx.ASGITransport(app=server.streamable_http_app())

    async def _request() -> httpx.Response:
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.post("/mcp", json={"jsonrpc": "2.0", "method": "initialize", "id": 1})

    response = asyncio.run(_request())
    assert response.status_code == 401


def test_mcp_http_lists_core_tools(http_mcp_url: tuple[str, str]) -> None:
    url, token = http_mcp_url

    async def _list_tools() -> set[str]:
        async with _authenticated_mcp_client(url, token) as session:
            tools = await session.list_tools()
            return {tool.name for tool in tools.tools}

    names = asyncio.run(_list_tools())
    assert MCP_TOOL_NAMES <= names
    assert not LIFECYCLE_TOOL_NAMES & names


def test_mcp_serve_cli_with_bearer_lists_tools(serve_cli_url: tuple[str, str]) -> None:
    url, token = serve_cli_url

    async def _list_tools() -> set[str]:
        async with _authenticated_mcp_client(url, token) as session:
            tools = await session.list_tools()
            return {tool.name for tool in tools.tools}

    names = asyncio.run(_list_tools())
    assert MCP_TOOL_NAMES <= names
    assert not LIFECYCLE_TOOL_NAMES & names


def test_mcp_http_server_check_stub(
    http_mcp_url: tuple[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url, token = http_mcp_url
    monkeypatch.setattr("dts_utils.mcp.tools.is_server_running", lambda **kwargs: True)

    async def _call() -> dict:
        async with _authenticated_mcp_client(url, token) as session:
            result = await session.call_tool("dts_server_check", {"host": "127.0.0.1"})
        payload = result.structuredContent
        assert isinstance(payload, dict)
        return payload

    payload = asyncio.run(_call())
    assert payload["running"] is True
    assert payload["host"] == "127.0.0.1"


def test_mcp_http_lifecycle_tools_never_registered(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DTS_MCP_ALLOW_SERVER_LIFECYCLE", "1")
    server = create_mcp_server(transport_mode="http")

    async def _names() -> set[str]:
        tools = await server.list_tools()
        return {tool.name for tool in tools}

    names = asyncio.run(_names())
    assert LIFECYCLE_TOOL_NAMES.isdisjoint(names)


def test_stdio_main_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, ...]] = []

    class FakeServer:
        def run(self, *, transport: str) -> None:
            calls.append(("run", transport))

    monkeypatch.setattr("dts_utils.mcp.server.create_mcp_server", lambda **kwargs: FakeServer())
    main([])
    assert calls == [("run", "stdio")]


def test_warn_if_insecure_bind_without_token(capsys: pytest.CaptureFixture[str]) -> None:
    warn_if_insecure_bind("0.0.0.0", token_set=False)
    err = capsys.readouterr().err
    assert MCP_TOKEN_ENV in err
    assert "warning" in err


def test_warn_if_insecure_bind_skipped_on_loopback(capsys: pytest.CaptureFixture[str]) -> None:
    warn_if_insecure_bind("127.0.0.1", token_set=False)
    assert capsys.readouterr().err == ""
