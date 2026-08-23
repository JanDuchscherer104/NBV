"""Regression coverage for app-wide scientific-label consumers."""

from __future__ import annotations

import inspect

import pytest

from aria_nbv.app.panels import candidates, optuna_sweep, rri, rri_binning, wandb
from aria_nbv.app.panels.vin_diag_tabs import bin_values, coral, geometry, summary


@pytest.mark.parametrize(
    ("module", "symbol", "identifier"),
    (
        (candidates, "_full_shell_color_payload", "validity_mask"),
        (optuna_sweep, "_optuna_field_label", "target_rri"),
        (rri, "render_rri_page", "oracle_rri"),
        (rri_binning, "render_rri_binning_page", "current_scientific_label"),
        (wandb, "_wandb_metric_label", "oracle_rri"),
        (bin_values, "render_bin_values_tab", "current_scientific_label"),
        (coral, "render_coral_tab", "current_scientific_label"),
        (geometry, "render_geometry_tab", "current_scientific_label"),
        (summary, "render_summary_tab", "current_scientific_label"),
    ),
)
def test_non_stored_rollout_consumers_use_shared_label_boundary(module, symbol: str, identifier: str) -> None:
    source = inspect.getsource(getattr(module, symbol))
    assert "current_scientific_label" in source
    assert identifier in source
