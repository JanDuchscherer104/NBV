"""Stateful one-step VIN and candidate-ranking evaluation metrics."""

from __future__ import annotations

import torch
from torch import Tensor
from torchmetrics import Metric as TorchMetric
from torchmetrics.classification import MulticlassConfusionMatrix
from torchmetrics.regression import SpearmanCorrCoef

from ..utils import TargetConfig
from .ranking import candidate_topk_oracle_hit, selected_action_oracle_comparison


class LabelHistogram(TorchMetric):
    """Accumulate label counts for ordinal classes."""

    counts: Tensor
    """``Tensor["K", int64]`` per-class counts, reduced by distributed sum."""

    full_state_update = False

    def __init__(self, num_classes: int) -> None:
        num_classes = int(num_classes)
        if num_classes < 1:
            raise ValueError("num_classes must be >= 1.")
        super().__init__()
        self.num_classes = num_classes
        self.add_state(
            "counts",
            default=torch.zeros(self.num_classes, dtype=torch.long),
            dist_reduce_fx="sum",
        )

    def update(self, target: Tensor) -> None:
        if target.numel() == 0:
            return
        labels = target.to(dtype=torch.int64).reshape(-1)
        if bool(((labels < 0) | (labels >= self.num_classes)).any().item()):
            raise ValueError(f"Expected labels within [0, {self.num_classes}), got {target}.")
        counts = torch.bincount(labels, minlength=self.num_classes)
        self.counts = self.counts + counts.to(device=self.counts.device)

    def compute(self) -> Tensor:
        return self.counts


class RriErrorStats(TorchMetric):
    """Accumulate finite-pair bias/variance statistics for RRI errors."""

    full_state_update = False
    sum_error: Tensor
    """``Tensor["", float32]`` sum of finite prediction-minus-label errors."""
    sum_error_sq: Tensor
    """``Tensor["", float32]`` sum of squared finite errors."""
    count: Tensor
    """``Tensor["", float32]`` count of finite error pairs."""

    def __init__(self) -> None:
        super().__init__()
        self.add_state("sum_error", default=torch.zeros((), dtype=torch.float32), dist_reduce_fx="sum")
        self.add_state("sum_error_sq", default=torch.zeros((), dtype=torch.float32), dist_reduce_fx="sum")
        self.add_state("count", default=torch.zeros((), dtype=torch.float32), dist_reduce_fx="sum")

    def update(self, pred_rri: Tensor, rri: Tensor) -> None:
        if pred_rri.numel() == 0 or rri.numel() == 0:
            return
        pred_flat = pred_rri.reshape(-1).to(device=self.sum_error.device, dtype=torch.float32)
        rri_flat = rri.reshape(-1).to(device=self.sum_error.device, dtype=torch.float32)
        if pred_flat.shape != rri_flat.shape:
            raise ValueError(
                "Expected pred_rri and rri to have matching shapes, "
                f"got {tuple(pred_flat.shape)} and {tuple(rri_flat.shape)}.",
            )
        finite = torch.isfinite(pred_flat) & torch.isfinite(rri_flat)
        if not bool(finite.any().item()):
            return
        error = pred_flat[finite] - rri_flat[finite]
        self.sum_error = self.sum_error + error.sum()
        self.sum_error_sq = self.sum_error_sq + (error * error).sum()
        self.count = self.count + torch.tensor(float(error.numel()), device=self.count.device, dtype=self.count.dtype)

    def compute(self) -> dict[str, Tensor]:
        if not bool(self.count.item()):
            return {}
        mean_error = self.sum_error / self.count
        mean_error_sq = self.sum_error_sq / self.count
        variance = (mean_error_sq - mean_error * mean_error).clamp_min(0.0)
        return {
            "bias2": mean_error * mean_error,
            "variance": variance,
        }

    def reset(self) -> None:  # type: ignore[override]
        super().reset()


class VinMetrics(TorchMetric):
    """Container for VIN metrics computed from candidate rankings."""

    full_state_update = False
    spearman: SpearmanCorrCoef | None
    """Optional buffered Spearman correlation metric for this stage."""
    confusion: MulticlassConfusionMatrix
    """Stateful ordinal-class confusion matrix for this stage."""
    label_hist: LabelHistogram
    """Stateful ordinal-label histogram for this stage."""
    has_updates: Tensor
    """``Tensor["", bool]`` indicating whether this stage received data."""

    def __init__(self, *, num_classes: int, enable_spearman: bool = True) -> None:
        super().__init__()
        self.enable_spearman = bool(enable_spearman)
        self.spearman = SpearmanCorrCoef() if self.enable_spearman else None
        self.confusion = MulticlassConfusionMatrix(num_classes=int(num_classes))
        self.label_hist = LabelHistogram(num_classes=int(num_classes))
        self.add_state("has_updates", default=torch.zeros((), dtype=torch.bool), dist_reduce_fx="max")

    def update(
        self,
        *,
        pred_scores: Tensor,
        rri: Tensor,
        pred_class: Tensor,
        labels: Tensor,
    ) -> None:
        if pred_scores.numel() == 0:
            return
        if self.spearman is not None:
            self.spearman.update(pred_scores, rri)
        self.confusion.update(pred_class, labels)
        self.label_hist.update(labels)
        self.has_updates.fill_(True)

    def compute(self) -> dict[str, Tensor]:
        if not bool(self.has_updates.item()):
            return {}
        metrics = {
            "confusion": self.confusion.compute(),
            "label_hist": self.label_hist.compute(),
        }
        if self.spearman is not None:
            metrics["spearman"] = self.spearman.compute()
        return metrics

    def reset(self) -> None:  # type: ignore[override]
        super().reset()
        if self.spearman is not None:
            self.spearman.reset()
        self.confusion.reset()
        self.label_hist.reset()


