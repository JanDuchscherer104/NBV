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

from .torch_rollout import (
    candidate_best_value,
    candidate_masked_mean,
    candidate_order_consistency,
    candidate_policy_entropy,
    selected_path_length_tensor,
    summarize_selected_rollout_tensors,
)


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


class SelectedPathCostMetrics(MetricBase):
    """Accumulate selected camera-center path cost in metres.

    The metric expects root-plus-selected camera centers in world coordinates
    and reports the finite mean path length. Invalid or non-finite path
    segments are ignored via a hard segment mask; fully invalid paths contribute
    no cost sample instead of contributing zero.
    """

    full_state_update = False

    def __init__(self) -> None:
        super().__init__()
        self.add_state("path_total", default=torch.zeros((), dtype=torch.float32), dist_reduce_fx="sum")
        self.add_state("path_count", default=torch.zeros((), dtype=torch.float32), dist_reduce_fx="sum")

    def update(self, camera_centers_world: Tensor, segment_valid_mask: Tensor | None = None) -> None:
        """Accumulate one batch of selected rollout paths.

        Args:
            camera_centers_world: ``Tensor["H+1 3"]`` or
                ``Tensor["B H+1 3"]`` camera centers in metres.
            segment_valid_mask: Optional hard mask over the ``H`` path
                segments. Masked or non-finite segments are excluded from the
                path sum.
        """

        path_lengths = selected_path_length_tensor(
            camera_centers_world.to(device=self.path_total.device, dtype=torch.float32),
            None if segment_valid_mask is None else segment_valid_mask.to(device=self.path_total.device),
        ).reshape(-1)
        valid = torch.isfinite(path_lengths)
        if not valid.any():
            return
        self.path_total = self.path_total + path_lengths[valid].sum()
        self.path_count = self.path_count + valid.to(dtype=torch.float32).sum()

    def compute(self) -> dict[str, Tensor]:
        """Return mean acquisition cost aliases for policy tables."""

        path_length = _safe_mean(self.path_total, self.path_count)
        return {"path_length_m": path_length, "cost": path_length}


class CandidateOrderConsistencyMetric(MetricBase):
    """Accumulate shuffled-candidate order-consistency diagnostics.

    This metric supports the proposal's requirement that finite candidate rows
    have no semantic ordering. It compares paired model scores from the same
    candidate table before and after a known gather-style permutation, then
    reports score agreement and top-1 stability over comparable valid tables.
    """

    full_state_update = False

    def __init__(self) -> None:
        super().__init__()
        self.add_state("mae_total", default=torch.zeros((), dtype=torch.float32), dist_reduce_fx="sum")
        self.add_state("mae_count", default=torch.zeros((), dtype=torch.float32), dist_reduce_fx="sum")
        self.add_state("top1_match_count", default=torch.zeros((), dtype=torch.float32), dist_reduce_fx="sum")
        self.add_state("valid_table_count", default=torch.zeros((), dtype=torch.float32), dist_reduce_fx="sum")
        self.add_state("table_count", default=torch.zeros((), dtype=torch.float32), dist_reduce_fx="sum")

    def update(
        self,
        scores: Tensor,
        shuffled_scores: Tensor,
        permutation: Tensor,
        valid_mask: Tensor | None = None,
        shuffled_valid_mask: Tensor | None = None,
        *,
        dim: int = -1,
    ) -> None:
        """Accumulate one paired original/shuffled candidate-score batch."""

        consistency = candidate_order_consistency(
            scores.to(device=self.mae_total.device, dtype=torch.float32),
            shuffled_scores.to(device=self.mae_total.device, dtype=torch.float32),
            permutation.to(device=self.mae_total.device, dtype=torch.long),
            None if valid_mask is None else valid_mask.to(device=self.mae_total.device),
            None if shuffled_valid_mask is None else shuffled_valid_mask.to(device=self.mae_total.device),
            dim=dim,
        )
        score_mae = consistency.score_mae.reshape(-1)
        valid_table = consistency.valid_table.reshape(-1)
        top1_match = consistency.top1_match.reshape(-1) & valid_table
        finite_mae = torch.isfinite(score_mae) & valid_table
        if finite_mae.any():
            self.mae_total = self.mae_total + score_mae[finite_mae].sum()
            self.mae_count = self.mae_count + finite_mae.to(dtype=torch.float32).sum()
        self.top1_match_count = self.top1_match_count + top1_match.to(dtype=torch.float32).sum()
        self.valid_table_count = self.valid_table_count + valid_table.to(dtype=torch.float32).sum()
        self.table_count = self.table_count + torch.tensor(float(valid_table.numel()), device=self.table_count.device)

    def compute(self) -> dict[str, Tensor]:
        """Return shuffled-candidate consistency diagnostics."""

        return {
            "candidate_order_score_mae": _safe_mean(self.mae_total, self.mae_count),
            "candidate_order_top1_match_rate": _safe_mean(self.top1_match_count, self.valid_table_count),
            "candidate_order_valid_table_rate": _safe_mean(self.valid_table_count, self.table_count),
        }


