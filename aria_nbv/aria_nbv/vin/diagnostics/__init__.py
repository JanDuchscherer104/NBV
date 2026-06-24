"""Diagnostics, summaries, and Plotly visualizations for VIN models."""

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
from .summarize_v2 import summarize_vin_v2

__all__ = [
    "build_alignment_figures",
    "build_candidate_encoding_figures",
    "build_field_token_histograms",
    "build_frustum_samples_figure",
    "build_prediction_alignment_figure",
    "build_vin_encoding_figures",
    "plot_vin_encodings_from_debug",
    "summarize_vin_v2",
    "summarize_vin_v3",
]
