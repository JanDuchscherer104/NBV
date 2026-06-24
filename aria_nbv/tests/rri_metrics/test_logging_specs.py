"""Tests for logging policy definitions on Metric/Loss enums."""

# ruff: noqa: S101, D103

from __future__ import annotations

from aria_nbv.rri_metrics.logging import Loss, Metric
from aria_nbv.utils import Stage


def test_loss_log_spec_train_progbar() -> None:
    spec = Loss.LOSS.log_spec(Stage.TRAIN)
    assert spec.on_step is True
    assert spec.on_epoch is True
    assert spec.prog_bar is True


def test_loss_log_spec_val_progbar() -> None:
    spec = Loss.CORAL_REL_RANDOM.log_spec(Stage.VAL)
    assert spec.on_step is False
    assert spec.on_epoch is True
    assert spec.prog_bar is True


def test_metric_log_spec_epoch_only() -> None:
    spec = Metric.SPEARMAN.log_spec(Stage.TEST)
    assert spec.on_step is False
    assert spec.on_epoch is True
    assert spec.prog_bar is False


def test_metric_log_spec_step_only_train() -> None:
    spec = Metric.SPEARMAN_STEP.log_spec(Stage.TRAIN)
    assert spec.on_step is True
    assert spec.on_epoch is False
    assert spec.enabled is True

    spec_val = Metric.SPEARMAN_STEP.log_spec(Stage.VAL)
    assert spec_val.enabled is False


def test_candidate_oracle_hit_metrics_log_like_training_scalars() -> None:
    for metric in (Metric.CANDIDATE_TOP1_ORACLE_HIT, Metric.CANDIDATE_TOP3_ORACLE_HIT):
        train_spec = metric.log_spec(Stage.TRAIN)
        assert train_spec.on_step is True
        assert train_spec.on_epoch is True
        assert train_spec.prog_bar is False

        val_spec = metric.log_spec(Stage.VAL)
        assert val_spec.on_step is False
        assert val_spec.on_epoch is True
        assert val_spec.enabled is True


def test_metric_log_spec_val_only() -> None:
    spec_train = Metric.PRED_RRI_BIAS2.log_spec(Stage.TRAIN)
    assert spec_train.enabled is False

    spec_val = Metric.PRED_RRI_BIAS2.log_spec(Stage.VAL)
    assert spec_val.on_epoch is True
    assert spec_val.enabled is True
