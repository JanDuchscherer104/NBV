"""Tests for VIN bin value diagnostics helpers."""

# ruff: noqa: S101, D103, SLF001, PLR2004

import torch

from aria_nbv.app.panels.vin_diag_tabs import bin_values as bin_values_tab
from aria_nbv.rri_metrics.ordinal import RriOrdinalBinner


def test_build_bin_value_payload_uses_bin_means_when_available() -> None:
    binner = RriOrdinalBinner(
        num_classes=4,
        edges=torch.tensor([0.1, 0.2, 0.3], dtype=torch.float32),
        bin_means=torch.tensor([0.05, 0.15, 0.25, 0.35], dtype=torch.float32),
    )
    learned_u = torch.tensor([0.05, 0.14, 0.28, 0.36], dtype=torch.float32)
    payload = bin_values_tab._build_bin_value_payload(
        binner=binner,
        learned_u=learned_u,
    )
    assert payload.centers_df.attrs["baseline_name"] == "bin_mean"
    assert payload.edges_df.shape[0] == 3
    assert payload.centers_df.shape[0] == 4
    assert "learned_u_minus_bin_mean" in payload.centers_df.columns
    assert payload.stats["max_abs_delta"] > 0.0


def test_build_bin_value_payload_falls_back_to_midpoints() -> None:
    binner = RriOrdinalBinner(
        num_classes=4,
        edges=torch.tensor([0.1, 0.2, 0.3], dtype=torch.float32),
    )
    midpoints = binner.class_midpoints()
    learned_u = midpoints + torch.tensor([0.0, 0.01, -0.01, 0.02], dtype=torch.float32)
    payload = bin_values_tab._build_bin_value_payload(
        binner=binner,
        learned_u=learned_u,
    )
    assert payload.centers_df.attrs["baseline_name"] == "midpoint"
    assert "learned_u_minus_midpoint" in payload.centers_df.columns
