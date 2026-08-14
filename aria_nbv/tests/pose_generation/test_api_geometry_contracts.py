"""Regression tests for geometry-facing config boundaries.

These tests keep the executable owner honest about coercion and failure
contracts that are easy to lose when configuration is moved between modules.
"""

from __future__ import annotations

import pytest

from aria_nbv.pose_generation.candidate_generation import CandidateViewGeneratorConfig
from aria_nbv.rendering.candidate_depth_renderer import CandidateDepthRendererConfig
from aria_nbv.utils import Verbosity


def test_candidate_config_distinguishes_omitted_view_caps_from_explicit_none() -> None:
    """Omitted caps keep field defaults while explicit None uses the fallback."""

    omitted = CandidateViewGeneratorConfig(device="cpu")
    assert omitted.view_kappa == omitted.kappa
    assert omitted.view_max_azimuth_deg == 60.0
    assert omitted.view_max_elevation_deg == 30.0

    config = CandidateViewGeneratorConfig(
        kappa=7.0,
        view_kappa=None,
        view_max_angle_deg=12.0,
        view_max_azimuth_deg=None,
        view_max_elevation_deg=None,
        is_debug=True,
        device="cpu",
    )

    omitted_with_kappa = CandidateViewGeneratorConfig(kappa=7.0, device="cpu")
    assert config.view_kappa == omitted_with_kappa.view_kappa == 7.0
    assert config.view_max_azimuth_deg == 12.0
    assert config.view_max_elevation_deg == 12.0
    assert config.verbosity is Verbosity.VERBOSE


def test_candidate_renderer_rejects_half_specified_exact_size() -> None:
    """Exact output dimensions are an atomic width/height pair."""

    with pytest.raises(ValueError, match="must be set together"):
        CandidateDepthRendererConfig(output_width_px=320)
