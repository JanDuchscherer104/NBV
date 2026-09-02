"""Streamlit configuration workspace interaction contracts."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from streamlit.testing.v1 import AppTest

from aria_nbv.utils import BaseConfig


class _PanelConfig(BaseConfig):
    count: int = Field(default=2, ge=1, le=5)
    """Bounded count shown by the schema-derived widget."""


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
