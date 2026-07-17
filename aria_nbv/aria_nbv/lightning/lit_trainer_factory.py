"""Construct the external Lightning trainer and attach run-owned services.

This module provides one config-as-factory surface for loop limits, devices,
precision, validation cadence, deterministic/debug behavior, callbacks, and
optional W&B logging. It owns trainer construction only; the experiment owns
run paths and seeding, while the module owns scorer/loss/optimizer state.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, Self

import pytorch_lightning as pl
import torch
from pydantic import Field, model_validator
from pytorch_lightning.callbacks import ModelCheckpoint

from ..configs.wandb_config import WandbConfig
from ..utils import Console, TargetConfig
from .lit_trainer_callbacks import TrainerCallbacksConfig

if TYPE_CHECKING:
    from optuna import Trial

    from ..configs.optuna_config import OptunaConfig


class TrainerFactoryConfig(TargetConfig[pl.Trainer]):
    """Configure one external Lightning trainer and its attached services."""

    @property
    def target_type(self) -> type[pl.Trainer]:
        """Return the external Lightning trainer factory target."""

        return pl.Trainer

    is_debug: bool = False
    """Force CPU fast-dev execution, anomaly detection, and no checkpoint callback."""

    fast_dev_run: bool = False
    """Ask Lightning to run one batch per loop as an integration smoke test."""

    accelerator: str = "auto"
    """Lightning accelerator selector such as ``"auto"``, ``"cpu"``, or ``"gpu"``."""

    devices: int | str | Sequence[int] = "auto"
    """Device count, selector, or explicit device-index sequence passed to Lightning."""

    strategy: str | None = "auto"
    """Optional distributed-execution strategy; ``"auto"`` delegates selection."""

    max_epochs: int | None = 50
    """Maximum training epochs; ``None`` delegates the unbounded policy to Lightning."""

    precision: str | int = "32"
    """Lightning numeric-precision policy, including mixed-precision strings."""

    default_root_dir: Path | None = None
    """Root directory used by Lightning for logger-free run artifacts."""

    tf32_matmul_precision: str | None = "medium"
    """Optional process-wide float32 matmul precision set before trainer construction."""

    gradient_clip_val: float | None = 1.0
    """Optional gradient clipping threshold applied by Lightning."""

    accumulate_grad_batches: int = 1
    """Positive number of batches accumulated per optimizer step."""

    log_every_n_steps: int = 1
    """Trainer logging cadence in optimizer/training steps."""

    deterministic: bool | str | None = None
    """Lightning deterministic-algorithm policy; ``None`` preserves framework defaults."""

    limit_train_batches: int | float | None = None
    """Optional absolute count or fraction limiting each training epoch."""

    limit_val_batches: int | float | None = None
    """Optional absolute count or fraction limiting each validation epoch."""

    check_val_every_n_epoch: int = 1
    """Epoch cadence for validation when validation is enabled."""

    num_sanity_val_steps: int = 2
    """Validation batches run before training; ``-1`` checks the entire loader."""
    enable_validation: bool = False
    """Enable validation; false zeroes validation limits/cadence during validation."""

    enable_model_summary: bool = True
    """Enable Lightning's default model summary callback.

    When using `pytorch_lightning.callbacks.RichModelSummary`, consider
    disabling this to avoid duplicate summaries.
    """

    callbacks: TrainerCallbacksConfig = Field(default_factory=TrainerCallbacksConfig)
    """Callback collection factory attached to the constructed trainer."""

    use_wandb: bool = True
    """Use the configured W&B logger outside debug mode."""

    wandb_config: WandbConfig = Field(default_factory=WandbConfig)
    """W&B logger config instantiated only when `use_wandb` is true."""

    @model_validator(mode="after")
    def _debug_defaults(self) -> Self:
        console = Console.with_prefix(self.__class__.__name__, "_debug_defaults")

        if self.is_debug:
            object.__setattr__(self, "fast_dev_run", True)
            object.__setattr__(self, "accelerator", "cpu")
            object.__setattr__(self, "devices", 1)
            object.__setattr__(self.callbacks, "use_model_checkpoint", False)
            torch.autograd.set_detect_anomaly(True)
            console.log(
                "Debug settings: fast_dev_run=True, accelerator=cpu, devices=1, checkpointing disabled, "
                "anomaly detection enabled",
            )

        if self.fast_dev_run:
            Console.with_prefix(self.__class__.__name__).log(
                "Fast dev run enabled; trainer will use a single batch per split.",
            )
        if not self.enable_validation:
            object.__setattr__(self, "limit_val_batches", 0)
            object.__setattr__(self, "check_val_every_n_epoch", 0)
            console.log("Validation disabled: limit_val_batches=0, check_val_every_n_epoch=0, num_sanity_val_steps=0.")
        return self

    def setup_target(
        self,
        experiment: Any | None = None,
        *,
        trial: "Trial | None" = None,
        optuna_config: "OptunaConfig | None" = None,
    ) -> pl.Trainer:
        """Instantiate a Trainer after logger and callback ownership is resolved.

        Args:
            experiment: Optional experiment providing an `optuna_config` fallback.
            trial: Optional Optuna trial forwarded to callback construction.
            optuna_config: Explicit pruning configuration, preferred over the
                experiment fallback.

        Returns:
            External Lightning trainer owning the fresh logger and callbacks.

        Notes:
            TF32 precision is process-wide. Debug mode uses Lightning's default
            logger; normal mode uses W&B only when configured. Checkpointing is
            enabled precisely when callback construction produced a checkpoint
            callback.
        """
        console = Console.with_prefix(self.__class__.__name__, "setup_target")

        resolved_optuna = optuna_config
        if resolved_optuna is None and experiment is not None:
            resolved_optuna = getattr(experiment, "optuna_config", None)

        if self.tf32_matmul_precision is not None:
            try:
                torch.set_float32_matmul_precision(str(self.tf32_matmul_precision))
                console.log(
                    f"Set TF32 matmul precision to '{self.tf32_matmul_precision}'",
                )
            except Exception as exc:  # pragma: no cover - hardware dependent
                console.warn(f"Failed to set TF32 matmul precision: {exc}")

        logger: Any = False
        if self.is_debug:
            logger = True
            console.log("Using default logger (debug mode)")
        elif self.use_wandb:
            logger = self.wandb_config.setup_target()
            console.log(f"Using W&B logger: {self.wandb_config.name}")
        else:
            console.log("No logger configured")

        callbacks = self.callbacks.setup_target(
            model_name=None,
            has_logger=bool(logger),
            trial=trial,
            optuna_config=resolved_optuna,
        )
        enable_checkpointing = any(isinstance(callback, ModelCheckpoint) for callback in callbacks)
        console.log(f"Configured {len(callbacks)} callbacks.")

        return pl.Trainer(
            accelerator=self.accelerator,
            devices=self.devices,
            strategy=self.strategy,
            max_epochs=self.max_epochs,
            precision=self.precision,
            default_root_dir=self.default_root_dir,
            gradient_clip_val=self.gradient_clip_val,
            accumulate_grad_batches=self.accumulate_grad_batches,
            log_every_n_steps=self.log_every_n_steps,
            fast_dev_run=self.fast_dev_run,
            deterministic=self.deterministic,
            limit_train_batches=self.limit_train_batches,
            limit_val_batches=self.limit_val_batches,
            check_val_every_n_epoch=self.check_val_every_n_epoch,
            enable_checkpointing=enable_checkpointing,
            enable_model_summary=bool(self.enable_model_summary),
            callbacks=callbacks,
            logger=logger,
            num_sanity_val_steps=self.num_sanity_val_steps,
        )


__all__ = ["TrainerFactoryConfig"]
