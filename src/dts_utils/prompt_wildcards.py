"""Brace wildcards in prompts: pick one random alternative per `{ … }` block."""

from __future__ import annotations

import random
import unicodedata

from dts_utils.exceptions import PromptWildcardError

# Tunables (tests may monkeypatch).
DEFAULT_MAX_PASSES = 128
DEFAULT_MAX_EXPANDED_CHARS = 100_000


def _split_at_depth_zero(text: str, delimiter: str) -> list[str]:
    """Split on *delimiter* only where brace nesting depth is 0."""
    parts: list[str] = []
    start = 0
    depth = 0
    for idx, c in enumerate(text):
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        elif c == delimiter and depth == 0:
            parts.append(text[start:idx])
            start = idx + 1
    parts.append(text[start:])
    return parts


def _trim_alt_edges(s: str) -> str:
    """Trim spaces/tabs only so intentional newlines inside an alternative stay."""
    return s.strip(" \t")


def _split_alternatives(inner: str) -> list[str]:
    """Split one `{ … }` body into choices.

    If the body contains ``|`` anywhere, alternatives are separated by ``|`` at brace depth 0
    (pipes inside nested ``{…}`` do not split). Otherwise alternatives are separated by commas
    at depth 0 only (commas inside nested braces stay literal).
    """
    text = inner.strip()
    delim = "|" if "|" in text else ","
    raw = _split_at_depth_zero(text, delim)
    out = [_trim_alt_edges(p) for p in raw]
    return [p for p in out if p]


def _expand_one_block(inner: str, rng: random.Random) -> str:
    options = _split_alternatives(inner)
    if not options:
        return "{" + inner + "}"
    return rng.choice(options)


def _expand_one_pass(prompt: str, rng: random.Random) -> str:
    """Expand every top-level `{ … }` region once (balanced braces)."""
    if "{" not in prompt:
        return prompt
    out: list[str] = []
    i = 0
    n = len(prompt)
    while i < n:
        j = prompt.find("{", i)
        if j == -1:
            out.append(prompt[i:])
            break
        out.append(prompt[i:j])
        depth = 1
        k = j + 1
        while k < n and depth:
            c = prompt[k]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
            k += 1
        if depth != 0:
            out.append(prompt[j:])
            break
        inner = prompt[j + 1 : k - 1]
        out.append(_expand_one_block(inner, rng))
        i = k
    return "".join(out)


def expand_prompt_wildcards(
    prompt: str,
    rng: random.Random | None = None,
    *,
    max_passes: int | None = None,
    max_chars: int | None = None,
) -> str:
    """Expand `{ … }` wildcards, including choices that embed further `{ … }`.

    Rules per block:

    - ``{ yes | no }`` — choices separated by ``|`` at brace depth 0 (pipes nested inside ``{…}`` do not split).
    - ``{ yes, no }`` — comma-separated at depth 0 when there is no ``|`` anywhere in the block.
    - If a block contains ``|``, only depth-0 ``|`` splits (commas inside nested ``{…}`` stay literal).

    Expansion repeats until no ``{`` remains or a pass makes no progress. Limits:

    - ``max_passes``: stop after this many full passes (deep nesting); default from ``DEFAULT_MAX_PASSES``.
    - ``max_chars``: refuse longer expanded strings (runaway templates); default from ``DEFAULT_MAX_EXPANDED_CHARS``.

    Prompt text is normalized with Unicode NFKC first so full-width ``｛｝｜`` from pasted sources are treated like ASCII ``{}|``.

    Raises:
        PromptWildcardError: Unclosed braces, empty alternatives, no progress with ``{`` left,
            or limits exceeded.
    """
    lim_passes = DEFAULT_MAX_PASSES if max_passes is None else max_passes
    lim_chars = DEFAULT_MAX_EXPANDED_CHARS if max_chars is None else max_chars
    if not prompt:
        return prompt
    prompt = unicodedata.normalize("NFKC", prompt)
    if "{" not in prompt:
        return prompt
    r = rng if rng is not None else random.Random()
    current = prompt
    for _ in range(lim_passes):
        if len(current) > lim_chars:
            raise PromptWildcardError(
                f"Expanded prompt exceeds maximum length ({lim_chars} characters)."
            )
        if "{" not in current:
            return current
        nxt = _expand_one_pass(current, r)
        if nxt == current:
            raise PromptWildcardError(
                "Unresolved {...} wildcards (empty alternatives, invalid braces, or unsupported syntax)."
            )
        current = nxt
    if len(current) > lim_chars:
        raise PromptWildcardError(
            f"Expanded prompt exceeds maximum length ({lim_chars} characters)."
        )
    if "{" not in current:
        return current
    raise PromptWildcardError(
        f"Wildcard expansion exceeded maximum passes ({lim_passes}); simplify nesting."
    )
