from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from dts_utils import cli_router
from dts_utils import generate as generate_mod
from dts_utils.pipeline.generate_dispatch import generate_uses_pipeline_profile


def _patch_pipeline_profile_lookup(
    monkeypatch: pytest.MonkeyPatch,
    *,
    stems: frozenset[str],
) -> None:
    def _is_pipeline(name: str, config_dir: Path | None = None) -> bool:
        return Path(str(name)).stem in stems

    monkeypatch.setattr("dts_utils.pipeline.generate_dispatch.is_pipeline_profile", _is_pipeline)
    monkeypatch.setattr("dts_utils.cli_router.generate_uses_pipeline_profile", lambda profile: _is_pipeline(profile or ""))
    monkeypatch.setattr("dts_utils.generate.generate_uses_pipeline_profile", lambda profile: _is_pipeline(profile or ""))


def test_generate_uses_pipeline_profile_detects_block(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_pipeline_profile_lookup(monkeypatch, stems=frozenset({"prompt-to-video"}))
    assert generate_uses_pipeline_profile("prompt-to-video")
    assert not generate_uses_pipeline_profile("default")


def test_generate_main_runs_pipeline_when_profile_is_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_pipeline_profile_lookup(monkeypatch, stems=frozenset({"prompt-to-video"}))

    with patch("dts_utils.generate.run_generate_pipeline", return_value=0) as run_pipeline:
        rc = generate_mod.main(
            [
                "--prompt",
                "neon city",
                "--profile",
                "prompt-to-video",
                "--trust-server-cert",
            ]
        )

    assert rc == 0
    run_pipeline.assert_called_once()


def test_generate_shorthand_uses_profile_for_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_pipeline_profile_lookup(monkeypatch, stems=frozenset({"prompt-to-video"}))
    monkeypatch.setattr("sys.argv", ["dts-utils", "neon city", "prompt-to-video"])
    with patch.object(cli_router, "generate_main", return_value=0) as generate_main:
        with pytest.raises(SystemExit):
            cli_router.main()

    generate_main.assert_called_once_with(
        ["--prompt", "neon city", "--profile", "prompt-to-video", "--trust-server-cert", "--open"]
    )
