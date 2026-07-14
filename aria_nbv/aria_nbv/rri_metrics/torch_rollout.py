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

By convention, ``B`` indexes independent rollout or candidate tables, ``H``
indexes selected horizon steps, and ``C`` is the reducible candidate axis.
Oracle-value arguments are evaluation labels; predicted-score and selection
probability arguments are actor-side policy outputs.
"""

from __future__ import annotations

from collections.abc import Sequence
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
    """``Tensor["B", float32]`` dimensionless discounted selected return; empty rows are ``NaN``."""
    endpoint_gain: Tensor
    """``Tensor["B", float32]`` dimensionless root-normalized endpoint gain."""
    endpoint_log_gain: Tensor
    """``Tensor["B", float32]`` dimensionless logarithmic endpoint gain."""
    valid_steps: Tensor
    """``Tensor["B", int64]`` count of finite, hard-valid selected rewards."""
    valid_endpoint: Tensor
    """``Tensor["B", bool]`` comparability mask for finite non-negative endpoint errors."""


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
    """``Tensor["B", float32]`` inverse-aligned score MAE over comparable hard-valid rows."""
    top1_match: Tensor
    """``Tensor["B", bool]`` agreement of the best comparable candidate after inverse alignment."""
    valid_table: Tensor
    """``Tensor["B", bool]`` mask for tables containing at least one comparable row."""


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
    """``Tensor["B", float32]`` oracle-best minus selected oracle value; invalid tables are ``NaN``."""
    selected_oracle_rank: Tensor
    """``Tensor["B", float32]`` one-based selected rank among finite hard-valid oracle labels."""
    selected_oracle_percentile: Tensor
    """``Tensor["B", float32]`` rank percentile where one is best and zero is worst."""
    valid_table: Tensor
    """``Tensor["B", bool]`` mask for tables with a comparable selected oracle label."""


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
    """``Tensor["B", float32]`` mean finite hard-valid candidate path increment, metres."""
    min_m: Tensor
    """``Tensor["B", float32]`` minimum finite hard-valid candidate path increment, metres."""
    max_m: Tensor
    """``Tensor["B", float32]`` maximum finite hard-valid candidate path increment, metres."""
    valid_table: Tensor
    """``Tensor["B", bool]`` mask for tables with at least one comparable path increment."""


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
    """``Tensor["B", float32]`` audited-reason share over hard-invalid rows only."""
    valid_table: Tensor
    """``Tensor["B", bool]`` mask for tables with at least one hard-invalid row."""


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
        ``Tensor["...", float32]`` entropy in nats per candidate table after
        reducing `dim`.
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


def _id_membership(values: Tensor, family_ids: Sequence[int] | Tensor) -> Tensor:
    if isinstance(family_ids, Tensor):
        ids = family_ids.to(device=values.device, dtype=values.dtype).reshape(-1)
    else:
        ids = torch.as_tensor(tuple(family_ids), device=values.device, dtype=values.dtype).reshape(-1)
    if ids.numel() == 0:
        return torch.zeros_like(values, dtype=torch.bool)
    return (values.unsqueeze(-1) == ids).any(dim=-1)


__all__ = [
    "TorchRolloutMetrics",
    "CandidateOrderConsistency",
    "CandidatePathIncrementStats",
    "CandidatePrimaryInvalidReasonStats",
    "SelectedActionOracleComparison",
    "candidate_best_value",
    "candidate_masked_mean",
    "candidate_order_consistency",
    "candidate_path_increment_stats",
    "candidate_policy_entropy",
    "candidate_primary_invalid_reason_share",
    "candidate_provenance_share",
    "candidate_topk_oracle_hit",
    "discounted_selected_return",
    "endpoint_log_gain_tensor",
    "endpoint_target_gain_tensor",
    "selected_action_oracle_comparison",
    "selected_path_length_tensor",
    "summarize_selected_rollout_tensors",
]
