"""Shared optimizer and learning-rate scheduler configuration for Lightning.

:class:`AdamWConfig` serves both the one-step
:class:`aria_nbv.lightning.VinLightningModule` and finite-horizon
:class:`aria_nbv.lightning.qh_module.QhLightningModule`. Scheduler factories
provide the common Lightning mapping and step-budget contracts without owning
either objective. Each consuming module retains optimizer selection, stepping
order, and scheduler-admission policy; the Trainer owns the final one-cycle
step budget.
"""

from __future__ import annotations

from typing import Any, Literal

import pytorch_lightning as pl
from pydantic import FiniteFloat
from torch import Tensor
from torch.nn import functional as functional
from torch.optim import AdamW, Optimizer
from torch.optim.lr_scheduler import OneCycleLR, ReduceLROnPlateau

from ..utils import Optimizable, TargetConfig, optimizable_field


class AdamWConfig(TargetConfig[Optimizer]):
    """Configure AdamW for a Lightning module's trainable parameters."""

    @property
    def target_type(self) -> type[Optimizer]:
        """Factory target for `aria_nbv.utils.base_config.BaseConfig.setup_target`."""
        return AdamW

    learning_rate: FiniteFloat = optimizable_field(
        default=1e-3,
        optimizable=Optimizable.continuous(
            low=1e-5,
            high=3e-4,
            log=True,
            description="AdamW learning rate.",
            relies_on={"module_config.lr_scheduler.max_lr": (None,)},
        ),
    )
    """Learning rate for AdamW."""

    weight_decay: FiniteFloat = optimizable_field(
        default=1e-3,
        optimizable=Optimizable.continuous(
            low=1e-4,
            high=1e-1,
            log=True,
            description="AdamW weight decay.",
        ),
    )
    """Weight decay for AdamW."""

    def setup_target(self, params: list[Tensor]) -> Optimizer:
        """Create AdamW over the exact trainable parameter list.

        Args:
            params: Materialized parameters selected by the consuming
                :meth:`aria_nbv.lightning.VinLightningModule.configure_optimizers`
                or
                :meth:`aria_nbv.lightning.qh_module.QhLightningModule.configure_optimizers`.

        Returns:
            Optimizer owned and stepped by Lightning.
        """

        return AdamW(
            params=params,
            lr=self.learning_rate,
            weight_decay=self.weight_decay,
        )


class ReduceLrOnPlateauConfig(TargetConfig[ReduceLROnPlateau]):
    """Configure metric-driven learning-rate decay for Lightning."""

    @property
    def target_type(self) -> type[ReduceLROnPlateau]:
        """Factory target for `aria_nbv.utils.base_config.BaseConfig.setup_target`."""
        return ReduceLROnPlateau

    mode: Literal["min", "max"] = "min"
    """Whether to reduce on metric min or max."""

    factor: FiniteFloat = 0.2
    """Multiplicative factor of LR reduction."""

    patience: int = 2
    """Number of steps with no improvement before reducing the LR."""

    threshold: FiniteFloat = 1e-4
    """Threshold for measuring new optimum."""

    threshold_mode: Literal["rel", "abs"] = "rel"
    """Threshold interpretation (relative or absolute)."""

    cooldown: int = 0
    """Number of epochs to wait before resuming normal operation."""

    min_lr: FiniteFloat | list[FiniteFloat] = 0.0
    """Lower bound on the learning rate."""

    eps: FiniteFloat = 1e-8
    """Minimal decay applied to LR."""

    monitor: str = "train/loss"
    """Metric name to monitor for plateau reduction."""

    interval: Literal["step", "epoch"] = "epoch"
    """Scheduler interval (step or epoch)."""

    frequency: int = 1
    """Scheduler frequency."""

    def setup_target(
        self,
        optimizer: Optimizer,
        *,
        trainer: pl.Trainer | None = None,
    ) -> ReduceLROnPlateau:
        """Create a plateau scheduler over one optimizer.

        Args:
            optimizer: Optimizer whose parameter-group rates are mutated.
            trainer: Accepted for the shared scheduler factory interface; not
                used because plateau scheduling is metric driven.

        Returns:
            Scheduler instance later stepped by Lightning.
        """

        return ReduceLROnPlateau(
            optimizer,
            mode=self.mode,
            factor=self.factor,
            patience=self.patience,
            threshold=self.threshold,
            threshold_mode=self.threshold_mode,
            cooldown=self.cooldown,
            min_lr=self.min_lr,
            eps=self.eps,
        )

    def setup_lightning(
        self,
        optimizer: Optimizer,
        *,
        trainer: pl.Trainer | None = None,
    ) -> dict[str, Any]:
        """Build the Lightning lr_scheduler config for ReduceLROnPlateau.

        Args:
            optimizer: Optimizer instance to schedule.
            trainer: Optional Lightning trainer (unused for plateau).

        Returns:
            Lightning lr_scheduler configuration dictionary.
        """
        scheduler = self.setup_target(optimizer, trainer=trainer)
        return {
            "scheduler": scheduler,
            "monitor": self.monitor,
            "interval": self.interval,
            "frequency": self.frequency,
        }


