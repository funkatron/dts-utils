"""Top-level CLI dispatch: client subcommands vs macOS server lifecycle."""

from __future__ import annotations

import os
import sys

from dts_utils.cli_prog import cli_command_name
from dts_utils.model_index.cli import main as models_main

from dts_utils.configs import (
    DEFAULT_CONFIGURATION_ENV,
    DEFAULT_PROFILE_NAME,
    ensure_default_generation_json_config,
    main as configs_main,
)
from dts_utils.generate import main as generate_main
from dts_utils.pipeline.generate_dispatch import generate_uses_pipeline_profile
from dts_utils.grpc.reflect import main as reflect_main
from dts_utils.pipeline.cli import main as pipeline_main
from dts_utils.web.cli import main as web_main
from dts_utils.installer.server_installer import DTSServerInstaller
from dts_utils.tls_export import main as tls_main

SERVER_LIFECYCLE_SUBCOMMANDS = frozenset(
    {"install", "uninstall", "start", "stop", "restart", "test", "check", "status", "tail"}
)

HELP_FLAGS = frozenset({"-h", "--help"})


def top_level_help_text() -> str:
    p = cli_command_name()
    return f"""
Usage:
    {p} "PROMPT" [PROFILE] [generate options]
    {p} generate --prompt PROMPT [options]
    {p} server <install|start|stop|restart|check|status|tail> [...]
    {p} web [serve options]
    {p} web <install|start|stop|restart|status|uninstall|tail> [...]
    {p} configs <path|list|scaffold-from-metadata|scaffold-pipeline|import-draw-things> [...]
    {p} reflect [options]
    {p} tls <path|export> [...]
    {p} models <build|search|show|report|installed|status|fetch|doctor> [...]
    {p} pipeline <run> [...]

Commands:
    prompt shorthand   Generate from a quoted prompt; uses --trust-server-cert --open.
    generate           Send image or pipeline generation requests to gRPCServerCLI.
    server             Manage the Draw Things gRPC server LaunchAgent on port 7859.
    web                Run or manage the local web UI on port 8765.
    configs            Manage saved Draw Things JSON generation profiles.
    reflect            Inspect gRPC reflection metadata.
    tls                Export or print the pinned server TLS certificate path.
    models             Inspect, fetch, and report local Draw Things model metadata.
    pipeline           Run pipeline plans directly.

Help:
    {p} server --help
    {p} web --help
    {p} generate --help
""".strip()


def should_show_top_level_help(argv: list[str]) -> bool:
    return len(argv) < 2 or argv[1] in HELP_FLAGS

def server_subcommand_help_text() -> str:
    p = cli_command_name()
    return f"""
Draw Things gRPC server (macOS LaunchAgent for gRPCServerCLI)

Lifecycle commands require the ``server`` prefix so they stay distinct from client RPC tools:

    {p} server install [...]           Install binary + LaunchAgent
    {p} server uninstall              Remove LaunchAgent service + binary
    {p} server start                  Load plist into launchd (start job)
    {p} server stop                   Boot out job (plist stays on disk)
    {p} server restart [--no-model-browser]
    {p} server test|check [--port PORT]    Probe localhost listener (check = alias for test)
    {p} server status                      Show LaunchAgent flags and model-browser state
    {p} server tail [--last DURATION]      Follow gRPCServerCLI logs (macOS Unified Logging)
""".strip()


# Import names matched by ``prepare_argv_for_installer_dispatch`` / ``main``.
_CLIENT_HANDLER_ATTR: dict[str, str] = {
    "generate": "generate_main",
    "configs": "configs_main",
    "reflect": "reflect_main",
    "tls": "tls_main",
    "models": "models_main",
    "web": "web_main",
    "pipeline": "pipeline_main",
}


def _configuration_for_shorthand(profile_from_argv: str | None) -> tuple[str | None, str | None]:
    """Return ``(configuration name or path, error message)`` for generate shorthand."""
    if profile_from_argv:
        return profile_from_argv, None
    env = os.environ.get(DEFAULT_CONFIGURATION_ENV, "").strip()
    if env:
        return env, None
    ensure_default_generation_json_config()
    return DEFAULT_PROFILE_NAME, None


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
    prog = cli_command_name(argv)
    if len(positionals) == 0:
        return [], f"{prog}: expected a prompt after the command name."
    if len(positionals) > 2:
        return [], (
            f"{prog}: too many positional arguments (prompt and optional profile only). "
            f'Quote multi-word prompts, e.g. {prog} "a red house" portrait'
        )
    prompt = positionals[0]
    profile = positionals[1] if len(positionals) == 2 else None
    config_value, err = _configuration_for_shorthand(profile)
    if err:
        return [], err
    assert config_value is not None  # set whenever err is None
    if profile and generate_uses_pipeline_profile(profile):
        expanded = ["--prompt", prompt, "--profile", profile, "--trust-server-cert", "--open"]
    else:
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
    """Strip ``<prog> server <cmd>`` to ``<prog> <cmd>``, or refuse bare lifecycle verbs.

    Return an exit status when argv should stop early (help text, misuse). Otherwise return
    ``None`` and mutate ``argv`` in place when ``server …`` was used.
    """
    if len(argv) < 2:
        return None
    prog = cli_command_name(argv)
    if argv[1] == "server":
        if len(argv) == 2 or argv[2] in HELP_FLAGS:
            print(server_subcommand_help_text())
            return 0
        sub = argv[2]
        if sub not in SERVER_LIFECYCLE_SUBCOMMANDS:
            subs = ", ".join(sorted(SERVER_LIFECYCLE_SUBCOMMANDS))
            print(f"{prog}: unknown server subcommand {sub!r}. Expected: {subs}.", file=sys.stderr)
            return 2
        argv[:] = [argv[0], argv[2], *argv[3:]]
        return None
    if argv[1] in SERVER_LIFECYCLE_SUBCOMMANDS:
        print(
            f"{prog}: LaunchAgent lifecycle commands must use `server`, e.g.\n"
            f"    uv run {prog} server {argv[1]} [...]",
            file=sys.stderr,
        )
        return 2
    return None


def main() -> None:
    """Entry point for the ``dts-utils`` console script."""
    argv = sys.argv
    if should_show_top_level_help(argv):
        print(top_level_help_text())
        sys.exit(0)
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
