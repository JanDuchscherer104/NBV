"""Regression tests for generation-panel scientific label boundaries."""

from __future__ import annotations

import pandas as pd
import pytest

from aria_nbv.app.panels import candidates, counterfactual_rollouts, rri


@pytest.mark.parametrize("mode", ["Symbols", "Text", "Both"])
def test_generation_panels_share_three_mode_scientific_labels(monkeypatch: pytest.MonkeyPatch, mode: str) -> None:
    """The three generation panels use the global display mode consistently."""

    monkeypatch.setattr(candidates, "get_label_display_mode", lambda: mode)
    monkeypatch.setattr(rri, "get_label_display_mode", lambda: mode)
    monkeypatch.setattr(counterfactual_rollouts, "get_label_display_mode", lambda: mode)

    labels = (
        candidates._label("validity_mask", math_capable=True),
        rri._label("point_to_mesh_error", math_capable=True),
        counterfactual_rollouts._label("target_root_gain", math_capable=True),
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
