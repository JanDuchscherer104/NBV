"""Dispatcher for Streamlit panel renderers.

This module intentionally re-exports the dedicated panel modules in
``aria_nbv.app.panels``. Panel logic and plotting helpers live in their
respective component modules (e.g., ``utils.data_plotting`` or
``pose_generation.plotting``).
"""

from __future__ import annotations

from .panels.candidates import render_candidates_page
from .panels.counterfactual_rollouts import render_counterfactual_rollouts_page
from .panels.data import render_data_page
from .panels.depth import render_depth_page
from .panels.offline_dataset import render_offline_dataset_page
from .panels.optuna_sweep import render_optuna_sweep_page
from .panels.rri import render_rri_page
from .panels.rri_binning import render_rri_binning_page
from .panels.stored_rollouts import render_stored_rollouts_panel
from .panels.vin_diagnostics import render_vin_diagnostics_page
from .panels.wandb import render_wandb_analysis_page

__all__ = [
    "render_candidates_page",
    "render_counterfactual_rollouts_page",
    "render_data_page",
    "render_depth_page",
    "render_offline_dataset_page",
    "render_optuna_sweep_page",
    "render_rri_page",
    "render_rri_binning_page",
    "render_stored_rollouts_panel",
    "render_vin_diagnostics_page",
    "render_wandb_analysis_page",
]
