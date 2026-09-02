"""Streamlit configuration workspace interaction contracts."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from streamlit.testing.v1 import AppTest

from aria_nbv.utils import BaseConfig


class _PanelConfig(BaseConfig):
    count: int = Field(default=2, ge=1, le=5)
    """Bounded count shown by the schema-derived widget."""

    mode: Literal["fast", "safe"] = "safe"
    """Closed choice rendered as a select box from Pydantic schema metadata."""


def _configuration_app(catalog, configs_dir) -> None:
    from aria_nbv.app.panels.configuration import render_configuration_workspace

    render_configuration_workspace(catalog, configs_dir=configs_dir)


def test_configuration_page_inspects_without_runtime_construction(tmp_path: Path) -> None:
    (tmp_path / "test.toml").write_text("count = 2\n", encoding="utf-8")

    app = AppTest.from_function(
        _configuration_app,
        args=({"Test config": _PanelConfig}, tmp_path),
    ).run()

    assert not app.exception
    assert app.header[0].value == "Configuration Workspace"
    assert app.number_input[0].label == "count"
    assert app.number_input[0].min == 1
    assert app.number_input[0].max == 5


def test_trusted_file_patterns_are_closed_over_the_catalog() -> None:
    from aria_nbv.app.panels.configuration import trusted_config_catalog, trusted_config_patterns

    patterns = trusted_config_patterns()

    assert patterns.keys() == trusted_config_catalog().keys()
    assert "build_rollouts_v1_cuda_campaign_writer.toml" not in patterns["Rollout writer"]
    assert "build_rollouts_v2_cuda_campaign_writer.toml" in patterns["Rollout writer"]
    assert "build_rollouts_v2_realistic.toml" in patterns["Rollout writer"]
    assert "build_rollouts_v3_target_shell_experiment.toml" in patterns["Rollout writer"]
    assert patterns["Rerun inspector"] == ("rerun_offline.toml",)


def test_typed_config_fields_use_pydantic_choices_and_bounds() -> None:
    from aria_nbv.configs import describe_config_model

    descriptors = describe_config_model(_PanelConfig)
    assert next(item for item in descriptors if item.path == "count").minimum == 1
    assert next(item for item in descriptors if item.path == "count").maximum == 5
    assert next(item for item in descriptors if item.path == "mode").choices == ("fast", "safe")


def test_toml_variant_selector_returns_validated_path_and_model(tmp_path: Path) -> None:
    from aria_nbv.app.panels.configuration import select_toml_config

    path = tmp_path / "safe.toml"
    path.write_text("count = 3\nmode = 'fast'\n", encoding="utf-8")

    class _Ui:
        def selectbox(self, _label, options, **_kwargs):
            return options[0]

        def info(self, *_args, **_kwargs):
            pass

        def error(self, *_args, **_kwargs):
            raise AssertionError("valid fixture was rejected")

    selected = select_toml_config(
        _PanelConfig,
        [path],
        ui=_Ui(),
        label="Config",
        key_prefix="test",
    )

    assert selected is not None
    assert selected.path == path.resolve()
    assert selected.config.count == 3
    assert selected.config.mode == "fast"


def test_toml_variant_selector_preserves_reviewed_order(tmp_path: Path) -> None:
    from aria_nbv.app.panels.configuration import select_toml_config

    first = tmp_path / "reviewed-default.toml"
    second = tmp_path / "older-pilot.toml"
    first.write_text("count = 2\nmode = 'safe'\n", encoding="utf-8")
    second.write_text("count = 3\nmode = 'fast'\n", encoding="utf-8")

    class _Ui:
        def selectbox(self, _label, options, **_kwargs):
            assert options == (first.resolve(), second.resolve())
            return options[0]

        def info(self, *_args, **_kwargs):
            pass

        def error(self, *_args, **_kwargs):
            raise AssertionError("valid fixture was rejected")

    selected = select_toml_config(
        _PanelConfig,
        [first, second],
        ui=_Ui(),
        label="Config",
        key_prefix="ordered",
    )

    assert selected is not None
    assert selected.path == first.resolve()


def test_candidate_interactive_bounds_are_domain_owned() -> None:
    from aria_nbv.pose_generation import candidate_config_ui_bounds

    bounds = candidate_config_ui_bounds()

    assert bounds["num_samples"] == (2, 512)
    assert bounds["max_step_distance_m"] == (1e-9, None)


def _candidate_config_app() -> None:
    from aria_nbv.app.panels.configuration import render_typed_config_fields
    from aria_nbv.pose_generation import CandidateViewGeneratorConfig, candidate_config_ui_bounds

    render_typed_config_fields(
        CandidateViewGeneratorConfig(),
        key_prefix="candidate",
        bounds=candidate_config_ui_bounds(),
    )


def test_candidate_config_app_exposes_safe_num_samples_boundary() -> None:
    app = AppTest.from_function(_candidate_config_app).run()

    assert not app.exception
    num_samples = next(widget for widget in app.number_input if widget.label == "num_samples")
    assert num_samples.min == 2
    assert num_samples.max == 512


def test_typed_config_fields_keep_last_valid_config_on_validation_error() -> None:
    from aria_nbv.app.panels.configuration import render_typed_config_fields

    class _Ui:
        errors: list[str]

        def __init__(self) -> None:
            self.errors = []

        def number_input(self, _label, **_kwargs):
            return 0

        def selectbox(self, _label, options, **_kwargs):
            return options[0]

        def error(self, message, **_kwargs):
            self.errors.append(str(message))

    ui = _Ui()
    config = _PanelConfig()
    result = render_typed_config_fields(config, ui=ui, key_prefix="test")

    assert result == config
    assert ui.errors and "Invalid configuration draft" in ui.errors[0]
