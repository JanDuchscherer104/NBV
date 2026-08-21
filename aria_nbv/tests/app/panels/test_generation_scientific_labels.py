"""Regression tests for generation-panel scientific label boundaries."""

from __future__ import annotations

import pandas as pd
import pytest

from aria_nbv.app.panels import common, counterfactual_rollouts


@pytest.mark.parametrize("mode", ["Symbols", "Text", "Both"])
def test_generation_panels_share_three_mode_scientific_labels(monkeypatch: pytest.MonkeyPatch, mode: str) -> None:
    """The three generation panels use the global display mode consistently."""

    monkeypatch.setattr(common, "get_label_display_mode", lambda: mode)

    labels = (
        common.current_scientific_label("validity_mask", surface="markdown"),
        common.current_scientific_label("point_to_mesh_error", surface="markdown"),
        common.current_scientific_label("target_root_gain", surface="markdown"),
    )
    if mode == "Text":
        assert all("$" not in label for label in labels)
    else:
        assert all("$" in label for label in labels)
    if mode == "Both":
        assert all(" — " in label for label in labels)


def test_generation_labeling_does_not_change_factual_dataframe_schema() -> None:
    """Display labels remain separate from raw score columns used by reports."""

    raw = pd.DataFrame(
        {
            "target_root_gain": [0.1],
            "target_rri": [0.2],
            "selection_probability": [0.5],
            "validity": [True],
        }
    )
    displayed = raw.rename(columns={column: column for column in raw.columns})
    assert list(displayed.columns) == list(raw.columns)
    assert displayed.equals(raw)


def test_plotly_facing_generation_labels_are_plain_text(monkeypatch: pytest.MonkeyPatch) -> None:
    """Plotly receives readable labels because it does not render TeX markup."""

    monkeypatch.setattr(common, "get_label_display_mode", lambda: "Both")
    figure = counterfactual_rollouts._build_fanout_band_figure(
        pd.DataFrame(
            {
                "trajectory": [0],
                "step": [1],
                "fanout_q025": [0.1],
                "fanout_q975": [0.2],
                "selected_target_rri": [0.15],
                "selected_target_root_gain": [0.16],
            }
        )
    )
    labels = [
        figure.layout.title.text,
        figure.layout.xaxis.title.text,
        figure.layout.yaxis.title.text,
        *(trace.name for trace in figure.data),
    ]
    assert all("$" not in str(label) and "\\" not in str(label) for label in labels)
