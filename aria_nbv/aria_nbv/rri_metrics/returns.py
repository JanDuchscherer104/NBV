r"""Differentiable gains and returns for finite-horizon NBV evaluation.

This module provides reducers that share the hard-mask contract used by rollout replay: invalid or
unsupervised actions are ignored, never converted into low rewards. For root
error $d_0$, final error $d_H$, and selected root-normalized rewards $r_t$,

$$
G_0^{(H)}=\sum_{t=0}^{H-1}\gamma^t r_t,
\qquad
J_e^{(H)}=\frac{d_0-d_H}{d_0+\epsilon}.
$$

Python mapping reducers serve inspection/UI paths; tensor reducers remain
differentiable for batched evaluation and future finite-candidate ``Q_H`` use.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from math import isfinite
from typing import Any

import torch
from torch import Tensor


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


@dataclass(frozen=True, slots=True)
class TorchRolloutMetrics:
    """Batched target-rollout metrics for selected trajectories.

    Attributes:
        discounted_return: ``Tensor["B"]`` discounted sum of selected
            root-normalized target gains.
        endpoint_gain: ``Tensor["B"]`` root-normalized endpoint target-error
            gain ``(d_0 - d_H) / (d_0 + eps)``.
        endpoint_log_gain: ``Tensor["B"]`` log target-error reduction
            ``log(d_0 + eps) - log(d_H + eps)``.
        valid_steps: ``Tensor["B"]`` count of finite selected rewards included
            in `discounted_return`.
        valid_endpoint: ``Tensor["B"]`` mask for trajectories with finite,
            non-negative endpoint errors.
    """

    discounted_return: Tensor
    """``Tensor["B", float32]`` dimensionless discounted return; empty rows are ``NaN``."""

    endpoint_gain: Tensor
    """``Tensor["B", float32]`` dimensionless root-normalized endpoint gain."""

    endpoint_log_gain: Tensor
    """``Tensor["B", float32]`` dimensionless logarithmic endpoint gain."""

    valid_steps: Tensor
    """``Tensor["B", int64]`` count of finite hard-valid selected rewards."""

    valid_endpoint: Tensor
    """``Tensor["B", bool]`` comparability mask for finite non-negative endpoint errors."""


def selected_target_rri(metrics: Mapping[str, Any]) -> float | None:
    """Return the selected-step target RRI from one metric mapping."""

    return _finite_metric(metrics, "target_rri", "rri")


def selected_target_reward(metrics: Mapping[str, Any]) -> float | None:
    """Return the selected-step root-normalized reward used by rollout/Q_H."""

    return _finite_metric(metrics, "target_root_gain", "root_gain")


def target_point_mesh_error_before(metrics: Mapping[str, Any]) -> float | None:
    """Return selected-step target point-mesh error before adding the view."""

    return _point_mesh_error(metrics, "before")


def target_point_mesh_error_after(metrics: Mapping[str, Any]) -> float | None:
    """Return selected-step target point-mesh error after adding the view."""

    return _point_mesh_error(metrics, "after")


def root_normalized_gain(
    before: Tensor,
    after: Tensor,
    root_error: Tensor,
    *,
    eps: float = 1e-12,
) -> Tensor:
    """Compute gain normalized by the rollout-root reconstruction error."""

    return (before - after) / root_error.clamp_min(eps)


def log_error_gain(before: Tensor, after: Tensor, *, eps: float = 1e-12) -> Tensor:
    """Compute logarithmic reconstruction-error reduction."""

    return torch.log(before.clamp_min(eps)) - torch.log(after.clamp_min(eps))


def discounted_selected_return(
    rewards: Tensor,
    valid_mask: Tensor | None = None,
    *,
    gamma: float = 1.0,
) -> Tensor:
    """Compute discounted returns over selected rewards.

    Args:
        rewards: ``Tensor["B H"]`` or ``Tensor["H"]`` selected per-step
            rewards, normally `target_root_gain`.
        valid_mask: Optional boolean tensor with the same shape as `rewards`.
            Non-finite rewards are ignored even when this mask is ``True``.
        gamma: Non-negative discount factor.

    Returns:
        Tensor with shape ``Tensor["B"]`` for 2-D inputs or scalar shape for
        1-D inputs. Rows with no valid finite rewards return ``NaN``.
    """

    if gamma < 0.0:
        raise ValueError("gamma must be non-negative.")
    batched, squeeze = _as_step_matrix(rewards)
    valid = _finite_mask(batched, valid_mask)
    weights = _discount_weights(batched.shape[1], gamma=gamma, device=batched.device, dtype=batched.dtype)
    values = torch.where(valid, batched, torch.zeros_like(batched))
    result = (values * weights.unsqueeze(0)).sum(dim=1)
    result = torch.where(valid.any(dim=1), result, torch.full_like(result, float("nan")))
    return result.squeeze(0) if squeeze else result


def endpoint_target_gain_tensor(
    initial_error: Tensor,
    final_error: Tensor,
    *,
    eps: float = 1e-8,
) -> Tensor:
    """Compute root-normalized endpoint gain from target point-mesh errors.

    Args:
        initial_error: Initial target point-mesh error ``d_0``.
        final_error: Final target point-mesh error ``d_H``.
        eps: Positive denominator guard.

    Returns:
        Tensor broadcast from the input shapes. Entries with non-finite or
        negative endpoint errors return ``NaN``.
    """

    initial, final = torch.broadcast_tensors(initial_error, final_error)
    valid = _valid_endpoint_errors(initial, final)
    gain = (initial - final) / (initial + float(eps))
    return torch.where(valid, gain, torch.full_like(gain, float("nan")))


def endpoint_log_gain_tensor(
    initial_error: Tensor,
    final_error: Tensor,
    *,
    eps: float = 1e-8,
) -> Tensor:
    """Compute endpoint log target-error reduction.

    Args:
        initial_error: Initial target point-mesh error ``d_0``.
        final_error: Final target point-mesh error ``d_H``.
        eps: Positive log guard.

    Returns:
        Tensor broadcast from the input shapes. Entries with non-finite or
        negative endpoint errors return ``NaN``.
    """

    initial, final = torch.broadcast_tensors(initial_error, final_error)
    valid = _valid_endpoint_errors(initial, final)
    gain = torch.log(initial + float(eps)) - torch.log(final + float(eps))
    return torch.where(valid, gain, torch.full_like(gain, float("nan")))


def summarize_selected_rollout_tensors(
    rewards: Tensor,
    initial_error: Tensor,
    final_error: Tensor,
    valid_mask: Tensor | None = None,
    *,
    gamma: float = 1.0,
    eps: float = 1e-8,
) -> TorchRolloutMetrics:
    """Summarize selected target-rollout tensors in one batched call.

    Args:
        rewards: ``Tensor["B H"]`` selected rewards, normally
            root-normalized target gains.
        initial_error: ``Tensor["B"]`` initial target point-mesh errors.
        final_error: ``Tensor["B"]`` final target point-mesh errors.
        valid_mask: Optional ``Tensor["B H"]`` mask for reward supervision.
        gamma: Non-negative discount factor.
        eps: Denominator and log guard for endpoint metrics.

    Returns:
        `TorchRolloutMetrics` with one value per trajectory.
    """

    rewards_2d, squeeze = _as_step_matrix(rewards)
    valid = _finite_mask(rewards_2d, valid_mask)
    discounted = discounted_selected_return(rewards_2d, valid, gamma=gamma)
    initial, final = torch.broadcast_tensors(initial_error.reshape(-1), final_error.reshape(-1))
    endpoint = endpoint_target_gain_tensor(initial, final, eps=eps)
    log_gain = endpoint_log_gain_tensor(initial, final, eps=eps)
    valid_endpoint = _valid_endpoint_errors(initial, final)
    valid_steps = valid.sum(dim=1)
    if squeeze:
        return TorchRolloutMetrics(
            discounted_return=discounted.squeeze(0),
            endpoint_gain=endpoint.squeeze(0),
            endpoint_log_gain=log_gain.squeeze(0),
            valid_steps=valid_steps.squeeze(0),
            valid_endpoint=valid_endpoint.squeeze(0),
        )
    return TorchRolloutMetrics(
        discounted_return=discounted,
        endpoint_gain=endpoint,
        endpoint_log_gain=log_gain,
        valid_steps=valid_steps,
        valid_endpoint=valid_endpoint,
    )


def finite_horizon_target_return(
    selected_metric_rows: Iterable[Mapping[str, Any]],
    *,
    gamma: float = 1.0,
) -> float | None:
    """Compute a discounted return through the tensor-first kernel."""

    rewards = [selected_target_reward(row) for row in selected_metric_rows]
    if not rewards:
        return None
    values = torch.tensor([float("nan") if value is None else value for value in rewards], dtype=torch.float64)
    return _optional_scalar(discounted_selected_return(values, gamma=gamma))


def endpoint_target_gain(
    selected_metric_rows: Iterable[Mapping[str, Any]],
    *,
    eps: float = 1e-8,
) -> float | None:
    """Compute endpoint gain through the tensor-first kernel."""

    initial, final = _endpoint_errors(selected_metric_rows)
    if initial is None or final is None:
        return None
    value = endpoint_target_gain_tensor(
        torch.tensor(initial, dtype=torch.float64),
        torch.tensor(final, dtype=torch.float64),
        eps=eps,
    )
    return _optional_scalar(value)


def endpoint_log_gain(
    selected_metric_rows: Iterable[Mapping[str, Any]],
    *,
    eps: float = 1e-8,
) -> float | None:
    """Compute endpoint log gain through the tensor-first kernel."""

    initial, final = _endpoint_errors(selected_metric_rows)
    if initial is None or final is None:
        return None
    value = endpoint_log_gain_tensor(
        torch.tensor(initial, dtype=torch.float64),
        torch.tensor(final, dtype=torch.float64),
        eps=eps,
    )
    return _optional_scalar(value)


def summarize_target_rollout_metrics(
    selected_metric_rows: Iterable[Mapping[str, Any]],
    *,
    gamma: float = 1.0,
    eps: float = 1e-8,
) -> TargetRolloutMetricSummary:
    """Summarize one selected trajectory using the canonical tensor kernels."""

    rows = list(selected_metric_rows)
    initial, final = _endpoint_errors(rows)
    return TargetRolloutMetricSummary(
        cumulative_return=finite_horizon_target_return(rows, gamma=gamma),
        endpoint_gain=endpoint_target_gain(rows, eps=eps),
        log_gain=endpoint_log_gain(rows, eps=eps),
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


def _as_step_matrix(values: Tensor) -> tuple[Tensor, bool]:
    if values.ndim == 1:
        return values.unsqueeze(0), True
    if values.ndim == 2:
        return values, False
    raise ValueError(f"Expected rollout tensor with shape (H,) or (B,H), got {tuple(values.shape)}.")


def _discount_weights(length: int, *, gamma: float, device: torch.device, dtype: torch.dtype) -> Tensor:
    steps = torch.arange(length, device=device, dtype=dtype)
    return torch.pow(torch.as_tensor(float(gamma), device=device, dtype=dtype), steps)


def _finite_mask(values: Tensor, valid_mask: Tensor | None) -> Tensor:
    valid = torch.isfinite(values)
    if valid_mask is None:
        return valid
    mask = torch.broadcast_to(valid_mask.to(device=values.device, dtype=torch.bool), values.shape)
    return valid & mask


def _valid_endpoint_errors(initial_error: Tensor, final_error: Tensor) -> Tensor:
    return torch.isfinite(initial_error) & torch.isfinite(final_error) & (initial_error >= 0.0) & (final_error >= 0.0)


def _optional_scalar(value: Tensor) -> float | None:
    scalar = float(value.detach().cpu().item())
    return scalar if isfinite(scalar) else None


__all__ = [
    "TargetRolloutMetricSummary",
    "TorchRolloutMetrics",
    "discounted_selected_return",
    "endpoint_log_gain",
    "endpoint_log_gain_tensor",
    "endpoint_target_gain",
    "endpoint_target_gain_tensor",
    "finite_horizon_target_return",
    "log_error_gain",
    "root_normalized_gain",
    "selected_target_reward",
    "selected_target_rri",
    "summarize_selected_rollout_tensors",
    "summarize_target_rollout_metrics",
    "target_point_mesh_error_after",
    "target_point_mesh_error_before",
]