class OneCycleSchedulerConfig(TargetConfig[OneCycleLR]):
    """Configure a step-wise one-cycle learning-rate and momentum schedule."""

    @property
    def target_type(self) -> type[OneCycleLR]:
        """Return the external one-cycle scheduler factory target."""

        return OneCycleLR

    max_lr: FiniteFloat | None = optimizable_field(
        default=1e-4,
        optimizable=Optimizable.continuous(
            low=1e-5,
            high=3e-3,
            log=True,
            description="OneCycleLR maximum learning rate.",
        ),
    )
    """Maximum learning rate in the cycle (defaults to optimizer LR)."""

    base_momentum: FiniteFloat = 0.85
    """Lower momentum boundary in the cycle."""

    max_momentum: FiniteFloat = 0.95
    """Upper momentum boundary in the cycle."""

    div_factor: FiniteFloat = optimizable_field(
        default=25.0,
        optimizable=Optimizable.continuous(
            low=5.0,
            high=50.0,
            description="OneCycleLR div_factor (initial lr = max_lr / div_factor).",
        ),
    )
    """Initial learning rate = max_lr / div_factor."""

    final_div_factor: FiniteFloat = optimizable_field(
        default=1e4,
        optimizable=Optimizable.continuous(
            low=1e2,
            high=1e5,
            log=True,
            description="OneCycleLR final_div_factor (final lr = max_lr / (div_factor * final_div_factor)).",
        ),
    )
    """Final learning rate = max_lr / (div_factor * final_div_factor)."""

    pct_start: FiniteFloat = optimizable_field(
        default=0.3,
        optimizable=Optimizable.continuous(
            low=0.05,
            high=0.5,
            description="Percentage of cycle spent increasing learning rate.",
        ),
    )
    """Percentage of cycle spent increasing learning rate."""

    anneal_strategy: Literal["cos", "linear"] = "cos"
    """Annealing strategy: 'cos' or 'linear'."""

    def setup_target(
        self,
        optimizer: Optimizer,
        *,
        total_steps: int | None = None,
        trainer: pl.Trainer | None = None,
    ) -> OneCycleLR:
        """Create a one-cycle scheduler after resolving the total step budget.

        Args:
            optimizer: Optimizer whose learning rate and momentum are scheduled.
            total_steps: Explicit positive optimizer-step count. When omitted,
                `trainer.estimated_stepping_batches` or its datamodule/epoch
                fallback is used.
            trainer: Optional configured trainer used for step-budget inference.

        Returns:
            Step-wise scheduler owned by Lightning.
        """

        if total_steps is None:
            total_steps = self._resolve_total_steps(trainer)
        if total_steps <= 0:
            raise ValueError("OneCycleLR requires total_steps > 0.")

        max_lr = self.max_lr
        if max_lr is None:
            max_lr = optimizer.param_groups[0]["lr"]

        return OneCycleLR(
            optimizer,
            max_lr=max_lr,
            total_steps=total_steps,
            pct_start=self.pct_start,
            anneal_strategy=self.anneal_strategy,
            cycle_momentum=True,
            base_momentum=self.base_momentum,
            max_momentum=self.max_momentum,
            div_factor=self.div_factor,
            final_div_factor=self.final_div_factor,
        )

    def setup_lightning(
        self,
        optimizer: Optimizer,
        *,
        total_steps: int | None = None,
        trainer: pl.Trainer | None = None,
    ) -> dict[str, Any]:
        """Build the Lightning lr_scheduler config for OneCycleLR.

        Args:
            optimizer: Optimizer instance to schedule.
            total_steps: Optional total step count for the cycle.
            trainer: Optional Lightning trainer used to infer total_steps.

        Returns:
            Lightning lr_scheduler configuration dictionary.
        """
        scheduler = self.setup_target(
            optimizer,
            total_steps=total_steps,
            trainer=trainer,
        )
        return {"scheduler": scheduler, "interval": "step"}

    @staticmethod
    def _resolve_total_steps(trainer: pl.Trainer | None) -> int:
        if trainer is None:
            raise ValueError(
                "OneCycleLR requires either total_steps or a configured trainer.",
            )

        total_steps = int(getattr(trainer, "estimated_stepping_batches", 0) or 0)
        if total_steps > 0:
            return total_steps

        datamodule = getattr(trainer, "datamodule", None)
        if datamodule is None:
            raise ValueError(
                "Trainer is missing a datamodule; cannot infer total_steps for OneCycleLR.",
            )

        steps_per_epoch = len(datamodule.train_dataloader())
        max_epochs = int(getattr(trainer, "max_epochs", 1) or 1)
        return steps_per_epoch * max_epochs
