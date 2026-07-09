"""Collect API surface inventory and parse user-doc mentions (for drift tests / docgen)."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from pathlib import Path

from dts_utils.mcp.server import create_mcp_server
from dts_utils.mcp.tools import LIFECYCLE_TOOL_NAMES, MCP_TOOL_NAMES
from dts_utils.web.app import create_app

_REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_API_DOC = _REPO_ROOT / "docs" / "web-api.md"
MCP_AGENTS_DOC = _REPO_ROOT / "docs" / "mcp-for-agents.md"
CLI_DOC = _REPO_ROOT / "CLI.md"
GENERATED_MCP_TOOLS = _REPO_ROOT / "docs" / "generated" / "mcp-tools.md"

_ROUTE_PARAM_RE = re.compile(r"\{(\w+):\w+\}")


def normalize_route_path(path: str) -> str:
    """``/api/foo/{run_id:str}`` → ``/api/foo/{run_id}`` for doc comparison."""
    return _ROUTE_PARAM_RE.sub(r"{\1}", path)


@dataclass(frozen=True, slots=True)
class WebRoute:
    methods: frozenset[str]
    path: str

    @property
    def normalized_path(self) -> str:
        return normalize_route_path(self.path)


def web_routes_from_app() -> list[WebRoute]:
    app = create_app()
    out: list[WebRoute] = []
    for route in app.routes:
        methods = getattr(route, "methods", None)
        path = getattr(route, "path", None)
        if not methods or not path:
            continue
        out.append(WebRoute(methods=frozenset(methods), path=path))
    return sorted(out, key=lambda r: (r.normalized_path, sorted(r.methods)))


def web_routes_documented_in(markdown: str) -> set[tuple[str, str]]:
    """Return ``(METHOD, path)`` pairs mentioned in ``web-api.md``."""
    documented: set[tuple[str, str]] = set()
    for match in re.finditer(r"^### `(GET|POST|DELETE|PUT|PATCH) ([^`]+)`", markdown, re.MULTILINE):
        documented.add((match.group(1), normalize_route_path(match.group(2))))
    for match in re.finditer(
        r"\|\s*\*\*(GET|POST|DELETE|PUT|PATCH)\*\*\s*\|\s*\*\*`([^`]+)`\*\*",
        markdown,
    ):
        documented.add((match.group(1), normalize_route_path(match.group(2))))
    example = re.search(
        r"\*\*Example:\*\* `/api/pipeline/artifact/[^`]+`",
        markdown,
    )
    if example:
        documented.add(
            (
                "GET",
                normalize_route_path("/api/pipeline/artifact/{run_id}/{step_id}/{filename}"),
            )
        )
    return documented


def web_routes_missing_from_doc(
    *,
    doc_path: Path = WEB_API_DOC,
) -> list[tuple[WebRoute, set[str]]]:
    """For each app route, methods not documented in ``web-api.md``."""
    text = doc_path.read_text(encoding="utf-8")
    documented = web_routes_documented_in(text)
    missing: list[tuple[WebRoute, set[str]]] = []
    for route in web_routes_from_app():
        if route.normalized_path == "/":
            continue
        check_methods = {m for m in route.methods if m not in {"HEAD", "OPTIONS"}}
        undocumented = {m for m in check_methods if (m, route.normalized_path) not in documented}
        if undocumented:
            missing.append((route, undocumented))
    return missing


def mcp_tool_names_in_markdown(markdown: str) -> set[str]:
    return set(re.findall(r"`(dts_[a-z0-9_]+)`", markdown))


def mcp_tools_missing_from_agents_doc(
    *,
    doc_path: Path = MCP_AGENTS_DOC,
    include_lifecycle: bool = True,
) -> set[str]:
    text = doc_path.read_text(encoding="utf-8")
    mentioned = mcp_tool_names_in_markdown(text)
    expected = set(MCP_TOOL_NAMES)
    if include_lifecycle:
        expected |= LIFECYCLE_TOOL_NAMES
    return expected - mentioned


CLI_COMMAND_HEADINGS = (
    "generate",
    "server",
    "configs",
    "models",
    "pipeline",
    "web",
    "reflect",
    "tls",
    "mcp",
)


def cli_sections_missing_from_cli_md(*, doc_path: Path = CLI_DOC) -> list[str]:
    text = doc_path.read_text(encoding="utf-8")
    missing: list[str] = []
    for cmd in CLI_COMMAND_HEADINGS:
        if cmd == "mcp":
            if not re.search(r"^### MCP\b", text, re.MULTILINE | re.IGNORECASE):
                missing.append(cmd)
        elif not re.search(rf"^### {re.escape(cmd)}\b", text, re.MULTILINE | re.IGNORECASE):
            missing.append(cmd)
    return missing


async def mcp_tools_for_docgen() -> list:
    server = create_mcp_server()
    tools = await server.list_tools()
    return sorted(tools, key=lambda t: t.name)


def _schema_properties(schema: object) -> dict[str, object]:
    if not isinstance(schema, dict):
        return {}
    props = schema.get("properties")
    return props if isinstance(props, dict) else {}


def render_mcp_tools_markdown(tools: list) -> str:
    lines = [
        "# MCP tools reference (generated)",
        "",
        "Do not edit by hand. Regenerate:",
        "",
        "```bash",
        "uv run python scripts/generate_docs.py",
        "```",
        "",
        "Narrative guide: [mcp-for-agents.md](../mcp-for-agents.md). Operator setup: [CLI.md § MCP](../CLI.md#mcp-dts-utils-mcp).",
        "",
    ]
    for tool in tools:
        lines.append(f"## `{tool.name}`")
        lines.append("")
        desc = (tool.description or "").strip()
        if desc:
            lines.append(desc)
            lines.append("")
        schema = tool.inputSchema if isinstance(tool.inputSchema, dict) else {}
        required = schema.get("required")
        req_set = set(required) if isinstance(required, list) else set()
        props = _schema_properties(schema)
        if props:
            lines.append("| Parameter | Type | Required | Description |")
            lines.append("| --- | --- | --- | --- |")
            for name, spec in sorted(props.items()):
                if not isinstance(spec, dict):
                    continue
                typ = spec.get("type", "")
                if "anyOf" in spec:
                    typ = " / ".join(
                        str(x.get("type", "object")) for x in spec["anyOf"] if isinstance(x, dict)
                    )
                desc_cell = str(spec.get("description", "")).replace("|", "\\|").replace("\n", " ")
                req = "yes" if name in req_set else "no"
                default = spec.get("default")
                if default is not None and req == "no":
                    desc_cell = f"{desc_cell} (default: `{default}`)".strip()
                lines.append(f"| `{name}` | {typ} | {req} | {desc_cell} |")
            lines.append("")
        else:
            lines.append("_No parameters._")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


async def write_mcp_tools_doc(*, output: Path = GENERATED_MCP_TOOLS) -> Path:
    tools = await mcp_tools_for_docgen()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_mcp_tools_markdown(tools), encoding="utf-8")
    return output


def write_mcp_tools_doc_sync(*, output: Path = GENERATED_MCP_TOOLS) -> Path:
    return asyncio.run(write_mcp_tools_doc(output=output))
