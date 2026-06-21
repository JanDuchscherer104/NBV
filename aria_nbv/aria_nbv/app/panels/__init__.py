"""Streamlit panels for the NBV app."""

from __future__ import annotations

from .candidates import render_candidates_page
from .counterfactual_rollouts import render_counterfactual_rollouts_page
from .data import render_data_page
from .depth import render_depth_page
from .offline_dataset import render_offline_dataset_page
from .rl import render_rl_page
from .rri import render_rri_page
from .rri_binning import render_rri_binning_page
from .stored_rollouts import render_stored_rollouts_panel
from .testing_attribution import render_testing_attribution_page
from .vin_diagnostics import render_vin_diagnostics_page
from .wandb import render_wandb_analysis_page

__all__ = [
    "render_candidates_page",
    "render_counterfactual_rollouts_page",
    "render_data_page",
    "render_depth_page",
    "render_offline_dataset_page",
    "render_rl_page",
    "render_rri_binning_page",
    "render_rri_page",
    "render_stored_rollouts_panel",
    "render_vin_diagnostics_page",
    "render_wandb_analysis_page",
    "render_testing_attribution_page",
]
