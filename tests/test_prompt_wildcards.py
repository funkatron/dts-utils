"""Tests for prompt `{…}` wildcard expansion."""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from dts_utils.exceptions import ConfigurationError, PromptWildcardError
from dts_utils.generate_api import ImageGenerationRequestOptions, build_image_generation_request
from dts_utils.prompt_wildcards import expand_prompt_wildcards


class PickFirst:
    def choice(self, seq: list[str]) -> str:
        return seq[0]


class PickLast:
    def choice(self, seq: list[str]) -> str:
        return seq[-1]


class SeqPick:
    """Deterministic multi-step expansion: each ``choice`` consumes the next planned token."""

    def __init__(self, planned: list[str]) -> None:
        self._planned = list(planned)
        self._i = 0

    def choice(self, seq: list[str]) -> str:
        want = self._planned[self._i]
        self._i += 1
        assert want in seq, f"{want!r} not in {seq!r}"
        return want


def test_expand_empty_string() -> None:
    assert expand_prompt_wildcards("") == ""


def test_expand_plain_unchanged() -> None:
    assert expand_prompt_wildcards("hello world") == "hello world"


def test_expand_normalizes_fullwidth_braces_and_pipe() -> None:
    """NFKC maps U+FF5B/FF5D/FF5C to ASCII `{`, `}`, `|` so pasted “smart” punctuation works."""
    assert expand_prompt_wildcards("｛a｜b｝", rng=PickFirst()) == "a"
    assert expand_prompt_wildcards("｛天｜地｝", rng=PickFirst()) == "天"


def test_expand_no_braces_even_if_special_chars() -> None:
    assert expand_prompt_wildcards("a | b, c") == "a | b, c"


def test_expand_pipe_single_pass() -> None:
    assert expand_prompt_wildcards("{a|b}", rng=PickFirst()) == "a"
    assert expand_prompt_wildcards("{a|b}", rng=PickLast()) == "b"


def test_expand_comma_when_no_pipe() -> None:
    assert expand_prompt_wildcards("{a, b}", rng=PickFirst()) == "a"
    assert expand_prompt_wildcards("{a, b, c}", rng=PickLast()) == "c"


def test_pipe_delimiter_wins_over_commas_in_segment() -> None:
    assert expand_prompt_wildcards("{a,b|c}", rng=PickFirst()) == "a,b"


def test_single_alternative_brace_forms() -> None:
    assert expand_prompt_wildcards("{only}", rng=PickFirst()) == "only"
    assert expand_prompt_wildcards("{ solo }", rng=PickLast()) == "solo"


def test_nested_expand_second_pass() -> None:
    assert expand_prompt_wildcards("{{a|b}|c}", rng=PickFirst()) == "a"
    assert expand_prompt_wildcards("{{a|b}|c}", rng=PickLast()) == "c"


def test_triple_nesting_pick_first() -> None:
    assert expand_prompt_wildcards("{{{a|b}|c}|d}", rng=PickFirst()) == "a"


def test_nested_brace_alternative_expands_in_second_pass() -> None:
    rng = SeqPick(["{b|c}", "b"])
    assert expand_prompt_wildcards("{a|{b|c}}", rng=rng) == "b"


def test_comma_split_respects_nested_braces() -> None:
    assert expand_prompt_wildcards("{a,{b,c}}", rng=PickFirst()) == "a"
    assert expand_prompt_wildcards("{a,{b,c}}", rng=PickLast()) == "c"


def test_comma_literal_inside_pipe_segment() -> None:
    assert expand_prompt_wildcards("{red, bold | blue}", rng=PickFirst()) == "red, bold"


def test_unicode_alternatives() -> None:
    assert expand_prompt_wildcards("{猫|犬}", rng=PickFirst()) == "猫"


def test_newline_inside_alternatives() -> None:
    assert expand_prompt_wildcards("{hello\n|world}", rng=PickFirst()) == "hello\n"


def test_double_comma_filters_empty_segments() -> None:
    assert expand_prompt_wildcards("{a,,b}", rng=PickFirst()) == "a"
    assert expand_prompt_wildcards("{a,,b}", rng=PickLast()) == "b"


