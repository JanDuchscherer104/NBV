"""Non-differentiable candidate-ranking evaluation.

This module provides comparisons of actor-selected or predicted candidates against finite
hard-valid Oracle label tables without changing selection behavior.
"""

from __future__ import annotations

from dataclasses import dataclass

import torch
from torch import Tensor


@dataclass(frozen=True, slots=True)
class SelectedActionOracleComparison:
    """Per-table oracle diagnostics for a selected candidate action.

    Attributes:
        selected_oracle_regret: ``Tensor["B"]`` oracle-best value minus the
            selected candidate's oracle value. Lower is better; oracle-best
            ties have zero regret.
        selected_oracle_rank: ``Tensor["B"]`` one-based selected-candidate rank
            among finite hard-valid oracle labels. Tied oracle-best candidates
            have rank ``1``.
        selected_oracle_percentile: ``Tensor["B"]`` rank percentile in
            ``[0, 1]`` where ``1`` means oracle-best and ``0`` means worst
            among comparable finite labels.
        valid_table: ``Tensor["B"]`` mask for tables with a finite valid
            selected label and at least one finite valid oracle candidate.
    """

    selected_oracle_regret: Tensor
    """``Tensor["B", float32]`` Oracle-best minus selected value; invalid tables are ``NaN``."""

    selected_oracle_rank: Tensor
    """``Tensor["B", float32]`` one-based selected rank; invalid tables are ``NaN``."""

    selected_oracle_percentile: Tensor
    """``Tensor["B", float32]`` selected rank percentile in ``[0, 1]``."""

    valid_table: Tensor
    """``Tensor["B", bool]`` mask for tables with comparable selected and Oracle values."""


def candidate_topk_oracle_hit(
    predicted_scores: Tensor,
    oracle_values: Tensor,
    valid_mask: Tensor | None = None,
    *,
    top_k: int = 1,
    dim: int = -1,
) -> Tensor:
    """Report whether predicted top-k rows include an oracle-best candidate.

    The oracle-best tied set is computed from finite oracle values under the
    hard mask. Non-finite predicted scores are excluded from the predicted
    top-k set without removing their oracle labels, so a model that emits
    ``NaN`` on the true best row records a miss when other finite predictions
    exist. Predicted ties at the kth boundary are included to avoid arbitrary
    tie-breaking.

    Args:
        predicted_scores: Candidate scores produced by a model or policy.
        oracle_values: Candidate oracle values with the same shape as
            ``predicted_scores``.
        valid_mask: Optional hard-validity mask broadcastable to
            ``predicted_scores``.
        top_k: Number of predicted candidates to consider before kth-boundary
            ties are expanded.
        dim: Candidate dimension.

    Returns:
        Float hit indicator per candidate table. Empty oracle-labeled tables or
        tables with no finite predictions return ``NaN``.
    """

    if top_k < 1:
        raise ValueError("top_k must be >= 1.")
    if predicted_scores.shape != oracle_values.shape:
        raise ValueError(
            "Expected predicted_scores and oracle_values to have matching shapes, "
            f"got {tuple(predicted_scores.shape)} and {tuple(oracle_values.shape)}.",
        )
    if dim < 0:
        dim = predicted_scores.ndim + dim
    if dim < 0 or dim >= predicted_scores.ndim:
        raise ValueError(f"dim={dim} is outside tensor rank {predicted_scores.ndim}.")

    scores = predicted_scores.to(dtype=torch.float32)
    oracle = oracle_values.to(device=scores.device, dtype=torch.float32)
    if valid_mask is None:
        hard_mask = torch.ones_like(scores, dtype=torch.bool)
    else:
        hard_mask = torch.broadcast_to(valid_mask.to(device=scores.device, dtype=torch.bool), scores.shape)
    if dim != scores.ndim - 1:
        scores = scores.movedim(dim, -1)
        oracle = oracle.movedim(dim, -1)
        hard_mask = hard_mask.movedim(dim, -1)

    table_shape = scores.shape[:-1]
    num_candidates = scores.shape[-1]
    if num_candidates == 0:
        return torch.full(table_shape, float("nan"), device=scores.device, dtype=torch.float32)

    scores_2d = scores.reshape(-1, num_candidates)
    oracle_2d = oracle.reshape(-1, num_candidates)
    mask_2d = hard_mask.reshape(-1, num_candidates)

    oracle_valid = mask_2d & torch.isfinite(oracle_2d)
    pred_valid = mask_2d & torch.isfinite(scores_2d)
    oracle_filled = torch.where(oracle_valid, oracle_2d, torch.full_like(oracle_2d, -torch.inf))
    oracle_best = oracle_filled.max(dim=-1).values
    has_oracle = torch.isfinite(oracle_best)
    oracle_best_set = oracle_valid & (oracle_2d == oracle_best.unsqueeze(-1))

    pred_filled = torch.where(pred_valid, scores_2d, torch.full_like(scores_2d, -torch.inf))
    pred_count = pred_valid.to(dtype=torch.long).sum(dim=-1)
    has_prediction = pred_count > 0
    topk_per_table = pred_count.clamp(max=int(top_k))
    kth_index = topk_per_table.clamp_min(1) - 1
    kth_score = pred_filled.sort(dim=-1, descending=True).values.gather(dim=-1, index=kth_index.unsqueeze(-1))
    predicted_topk = pred_valid & (scores_2d >= kth_score)

    comparable = has_oracle & has_prediction
    hit = (predicted_topk & oracle_best_set).any(dim=-1).to(dtype=torch.float32)
    result = torch.where(comparable, hit, torch.full_like(hit, float("nan")))
    return result.reshape(table_shape)


