"""Tests for the panels dispatcher module."""

from __future__ import annotations

import subprocess
import sys

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


def test_panels_dispatcher_exports_campaign_generation_lazily() -> None:
    """Campaign page is a facade export, not an eager Streamlit import."""
    import importlib
    import sys

    sys.modules.pop("aria_nbv.app.panels.campaign_generation", None)
    dispatcher = importlib.reload(panels)
    assert "aria_nbv.app.panels.campaign_generation" not in sys.modules
    renderer = dispatcher.render_campaign_generation_page
    assert callable(renderer)
    assert "aria_nbv.app.panels.campaign_generation" in sys.modules


def test_panels_dispatcher_reexports() -> None:
    """Ensure the package facade lazily exports dedicated panel renderers."""
    assert panels.render_candidates_page is candidates.render_candidates_page
    assert panels.render_counterfactual_rollouts_page is counterfactual_rollouts.render_counterfactual_rollouts_page
    assert panels.render_data_page is data.render_data_page
    assert panels.render_depth_page is depth.render_depth_page
    assert panels.render_offline_dataset_page is offline_dataset.render_offline_dataset_page
    assert panels.render_rri_page is rri.render_rri_page
    assert panels.render_rri_binning_page is rri_binning.render_rri_binning_page
    assert panels.render_vin_diagnostics_page is vin_diagnostics.render_vin_diagnostics_page
    assert panels.render_wandb_analysis_page is wandb.render_wandb_analysis_page


def test_panels_package_import_does_not_load_panel_modules() -> None:
    """Importing the facade alone must not evaluate individual panels."""

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; import aria_nbv.app.panels; "
                "print(any(name.startswith('aria_nbv.app.panels.') for name in sys.modules))"
            ),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == "False"
    assert "No runtime found" not in result.stderr