class VinMetricsConfig(TargetConfig[VinMetrics]):
    """Configuration for VIN torchmetrics bundles."""

    @property
    def target_type(self) -> type[VinMetrics]:
        """Factory target for `aria_nbv.utils.base_config.BaseConfig.setup_target`."""
        return VinMetrics

    num_classes: int
    """Number of ordinal classes used for confusion/histogram metrics."""

    enable_spearman: bool = True
    """Enable rank-correlation metrics that buffer all predictions/targets."""

    def setup_target(self) -> VinMetrics:
        return self.target(num_classes=int(self.num_classes), enable_spearman=bool(self.enable_spearman))


def topk_accuracy_from_probs(probs: Tensor, labels: Tensor, *, top_k: int) -> Tensor:
    """Compute top-k accuracy from class probabilities.

    Args:
        probs: ``Tensor["N K"]`` class probabilities.
        labels: ``Tensor["N"]`` integer class labels.
        top_k: Number of highest-probability classes to consider.

    Returns:
        ``Tensor[""]`` scalar accuracy in ``[0, 1]``.
    """
    if top_k < 1:
        raise ValueError("top_k must be >= 1.")
    if probs.numel() == 0 or labels.numel() == 0:
        return torch.tensor(float("nan"), device=probs.device)
    if probs.ndim != 2:
        raise ValueError(f"Expected probs with shape (N, K), got {tuple(probs.shape)}.")
    labels = labels.reshape(-1)
    if probs.shape[0] != labels.shape[0]:
        raise ValueError(
            f"Expected probs and labels to have matching first dimension, got {probs.shape[0]} and {labels.shape[0]}.",
        )
    k = min(int(top_k), probs.shape[-1])
    topk = probs.topk(k=k, dim=-1).indices
    correct = (topk == labels.unsqueeze(-1)).any(dim=-1)
    return correct.to(dtype=torch.float32).mean()


class CandidateTopKOracleHitMetric(TorchMetric):
    """Accumulate candidate top-k oracle-hit rate.

    This metric evaluates one-step candidate ranking directly: a table is a hit
    when the model's top-k predicted rows include at least one finite
    oracle-best candidate under the hard action mask. It keeps non-finite model
    scores separate from oracle labels, matching `candidate_topk_oracle_hit`.
    """

    full_state_update = False
    hit_total: Tensor
    """``Tensor["", float32]`` sum of finite table-level oracle hits."""
    hit_count: Tensor
    """``Tensor["", float32]`` number of comparable candidate tables."""

    def __init__(self, *, top_k: int = 1) -> None:
        super().__init__()
        if top_k < 1:
            raise ValueError("top_k must be >= 1.")
        self.top_k = int(top_k)
        self.add_state("hit_total", default=torch.zeros((), dtype=torch.float32), dist_reduce_fx="sum")
        self.add_state("hit_count", default=torch.zeros((), dtype=torch.float32), dist_reduce_fx="sum")

    def update(
        self,
        predicted_scores: Tensor,
        oracle_values: Tensor,
        valid_mask: Tensor | None = None,
        *,
        dim: int = -1,
    ) -> None:
        """Accumulate one batch of candidate prediction/oracle tables."""

        hits = candidate_topk_oracle_hit(
            predicted_scores.to(device=self.hit_total.device, dtype=torch.float32),
            oracle_values.to(device=self.hit_total.device, dtype=torch.float32),
            None if valid_mask is None else valid_mask.to(device=self.hit_total.device),
            top_k=self.top_k,
            dim=dim,
        ).reshape(-1)
        finite = torch.isfinite(hits)
        if not finite.any():
            return
        self.hit_total = self.hit_total + hits[finite].sum()
        self.hit_count = self.hit_count + finite.to(dtype=torch.float32).sum()

    def compute(self) -> Tensor:
        """Return finite mean top-k hit rate or ``NaN`` when empty."""

        return _safe_mean(self.hit_total, self.hit_count)


