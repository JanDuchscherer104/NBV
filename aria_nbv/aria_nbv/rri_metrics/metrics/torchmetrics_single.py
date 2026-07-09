"""Stateful TorchMetrics for one-step VIN/RRI training."""

from __future__ import annotations

import torch
from torch import Tensor
from torchmetrics import Metric as TorchMetric
from torchmetrics.classification import MulticlassConfusionMatrix
from torchmetrics.regression import SpearmanCorrCoef

from ...utils import TargetConfig


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


__all__ = [
    "LabelHistogram",
    "RriErrorStats",
    "VinMetrics",
    "VinMetricsConfig",
]
