from __future__ import annotations

import json
from pathlib import Path

import pytest

from dts_utils.exceptions import ConfigurationError
from dts_utils.pipeline.profile import (
    PIPELINE_METADATA_KEY,
    list_pipeline_profile_names,
    load_pipeline_profile,
    merge_profile_into_run_args,
    parse_pipeline_settings,
    uses_drawthings_t2i,
)


def test_parse_pipeline_profile_fixture() -> None:
    raw = json.loads(
        (Path(__file__).parent / "fixtures/pipeline_profiles/prompt-to-video.json").read_text(encoding="utf-8")
    )
    settings = parse_pipeline_settings(
        profile_stem="prompt-to-video",
        profile_path=Path("prompt-to-video.json"),
        raw=raw,
    )
    assert settings is not None
    assert settings.t2i_configuration == "default"
    assert settings.video_configuration == "LTX-2.3-22B-Port"
    assert settings.grpc.trust_server_cert is True
    assert settings.fps == 25


def test_list_pipeline_profile_names_scans_config_dir(tmp_path: Path) -> None:
    config_dir = tmp_path / "configurations"
    config_dir.mkdir()
    (config_dir / "plain.json").write_text('{"model": "x.ckpt"}', encoding="utf-8")
    (config_dir / "prompt-to-video.json").write_text(
        json.dumps({"_dts_utils_pipeline": {"video_configuration": "ltx"}}),
        encoding="utf-8",
    )
    assert list_pipeline_profile_names(config_dir=config_dir) == ["prompt-to-video"]


def test_merge_profile_into_run_args(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from argparse import Namespace

    config_dir = tmp_path / "configurations"
    config_dir.mkdir()
    profile_path = config_dir / "prompt-to-video.json"
    profile_path.write_text(
        (Path(__file__).parent / "fixtures/pipeline_profiles/prompt-to-video.json").read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "dts_utils.pipeline.profile.resolve_configuration_value",
        lambda value, config_dir=None: profile_path,
    )

    args = Namespace(
        profile="prompt-to-video",
        configuration=None,
        configuration_json=None,
        video_configuration=None,
        video_configuration_json=None,
        i2v_backend=None,
        preset=None,
        fps=None,
        video_width=None,
        video_height=None,
        seconds=None,
        width=None,
        height=None,
        seed=None,
        negative_prompt=None,
        video_negative_prompt=None,
        video_prompt=None,
        run_root=None,
        host=None,
        port=None,
        no_tls=None,
        trust_server_cert=None,
        force_trust_server_cert=None,
        max_message_mb=None,
        user=None,
        shared_secret=None,
        root_cert=None,
    )
    settings = merge_profile_into_run_args(args, config_dir=config_dir)
    assert settings.profile_stem == "prompt-to-video"
    assert args.configuration == "default"
    assert args.video_configuration == "LTX-2.3-22B-Port"
    assert args.trust_server_cert is True
    assert args.fps == 25


def test_load_pipeline_profile_requires_block(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    profile_path = tmp_path / "empty.json"
    profile_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        "dts_utils.pipeline.profile.resolve_configuration_value",
        lambda value, config_dir=None: profile_path,
    )
    with pytest.raises(ConfigurationError, match=PIPELINE_METADATA_KEY):
        load_pipeline_profile("empty", config_dir=tmp_path)


def test_uses_drawthings_t2i_respects_profile_mode() -> None:
    from dts_utils.pipeline.profile import PipelineProfileSettings

    profile = PipelineProfileSettings(
        profile_stem="p",
        profile_path=Path("p.json"),
        t2i_mode="drawthings",
    )
    assert uses_drawthings_t2i(
        has_prompt=True,
        configuration=None,
        configuration_json=None,
        profile=profile,
    )
    profile_preset = PipelineProfileSettings(
        profile_stem="p",
        profile_path=Path("p.json"),
        t2i_mode="preset",
    )
    assert not uses_drawthings_t2i(
        has_prompt=True,
        configuration="default",
        configuration_json=None,
        profile=profile_preset,
    )
