"""Operational validity, provenance, path, and policy audits for rollouts.

These reducers are evaluation-only. They inspect replay/store behavior and are
not reconstruction metrics or training objectives.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import torch
from torch import Tensor
from torchmetrics import Metric as MetricBase


@dataclass(frozen=True, slots=True)
class CandidateOrderConsistency:
    """Per-table diagnostics for shuffled-candidate consistency.

    Attributes:
        score_mae: ``Tensor["B"]`` mean absolute score difference after
            inverse-aligning shuffled predictions to the original candidate
            order.
        top1_match: ``Tensor["B"]`` boolean indicator that the best valid
            candidate index is unchanged by shuffling.
        valid_table: ``Tensor["B"]`` boolean indicator that a table had at
            least one comparable valid candidate.
    """

    score_mae: Tensor
    top1_match: Tensor
    valid_table: Tensor


@dataclass(frozen=True, slots=True)
class CandidatePathIncrementStats:
    """Per-table movement-cost diagnostics for candidate action rows.

    The rollout replay contract stores each candidate row's path increment,
    currently persisted as ``motion_step_length_m`` in rollout diagnostics.
    These statistics summarize that candidate-set cost distribution without
    changing the selected policy cost column.

    Attributes:
        mean_m: ``Tensor["B"]`` mean finite path increment in metres.
        min_m: ``Tensor["B"]`` minimum finite path increment in metres.
        max_m: ``Tensor["B"]`` maximum finite path increment in metres.
        valid_table: ``Tensor["B"]`` mask for tables with at least one finite
            hard-valid path increment.
    """

    mean_m: Tensor
    min_m: Tensor
    max_m: Tensor
    valid_table: Tensor


@dataclass(frozen=True, slots=True)
class CandidatePrimaryInvalidReasonStats:
    """Per-table primary invalid-reason share among rejected candidate rows.

    Rollout replay tables persist the complete invalidity bitset and one
    priority-selected ``primary_invalid_reason`` per candidate row. This
    diagnostic intentionally consumes only the primary reason field; use the
    bitset arrays when auditing overlapping reason vectors.

    Attributes:
        share_of_invalid: ``Tensor["B"]`` fraction of hard-invalid candidate
            rows whose primary reason belongs to the configured reason group.
        valid_table: ``Tensor["B"]`` mask for tables with at least one
            hard-invalid candidate row and therefore a meaningful denominator.
    """

    share_of_invalid: Tensor
    valid_table: Tensor


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


def candidate_order_consistency(
    scores: Tensor,
    shuffled_scores: Tensor,
    permutation: Tensor,
    valid_mask: Tensor | None = None,
    shuffled_valid_mask: Tensor | None = None,
    *,
    dim: int = -1,
) -> CandidateOrderConsistency:
    """Compare candidate scores before and after a candidate-order shuffle.

    Args:
        scores: Original candidate scores.
        shuffled_scores: Scores from the same candidate table after shuffling.
        permutation: Gather-style permutation where
            ``shuffled_scores[..., j]`` corresponds to
            ``scores[..., permutation[..., j]]`` along `dim`.
        valid_mask: Optional hard-validity mask for `scores`.
        shuffled_valid_mask: Optional hard-validity mask for `shuffled_scores`.
            If omitted, `valid_mask` is gathered through `permutation`.
        dim: Candidate dimension.

    Returns:
        `CandidateOrderConsistency` with per-table score MAE, top-1 agreement,
        and valid-table mask. Empty comparable tables report ``NaN`` MAE and
        ``False`` top-1 agreement.
    """

    if dim < 0:
        dim = scores.ndim + dim
    if scores.shape != shuffled_scores.shape:
        raise ValueError(
            f"Expected score shapes to match, got {tuple(scores.shape)} and {tuple(shuffled_scores.shape)}."
        )
    if permutation.shape != scores.shape:
        raise ValueError(f"Expected permutation shape {tuple(scores.shape)}, got {tuple(permutation.shape)}.")
    if dim != scores.ndim - 1:
        scores = scores.movedim(dim, -1)
        shuffled_scores = shuffled_scores.movedim(dim, -1)
        permutation = permutation.movedim(dim, -1)
        if valid_mask is not None:
            valid_mask = valid_mask.movedim(dim, -1)
        if shuffled_valid_mask is not None:
            shuffled_valid_mask = shuffled_valid_mask.movedim(dim, -1)

    original, squeeze = _as_candidate_matrix(scores)
    shuffled, _ = _as_candidate_matrix(shuffled_scores)
    perm, _ = _as_candidate_matrix(permutation.to(device=original.device, dtype=torch.long))
    if perm.min().item() < 0 or perm.max().item() >= original.shape[-1]:
        raise ValueError("permutation contains indices outside the candidate dimension.")

    aligned_shuffled = torch.empty_like(shuffled)
    aligned_shuffled.scatter_(dim=-1, index=perm, src=shuffled)
    original_valid = _candidate_valid_matrix(original, valid_mask)
    if shuffled_valid_mask is None:
        shuffled_valid = torch.gather(original_valid, dim=-1, index=perm)
    else:
        shuffled_valid = _candidate_valid_matrix(shuffled, shuffled_valid_mask)
    aligned_shuffled_valid = torch.empty_like(shuffled_valid)
    aligned_shuffled_valid.scatter_(dim=-1, index=perm, src=shuffled_valid)

    comparable = original_valid & aligned_shuffled_valid & torch.isfinite(aligned_shuffled)
    abs_diff = (original - aligned_shuffled).abs()
    total = torch.where(comparable, abs_diff, torch.zeros_like(abs_diff)).sum(dim=-1)
    count = comparable.to(dtype=torch.float32).sum(dim=-1)
    score_mae = torch.where(count > 0, total / count.clamp_min(1.0), torch.full_like(total, float("nan")))
    original_top = _masked_argmax(original, original_valid)
    aligned_top = _masked_argmax(aligned_shuffled, aligned_shuffled_valid)
    valid_table = count > 0
    top1_match = valid_table & (original_top == aligned_top)
    if squeeze:
        return CandidateOrderConsistency(
            score_mae=score_mae.squeeze(0),
            top1_match=top1_match.squeeze(0),
            valid_table=valid_table.squeeze(0),
        )
    return CandidateOrderConsistency(score_mae=score_mae, top1_match=top1_match, valid_table=valid_table)


def candidate_policy_entropy(
    selection_probabilities: Tensor,
    valid_mask: Tensor | None = None,
    *,
    dim: int = -1,
) -> Tensor:
    """Compute masked per-table entropy from candidate selection probabilities.

    This is the torch-native counterpart to rollout-store inspection entropy.
    It accepts probabilities before or after normalization, filters hard-invalid
    rows plus non-finite and non-positive entries, renormalizes over the
    candidate axis, and returns ``NaN`` for tables with no positive finite mass.

    Args:
        selection_probabilities: Candidate selection probabilities or
            probability-like non-negative weights.
        valid_mask: Optional hard-validity mask broadcastable to
            ``selection_probabilities``.
        dim: Candidate dimension.

    Returns:
        Entropy per candidate table after reducing `dim`.
    """

    values = selection_probabilities.to(dtype=torch.float32)
    valid = torch.isfinite(values) & (values > 0.0)
    if valid_mask is not None:
        valid = valid & torch.broadcast_to(valid_mask.to(device=values.device, dtype=torch.bool), values.shape)
    positive = torch.where(valid, values, torch.zeros_like(values))
    mass = positive.sum(dim=dim, keepdim=True)
    normalized = torch.where(mass > 0.0, positive / mass.clamp_min(torch.finfo(positive.dtype).tiny), positive)
    entropy_terms = torch.where(normalized > 0.0, normalized * normalized.log(), torch.zeros_like(normalized))
    entropy = -entropy_terms.sum(dim=dim)
    return torch.where(mass.squeeze(dim) > 0.0, entropy, torch.full_like(entropy, float("nan")))


def candidate_provenance_share(
    strategy_ids: Tensor,
    position_ids: Tensor,
    *,
    strategy_family_ids: Sequence[int] | Tensor = (),
    position_family_ids: Sequence[int] | Tensor = (),
    valid_mask: Tensor | None = None,
    dim: int = -1,
) -> Tensor:
    """Compute per-table share of candidates from selected provenance families.

    Candidate generation stores view-direction provenance (`strategy_ids`) and
    position-family provenance (`position_ids`) separately. This helper reports
    the fraction of hard-valid rows whose strategy or position id belongs to the
    requested family sets. It is intentionally id-based so rollout stores can
    compute radial/backtrack diagnostics from persisted tensors without
    importing pose-generation enums.

    Args:
        strategy_ids: Stable view-direction ids, such as radial-away or
            radial-towards strategy ids.
        position_ids: Stable position-family ids aligned with `strategy_ids`,
            such as the revisit-backtrack position id.
        strategy_family_ids: Strategy ids counted as part of the audited
            family. Empty means no strategy id contributes.
        position_family_ids: Position ids counted as part of the audited
            family. Empty means no position id contributes.
        valid_mask: Optional hard candidate validity mask. Rows with only
            negative placeholder provenance ids are excluded from the
            denominator.
        dim: Candidate dimension reduced inside each table.

    Returns:
        Share tensor after reducing `dim`. Tables with no non-placeholder
        provenance rows return ``NaN`` so missing provenance is not reported as
        zero diversity.
    """

    if strategy_ids.shape != position_ids.shape:
        raise ValueError(
            "Expected strategy_ids and position_ids to have matching shapes, "
            f"got {tuple(strategy_ids.shape)} and {tuple(position_ids.shape)}.",
        )
    if dim < 0:
        dim = strategy_ids.ndim + dim
    if dim < 0 or dim >= strategy_ids.ndim:
        raise ValueError(f"dim={dim} is outside tensor rank {strategy_ids.ndim}.")

    strategy = strategy_ids.to(dtype=torch.long)
    position = position_ids.to(device=strategy.device, dtype=torch.long)
    if dim != strategy.ndim - 1:
        strategy = strategy.movedim(dim, -1)
        position = position.movedim(dim, -1)
        if valid_mask is not None:
            valid_mask = valid_mask.movedim(dim, -1)

    hard_valid = (strategy >= 0) | (position >= 0)
    if valid_mask is not None:
        hard_valid = hard_valid & torch.broadcast_to(
            valid_mask.to(device=strategy.device, dtype=torch.bool), strategy.shape
        )

    selected = _id_membership(strategy, strategy_family_ids) | _id_membership(position, position_family_ids)
    selected = selected & hard_valid
    numerator = selected.to(dtype=torch.float32).sum(dim=-1)
    denominator = hard_valid.to(dtype=torch.float32).sum(dim=-1)
    return torch.where(
        denominator > 0, numerator / denominator.clamp_min(1.0), torch.full_like(numerator, float("nan"))
    )


def candidate_path_increment_stats(
    path_increment_m: Tensor,
    valid_mask: Tensor,
    *,
    dim: int = -1,
) -> CandidatePathIncrementStats:
    """Summarize per-candidate path increments under the hard action mask.

    Args:
        path_increment_m: Candidate movement cost in metres, usually rollout
            diagnostic ``motion_step_length_m``.
        valid_mask: Boolean hard-validity mask broadcastable to
            ``path_increment_m``. Invalid rows are excluded from all statistics
            rather than treated as zero-cost actions.
        dim: Candidate dimension reduced inside each table.

    Returns:
        `CandidatePathIncrementStats` with per-table mean/min/max increments.
        Empty tables return ``NaN`` statistics and ``valid_table=False``.
    """

    if dim < 0:
        dim = path_increment_m.ndim + dim
    if dim < 0 or dim >= path_increment_m.ndim:
        raise ValueError(f"dim={dim} is outside tensor rank {path_increment_m.ndim}.")

    increments = path_increment_m.to(dtype=torch.float32)
    hard_mask = torch.broadcast_to(valid_mask.to(device=increments.device, dtype=torch.bool), increments.shape)
    if dim != increments.ndim - 1:
        increments = increments.movedim(dim, -1)
        hard_mask = hard_mask.movedim(dim, -1)

    valid = hard_mask & torch.isfinite(increments)
    count = valid.to(dtype=torch.float32).sum(dim=-1)
    total = torch.where(valid, increments, torch.zeros_like(increments)).sum(dim=-1)
    mean = total / count.clamp_min(1.0)

    min_filled = torch.where(valid, increments, torch.full_like(increments, torch.inf))
    max_filled = torch.where(valid, increments, torch.full_like(increments, -torch.inf))
    min_m = min_filled.min(dim=-1).values
    max_m = max_filled.max(dim=-1).values
    valid_table = count > 0
    nan = torch.full_like(mean, float("nan"))
    return CandidatePathIncrementStats(
        mean_m=torch.where(valid_table, mean, nan),
        min_m=torch.where(valid_table, min_m, nan),
        max_m=torch.where(valid_table, max_m, nan),
        valid_table=valid_table,
    )


def candidate_primary_invalid_reason_share(
    primary_invalid_reason: Tensor,
    valid_mask: Tensor,
    *,
    reason_ids: Sequence[int] | Tensor,
    dim: int = -1,
) -> CandidatePrimaryInvalidReasonStats:
    """Summarize primary invalid-reason concentration among rejected rows.

    Args:
        primary_invalid_reason: Stable primary invalid-reason ids aligned with
            the candidate table, typically ``candidates/primary_invalid_reason``.
        valid_mask: Boolean hard-validity mask where ``True`` marks valid
            policy actions. Valid rows are excluded from both numerator and
            denominator.
        reason_ids: Reason ids counted as the audited group. The sequence must
            be non-empty so the metric identity is explicit at construction.
        dim: Candidate dimension reduced inside each table.

    Returns:
        `CandidatePrimaryInvalidReasonStats` whose share is measured over
        invalid rows only. Tables with no invalid rows report ``NaN`` and
        ``valid_table=False``.
    """

    if isinstance(reason_ids, Tensor):
        ids = reason_ids.reshape(-1)
    else:
        ids = torch.as_tensor(tuple(reason_ids), dtype=torch.long).reshape(-1)
    if ids.numel() == 0:
        raise ValueError("reason_ids must contain at least one primary invalid-reason id.")
    if dim < 0:
        dim = primary_invalid_reason.ndim + dim
    if dim < 0 or dim >= primary_invalid_reason.ndim:
        raise ValueError(f"dim={dim} is outside tensor rank {primary_invalid_reason.ndim}.")

    reasons = primary_invalid_reason.to(dtype=torch.long)
    hard_valid = torch.broadcast_to(valid_mask.to(device=reasons.device, dtype=torch.bool), reasons.shape)
    ids = ids.to(device=reasons.device, dtype=reasons.dtype)
    if dim != reasons.ndim - 1:
        reasons = reasons.movedim(dim, -1)
        hard_valid = hard_valid.movedim(dim, -1)

    invalid_rows = ~hard_valid
    selected = invalid_rows & _id_membership(reasons, ids)
    numerator = selected.to(dtype=torch.float32).sum(dim=-1)
    denominator = invalid_rows.to(dtype=torch.float32).sum(dim=-1)
    valid_table = denominator > 0
    share = numerator / denominator.clamp_min(1.0)
    return CandidatePrimaryInvalidReasonStats(
        share_of_invalid=torch.where(valid_table, share, torch.full_like(share, float("nan"))),
        valid_table=valid_table,
    )


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


def _as_path_matrix(values: Tensor) -> tuple[Tensor, bool]:
    if values.ndim == 2 and values.shape[-1] == 3:
        return values.unsqueeze(0), True
    if values.ndim == 3 and values.shape[-1] == 3:
        return values, False
    raise ValueError(f"Expected path tensor with shape (H+1,3) or (B,H+1,3), got {tuple(values.shape)}.")


def _as_candidate_matrix(values: Tensor) -> tuple[Tensor, bool]:
    if values.ndim == 1:
        return values.unsqueeze(0), True
    if values.ndim == 2:
        return values, False
    raise ValueError(f"Expected candidate tensor with shape (N,) or (B,N), got {tuple(values.shape)}.")


def _candidate_valid_matrix(values: Tensor, valid_mask: Tensor | None) -> Tensor:
    valid = torch.isfinite(values)
    if valid_mask is None:
        return valid
    mask = torch.broadcast_to(valid_mask.to(device=values.device, dtype=torch.bool), values.shape)
    return valid & mask


def _masked_argmax(values: Tensor, valid_mask: Tensor) -> Tensor:
    filled = torch.where(valid_mask, values, torch.full_like(values, -torch.inf))
    return filled.argmax(dim=-1)


def _finite_mask(values: Tensor, valid_mask: Tensor | None) -> Tensor:
    valid = torch.isfinite(values)
    if valid_mask is None:
        return valid
    mask = torch.broadcast_to(valid_mask.to(device=values.device, dtype=torch.bool), values.shape)
    return valid & mask


def _id_membership(values: Tensor, family_ids: Sequence[int] | Tensor) -> Tensor:
    if isinstance(family_ids, Tensor):
        ids = family_ids.to(device=values.device, dtype=values.dtype).reshape(-1)
    else:
        ids = torch.as_tensor(tuple(family_ids), device=values.device, dtype=values.dtype).reshape(-1)
    if ids.numel() == 0:
        return torch.zeros_like(values, dtype=torch.bool)
    return (values.unsqueeze(-1) == ids).any(dim=-1)


class CandidateTableMetrics(MetricBase):
    """Accumulate hard-mask candidate-table diagnostics.

    The metric reports valid/invalid fractions and validity-aware value
    summaries over finite candidate tables. Invalid rows affect invalidity
    diagnostics but never enter the value mean or best-value mean.
    """

    full_state_update = False
    valid_count: Tensor
    """``Tensor["", float32]`` number of hard-valid candidate rows."""
    total_count: Tensor
    """``Tensor["", float32]`` number of candidate rows presented."""
    mean_total: Tensor
    """``Tensor["", float32]`` sum of finite per-table candidate means."""
    mean_count: Tensor
    """``Tensor["", float32]`` number of finite per-table candidate means."""
    best_total: Tensor
    """``Tensor["", float32]`` sum of finite per-table best values."""
    best_count: Tensor
    """``Tensor["", float32]`` number of finite per-table best values."""

    def __init__(self) -> None:
        super().__init__()
        self.add_state("valid_count", default=torch.zeros((), dtype=torch.float32), dist_reduce_fx="sum")
        self.add_state("total_count", default=torch.zeros((), dtype=torch.float32), dist_reduce_fx="sum")
        self.add_state("mean_total", default=torch.zeros((), dtype=torch.float32), dist_reduce_fx="sum")
        self.add_state("mean_count", default=torch.zeros((), dtype=torch.float32), dist_reduce_fx="sum")
        self.add_state("best_total", default=torch.zeros((), dtype=torch.float32), dist_reduce_fx="sum")
        self.add_state("best_count", default=torch.zeros((), dtype=torch.float32), dist_reduce_fx="sum")

    def update_validity(self, valid_mask: Tensor) -> None:
        """Accumulate candidate hard-mask validity without value summaries."""

        mask = valid_mask.to(device=self.valid_count.device, dtype=torch.bool)
        self.valid_count = self.valid_count + mask.to(dtype=torch.float32).sum()
        self.total_count = self.total_count + torch.tensor(float(mask.numel()), device=self.total_count.device)

    def update(self, values: Tensor, valid_mask: Tensor, *, dim: int = -1) -> None:
        """Accumulate validity-aware candidate table summaries.

        Args:
            values: Candidate values such as rewards, Q estimates, or coverage.
            valid_mask: Boolean hard-validity mask broadcastable to ``values``.
            dim: Candidate dimension reduced inside each table.
        """

        values_f = values.to(device=self.valid_count.device, dtype=torch.float32)
        mask = torch.broadcast_to(valid_mask.to(device=self.valid_count.device, dtype=torch.bool), values_f.shape)
        self.update_validity(mask)

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


class CandidatePathIncrementMetric(MetricBase):
    """Accumulate candidate action path-increment diagnostics in metres.

    The metric summarizes the per-table distribution of hard-valid candidate
    movement costs, usually sourced from rollout ``motion_step_length_m`` rows.
    It is separate from selected policy cost: this class describes the action
    set offered to the policy, not the action the policy selected.
    """

    full_state_update = False
    mean_total: Tensor
    """``Tensor["", float32]`` sum of finite table mean increments."""
    mean_count: Tensor
    """``Tensor["", float32]`` number of finite table mean increments."""
    min_total: Tensor
    """``Tensor["", float32]`` sum of finite table minimum increments."""
    min_count: Tensor
    """``Tensor["", float32]`` number of finite table minimum increments."""
    max_total: Tensor
    """``Tensor["", float32]`` sum of finite table maximum increments."""
    max_count: Tensor
    """``Tensor["", float32]`` number of finite table maximum increments."""
    valid_table_count: Tensor
    """``Tensor["", float32]`` number of tables with finite increments."""
    table_count: Tensor
    """``Tensor["", float32]`` number of candidate tables presented."""

    def __init__(self) -> None:
        super().__init__()
        self.add_state("mean_total", default=torch.zeros((), dtype=torch.float32), dist_reduce_fx="sum")
        self.add_state("mean_count", default=torch.zeros((), dtype=torch.float32), dist_reduce_fx="sum")
        self.add_state("min_total", default=torch.zeros((), dtype=torch.float32), dist_reduce_fx="sum")
        self.add_state("min_count", default=torch.zeros((), dtype=torch.float32), dist_reduce_fx="sum")
        self.add_state("max_total", default=torch.zeros((), dtype=torch.float32), dist_reduce_fx="sum")
        self.add_state("max_count", default=torch.zeros((), dtype=torch.float32), dist_reduce_fx="sum")
        self.add_state("valid_table_count", default=torch.zeros((), dtype=torch.float32), dist_reduce_fx="sum")
        self.add_state("table_count", default=torch.zeros((), dtype=torch.float32), dist_reduce_fx="sum")

    def update(
        self,
        path_increment_m: Tensor,
        valid_mask: Tensor,
        *,
        dim: int = -1,
    ) -> None:
        """Accumulate one batch of candidate path-increment tables."""

        stats = candidate_path_increment_stats(
            path_increment_m.to(device=self.mean_total.device, dtype=torch.float32),
            valid_mask.to(device=self.mean_total.device),
            dim=dim,
        )
        mean_m = stats.mean_m.reshape(-1)
        min_m = stats.min_m.reshape(-1)
        max_m = stats.max_m.reshape(-1)
        valid_table = stats.valid_table.reshape(-1)

        mean_valid = torch.isfinite(mean_m) & valid_table
        min_valid = torch.isfinite(min_m) & valid_table
        max_valid = torch.isfinite(max_m) & valid_table
        if mean_valid.any():
            self.mean_total = self.mean_total + mean_m[mean_valid].sum()
            self.mean_count = self.mean_count + mean_valid.to(dtype=torch.float32).sum()
        if min_valid.any():
            self.min_total = self.min_total + min_m[min_valid].sum()
            self.min_count = self.min_count + min_valid.to(dtype=torch.float32).sum()
        if max_valid.any():
            self.max_total = self.max_total + max_m[max_valid].sum()
            self.max_count = self.max_count + max_valid.to(dtype=torch.float32).sum()
        self.valid_table_count = self.valid_table_count + valid_table.to(dtype=torch.float32).sum()
        self.table_count = self.table_count + torch.tensor(float(valid_table.numel()), device=self.table_count.device)

    def compute(self) -> dict[str, Tensor]:
        """Return finite means of candidate path-increment table statistics."""

        if self.table_count > 0:
            valid_table_rate = self.valid_table_count / self.table_count.clamp_min(1.0)
        else:
            valid_table_rate = torch.zeros_like(self.valid_table_count)
        return {
            "candidate_path_increment_mean_m": _safe_mean(self.mean_total, self.mean_count),
            "candidate_path_increment_min_m": _safe_mean(self.min_total, self.min_count),
            "candidate_path_increment_max_m": _safe_mean(self.max_total, self.max_count),
            "candidate_path_increment_valid_table_rate": valid_table_rate,
        }


class CandidatePrimaryInvalidReasonMetric(MetricBase):
    """Accumulate primary invalid-reason share among rejected candidates.

    The configured reason ids identify one stable rejection family, for example
    path-collision or target-support failures. Shares are measured over
    hard-invalid rows only; valid action rows stay out of the denominator so
    this diagnostic complements, rather than redefines, aggregate invalidity.
    """

    full_state_update = False
    share_total: Tensor
    """``Tensor["", float32]`` sum of finite invalid-reason shares."""
    share_count: Tensor
    """``Tensor["", float32]`` number of finite invalid-reason shares."""
    valid_table_count: Tensor
    """``Tensor["", float32]`` number of tables with invalid rows."""
    table_count: Tensor
    """``Tensor["", float32]`` number of candidate tables presented."""

    def __init__(self, *, reason_ids: tuple[int, ...]) -> None:
        super().__init__()
        if not reason_ids:
            raise ValueError("reason_ids must contain at least one primary invalid-reason id.")
        self.reason_ids = tuple(int(value) for value in reason_ids)
        self.add_state("share_total", default=torch.zeros((), dtype=torch.float32), dist_reduce_fx="sum")
        self.add_state("share_count", default=torch.zeros((), dtype=torch.float32), dist_reduce_fx="sum")
        self.add_state("valid_table_count", default=torch.zeros((), dtype=torch.float32), dist_reduce_fx="sum")
        self.add_state("table_count", default=torch.zeros((), dtype=torch.float32), dist_reduce_fx="sum")

    def update(
        self,
        primary_invalid_reason: Tensor,
        valid_mask: Tensor,
        *,
        dim: int = -1,
    ) -> None:
        """Accumulate one batch of primary invalid-reason ids."""

        stats = candidate_primary_invalid_reason_share(
            primary_invalid_reason.to(device=self.share_total.device),
            valid_mask.to(device=self.share_total.device),
            reason_ids=self.reason_ids,
            dim=dim,
        )
        shares = stats.share_of_invalid.reshape(-1)
        valid_table = stats.valid_table.reshape(-1)
        finite = torch.isfinite(shares) & valid_table
        if finite.any():
            self.share_total = self.share_total + shares[finite].sum()
            self.share_count = self.share_count + finite.to(dtype=torch.float32).sum()
        self.valid_table_count = self.valid_table_count + valid_table.to(dtype=torch.float32).sum()
        self.table_count = self.table_count + torch.tensor(float(valid_table.numel()), device=self.table_count.device)

    def compute(self) -> dict[str, Tensor]:
        """Return reason-group share and denominator-validity rate."""

        if self.table_count > 0:
            valid_table_rate = self.valid_table_count / self.table_count.clamp_min(1.0)
        else:
            valid_table_rate = torch.zeros_like(self.valid_table_count)
        return {
            "candidate_primary_invalid_reason_share_of_invalid": _safe_mean(self.share_total, self.share_count),
            "candidate_primary_invalid_reason_valid_table_rate": valid_table_rate,
        }


class SelectedPathCostMetrics(MetricBase):
    """Accumulate selected camera-center path cost in metres.

    The metric expects root-plus-selected camera centers in world coordinates
    and reports the finite mean path length. Invalid or non-finite path
    segments are ignored via a hard segment mask; fully invalid paths contribute
    no cost sample instead of contributing zero.
    """

    full_state_update = False
    path_total: Tensor
    """``Tensor["", float32]`` sum of finite selected path lengths."""
    path_count: Tensor
    """``Tensor["", float32]`` number of finite selected paths."""

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
    mae_total: Tensor
    """``Tensor["", float32]`` sum of finite paired score errors."""
    mae_count: Tensor
    """``Tensor["", float32]`` number of finite paired score errors."""
    top1_match_count: Tensor
    """``Tensor["", float32]`` number of comparable top-1 matches."""
    valid_table_count: Tensor
    """``Tensor["", float32]`` number of comparable candidate tables."""
    table_count: Tensor
    """``Tensor["", float32]`` number of paired candidate tables presented."""

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
    entropy_total: Tensor
    """``Tensor["", float32]`` sum of finite candidate-policy entropies."""
    entropy_count: Tensor
    """``Tensor["", float32]`` number of finite candidate-policy entropies."""

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


class CandidateProvenanceShareMetric(MetricBase):
    """Accumulate candidate provenance-family share diagnostics.

    The metric reports the finite mean fraction of hard-valid candidate rows
    that belong to configured strategy or position id families. It is designed
    for rollout-diversity audits such as radial-away/radial-towards plus
    revisit-backtrack coverage. The ids are passed as persisted integer
    provenance values, so callers do not need pose-generation enum imports.
    """

    full_state_update = False
    share_total: Tensor
    """``Tensor["", float32]`` sum of finite provenance-family shares."""
    share_count: Tensor
    """``Tensor["", float32]`` number of finite provenance-family shares."""

    def __init__(
        self,
        *,
        strategy_family_ids: tuple[int, ...] = (),
        position_family_ids: tuple[int, ...] = (),
    ) -> None:
        super().__init__()
        if not strategy_family_ids and not position_family_ids:
            raise ValueError("At least one strategy or position provenance family id is required.")
        self.strategy_family_ids = tuple(int(value) for value in strategy_family_ids)
        self.position_family_ids = tuple(int(value) for value in position_family_ids)
        self.add_state("share_total", default=torch.zeros((), dtype=torch.float32), dist_reduce_fx="sum")
        self.add_state("share_count", default=torch.zeros((), dtype=torch.float32), dist_reduce_fx="sum")

    def update(
        self,
        strategy_ids: Tensor,
        position_ids: Tensor,
        valid_mask: Tensor | None = None,
        *,
        dim: int = -1,
    ) -> None:
        """Accumulate one batch of candidate provenance tables."""

        shares = candidate_provenance_share(
            strategy_ids.to(device=self.share_total.device),
            position_ids.to(device=self.share_total.device),
            strategy_family_ids=self.strategy_family_ids,
            position_family_ids=self.position_family_ids,
            valid_mask=None if valid_mask is None else valid_mask.to(device=self.share_total.device),
            dim=dim,
        ).reshape(-1)
        finite = torch.isfinite(shares)
        if not finite.any():
            return
        self.share_total = self.share_total + shares[finite].sum()
        self.share_count = self.share_count + finite.to(dtype=torch.float32).sum()

    def compute(self) -> Tensor:
        """Return finite mean family share or ``NaN`` when no tables were valid."""

        return _safe_mean(self.share_total, self.share_count)


def _safe_mean(total: Tensor, count: Tensor) -> Tensor:
    return torch.where(count > 0, total / count.clamp_min(1.0), torch.full_like(total, float("nan")))


__all__ = [
    "CandidateOrderConsistency",
    "CandidateOrderConsistencyMetric",
    "CandidatePathIncrementMetric",
    "CandidatePathIncrementStats",
    "CandidatePolicyEntropyMetric",
    "CandidatePrimaryInvalidReasonMetric",
    "CandidatePrimaryInvalidReasonStats",
    "CandidateProvenanceShareMetric",
    "CandidateTableMetrics",
    "SelectedPathCostMetrics",
    "candidate_best_value",
    "candidate_masked_mean",
    "candidate_order_consistency",
    "candidate_path_increment_stats",
    "candidate_policy_entropy",
    "candidate_primary_invalid_reason_share",
    "candidate_provenance_share",
    "selected_path_length_tensor",
]