def selected_action_oracle_comparison(
    oracle_values: Tensor,
    selected_indices: Tensor,
    valid_mask: Tensor,
    *,
    dim: int = -1,
) -> SelectedActionOracleComparison:
    """Compare selected candidate actions against oracle-best candidate labels.

    This reducer is for policy evaluation, not supervision. It reads a selected
    candidate index per table and reports how far that action is from the
    finite oracle-best row under the hard action mask. Invalid selected indices,
    masked selected rows, non-finite selected labels, and empty oracle tables
    return ``NaN`` diagnostics with ``valid_table=False``.

    Args:
        oracle_values: Candidate oracle values, such as target reward or
            finite-horizon oracle return.
        selected_indices: Selected candidate indices with shape equal to
            ``oracle_values`` after removing `dim`; values may be integer or
            floating tensors, but non-finite or non-integral entries are
            treated as invalid selections.
        valid_mask: Boolean hard-validity mask broadcastable to
            ``oracle_values``.
        dim: Candidate dimension.

    Returns:
        `SelectedActionOracleComparison` with per-table regret, one-based rank,
        rank percentile, and comparability mask.
    """

    if dim < 0:
        dim = oracle_values.ndim + dim
    if dim < 0 or dim >= oracle_values.ndim:
        raise ValueError(f"dim={dim} is outside tensor rank {oracle_values.ndim}.")

    oracle = oracle_values.to(dtype=torch.float32)
    hard_mask = torch.broadcast_to(valid_mask.to(device=oracle.device, dtype=torch.bool), oracle.shape)
    if dim != oracle.ndim - 1:
        oracle = oracle.movedim(dim, -1)
        hard_mask = hard_mask.movedim(dim, -1)

    table_shape = oracle.shape[:-1]
    num_candidates = oracle.shape[-1]
    selected = torch.broadcast_to(selected_indices.to(device=oracle.device), table_shape)
    if num_candidates == 0:
        nan = torch.full(table_shape, float("nan"), device=oracle.device, dtype=torch.float32)
        return SelectedActionOracleComparison(
            selected_oracle_regret=nan,
            selected_oracle_rank=nan,
            selected_oracle_percentile=nan,
            valid_table=torch.zeros(table_shape, device=oracle.device, dtype=torch.bool),
        )

    oracle_2d = oracle.reshape(-1, num_candidates)
    hard_2d = hard_mask.reshape(-1, num_candidates)
    selected_flat = selected.reshape(-1)
    selected_float = selected_flat.to(dtype=torch.float32)
    selected_integral = torch.isfinite(selected_float) & (selected_float == selected_float.round())
    selected_long = torch.where(
        selected_integral,
        selected_float.to(dtype=torch.long),
        torch.zeros_like(selected_float, dtype=torch.long),
    )
    selected_in_bounds = selected_integral & (selected_long >= 0) & (selected_long < num_candidates)
    safe_selected = selected_long.clamp(min=0, max=num_candidates - 1)

    oracle_valid = hard_2d & torch.isfinite(oracle_2d)
    valid_count = oracle_valid.to(dtype=torch.float32).sum(dim=-1)
    has_oracle = valid_count > 0
    selected_hard_valid = hard_2d.gather(dim=-1, index=safe_selected.unsqueeze(-1)).squeeze(-1)
    selected_value = oracle_2d.gather(dim=-1, index=safe_selected.unsqueeze(-1)).squeeze(-1)
    selected_label_valid = selected_in_bounds & selected_hard_valid & torch.isfinite(selected_value)
    valid_table = has_oracle & selected_label_valid

    oracle_filled = torch.where(oracle_valid, oracle_2d, torch.full_like(oracle_2d, -torch.inf))
    oracle_best = oracle_filled.max(dim=-1).values
    regret = oracle_best - selected_value
    better_count = (oracle_valid & (oracle_2d > selected_value.unsqueeze(-1))).to(dtype=torch.float32).sum(dim=-1)
    rank = 1.0 + better_count
    percentile = torch.where(
        valid_count > 1.0,
        1.0 - ((rank - 1.0) / (valid_count - 1.0).clamp_min(1.0)),
        torch.ones_like(rank),
    )
    nan = torch.full_like(regret, float("nan"))
    return SelectedActionOracleComparison(
        selected_oracle_regret=torch.where(valid_table, regret, nan).reshape(table_shape),
        selected_oracle_rank=torch.where(valid_table, rank, nan).reshape(table_shape),
        selected_oracle_percentile=torch.where(valid_table, percentile, nan).reshape(table_shape),
        valid_table=valid_table.reshape(table_shape),
    )


__all__ = [
    "SelectedActionOracleComparison",
    "candidate_topk_oracle_hit",
    "selected_action_oracle_comparison",
]
