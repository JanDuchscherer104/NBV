"""Tests for shared plotting helpers."""

import numpy as np

from aria_nbv.utils.plotting import _histogram_overlay


def test_histogram_overlay_log_x_axis() -> None:
    """Enabling log-x should set axis type and keep x values positive."""
    expected_traces = 2
    series = [
        ("a", np.asarray([0.0, 1e-6, 1e-3, 1e-1, 1.0, 10.0], dtype=float)),
        ("b", np.asarray([0.0, 1e-4, 1e-2, 1e-1, 1.0], dtype=float)),
    ]
    fig = _histogram_overlay(
        series,
        bins=8,
        title="test",
        xaxis_title="x",
        log1p_counts=False,
        log_x=True,
    )
    if fig.layout.xaxis.type != "log":
        raise AssertionError("Expected a log-x axis when log_x=True.")
    if len(fig.data) != expected_traces:
        msg = f"Expected {expected_traces} traces, got {len(fig.data)}."
        raise AssertionError(msg)
    for trace in fig.data:
        xs = np.asarray(trace.x, dtype=float)
        if not np.all(xs > 0.0):
            raise AssertionError("Expected positive x centers for log-x histogram.")


def test_histogram_overlay_log_x_requires_positive_values() -> None:
    """When no positive finite values exist, return an empty figure."""
    series = [("a", np.asarray([0.0, -1.0, np.nan], dtype=float))]
    fig = _histogram_overlay(
        series,
        bins=8,
        title="test",
        xaxis_title="x",
        log1p_counts=False,
        log_x=True,
    )
    if len(fig.data) != 0:
        raise AssertionError(
            "Expected no traces when log_x=True and data has no positive values.",
        )