class CandidatePolicyEntropyMetric(MetricBase):
    """Accumulate masked candidate-policy entropy diagnostics.

    The metric summarizes selection diversity for finite candidate tables. It
    consumes probabilities or probability-like weights, delegates masking and
    renormalization to `candidate_policy_entropy`, and reports the finite mean
    entropy. Invalid candidates affect entropy support only; invalidity remains
    owned by `CandidateTableMetrics`.
    """

    full_state_update = False

    def __init__(self) -> None:
        super().__init__()
        self.add_state("entropy_total", default=torch.zeros((), dtype=torch.float32), dist_reduce_fx="sum")
        self.add_state("entropy_count", default=torch.zeros((), dtype=torch.float32), dist_reduce_fx="sum")

    def update(
        self,
        selection_probabilities: Tensor,
        valid_mask: Tensor | None = None,
        *,
        dim: int = -1,
    ) -> None:
        """Accumulate one batch of candidate selection probabilities."""

        entropy = candidate_policy_entropy(
            selection_probabilities.to(device=self.entropy_total.device, dtype=torch.float32),
            None if valid_mask is None else valid_mask.to(device=self.entropy_total.device),
            dim=dim,
        ).reshape(-1)
        finite = torch.isfinite(entropy)
        if not finite.any():
            return
        self.entropy_total = self.entropy_total + entropy[finite].sum()
        self.entropy_count = self.entropy_count + finite.to(dtype=torch.float32).sum()

    def compute(self) -> Tensor:
        """Return mean entropy or ``NaN`` when no table had positive mass."""

        return _safe_mean(self.entropy_total, self.entropy_count)


