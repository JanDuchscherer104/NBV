"""Stateful evaluation for differentiable multi-step rollout returns."""

from __future__ import annotations

import torch
from torch import Tensor
from torchmetrics import Metric as MetricBase

from .returns import summarize_selected_rollout_tensors


class SelectedRolloutMetrics(MetricBase):
    """Accumulate selected-action rollout metrics from tensor batches.

    The metric reports trajectory-level means for finite-horizon return
    ``return_h``, endpoint target gain, endpoint log-gain, valid selected steps,
    and endpoint validity. Trajectory-level aggregation avoids horizon-length
    bias and matches the proposal's policy comparison table.
    """

    full_state_update = False
    return_total: Tensor
    """``Tensor["", float32]`` sum of finite trajectory returns."""
    return_count: Tensor
    """``Tensor["", float32]`` number of finite trajectory returns."""
    endpoint_gain_total: Tensor
    """``Tensor["", float32]`` sum of finite endpoint target gains."""
    endpoint_gain_count: Tensor
    """``Tensor["", float32]`` number of finite endpoint target gains."""
    endpoint_log_gain_total: Tensor
    """``Tensor["", float32]`` sum of finite endpoint log gains."""
    endpoint_log_gain_count: Tensor
    """``Tensor["", float32]`` number of finite endpoint log gains."""
    valid_steps_total: Tensor
    """``Tensor["", float32]`` sum of hard-valid selected rollout steps."""
    rollout_count: Tensor
    """``Tensor["", float32]`` number of rollout trajectories presented."""
    valid_endpoint_count: Tensor
    """``Tensor["", float32]`` number of trajectories with valid endpoints."""

    def __init__(self, *, gamma: float = 1.0, eps: float = 1e-8) -> None:
        super().__init__()
        if gamma < 0.0:
            raise ValueError("gamma must be non-negative.")
        if eps < 0.0:
            raise ValueError("eps must be non-negative.")
        self.gamma = float(gamma)
        self.eps = float(eps)
        self.add_state("return_total", default=torch.zeros((), dtype=torch.float32), dist_reduce_fx="sum")
        self.add_state("return_count", default=torch.zeros((), dtype=torch.float32), dist_reduce_fx="sum")
        self.add_state("endpoint_gain_total", default=torch.zeros((), dtype=torch.float32), dist_reduce_fx="sum")
        self.add_state("endpoint_gain_count", default=torch.zeros((), dtype=torch.float32), dist_reduce_fx="sum")
        self.add_state("endpoint_log_gain_total", default=torch.zeros((), dtype=torch.float32), dist_reduce_fx="sum")
        self.add_state("endpoint_log_gain_count", default=torch.zeros((), dtype=torch.float32), dist_reduce_fx="sum")
        self.add_state("valid_steps_total", default=torch.zeros((), dtype=torch.float32), dist_reduce_fx="sum")
        self.add_state("rollout_count", default=torch.zeros((), dtype=torch.float32), dist_reduce_fx="sum")
        self.add_state("valid_endpoint_count", default=torch.zeros((), dtype=torch.float32), dist_reduce_fx="sum")

    def update(
        self,
        rewards: Tensor,
        initial_error: Tensor,
        final_error: Tensor,
        valid_mask: Tensor | None = None,
    ) -> None:
        """Accumulate one batch of selected target-rollout tensors.

        Args:
            rewards: ``Tensor["B H"]`` or ``Tensor["H"]`` selected rewards,
                normally root-normalized target gains.
            initial_error: Initial target point-mesh errors ``d_0``.
            final_error: Endpoint target point-mesh errors ``d_H``.
            valid_mask: Optional hard supervision mask over selected rewards.
        """

        summary = summarize_selected_rollout_tensors(
            rewards.to(device=self.return_total.device, dtype=torch.float32),
            initial_error.to(device=self.return_total.device, dtype=torch.float32),
            final_error.to(device=self.return_total.device, dtype=torch.float32),
            None if valid_mask is None else valid_mask.to(device=self.return_total.device),
            gamma=self.gamma,
            eps=self.eps,
        )
        returns = summary.discounted_return.reshape(-1).to(dtype=torch.float32)
        endpoint_gain = summary.endpoint_gain.reshape(-1).to(dtype=torch.float32)
        endpoint_log_gain = summary.endpoint_log_gain.reshape(-1).to(dtype=torch.float32)
        valid_steps = summary.valid_steps.reshape(-1).to(dtype=torch.float32)
        valid_endpoint = summary.valid_endpoint.reshape(-1).to(dtype=torch.bool)

        return_mask = torch.isfinite(returns)
        endpoint_gain_mask = torch.isfinite(endpoint_gain)
        endpoint_log_gain_mask = torch.isfinite(endpoint_log_gain)
        self.return_total = self.return_total + torch.where(return_mask, returns, torch.zeros_like(returns)).sum()
        self.return_count = self.return_count + return_mask.to(dtype=torch.float32).sum()
        self.endpoint_gain_total = (
            self.endpoint_gain_total
            + torch.where(endpoint_gain_mask, endpoint_gain, torch.zeros_like(endpoint_gain)).sum()
        )
        self.endpoint_gain_count = self.endpoint_gain_count + endpoint_gain_mask.to(dtype=torch.float32).sum()
        self.endpoint_log_gain_total = (
            self.endpoint_log_gain_total
            + torch.where(endpoint_log_gain_mask, endpoint_log_gain, torch.zeros_like(endpoint_log_gain)).sum()
        )
        self.endpoint_log_gain_count = (
            self.endpoint_log_gain_count + endpoint_log_gain_mask.to(dtype=torch.float32).sum()
        )
        self.valid_steps_total = self.valid_steps_total + valid_steps.sum()
        self.rollout_count = self.rollout_count + torch.tensor(
            float(valid_steps.numel()),
            device=self.rollout_count.device,
        )
        self.valid_endpoint_count = self.valid_endpoint_count + valid_endpoint.to(dtype=torch.float32).sum()

    def compute(self) -> dict[str, Tensor]:
        """Return aggregate rollout metrics with proposal-aligned keys."""

        return {
            "return_h": _safe_mean(self.return_total, self.return_count),
            "endpoint_gain": _safe_mean(self.endpoint_gain_total, self.endpoint_gain_count),
            "endpoint_log_gain": _safe_mean(self.endpoint_log_gain_total, self.endpoint_log_gain_count),
            "valid_steps": _safe_mean(self.valid_steps_total, self.rollout_count),
            "valid_endpoint_rate": _safe_mean(self.valid_endpoint_count, self.rollout_count),
        }


def _safe_mean(total: Tensor, count: Tensor) -> Tensor:
    return torch.where(count > 0, total / count.clamp_min(1.0), torch.full_like(total, float("nan")))


__all__ = ["SelectedRolloutMetrics"]
