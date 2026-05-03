"""Top-level ``dts-util`` dispatch: client subcommands vs macOS server lifecycle."""

from __future__ import annotations

import sys

from dts_util.model_index.cli import main as models_main

from dts_util.configs import main as configs_main
from dts_util.generate import main as generate_main
from dts_util.grpc.reflect import main as reflect_main
from dts_util.installer.server_installer import DTSServerInstaller
from dts_util.tls_export import main as tls_main

SERVER_LIFECYCLE_SUBCOMMANDS = frozenset({"install", "uninstall", "restart", "test", "check"})

SERVER_SUBCOMMAND_HELP = """
Draw Things gRPC server (macOS LaunchAgent for gRPCServerCLI)

Lifecycle commands require the ``server`` prefix so they stay distinct from client RPC tools:

    dts-util server install [...]           Install binary + LaunchAgent
    dts-util server uninstall              Remove LaunchAgent service + binary
    dts-util server restart [--model-browser]
    dts-util server test|check [--port PORT]    Probe localhost listener (check = alias for test)
""".strip()


# Import names matched by ``prepare_argv_for_installer_dispatch`` / ``main``.
_CLIENT_HANDLER_ATTR: dict[str, str] = {
    "generate": "generate_main",
    "configs": "configs_main",
    "reflect": "reflect_main",
    "tls": "tls_main",
    "models": "models_main",
}


def prepare_argv_for_installer_dispatch(argv: list[str]) -> int | None:
    """Strip ``dts-util server <cmd>`` to ``dts-util <cmd>``, or refuse bare lifecycle verbs.

    Return an exit status when argv should stop early (help text, misuse). Otherwise return
    ``None`` and mutate ``argv`` in place when ``server …`` was used.
    """
    if len(argv) < 2:
        return None
    if argv[1] == "server":
        if len(argv) == 2:
            print(SERVER_SUBCOMMAND_HELP)
            return 0
        sub = argv[2]
        if sub not in SERVER_LIFECYCLE_SUBCOMMANDS:
            subs = ", ".join(sorted(SERVER_LIFECYCLE_SUBCOMMANDS))
            print(f"dts-util: unknown server subcommand {sub!r}. Expected: {subs}.", file=sys.stderr)
            return 2
        argv[:] = [argv[0], argv[2], *argv[3:]]
        return None
    if argv[1] in SERVER_LIFECYCLE_SUBCOMMANDS:
        print(
            "dts-util: LaunchAgent lifecycle commands must use `server`, e.g.\n"
            f"    uv run dts-util server {argv[1]} [...]",
            file=sys.stderr,
        )
        return 2
    return None


def main() -> None:
    """Entry point for the ``dts-util`` console script."""
    argv = sys.argv
    code = prepare_argv_for_installer_dispatch(argv)
    if code is not None:
        sys.exit(code)
    if len(argv) > 1 and argv[1] in _CLIENT_HANDLER_ATTR:
        handler = getattr(sys.modules[__name__], _CLIENT_HANDLER_ATTR[argv[1]])
        sys.exit(handler(argv[2:]))
    installer = DTSServerInstaller()
    installer.run()
