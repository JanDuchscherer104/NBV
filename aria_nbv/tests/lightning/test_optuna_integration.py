"""Optuna integration tests for aria_nbv."""

from __future__ import annotations

# ruff: noqa: S101
from typing import TYPE_CHECKING

from pydantic import Field
from pytorch_lightning.callbacks import Callback

from aria_nbv.configs import OptunaConfig
from aria_nbv.lightning.lit_trainer_callbacks import TrainerCallbacksConfig
from aria_nbv.utils import BaseConfig, Optimizable, optimizable_field

if TYPE_CHECKING:
    from collections.abc import Sequence

EXPECTED_DROPOUT = 0.2
EXPECTED_DISCRETE = 1
EXPECTED_CHOICE = "a"


class DummyTrial:
    """Minimal Optuna-like trial stub for tests."""

    def __init__(self, number: int = 0) -> None:
        """Create a dummy trial with a fixed number."""
        self.number = int(number)
        self.params: dict[str, object] = {}
        self.user_attrs: dict[str, object] = {}

    def suggest_float(
        self,
        name: str,
        low: float,
        high: float,
        *,
        log: bool = False,
    ) -> float:
        """Return a deterministic midpoint float suggestion."""
        del log
        value = (float(low) + float(high)) / 2.0
        self.params[name] = value
        return value

    def suggest_int(
        self,
        name: str,
        low: int,
        high: int,
        *,
        step: int = 1,
        log: bool = False,
    ) -> int:
        """Return a deterministic integer suggestion."""
        del high, log
        value = int(low) + (int(step) - 1)
        self.params[name] = value
        return value

    def suggest_categorical(self, name: str, choices: Sequence[object]) -> object:
        """Return the first categorical choice."""
        value = choices[0]
        self.params[name] = value
        return value

    def set_user_attr(self, key: str, value: object) -> None:
        """Record a user attribute for the trial."""
        self.user_attrs[str(key)] = value


class InnerConfig(BaseConfig):
    """Inner config with an optimizable field."""

    dropout: float = optimizable_field(
        default=0.0,
        optimizable=Optimizable.continuous(low=0.0, high=0.4),
        ge=0.0,
        lt=1.0,
    )


class OuterConfig(BaseConfig):
    """Outer config nesting list/dict optimizables."""

    inner: InnerConfig = Field(default_factory=InnerConfig)
    values: list[object] = Field(
        default_factory=lambda: [
            Optimizable.discrete(low=1, high=3, step=1),
            7,
        ],
    )
    mapping: dict[str, object] = Field(
        default_factory=lambda: {
            "choice": Optimizable.categorical(choices=("a", "b")),
        },
    )


def test_optuna_setup_optimizables_traverses_tree() -> None:
    """Ensure Optuna suggestions traverse nested configs, lists, and dicts."""
    cfg = OuterConfig()
    trial = DummyTrial(number=3)
    opt_cfg = OptunaConfig()

    opt_cfg.setup_optimizables(cfg, trial)

    assert cfg.inner.dropout == EXPECTED_DROPOUT
    assert cfg.values[0] == EXPECTED_DISCRETE
    assert cfg.mapping["choice"] == EXPECTED_CHOICE
    assert opt_cfg.suggested_params["inner.dropout"] == EXPECTED_DROPOUT
    assert opt_cfg.suggested_params["values[0]"] == EXPECTED_DISCRETE
    assert opt_cfg.suggested_params["mapping.choice"] == EXPECTED_CHOICE


class DummyPruningCallback(Callback):
    """Placeholder pruning callback for tests."""


class DummyOptunaConfig:
    """OptunaConfig stand-in for pruning tests."""

    monitor: str = "val/loss"

    def get_pruning_callback(self, trial: object) -> Callback:
        """Return a dummy pruning callback."""
        del trial
        return DummyPruningCallback()


def test_trainer_callbacks_inject_optuna_pruning() -> None:
    """Ensure callbacks add pruning when trial is provided."""
    cfg = TrainerCallbacksConfig(
        use_model_checkpoint=True,
        use_early_stopping=True,
        use_optuna_pruning=False,
        use_tqdm_progress_bar=False,
        use_rich_progress_bar=False,
        use_rich_model_summary=False,
    )

    callbacks = cfg.setup_target(
        trial=DummyTrial(),
        optuna_config=DummyOptunaConfig(),  # type: ignore[arg-type]
        has_logger=False,
    )

    assert cfg.use_model_checkpoint is False
    assert cfg.use_early_stopping is False
    assert cfg.use_optuna_pruning is True
    assert any(isinstance(cb, DummyPruningCallback) for cb in callbacks)
