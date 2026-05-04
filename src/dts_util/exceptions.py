"""Domain errors for programmatic use of dts-util."""

from __future__ import annotations

import grpc


class DTSUtilError(Exception):
    """Base class for recover client/library failures."""


class ConfigurationError(DTSUtilError):
    """Invalid or missing Draw Things generation configuration."""


class PromptWildcardError(ConfigurationError):
    """Prompt ``{…}`` wildcards failed safety limits or could not be resolved."""


class ChannelSetupError(DTSUtilError):
    """gRPC channel or TLS setup failed before RPC."""


class GenerationRpcError(DTSUtilError):
    """gRPC call failed during image generation."""

    def __init__(
        self,
        message: str,
        *,
        code: grpc.StatusCode | None = None,
        details: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = details

    @classmethod
    def from_rpc_error(cls, exc: grpc.RpcError) -> GenerationRpcError:
        code = exc.code()
        details = exc.details() or ""
        return cls(
            f"RPC error: {code} {details}",
            code=code,
            details=details,
        )


class GenerationEmptyError(DTSUtilError):
    """The server completed without returning image tensors."""
