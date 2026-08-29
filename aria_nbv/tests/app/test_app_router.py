"""Router contracts for the grouped, lazy Streamlit application frame."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from inspect import getsource
from pathlib import Path
from typing import Any, cast

import pytest

from aria_nbv.app.app import NbvStreamlitApp
from aria_nbv.app.panels.offline_dataset import render_offline_dataset_page


@dataclass(slots=True)
class _Page:
    callback: Any
    title: str
    default: bool = False


class _Navigation:
    def run(self) -> None:
        return None


class _StreamlitFrame:
    def __init__(self) -> None:
        self.pages: dict[str, list[_Page]] | None = None
        self.position: str | None = None

    def set_page_config(self, **_: object) -> None:
        return None

    def Page(self, callback: Any, *, title: str, default: bool = False) -> _Page:  # noqa: N802
        return _Page(callback=callback, title=title, default=default)

    def navigation(self, pages: dict[str, list[_Page]], *, position: str) -> _Navigation:
        self.pages = pages
        self.position = position
        return _Navigation()


def test_router_uses_grouped_top_navigation_without_loading_panels(monkeypatch: pytest.MonkeyPatch) -> None:
    import aria_nbv.app.app as app_module

    before = {name for name in sys.modules if name.startswith("aria_nbv.app.panels.")}
    frame = _StreamlitFrame()
    monkeypatch.setattr(app_module, "st", frame)

    NbvStreamlitApp(config=cast(Any, object()))._render()

    assert frame.position == "top"
    assert frame.pages is not None
    assert list(frame.pages) == [
        "",
        "Training Data",
        "Generation",
        "Models & Experiments",
        "Reporting & Configuration",
        "Foundations / Single-step",
    ]
    assert [[page.title for page in pages] for pages in frame.pages.values()] == [
        ["Training Dataset"],
        ["Root Observation Store", "Rollout Supervision"],
        ["Campaign Generation", "Live Rollout Lab", "Candidate Proposals"],
        ["VIN Diagnostics", "RRI Binning", "W&B Runs", "Optuna Studies"],
        ["Scientific Reporting", "Configuration Workspace"],
        ["Observed Snippet", "Candidate Renders", "Single-step Oracle RRI"],
    ]
    assert frame.pages[""][0].default is True
    after = {name for name in sys.modules if name.startswith("aria_nbv.app.panels.")}
    assert after == before


def test_campaign_generation_callback_imports_and_calls_only_its_renderer(monkeypatch: pytest.MonkeyPatch) -> None:
    """Selecting the page owns the one lazy campaign-panel import."""
    recipe = object()
    calls: list[dict[str, Any]] = []
    fake_panel = type(
        "Panel",
        (),
        {"render_campaign_generation_page": lambda **kwargs: calls.append(kwargs)},
    )

    class Config:
        s2_report_section_id = "s2"

        def load_s2_report_recipe(self) -> tuple[object, Path]:
            return recipe, Path("/repo/.configs/reports/s2.toml")

    monkeypatch.setitem(sys.modules, "aria_nbv.app.panels.campaign_generation", fake_panel)
    app = NbvStreamlitApp(config=Config())  # type: ignore[arg-type]
    app._page_campaign_generation()
    assert calls == [
        {
            "s2_recipe": recipe,
            "s2_section_id": "s2",
            "s2_recipe_label": "/repo/.configs/reports/s2.toml",
        }
    ]


def test_training_dataset_callback_imports_and_calls_only_its_renderer(monkeypatch: pytest.MonkeyPatch) -> None:
    """PR 0 locks the Training Dataset facade and its explicit lazy dispatch."""

    calls: list[None] = []
    fake_panel = type(
        "Panel",
        (),
        {"render_training_dataset_page": lambda: calls.append(None)},
    )

    monkeypatch.setitem(sys.modules, "aria_nbv.app.panels.training_dataset", fake_panel)
    NbvStreamlitApp(config=cast(Any, object()))._page_training_dataset()

    assert calls == [None]


def test_rollout_supervision_callback_preserves_stable_facade_arguments(monkeypatch: pytest.MonkeyPatch) -> None:
    """PR 0 locks the stored-rollout facade and report-recipe handoff."""

    recipe = object()
    calls: list[dict[str, Any]] = []
    fake_panel = type(
        "Panel",
        (),
        {"render_stored_rollouts_panel": lambda **kwargs: calls.append(kwargs)},
    )

    class Config:
        s2_report_section_id = "s2"

        def load_s2_report_recipe(self) -> tuple[object, Path]:
            return recipe, Path("/repo/.configs/reports/s2.toml")

    monkeypatch.setitem(sys.modules, "aria_nbv.app.panels.stored_rollouts", fake_panel)
    NbvStreamlitApp(config=Config())._page_rollout_supervision()  # type: ignore[arg-type]

    assert calls == [
        {
            "s2_recipe": recipe,
            "s2_section_id": "s2",
            "s2_recipe_label": "/repo/.configs/reports/s2.toml",
        }
    ]


def test_live_rollout_callback_imports_and_calls_only_its_renderer(monkeypatch: pytest.MonkeyPatch) -> None:
    """PR 0 locks the live-lab facade without constructing runtime eagerly."""

    calls: list[None] = []
    fake_panel = type(
        "Panel",
        (),
        {"render_counterfactual_rollouts_page": lambda: calls.append(None)},
    )

    monkeypatch.setitem(sys.modules, "aria_nbv.app.panels.counterfactual_rollouts", fake_panel)
    NbvStreamlitApp(config=cast(Any, object()))._page_live_rollout_lab()

    assert calls == [None]


def test_root_store_page_has_no_nested_rollout_route() -> None:
    """Keep rollout supervision as a sibling navigation page."""

    source = getsource(render_offline_dataset_page)
    assert "Stored Rollouts" not in source
    assert "Dataset inspection section" not in source


def test_internal_page_headings_match_navigation_labels() -> None:
    """Keep page content headings aligned with the grouped navigation."""

    from aria_nbv.app.panels import candidates, counterfactual_rollouts, data, optuna_sweep, rri, wandb
    from aria_nbv.app.panels._stored_rollouts_page import render_stored_rollouts_page

    heading_contracts = (
        (render_stored_rollouts_page, 'st.header("Rollout Supervision")'),
        (counterfactual_rollouts._render_live_rollouts_tab, 'st.header("Live Rollout Lab")'),
        (candidates._render_live_candidates_page, 'st.header("Candidate Proposals")'),
        (data.render_data_page, 'st.header("Observed Snippet")'),
        (rri.render_rri_page, 'st.header("Single-step Oracle RRI")'),
        (wandb.render_wandb_analysis_page, 'st.header("W&B Runs")'),
        (optuna_sweep.render_optuna_sweep_page, 'st.header("Optuna Studies")'),
    )

    for render_page, expected_header in heading_contracts:
        assert expected_header in getsource(render_page)