def test_whitespace_only_alternative_dropped() -> None:
    assert expand_prompt_wildcards("{ |foo}", rng=PickFirst()) == "foo"


def test_empty_alternatives_raises() -> None:
    with pytest.raises(PromptWildcardError, match="Unresolved"):
        expand_prompt_wildcards("{||}", rng=PickFirst())


def test_whitespace_only_block_raises() -> None:
    with pytest.raises(PromptWildcardError, match="Unresolved"):
        expand_prompt_wildcards("{   }", rng=PickFirst())


def test_empty_brace_pair_raises() -> None:
    with pytest.raises(PromptWildcardError, match="Unresolved"):
        expand_prompt_wildcards("{}", rng=PickFirst())


def test_pipe_with_only_empty_segments_raises() -> None:
    with pytest.raises(PromptWildcardError, match="Unresolved"):
        expand_prompt_wildcards("{|}", rng=PickFirst())


def test_unclosed_open_brace_raises() -> None:
    with pytest.raises(PromptWildcardError, match="Unresolved"):
        expand_prompt_wildcards("{a|b", rng=PickFirst())


def test_literal_then_unclosed_trailing_brace_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("dts_utils.prompt_wildcards.DEFAULT_MAX_PASSES", 8)
    with pytest.raises(PromptWildcardError, match="Unresolved"):
        expand_prompt_wildcards("xx{a|b}{yy", rng=PickFirst())


def test_closing_brace_without_open_is_literal() -> None:
    assert expand_prompt_wildcards("ok}") == "ok}"


def test_prompt_wildcard_error_is_configuration_error() -> None:
    assert issubclass(PromptWildcardError, ConfigurationError)


def test_max_passes_exceeded_when_still_has_braces() -> None:
    with pytest.raises(PromptWildcardError, match="maximum passes"):
        expand_prompt_wildcards("{{a|b}|c}", rng=PickFirst(), max_passes=1)


def test_default_max_passes_uses_live_module_constant(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("dts_utils.prompt_wildcards.DEFAULT_MAX_PASSES", 1)
    with pytest.raises(PromptWildcardError, match="maximum passes"):
        expand_prompt_wildcards("{{a|b}|c}", rng=PickFirst())


def test_max_passes_one_succeeds_when_single_pass_enough() -> None:
    assert expand_prompt_wildcards("{x|y}", rng=PickFirst(), max_passes=1) == "x"


def test_max_chars_exceeded_before_any_expand() -> None:
    with pytest.raises(PromptWildcardError, match="maximum length"):
        expand_prompt_wildcards("{abcdefghij|x}", rng=PickFirst(), max_chars=5)


def test_max_chars_exceeded_after_expand(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("dts_utils.prompt_wildcards.DEFAULT_MAX_PASSES", 8)
    with pytest.raises(PromptWildcardError, match="maximum length"):
        expand_prompt_wildcards("{|bbbbbbbb}", rng=PickFirst(), max_chars=5)


def test_seeded_random_is_deterministic() -> None:
    rng = random.Random(42)
    out = expand_prompt_wildcards("{a|b|c|d|e}", rng=rng)
    rng2 = random.Random(42)
    assert expand_prompt_wildcards("{a|b|c|d|e}", rng=rng2) == out


def test_negative_prompt_empty_skipped_in_build(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cfg = tmp_path / "c.fb"
    cfg.write_bytes(b"fb")
    monkeypatch.setattr("dts_utils.generate_api.read_configuration_bytes", lambda **k: b"x")

    req = build_image_generation_request(
        ImageGenerationRequestOptions(prompt="{z|y}", negative_prompt="   ", configuration=cfg),
    )
    assert req.prompt in {"z", "y"}
    assert req.negativePrompt == ""


def test_build_expands_negative_prompt_wildcards(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cfg = tmp_path / "c.fb"
    cfg.write_bytes(b"fb")
    monkeypatch.setattr("dts_utils.generate_api.read_configuration_bytes", lambda **k: b"x")

    req = build_image_generation_request(
        ImageGenerationRequestOptions(
            prompt="ok",
            negative_prompt="{blur|noise}",
            configuration=cfg,
        ),
    )
    assert req.prompt == "ok"
    assert req.negativePrompt in {"blur", "noise"}
