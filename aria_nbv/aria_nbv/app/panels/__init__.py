"""Lazy public facade for Streamlit panel renderers.

Importing this package does not evaluate any panel module. Attribute access is
resolved on demand so cached decorators see an initialized Streamlit runtime.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORT_MODULES = {
    "render_candidates_page": ".candidates",
    "render_counterfactual_rollouts_page": ".counterfactual_rollouts",
    "render_data_page": ".data",
    "render_depth_page": ".depth",
    "render_offline_dataset_page": ".offline_dataset",
    "render_rri_binning_page": ".rri_binning",
    "render_rri_page": ".rri",
    "render_stored_rollouts_panel": ".stored_rollouts",
    "render_training_dataset_page": ".training_dataset",
    "render_vin_diagnostics_page": ".vin_diagnostics",
    "render_wandb_analysis_page": ".wandb",
}

__all__ = list(_EXPORT_MODULES)


def __getattr__(name: str) -> Any:
    """Import and return one panel renderer when first requested."""

    module_name = _EXPORT_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(module_name, __name__), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """Return package globals plus lazy renderer exports."""

    return sorted([*globals(), *__all__])
