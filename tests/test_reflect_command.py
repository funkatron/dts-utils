"""Tests for the dts-util reflect command."""

from __future__ import annotations

import json
from unittest.mock import patch

import grpc
import pytest
from google.protobuf import descriptor_pb2
from grpc_reflection.v1alpha import reflection_pb2

from dts_util.grpc import reflect
from dts_util.installer import server_installer


class FakeChannel:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class ReadyFuture:
    def result(self, timeout=None):
        return None


class FakeRpcError(grpc.RpcError):
    def code(self):
        return grpc.StatusCode.UNIMPLEMENTED

    def details(self):
        return "reflection not enabled"


def service_list_response(*service_names: str):
    return reflection_pb2.ServerReflectionResponse(
        list_services_response=reflection_pb2.ListServiceResponse(
            service=[reflection_pb2.ServiceResponse(name=name) for name in service_names]
        )
    )


def service_descriptor_response(service_name: str, *method_names: str):
    descriptor = descriptor_pb2.FileDescriptorProto()
    service = descriptor.service.add()
    service.name = service_name
    for method_name in method_names:
        service.method.add().name = method_name

    return reflection_pb2.ServerReflectionResponse(
        file_descriptor_response=reflection_pb2.FileDescriptorResponse(
            file_descriptor_proto=[descriptor.SerializeToString()]
        )
    )


def test_reflect_command_prints_json(monkeypatch, capsys):
    """Verify reflection output can be consumed by scripts and agents."""
    channel = FakeChannel()

    class FakeReflectionStub:
        def __init__(self, created_channel):
            assert created_channel is channel

        def ServerReflectionInfo(self, requests):
            request = next(requests)
            if request.HasField("list_services"):
                return iter([service_list_response("ImageGenerationService")])
            return iter([service_descriptor_response("ImageGenerationService", "Echo", "GenerateImage")])

    monkeypatch.setattr(reflect, "create_channel", lambda *args, **kwargs: channel)
    monkeypatch.setattr(reflect.grpc, "channel_ready_future", lambda created_channel: ReadyFuture())
    monkeypatch.setattr(reflect.reflection_pb2_grpc, "ServerReflectionStub", FakeReflectionStub)

    result = reflect.main(["--json", "--trust-server-cert"])

    captured = capsys.readouterr()
    assert result == 0
    assert channel.closed is True
    assert json.loads(captured.out) == {
        "target": "localhost:7859",
        "services": [{"name": "ImageGenerationService", "methods": ["Echo", "GenerateImage"]}],
    }


def test_reflect_command_reports_reflection_errors(monkeypatch, capsys):
    """Verify servers without reflection return an actionable failure."""
    channel = FakeChannel()

    class FakeReflectionStub:
        def __init__(self, created_channel):
            assert created_channel is channel

        def ServerReflectionInfo(self, requests):
            raise FakeRpcError()

    monkeypatch.setattr(reflect, "create_channel", lambda *args, **kwargs: channel)
    monkeypatch.setattr(reflect.grpc, "channel_ready_future", lambda created_channel: ReadyFuture())
    monkeypatch.setattr(reflect.reflection_pb2_grpc, "ServerReflectionStub", FakeReflectionStub)

    result = reflect.main([])

    captured = capsys.readouterr()
    assert result == 1
    assert "Reflection error: StatusCode.UNIMPLEMENTED reflection not enabled" in captured.err
    assert channel.closed is True


def test_reflect_command_reports_connection_setup_errors(monkeypatch, capsys):
    """Verify certificate and channel setup failures fail before reflection calls."""
    monkeypatch.setattr(reflect, "create_channel", lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("bad cert")))

    result = reflect.main(["--host", "example.com", "--trust-server-cert"])

    captured = capsys.readouterr()
    assert result == 1
    assert "Connection setup error: bad cert" in captured.err


def test_dts_util_main_dispatches_reflect(monkeypatch):
    """Verify dts-util reflect is routed before installer argument parsing."""
    monkeypatch.setattr("sys.argv", ["dts-util", "reflect", "--json"])
    with patch.object(server_installer, "reflect_main", return_value=0) as reflect_main:
        with pytest.raises(SystemExit) as exc_info:
            server_installer.main()

    reflect_main.assert_called_once_with(["--json"])
    assert exc_info.value.code == 0
