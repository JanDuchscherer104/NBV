"""Torch-native rollout metrics for target-conditioned NBV.

The helpers in `aria_nbv.rri_metrics.rollout` operate on Python mappings used
by CLI summaries and Streamlit tables. This module owns the tensor equivalent
for training and batched evaluation code: selected-action returns, endpoint
target gain, and validity-aware reductions over finite candidate tables.

All functions preserve the hard-mask contract used by
`aria_nbv.rollouts.zarr_store`: invalid or unsupervised candidates are ignored,
not treated as low-reward labels. Shapes are intentionally simple so both the
current one-step VIN scorer and future finite-candidate ``Q_H`` models can call
the same metric code.
"""

from __future__ import annotations

from dataclasses import dataclass

import torch
from torch import Tensor


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
    endpoint_gain: Tensor
    endpoint_log_gain: Tensor
    valid_steps: Tensor
    valid_endpoint: Tensor


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


def selected_path_length_tensor(camera_centers_world: Tensor, segment_valid_mask: Tensor | None = None) -> Tensor:
    """Compute selected camera-center path length in metres.

    Args:
        camera_centers_world: Camera centers in world coordinates with shape
            ``Tensor["H+1 3"]`` or ``Tensor["B H+1 3"]``. The first point is
            the decision-state root pose and later points are selected rollout
            views.
        segment_valid_mask: Optional hard mask over path segments with shape
            ``Tensor["H"]`` or ``Tensor["B H"]``. Non-finite segments are
            ignored even when this mask is ``True``.

    Returns:
        Selected path length in metres per rollout. Paths with no finite valid
        segment return ``NaN`` rather than ``0`` so invalidity remains separate
        from acquisition cost.
    """

    centers, squeeze = _as_path_matrix(camera_centers_world)
    deltas = centers[:, 1:, :] - centers[:, :-1, :]
    segment_lengths = torch.linalg.vector_norm(deltas, dim=-1)
    valid = torch.isfinite(deltas).all(dim=-1) & torch.isfinite(segment_lengths)
    if segment_valid_mask is not None:
        valid = valid & torch.broadcast_to(
            segment_valid_mask.to(device=centers.device, dtype=torch.bool),
            segment_lengths.shape,
        )
    total = torch.where(valid, segment_lengths, torch.zeros_like(segment_lengths)).sum(dim=1)
    result = torch.where(valid.any(dim=1), total, torch.full_like(total, float("nan")))
    return result.squeeze(0) if squeeze else result


def candidate_masked_mean(values: Tensor, valid_mask: Tensor, *, dim: int = -1) -> Tensor:
    """Reduce candidate-table values with a hard validity mask.

    Args:
        values: Candidate metric tensor.
        valid_mask: Boolean mask broadcastable to `values`.
        dim: Candidate dimension to reduce.

    Returns:
        Mean over finite, valid entries. Empty reductions return ``NaN``.
    """

    valid = _finite_mask(values, valid_mask)
    masked_values = torch.where(valid, values, torch.zeros_like(values))
    count = valid.sum(dim=dim)
    total = masked_values.sum(dim=dim)
    return torch.where(count > 0, total / count.clamp_min(1), torch.full_like(total, float("nan")))


def candidate_best_value(values: Tensor, valid_mask: Tensor, *, dim: int = -1) -> Tensor:
    """Return the best finite candidate value under a hard mask.

    Args:
        values: Candidate metric tensor.
        valid_mask: Boolean mask broadcastable to `values`.
        dim: Candidate dimension to reduce.

    Returns:
        Max over finite, valid entries. Empty reductions return ``NaN``.
    """

    valid = _finite_mask(values, valid_mask)
    filled = torch.where(valid, values, torch.full_like(values, -torch.inf))
    best = filled.max(dim=dim).values
    return torch.where(torch.isfinite(best), best, torch.full_like(best, float("nan")))


def _as_step_matrix(values: Tensor) -> tuple[Tensor, bool]:
    if values.ndim == 1:
        return values.unsqueeze(0), True
    if values.ndim == 2:
        return values, False
    raise ValueError(f"Expected rollout tensor with shape (H,) or (B,H), got {tuple(values.shape)}.")


def _as_path_matrix(values: Tensor) -> tuple[Tensor, bool]:
    if values.ndim == 2 and values.shape[-1] == 3:
        return values.unsqueeze(0), True
    if values.ndim == 3 and values.shape[-1] == 3:
        return values, False
    raise ValueError(f"Expected path tensor with shape (H+1,3) or (B,H+1,3), got {tuple(values.shape)}.")


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


__all__ = [
    "TorchRolloutMetrics",
    "candidate_best_value",
    "candidate_masked_mean",
    "discounted_selected_return",
    "endpoint_log_gain_tensor",
    "endpoint_target_gain_tensor",
    "selected_path_length_tensor",
    "summarize_selected_rollout_tensors",
]
