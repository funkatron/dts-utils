"""Top-level ``dts-util`` dispatch: client subcommands vs macOS server lifecycle."""

from __future__ import annotations

import os
import sys

from dts_util.model_index.cli import main as models_main

from dts_util.configs import configurations_dir, main as configs_main
from dts_util.generate import main as generate_main
from dts_util.grpc.reflect import main as reflect_main
from dts_util.installer.server_installer import DTSServerInstaller
from dts_util.tls_export import main as tls_main

SERVER_LIFECYCLE_SUBCOMMANDS = frozenset({"install", "uninstall", "restart", "test", "check"})

# When using ``dts-util "prompt" [profile]`` shorthand (no ``generate`` keyword), pick configuration from:
# optional second positional, then this env var, then ``default.json`` in the saved-config directory.
DEFAULT_CONFIGURATION_ENV = "DTS_UTIL_DEFAULT_CONFIGURATION"
FALLBACK_SAVED_CONFIG_NAME = "default"

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


def _configuration_for_shorthand(profile_from_argv: str | None) -> tuple[str | None, str | None]:
    """Return ``(configuration name or path, error message)`` for generate shorthand."""
    if profile_from_argv:
        return profile_from_argv, None
    env = os.environ.get(DEFAULT_CONFIGURATION_ENV, "").strip()
    if env:
        return env, None
    default_path = configurations_dir() / f"{FALLBACK_SAVED_CONFIG_NAME}.json"
    if default_path.is_file():
        return FALLBACK_SAVED_CONFIG_NAME, None
    return None, (
        "dts-util: generation needs a saved configuration. Either:\n"
        "  • Pass a profile: dts-util \"your prompt\" PROFILE_NAME\n"
        "  • Save default.json in the configs directory (see `dts-util configs path`)\n"
        f"  • Set {DEFAULT_CONFIGURATION_ENV} to a profile name or JSON path"
    )


def _split_shorthand_argv(argv: list[str]) -> tuple[list[str], str | None]:
    """Split ``argv[1:]`` into positional tokens (prompt / profile) and flag tokens.

    Positional parsing stops at the first token that starts with ``-`` (so flags must follow
    any profile name). Return ``(expanded_args_for_generate_main, error_message)``.
    """
    tail = argv[1:]
    positionals: list[str] = []
    flags: list[str] = []
    for tok in tail:
        if tok.startswith("-") and tok != "-":
            flags.append(tok)
        elif flags:
            flags.append(tok)
        else:
            positionals.append(tok)
    if len(positionals) == 0:
        return [], "dts-util: expected a prompt after the command name."
    if len(positionals) > 2:
        return [], (
            "dts-util: too many positional arguments (prompt and optional profile only). "
            'Quote multi-word prompts, e.g. dts-util "a red house" portrait'
        )
    prompt = positionals[0]
    profile = positionals[1] if len(positionals) == 2 else None
    config_value, err = _configuration_for_shorthand(profile)
    if err:
        return [], err
    assert config_value is not None  # set whenever err is None
    expanded = ["--prompt", prompt, "--configuration", config_value, "--trust-server-cert", "--open"]
    expanded.extend(flags)
    return expanded, None


def looks_like_generate_shorthand(argv: list[str]) -> bool:
    """True if ``argv`` should run as ``generate`` without the explicit subcommand."""
    if len(argv) < 2:
        return False
    head = argv[1]
    if head.startswith("-"):
        return False
    if head in _CLIENT_HANDLER_ATTR:
        return False
    if head in SERVER_LIFECYCLE_SUBCOMMANDS:
        return False
    if head == "server":
        return False
    return True


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
    if looks_like_generate_shorthand(argv):
        expanded, err = _split_shorthand_argv(argv)
        if err is not None:
            print(err, file=sys.stderr)
            sys.exit(2)
        sys.exit(generate_main(expanded))
    if len(argv) > 1 and argv[1] in _CLIENT_HANDLER_ATTR:
        handler = getattr(sys.modules[__name__], _CLIENT_HANDLER_ATTR[argv[1]])
        sys.exit(handler(argv[2:]))
    installer = DTSServerInstaller()
    installer.run()
