"""Router contracts for the grouped, lazy Streamlit application frame."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from inspect import getsource
from typing import Any

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
        self.session_state: dict[str, object] = {}
        self.segmented_calls: list[dict[str, object]] = []

    def set_page_config(self, **_: object) -> None:
        return None

    def Page(self, callback: Any, *, title: str, default: bool = False) -> _Page:  # noqa: N802
        return _Page(callback=callback, title=title, default=default)

    def navigation(self, pages: dict[str, list[_Page]], *, position: str) -> _Navigation:
        self.pages = pages
        self.position = position
        return _Navigation()

    def segmented_control(self, label: str, **kwargs: object) -> str:
        self.segmented_calls.append({"label": label, **kwargs})
        return str(kwargs["default"])


def test_router_uses_grouped_top_navigation_without_loading_panels(monkeypatch) -> None:
    import aria_nbv.app.app as app_module

    before = {name for name in sys.modules if name.startswith("aria_nbv.app.panels.")}
    frame = _StreamlitFrame()
    monkeypatch.setattr(app_module, "st", frame)

    NbvStreamlitApp(config=object())._render()

    assert frame.position == "top"
    assert frame.pages is not None
    assert list(frame.pages) == [
        "",
        "Training Data",
        "Generation",
        "Models & Experiments",
        "Foundations / Single-step",
    ]
    assert [[page.title for page in pages] for pages in frame.pages.values()] == [
        ["Training Dataset"],
        ["Root Observation Store", "Rollout Supervision"],
        ["Campaign Generation", "Live Rollout Lab", "Candidate Proposals"],
        ["VIN Diagnostics", "RRI Binning", "W&B Runs", "Optuna Studies"],
        ["Observed Snippet", "Candidate Renders", "Single-step Oracle RRI"],
    ]
    assert frame.pages[""][0].default is True
    after = {name for name in sys.modules if name.startswith("aria_nbv.app.panels.")}
    assert after == before
    assert frame.segmented_calls == [
        {
            "label": "Scientific labels",
            "options": ("Symbols", "Text", "Both"),
            "default": "Both",
            "key": "nbv_scientific_label_display",
            "help": "Choose canonical symbols, readable descriptions, or both where a surface supports mathematics.",
        }
    ]


def test_campaign_generation_callback_imports_and_calls_only_its_renderer(monkeypatch) -> None:
    """Selecting the page owns the one lazy campaign-panel import."""
    calls: list[str] = []
    fake_panel = type("Panel", (), {"render_campaign_generation_page": lambda: calls.append("render")})
    monkeypatch.setitem(sys.modules, "aria_nbv.app.panels.campaign_generation", fake_panel)
    app = NbvStreamlitApp(config=object())
    app._page_campaign_generation()
    assert calls == ["render"]


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
