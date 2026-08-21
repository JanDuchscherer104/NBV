from __future__ import annotations

import pandas as pd
import pytest

from aria_nbv.app.panels._stored_rollouts.reconstruction_return import _temporal_summary_figure
from aria_nbv.app.scientific_labels import format_scientific_label, scientific_label


@pytest.mark.parametrize(
    ("mode", "expected"),
    (
        ("Symbols", r"$G_{0:s,\mathrm{root}}^e$ (fraction)"),
        ("Text", "Cumulative target root gain (fraction)"),
        ("Both", r"$G_{0:s,\mathrm{root}}^e$ — Cumulative target root gain (fraction)"),
    ),
)
def test_canonical_label_display_modes(mode: str, expected: str) -> None:
    label = format_scientific_label(
        scientific_label("cumulative_target_root_gain"),
        mode=mode,  # type: ignore[arg-type]
        surface="markdown",
    )

    assert label == expected


def test_plain_scientific_surface_never_leaks_latex() -> None:
    label = format_scientific_label(
        scientific_label("q_h"),
        mode="Symbols",
        surface="plain",
    )

    assert "$" not in label
    assert label == "Finite-horizon action value"


def test_temporal_figure_keeps_raw_schema_and_uses_canonical_axis_label() -> None:
    rows = pd.DataFrame(
        {
            "metric": ["cumulative_target_root_gain", "cumulative_target_root_gain"],
            "units": ["fraction", "fraction"],
            "step_index": [0, 1],
            "trajectory": ["temperature_softmax", "temperature_softmax"],
            "q25": [0.0, 0.1],
            "q50": [0.0, 0.2],
            "q75": [0.0, 0.3],
            "median": [0.0, 0.2],
            "finite_count": [2, 2],
            "total_count": [2, 2],
            "missing_count": [0, 0],
            "store_count": [1, 1],
            "mean": [0.0, 0.2],
            "min": [0.0, 0.1],
            "max": [0.0, 0.3],
        },
    )
    original_columns = rows.columns.tolist()

    figure = _temporal_summary_figure(rows, group_field="trajectory", metric_label="ignored")

    assert rows.columns.tolist() == original_columns
    assert "Cumulative target root gain" in str(figure.layout.title.text)
    assert "Cumulative target root gain" in str(figure.layout.yaxis.title.text)
    assert "$" not in str(figure.layout.title.text)
    assert "\\" not in str(figure.layout.title.text)
    assert "$" not in str(figure.layout.yaxis.title.text)
    assert "\\" not in str(figure.layout.yaxis.title.text)