class SelectedActionOracleComparisonMetric(TorchMetric):
    """Accumulate selected-action oracle rank and regret diagnostics.

    This metric evaluates a policy's selected candidate against the finite
    oracle-labelled candidate table. It is intentionally separate from loss and
    training metrics: invalid selections are counted only through the valid
    table rate, and uncomparable rows do not contribute zero-valued regret or
    rank samples.
    """

    full_state_update = False
    regret_total: Tensor
    """``Tensor["", float32]`` sum of finite selected-action regrets."""
    regret_count: Tensor
    """``Tensor["", float32]`` number of finite regret samples."""
    rank_total: Tensor
    """``Tensor["", float32]`` sum of finite selected-action oracle ranks."""
    rank_count: Tensor
    """``Tensor["", float32]`` number of finite rank samples."""
    percentile_total: Tensor
    """``Tensor["", float32]`` sum of finite selected-action percentiles."""
    percentile_count: Tensor
    """``Tensor["", float32]`` number of finite percentile samples."""
    valid_table_count: Tensor
    """``Tensor["", float32]`` number of comparable candidate tables."""
    table_count: Tensor
    """``Tensor["", float32]`` number of candidate tables presented."""

    def __init__(self) -> None:
        super().__init__()
        self.add_state("regret_total", default=torch.zeros((), dtype=torch.float32), dist_reduce_fx="sum")
        self.add_state("regret_count", default=torch.zeros((), dtype=torch.float32), dist_reduce_fx="sum")
        self.add_state("rank_total", default=torch.zeros((), dtype=torch.float32), dist_reduce_fx="sum")
        self.add_state("rank_count", default=torch.zeros((), dtype=torch.float32), dist_reduce_fx="sum")
        self.add_state("percentile_total", default=torch.zeros((), dtype=torch.float32), dist_reduce_fx="sum")
        self.add_state("percentile_count", default=torch.zeros((), dtype=torch.float32), dist_reduce_fx="sum")
        self.add_state("valid_table_count", default=torch.zeros((), dtype=torch.float32), dist_reduce_fx="sum")
        self.add_state("table_count", default=torch.zeros((), dtype=torch.float32), dist_reduce_fx="sum")

    def update(
        self,
        oracle_values: Tensor,
        selected_indices: Tensor,
        valid_mask: Tensor,
        *,
        dim: int = -1,
    ) -> None:
        """Accumulate one batch of selected candidate indices and oracle values."""

        comparison = selected_action_oracle_comparison(
            oracle_values.to(device=self.regret_total.device, dtype=torch.float32),
            selected_indices.to(device=self.regret_total.device),
            valid_mask.to(device=self.regret_total.device),
            dim=dim,
        )
        regret = comparison.selected_oracle_regret.reshape(-1)
        rank = comparison.selected_oracle_rank.reshape(-1)
        percentile = comparison.selected_oracle_percentile.reshape(-1)
        valid_table = comparison.valid_table.reshape(-1)

        regret_valid = torch.isfinite(regret) & valid_table
        rank_valid = torch.isfinite(rank) & valid_table
        percentile_valid = torch.isfinite(percentile) & valid_table
        if regret_valid.any():
            self.regret_total = self.regret_total + regret[regret_valid].sum()
            self.regret_count = self.regret_count + regret_valid.to(dtype=torch.float32).sum()
        if rank_valid.any():
            self.rank_total = self.rank_total + rank[rank_valid].sum()
            self.rank_count = self.rank_count + rank_valid.to(dtype=torch.float32).sum()
        if percentile_valid.any():
            self.percentile_total = self.percentile_total + percentile[percentile_valid].sum()
            self.percentile_count = self.percentile_count + percentile_valid.to(dtype=torch.float32).sum()
        self.valid_table_count = self.valid_table_count + valid_table.to(dtype=torch.float32).sum()
        self.table_count = self.table_count + torch.tensor(float(valid_table.numel()), device=self.table_count.device)

    def compute(self) -> dict[str, Tensor]:
        """Return finite means plus the comparable-table rate."""

        if self.table_count > 0:
            valid_table_rate = self.valid_table_count / self.table_count.clamp_min(1.0)
        else:
            valid_table_rate = torch.zeros_like(self.valid_table_count)
        return {
            "selected_oracle_regret": _safe_mean(self.regret_total, self.regret_count),
            "selected_oracle_rank": _safe_mean(self.rank_total, self.rank_count),
            "selected_oracle_percentile": _safe_mean(self.percentile_total, self.percentile_count),
            "selected_oracle_valid_table_rate": valid_table_rate,
        }


def _safe_mean(total: Tensor, count: Tensor) -> Tensor:
    return torch.where(count > 0, total / count.clamp_min(1.0), torch.full_like(total, float("nan")))


__all__ = [
    "CandidateTopKOracleHitMetric",
    "LabelHistogram",
    "RriErrorStats",
    "SelectedActionOracleComparisonMetric",
    "VinMetrics",
    "VinMetricsConfig",
    "topk_accuracy_from_probs",
]
