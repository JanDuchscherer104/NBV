"""Stateful TorchMetrics for target-conditioned rollout evaluation.

`aria_nbv.rri_metrics.torch_rollout` owns pure tensor reducers. This module
wraps those reducers in `torchmetrics.Metric` classes for Lightning, batched
evaluation scripts, and future Q_H diagnostics. The stateful classes keep the
proposal's hard-mask semantics: invalid candidates are ignored or counted as
invalidity diagnostics, never converted into low-reward labels.
"""

from __future__ import annotations

import torch
from torch import Tensor
from torchmetrics import Metric as MetricBase

from .torch_rollout import candidate_best_value, candidate_masked_mean, summarize_selected_rollout_tensors


class FiniteMeanMetric(MetricBase):
    """Accumulate a finite mean for scalar policy-table metrics.

    This generic metric covers proposal-table columns such as scene RRI, action
    cost, runtime, and coverage once those values are already represented as
    tensors. Non-finite values and entries masked out by ``valid_mask`` are
    ignored; empty updates compute to ``NaN`` instead of silently reporting zero.
    """

    full_state_update = False

    def __init__(self) -> None:
        super().__init__()
        self.add_state("total", default=torch.zeros((), dtype=torch.float32), dist_reduce_fx="sum")
        self.add_state("count", default=torch.zeros((), dtype=torch.float32), dist_reduce_fx="sum")

    def update(self, values: Tensor, valid_mask: Tensor | None = None) -> None:
        """Accumulate finite values under an optional validity mask."""

        values_f = values.to(device=self.total.device, dtype=torch.float32)
        valid = torch.isfinite(values_f)
        if valid_mask is not None:
            mask = torch.broadcast_to(valid_mask.to(device=self.total.device, dtype=torch.bool), values_f.shape)
            valid = valid & mask
        if not valid.any():
            return
        self.total = self.total + values_f[valid].sum()
        self.count = self.count + valid.to(dtype=torch.float32).sum().to(device=self.count.device)

    def compute(self) -> Tensor:
        """Return the finite mean or ``NaN`` when no values were accumulated."""

        return _safe_mean(self.total, self.count)


class SelectedRolloutMetrics(MetricBase):
    """Accumulate selected-action rollout metrics from tensor batches.

    The metric reports trajectory-level means for finite-horizon return
    ``return_h``, endpoint target gain, endpoint log-gain, valid selected steps,
    and endpoint validity. Trajectory-level aggregation avoids horizon-length
    bias and matches the proposal's policy comparison table.
    """

    full_state_update = False

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


class CandidateTableMetrics(MetricBase):
    """Accumulate hard-mask candidate-table diagnostics.

    The metric reports valid/invalid fractions and validity-aware value
    summaries over finite candidate tables. Invalid rows affect invalidity
    diagnostics but never enter the value mean or best-value mean.
    """

    full_state_update = False

    def __init__(self) -> None:
        super().__init__()
        self.add_state("valid_count", default=torch.zeros((), dtype=torch.float32), dist_reduce_fx="sum")
        self.add_state("total_count", default=torch.zeros((), dtype=torch.float32), dist_reduce_fx="sum")
        self.add_state("mean_total", default=torch.zeros((), dtype=torch.float32), dist_reduce_fx="sum")
        self.add_state("mean_count", default=torch.zeros((), dtype=torch.float32), dist_reduce_fx="sum")
        self.add_state("best_total", default=torch.zeros((), dtype=torch.float32), dist_reduce_fx="sum")
        self.add_state("best_count", default=torch.zeros((), dtype=torch.float32), dist_reduce_fx="sum")

    def update(self, values: Tensor, valid_mask: Tensor, *, dim: int = -1) -> None:
        """Accumulate validity-aware candidate table summaries.

        Args:
            values: Candidate values such as rewards, Q estimates, or coverage.
            valid_mask: Boolean hard-validity mask broadcastable to ``values``.
            dim: Candidate dimension reduced inside each table.
        """

        values_f = values.to(device=self.valid_count.device, dtype=torch.float32)
        mask = torch.broadcast_to(valid_mask.to(device=self.valid_count.device, dtype=torch.bool), values_f.shape)
        valid = torch.isfinite(values_f) & mask
        self.valid_count = self.valid_count + valid.to(dtype=torch.float32).sum()
        self.total_count = self.total_count + torch.tensor(float(mask.numel()), device=self.total_count.device)

        means = candidate_masked_mean(values_f, mask, dim=dim).reshape(-1)
        best = candidate_best_value(values_f, mask, dim=dim).reshape(-1)
        mean_valid = torch.isfinite(means)
        best_valid = torch.isfinite(best)
        self.mean_total = self.mean_total + torch.where(mean_valid, means, torch.zeros_like(means)).sum()
        self.mean_count = self.mean_count + mean_valid.to(dtype=torch.float32).sum()
        self.best_total = self.best_total + torch.where(best_valid, best, torch.zeros_like(best)).sum()
        self.best_count = self.best_count + best_valid.to(dtype=torch.float32).sum()

    def compute(self) -> dict[str, Tensor]:
        """Return candidate validity and value diagnostics."""

        valid_rate = _safe_mean(self.valid_count, self.total_count)
        return {
            "candidate_valid_rate": valid_rate,
            "candidate_invalid_rate": 1.0 - valid_rate,
            "candidate_value_mean": _safe_mean(self.mean_total, self.mean_count),
            "candidate_best_value": _safe_mean(self.best_total, self.best_count),
        }


def _safe_mean(total: Tensor, count: Tensor) -> Tensor:
    return torch.where(count > 0, total / count.clamp_min(1.0), torch.full_like(total, float("nan")))


__all__ = [
    "CandidateTableMetrics",
    "FiniteMeanMetric",
    "SelectedRolloutMetrics",
]
