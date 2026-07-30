"""Finite-number contracts for shared Lightning optimizer configuration."""

# ruff: noqa: S101

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from aria_nbv.lightning.lit_module import VinLightningModuleConfig
from aria_nbv.lightning.optimizers import AdamWConfig, OneCycleSchedulerConfig, ReduceLrOnPlateauConfig

NONFINITE = (float("nan"), float("inf"), float("-inf"))


@pytest.mark.parametrize("value", NONFINITE)
@pytest.mark.parametrize(
    ("config_type", "field"),
    [
        (AdamWConfig, "learning_rate"),
        (AdamWConfig, "weight_decay"),
        (ReduceLrOnPlateauConfig, "factor"),
        (ReduceLrOnPlateauConfig, "threshold"),
        (ReduceLrOnPlateauConfig, "min_lr"),
        (ReduceLrOnPlateauConfig, "eps"),
        (OneCycleSchedulerConfig, "max_lr"),
        (OneCycleSchedulerConfig, "base_momentum"),
        (OneCycleSchedulerConfig, "max_momentum"),
        (OneCycleSchedulerConfig, "div_factor"),
        (OneCycleSchedulerConfig, "final_div_factor"),
        (OneCycleSchedulerConfig, "pct_start"),
    ],
)
def test_optimizer_float_fields_reject_nonfinite_values(
    config_type: type[AdamWConfig | ReduceLrOnPlateauConfig | OneCycleSchedulerConfig],
    field: str,
    value: float,
) -> None:
    with pytest.raises(ValidationError) as error:
        config_type.model_validate({field: value})

    assert any(item["loc"][0] == field and item["type"] == "finite_number" for item in error.value.errors())


@pytest.mark.parametrize("value", NONFINITE)
def test_plateau_min_lr_rejects_nonfinite_list_elements(value: float) -> None:
    with pytest.raises(ValidationError) as error:
        ReduceLrOnPlateauConfig(min_lr=[0.0, value])

    assert any(
        item["loc"][0] == "min_lr" and item["loc"][-1] == 1 and item["type"] == "finite_number"
        for item in error.value.errors()
    )


@pytest.mark.parametrize(
    ("config", "field"),
    [
        (AdamWConfig(), "learning_rate"),
        (ReduceLrOnPlateauConfig(), "threshold"),
        (OneCycleSchedulerConfig(), "pct_start"),
    ],
)
@pytest.mark.parametrize("value", NONFINITE)
def test_assignment_rejects_nonfinite_values(config: Any, field: str, value: float) -> None:
    with pytest.raises(ValidationError):
        setattr(config, field, value)


def test_finite_optimizer_values_preserve_valid_construction() -> None:
    adamw = AdamWConfig(learning_rate=2e-4, weight_decay=2e-3)
    plateau = ReduceLrOnPlateauConfig(factor=0.4, threshold=2e-4, min_lr=[0.0, 1e-6], eps=1e-9)
    one_cycle = OneCycleSchedulerConfig(
        max_lr=None,
        base_momentum=0.8,
        max_momentum=0.9,
        div_factor=20.0,
        final_div_factor=2e3,
        pct_start=0.25,
    )

    assert adamw.learning_rate == pytest.approx(2e-4)
    assert plateau.min_lr == [0.0, 1e-6]
    assert one_cycle.max_lr is None
    assert one_cycle.pct_start == pytest.approx(0.25)


@pytest.mark.parametrize("value", NONFINITE)
def test_one_step_module_propagates_shared_optimizer_finiteness(value: float) -> None:
    with pytest.raises(ValidationError) as error:
        VinLightningModuleConfig.model_validate({"optimizer": {"weight_decay": value}})

    assert error.value.errors()[0]["loc"] == ("optimizer", "weight_decay")
