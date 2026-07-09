"""Tests for the panels dispatcher module."""

from __future__ import annotations

from aria_nbv.app import panels
from aria_nbv.app.panels import (
    candidates,
    counterfactual_rollouts,
    data,
    depth,
    offline_dataset,
    rri,
    rri_binning,
    vin_diagnostics,
    wandb,
)


def test_panels_dispatcher_reexports() -> None:
    """Ensure dispatcher re-exports dedicated panel renderers."""
    assert panels.render_candidates_page is candidates.render_candidates_page
    assert panels.render_counterfactual_rollouts_page is counterfactual_rollouts.render_counterfactual_rollouts_page
    assert panels.render_data_page is data.render_data_page
    assert panels.render_depth_page is depth.render_depth_page
    assert panels.render_offline_dataset_page is offline_dataset.render_offline_dataset_page
    assert panels.render_rri_page is rri.render_rri_page
    assert panels.render_rri_binning_page is rri_binning.render_rri_binning_page
    assert panels.render_vin_diagnostics_page is vin_diagnostics.render_vin_diagnostics_page
    assert panels.render_wandb_analysis_page is wandb.render_wandb_analysis_page