class PolicyTableMetrics(MetricBase):
    """Accumulate proposal policy-comparison table metrics.

    The thesis policy table reports target endpoint gain, finite-horizon return,
    scene RRI, cost, invalidity, runtime, and coverage for each policy row. This
    composite metric keeps those columns under one TorchMetric interface while
    delegating the actual math to the smaller metric owners in this module.
    Candidate invalidity is the hard-mask invalid fraction from
    `CandidateTableMetrics`; it is never inferred from low values or low RRI.
    """

    full_state_update = False

    def __init__(self, *, gamma: float = 1.0, eps: float = 1e-8) -> None:
        super().__init__()
        self.selected = SelectedRolloutMetrics(gamma=gamma, eps=eps)
        self.scene_rri = FiniteMeanMetric()
        self.cost = FiniteMeanMetric()
        self.runtime = FiniteMeanMetric()
        self.coverage = FiniteMeanMetric()
        self.candidates = CandidateTableMetrics()

    def update(
        self,
        rewards: Tensor,
        initial_error: Tensor,
        final_error: Tensor,
        *,
        selected_valid_mask: Tensor | None = None,
        scene_rri: Tensor | None = None,
        cost: Tensor | None = None,
        selected_camera_centers_world: Tensor | None = None,
        selected_path_segment_valid_mask: Tensor | None = None,
        runtime: Tensor | None = None,
        coverage: Tensor | None = None,
        scalar_valid_mask: Tensor | None = None,
        candidate_values: Tensor | None = None,
        candidate_valid_mask: Tensor | None = None,
        candidate_dim: int = -1,
    ) -> None:
        """Accumulate one batch of policy-table tensors.

        Args:
            rewards: Selected target rewards ``Tensor["B H"]`` or
                ``Tensor["H"]``.
            initial_error: Initial target point-mesh errors ``d_0``.
            final_error: Endpoint target point-mesh errors ``d_H``.
            selected_valid_mask: Optional hard mask for selected rewards.
            scene_rri: Optional scene-level RRI values for the same policy row.
            cost: Optional acquisition or path-cost values.
            selected_camera_centers_world: Optional root-plus-selected camera
                centers ``Tensor["B H+1 3"]`` or ``Tensor["H+1 3"]`` used to
                derive path cost when ``cost`` is omitted.
            selected_path_segment_valid_mask: Optional hard mask over the
                selected path segments. Requires ``selected_camera_centers_world``.
            runtime: Optional runtime values, normally seconds.
            coverage: Optional scene/target coverage values.
            scalar_valid_mask: Optional mask for scalar columns only.
            candidate_values: Optional finite candidate table values used for
                value diagnostics.
            candidate_valid_mask: Optional hard candidate validity mask.
            candidate_dim: Candidate axis for candidate-table reductions.
        """

        self.selected.update(rewards, initial_error, final_error, selected_valid_mask)
        if selected_path_segment_valid_mask is not None and selected_camera_centers_world is None:
            raise ValueError("selected_path_segment_valid_mask requires selected_camera_centers_world.")
        if cost is None and selected_camera_centers_world is not None:
            cost = selected_path_length_tensor(
                selected_camera_centers_world.to(device=self.cost.total.device, dtype=torch.float32),
                None
                if selected_path_segment_valid_mask is None
                else selected_path_segment_valid_mask.to(device=self.cost.total.device),
            )
        for metric, values in (
            (self.scene_rri, scene_rri),
            (self.cost, cost),
            (self.runtime, runtime),
            (self.coverage, coverage),
        ):
            if values is not None:
                metric.update(values, scalar_valid_mask)
        if candidate_values is not None or candidate_valid_mask is not None:
            if candidate_values is None or candidate_valid_mask is None:
                raise ValueError("candidate_values and candidate_valid_mask must be provided together.")
            self.candidates.update(candidate_values, candidate_valid_mask, dim=candidate_dim)

    def compute(self) -> dict[str, Tensor]:
        """Return proposal table columns plus candidate diagnostics."""

        selected = self.selected.compute()
        candidates = self.candidates.compute()
        return {
            "endpoint_gain": selected["endpoint_gain"],
            "return_h": selected["return_h"],
            "scene_rri": self.scene_rri.compute(),
            "cost": self.cost.compute(),
            "invalidity": candidates["candidate_invalid_rate"],
            "runtime": self.runtime.compute(),
            "coverage": self.coverage.compute(),
            "endpoint_log_gain": selected["endpoint_log_gain"],
            "valid_steps": selected["valid_steps"],
            "valid_endpoint_rate": selected["valid_endpoint_rate"],
            "candidate_valid_rate": candidates["candidate_valid_rate"],
            "candidate_value_mean": candidates["candidate_value_mean"],
            "candidate_best_value": candidates["candidate_best_value"],
        }


def _safe_mean(total: Tensor, count: Tensor) -> Tensor:
    return torch.where(count > 0, total / count.clamp_min(1.0), torch.full_like(total, float("nan")))


__all__ = [
    "CandidateTableMetrics",
    "CandidateOrderConsistencyMetric",
    "CandidatePolicyEntropyMetric",
    "FiniteMeanMetric",
    "PolicyTableMetrics",
    "SelectedPathCostMetrics",
    "SelectedRolloutMetrics",
]
