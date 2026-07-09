"""Metric and loss names used by RRI/VIN logging surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ...utils import Stage, ValueStrEnum


@dataclass(frozen=True, slots=True)
class LogSpec:
    """Logging policy for a metric/loss."""

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


__all__ = [
    "LogSpec",
    "Logable",
    "Loss",
    "Metric",
    "loss_key",
    "metric_key",
]
