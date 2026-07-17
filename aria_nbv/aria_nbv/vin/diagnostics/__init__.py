"""Diagnostics, summaries, and Plotly visualizations for VIN models.

This package owns the stable app-facing exports for encoding figures and the
VIN-Core batch/model summary while implementation helpers remain in leaf modules.
"""

from __future__ import annotations

from .experimental_plotting import (
    build_alignment_figures,
    build_candidate_encoding_figures,
    build_field_token_histograms,
    build_frustum_samples_figure,
    build_prediction_alignment_figure,
    build_vin_encoding_figures,
    plot_vin_encodings_from_debug,
)
from .summarize import summarize_vin_v3

__all__ = [
    "build_alignment_figures",
    "build_candidate_encoding_figures",
    "build_field_token_histograms",
    "build_frustum_samples_figure",
    "build_prediction_alignment_figure",
    "build_vin_encoding_figures",
    "plot_vin_encodings_from_debug",
    "summarize_vin_v3",
]
