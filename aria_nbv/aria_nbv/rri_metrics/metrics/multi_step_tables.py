"""Finite-horizon target-RRI rollout metric helpers.

The helpers in this module operate on selected-step metric mappings emitted by
counterfactual rollout scorers. They keep rollout plotting and reporting code
from redefining thesis metrics locally:

* ``G_t^(H)`` is the discounted additive return over selected root-normalized
  target gains when available, falling back to state-relative target RRI for
  legacy rows.
* ``J_e^(H)`` is the endpoint target-error gain from the initial target
  point-mesh error to the final target point-mesh error.
* log-gain is an optional endpoint companion diagnostic.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from math import isfinite, log
from typing import Any


@dataclass(frozen=True, slots=True)
class TargetRolloutMetricSummary:
    """Selected-trajectory target-RRI and endpoint metric summary."""

    cumulative_return: float | None
    """Discounted ``G_t^(H)`` over selected root-normalized rewards."""
    endpoint_gain: float | None
    """Endpoint target-error gain ``J_e^(H)`` when point-mesh errors exist."""
    log_gain: float | None
    """Endpoint log target-error gain when point-mesh errors exist."""
    initial_error: float | None
    """Initial target point-mesh error used for endpoint metrics."""
    final_error: float | None
    """Final target point-mesh error used for endpoint metrics."""
    steps: int
    """Number of selected rollout steps represented by the input metrics."""


def selected_target_rri(metrics: Mapping[str, Any]) -> float | None:
    """Return the selected-step target RRI from one metric mapping."""

    return _finite_metric(metrics, "target_rri", "rri")


def selected_target_reward(metrics: Mapping[str, Any]) -> float | None:
    """Return the selected-step reward used for rollout/Q_H return."""

    return _finite_metric(metrics, "target_root_gain", "root_gain", "target_rri", "rri")


def target_point_mesh_error_before(metrics: Mapping[str, Any]) -> float | None:
    """Return selected-step target point-mesh error before adding the view."""

    return _point_mesh_error(metrics, "before")


def target_point_mesh_error_after(metrics: Mapping[str, Any]) -> float | None:
    """Return selected-step target point-mesh error after adding the view."""

    return _point_mesh_error(metrics, "after")


def finite_horizon_target_return(
    selected_metric_rows: Iterable[Mapping[str, Any]],
    *,
    gamma: float = 1.0,
) -> float | None:
    """Compute additive selected target-RRI return ``G_t^(H)``.

    Missing or non-finite rows are skipped. ``None`` is returned only when no
    finite selected target reward is present.
    """

    if gamma < 0.0:
        raise ValueError("gamma must be non-negative.")

    total = 0.0
    weight = 1.0
    found = False
    for metrics in selected_metric_rows:
        reward = selected_target_reward(metrics)
        if reward is not None:
            total += weight * reward
            found = True
        weight *= gamma
    return total if found else None


def endpoint_target_gain(
    selected_metric_rows: Iterable[Mapping[str, Any]],
    *,
    eps: float = 1e-8,
) -> float | None:
    """Compute endpoint target-error gain ``J_e^(H)``."""

    initial, final = _endpoint_errors(selected_metric_rows)
    if initial is None or final is None:
        return None
    return (initial - final) / (initial + eps)


def endpoint_log_gain(
    selected_metric_rows: Iterable[Mapping[str, Any]],
    *,
    eps: float = 1e-8,
) -> float | None:
    """Compute endpoint log target-error gain."""

    initial, final = _endpoint_errors(selected_metric_rows)
    if initial is None or final is None:
        return None
    return log(initial + eps) - log(final + eps)


def summarize_target_rollout_metrics(
    selected_metric_rows: Iterable[Mapping[str, Any]],
    *,
    gamma: float = 1.0,
    eps: float = 1e-8,
) -> TargetRolloutMetricSummary:
    """Compute ``G_t^(H)``, endpoint gain, and log-gain for one trajectory."""

    rows = list(selected_metric_rows)
    initial, final = _endpoint_errors(rows)
    return TargetRolloutMetricSummary(
        cumulative_return=finite_horizon_target_return(rows, gamma=gamma),
        endpoint_gain=None if initial is None or final is None else (initial - final) / (initial + eps),
        log_gain=None if initial is None or final is None else log(initial + eps) - log(final + eps),
        initial_error=initial,
        final_error=final,
        steps=len(rows),
    )


def _point_mesh_error(metrics: Mapping[str, Any], suffix: str) -> float | None:
    direct = _finite_metric(metrics, f"target_pm_dist_{suffix}")
    if direct is not None:
        return direct
    acc = _finite_metric(metrics, f"target_pm_acc_{suffix}")
    comp = _finite_metric(metrics, f"target_pm_comp_{suffix}")
    if acc is None or comp is None:
        return None
    return acc + comp


def _endpoint_errors(selected_metric_rows: Iterable[Mapping[str, Any]]) -> tuple[float | None, float | None]:
    rows = list(selected_metric_rows)
    if not rows:
        return None, None
    initial = target_point_mesh_error_before(rows[0])
    final = target_point_mesh_error_after(rows[-1])
    return initial, final


def _finite_metric(metrics: Mapping[str, Any], *names: str) -> float | None:
    for name in names:
        if name not in metrics:
            continue
        try:
            value = float(metrics[name])
        except (TypeError, ValueError):
            continue
        if isfinite(value):
            return value
    return None


__all__ = [
    "TargetRolloutMetricSummary",
    "endpoint_log_gain",
    "endpoint_target_gain",
    "finite_horizon_target_return",
    "selected_target_reward",
    "selected_target_rri",
    "summarize_target_rollout_metrics",
    "target_point_mesh_error_after",
    "target_point_mesh_error_before",
]
