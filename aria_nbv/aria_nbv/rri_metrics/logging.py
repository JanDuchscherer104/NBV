"""Metric and loss names plus torchmetrics bundles for VIN training.

This module centralizes logging keys (``Metric``/``Loss``) and stateful
torchmetrics objects used in Lightning. We prefer a single ``Metric`` container
that owns all sub-metrics because VIN needs *different* inputs per metric
(``pred_scores`` vs. ``pred_class`` vs. ``labels``), which is awkward to
represent with a plain ``MetricCollection``. The custom wrapper still follows
torchmetrics best practices: ``add_state`` for distributed reduction, explicit
``update``/``compute``/``reset`` methods, and ``full_state_update=False`` to
avoid unnecessary synchronization overhead.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import torch
from torch import Tensor
from torchmetrics import Metric as TorchMetric
from torchmetrics.classification import MulticlassConfusionMatrix
from torchmetrics.regression import SpearmanCorrCoef

from ..utils import Stage, TargetConfig, ValueStrEnum


@dataclass(frozen=True, slots=True)
class LogSpec:
    """Logging policy for a metric/loss.

    Attributes:
        on_step: Log on step-level updates.
        on_epoch: Log epoch-level aggregates.
        prog_bar: Show in Lightning's progress bar.
        enabled: Whether logging is enabled for the current stage.
    """

    on_step: bool
    on_epoch: bool
    prog_bar: bool
    enabled: bool = True


class Logable(ValueStrEnum):
    """Base class for loggable metric/loss names."""

    def log_spec(self, stage: Stage) -> LogSpec:
        """Return logging settings for this metric/loss at the given stage."""
        raise NotImplementedError("Every metric/loss must specify how it should be logged.")

    def on_step(self, stage: Stage) -> bool:
        return self.log_spec(stage).on_step

    def on_epoch(self, stage: Stage) -> bool:
        return self.log_spec(stage).on_epoch

    def prog_bar(self, stage: Stage) -> bool:
        return self.log_spec(stage).prog_bar


class Metric(Logable):
    """Metric suffixes composed with Stage as ``{stage}/{metric}``."""

    LOSS = "loss"
    """Legacy loss key (prefer `Loss` for losses)."""

    RRI_MEAN = "rri_mean"
    PRED_RRI_MEAN = "pred_rri_mean"
    PRED_RRI_BIAS2 = "pred_rri_bias2"
    PRED_RRI_VARIANCE = "pred_rri_variance"
    TOP3_ACCURACY = "top3_accuracy"
    CANDIDATE_TOP1_ORACLE_HIT = "candidate_top1_oracle_hit"
    CANDIDATE_TOP3_ORACLE_HIT = "candidate_top3_oracle_hit"
    SELECTED_ORACLE_REGRET = "selected_oracle_regret"
    SELECTED_ORACLE_RANK = "selected_oracle_rank"
    SELECTED_ORACLE_PERCENTILE = "selected_oracle_percentile"
    SELECTED_ORACLE_VALID_TABLE_RATE = "selected_oracle_valid_table_rate"
    AUX_REGRESSION_WEIGHT = "aux_regression_weight"
    CORAL_MONOTONICITY_VIOLATION_RATE = "coral_monotonicity_violation_rate"
    VOXEL_VALID_FRAC_MEAN = "voxel_valid_frac_mean"
    VOXEL_VALID_FRAC_STD = "voxel_valid_frac_std"
    SEMIDENSE_CANDIDATE_VIS_FRAC_MEAN = "semidense_candidate_vis_frac_mean"
    SEMIDENSE_CANDIDATE_VIS_FRAC_STD = "semidense_candidate_vis_frac_std"
    CANDIDATE_VALID_FRAC = "candidate_valid_frac"
    COVERAGE_WEIGHT_MEAN = "coverage_weight_mean"
    COVERAGE_WEIGHT_STRENGTH = "coverage_weight_strength"

    SPEARMAN = "spearman"
    SPEARMAN_STEP = "spearman_step"
    CONFUSION_MATRIX = "confusion_matrix"
    CONFUSION_MATRIX_STEP = "confusion_matrix_step"
    LABEL_HISTOGRAM = "label_histogram"
    LABEL_HISTOGRAM_STEP = "label_histogram_step"

    def log_spec(self, stage: Stage) -> LogSpec:
        match self:
            case Metric.LOSS:
                return LogSpec(on_step=stage is Stage.TRAIN, on_epoch=True, prog_bar=False)
            case (
                Metric.RRI_MEAN
                | Metric.PRED_RRI_MEAN
                | Metric.TOP3_ACCURACY
                | Metric.CANDIDATE_TOP1_ORACLE_HIT
                | Metric.CANDIDATE_TOP3_ORACLE_HIT
                | Metric.SELECTED_ORACLE_REGRET
                | Metric.SELECTED_ORACLE_RANK
                | Metric.SELECTED_ORACLE_PERCENTILE
                | Metric.SELECTED_ORACLE_VALID_TABLE_RATE
                | Metric.AUX_REGRESSION_WEIGHT
                | Metric.VOXEL_VALID_FRAC_MEAN
                | Metric.VOXEL_VALID_FRAC_STD
                | Metric.SEMIDENSE_CANDIDATE_VIS_FRAC_MEAN
                | Metric.SEMIDENSE_CANDIDATE_VIS_FRAC_STD
                | Metric.CANDIDATE_VALID_FRAC
                | Metric.COVERAGE_WEIGHT_MEAN
                | Metric.COVERAGE_WEIGHT_STRENGTH
            ):
                return LogSpec(on_step=stage is Stage.TRAIN, on_epoch=True, prog_bar=False)
            case Metric.CORAL_MONOTONICITY_VIOLATION_RATE:
                return LogSpec(on_step=stage is Stage.TRAIN, on_epoch=True, prog_bar=False)
            case Metric.PRED_RRI_BIAS2 | Metric.PRED_RRI_VARIANCE:
                if stage is not Stage.VAL:
                    return LogSpec(on_step=False, on_epoch=False, prog_bar=False, enabled=False)
                return LogSpec(on_step=False, on_epoch=True, prog_bar=False)
            case Metric.SPEARMAN:
                return LogSpec(on_step=False, on_epoch=True, prog_bar=False)
            case Metric.SPEARMAN_STEP:
                if stage is not Stage.TRAIN:
                    return LogSpec(on_step=False, on_epoch=False, prog_bar=False, enabled=False)
                return LogSpec(on_step=True, on_epoch=False, prog_bar=False)
            case Metric.CONFUSION_MATRIX | Metric.LABEL_HISTOGRAM:
                return LogSpec(on_step=False, on_epoch=True, prog_bar=False)
            case Metric.CONFUSION_MATRIX_STEP | Metric.LABEL_HISTOGRAM_STEP:
                if stage is not Stage.TRAIN:
                    return LogSpec(on_step=False, on_epoch=False, prog_bar=False, enabled=False)
                return LogSpec(on_step=True, on_epoch=False, prog_bar=False)
        raise ValueError(f"Unknown Metric: {self}")


class Loss(Logable):
    """Loss suffixes composed with Stage as ``{stage}/{loss}``."""

    LOSS = "loss"
    CORAL = "coral_loss"
    CORAL_REL_RANDOM = "coral_loss_rel_random"
    ORD_BALANCED_BCE = "coral_loss_balanced_bce"
    ORD_FOCAL = "coral_loss_focal"
    AUX_REGRESSION = "aux_regression_loss"

    def log_spec(self, stage: Stage) -> LogSpec:
        match self:
            case Loss.LOSS:
                return LogSpec(
                    on_step=stage is Stage.TRAIN,
                    on_epoch=True,
                    prog_bar=stage in {Stage.TRAIN, Stage.VAL},
                )
            case Loss.CORAL_REL_RANDOM:
                return LogSpec(
                    on_step=stage is Stage.TRAIN,
                    on_epoch=True,
                    prog_bar=stage in {Stage.TRAIN, Stage.VAL},
                )
            case Loss.CORAL | Loss.ORD_BALANCED_BCE | Loss.ORD_FOCAL | Loss.AUX_REGRESSION:
                return LogSpec(on_step=stage is Stage.TRAIN, on_epoch=True, prog_bar=False)
        raise ValueError(f"Unknown Loss: {self}")


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
        self.sum_error.zero_()
        self.sum_error_sq.zero_()
        self.count.zero_()


class VinMetrics(TorchMetric):
    """Container for VIN metrics computed from candidate rankings."""

    full_state_update = False

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
        if self.spearman is not None:
            self.spearman.reset()
        self.confusion.reset()
        self.label_hist.reset()
        self.has_updates.fill_(False)


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


def _namespace_prefix(stage: Stage, *, namespace: Literal["main", "aux"]) -> str:
    if namespace == "aux":
        return f"{stage.value}-aux/"
    return f"{stage.value}/"


def metric_key(
    stage: Stage,
    metric: Metric,
    *,
    namespace: Literal["main", "aux"] = "main",
) -> str:
    """Compose a logging key using the stage prefix."""
    return f"{_namespace_prefix(stage, namespace=namespace)}{metric.value}"


def loss_key(
    stage: Stage,
    loss: Loss,
    *,
    namespace: Literal["main", "aux"] = "main",
) -> str:
    """Compose a logging key using the stage prefix."""
    return f"{_namespace_prefix(stage, namespace=namespace)}{loss.value}"


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


__all__ = [
    "LabelHistogram",
    "Loss",
    "LogSpec",
    "Metric",
    "RriErrorStats",
    "VinMetrics",
    "VinMetricsConfig",
    "loss_key",
    "metric_key",
    "topk_accuracy_from_probs",
]
