"""Focused regressions for non-stored-rollout scientific presentation seams."""

from __future__ import annotations

import inspect

import pandas as pd
import pytest

from aria_nbv.app.panels import common, counterfactual_rollouts, offline_dataset, training_dataset


@pytest.mark.parametrize("mode", ["Symbols", "Text", "Both"])
def test_generation_labels_follow_global_display_mode(monkeypatch: pytest.MonkeyPatch, mode: str) -> None:
    monkeypatch.setattr(common, "get_label_display_mode", lambda: mode)
    labels = (
        common.current_scientific_label("target_root_gain", surface="markdown"),
        common.current_scientific_label("validity_mask", surface="markdown"),
    )
    if mode == "Text":
        assert all("$" not in label for label in labels)
    else:
        assert all("$" in label for label in labels)
    if mode == "Both":
        assert all(" — " in label for label in labels)


def test_generation_plot_labels_are_readable_and_schema_is_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(common, "get_label_display_mode", lambda: "Both")
    rows = pd.DataFrame(
        {
            "trajectory": [0],
            "step": [1],
            "fanout_q025": [0.1],
            "fanout_q975": [0.2],
            "selected_target_rri": [0.15],
            "selected_target_root_gain": [0.16],
        },
    )
    figure = counterfactual_rollouts._build_fanout_band_figure(rows)
    labels = [figure.layout.title.text, figure.layout.xaxis.title.text, figure.layout.yaxis.title.text]
    assert all("$" not in str(label) and "\\" not in str(label) for label in labels)
    assert list(rows.columns) == [
        "trajectory",
        "step",
        "fanout_q025",
        "fanout_q975",
        "selected_target_rri",
        "selected_target_root_gain",
    ]


def test_offline_stats_use_four_progressive_workspaces() -> None:
    assert offline_dataset._SECTIONS == ("Overview", "Content", "Runtime", "Details")
    source = inspect.getsource(offline_dataset._render_stats)
    assert "_render_coverage(coverage)" in source
    assert 'st.expander("Manifest and shapes"' in source


def test_training_qh_surface_uses_shared_scientific_label_helper() -> None:
    source = inspect.getsource(training_dataset.render_training_dataset_page)
    assert "current_scientific_label('q_h')" in source
    assert "current_scientific_label(metric.name)" in source
