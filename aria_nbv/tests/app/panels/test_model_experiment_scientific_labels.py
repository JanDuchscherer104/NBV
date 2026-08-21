"""Regression tests for model and experiment scientific label boundaries."""

# ruff: noqa: S101

from __future__ import annotations

from aria_nbv.app import scientific_labels
from aria_nbv.app.panels.optuna_sweep import _optuna_field_label
from aria_nbv.app.panels.wandb import _wandb_metric_label


def test_scientific_labels_support_all_display_modes() -> None:
    label = scientific_labels.scientific_label("target_rri")

    symbols = scientific_labels.format_scientific_label(label, mode="Symbols", surface="markdown")
    text = scientific_labels.format_scientific_label(label, mode="Text", surface="markdown")
    both = scientific_labels.format_scientific_label(label, mode="Both", surface="markdown")

    assert symbols.startswith("$") and "$" in symbols[1:]
    assert text == "Target RRI (fraction)"
    assert both.startswith("$") and "Target RRI" in both


def test_dynamic_model_labels_preserve_raw_unknown_keys() -> None:
    assert _wandb_metric_label("train/pred_rri_mean_epoch") == "Target RRI (fraction)"
    assert _wandb_metric_label("train/custom_metric") == "Train/Custom Metric"
    assert _optuna_field_label("rri") == "Oracle RRI (fraction)"
    assert _optuna_field_label("param.learning_rate") == "Param.Learning Rate"
