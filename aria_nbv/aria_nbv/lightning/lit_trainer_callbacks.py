"""Construct the callback set owned by each Lightning trainer.

This module provides config-as-factory wiring for checkpointing, early
stopping, learning-rate logging, progress display, model summaries, backbone
finetuning, timers, and Optuna pruning. It owns callback compatibility and
schedule validation; the trainer factory owns attachment and lifecycle calls.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Self

from pydantic import model_validator
from pytorch_lightning.callbacks import (
    BackboneFinetuning,
    Callback,
    EarlyStopping,
    LearningRateMonitor,
    ModelCheckpoint,
    RichModelSummary,
    RichProgressBar,
    Timer,
    TQDMProgressBar,
)

from ..configs import PathConfig
from ..utils import Console, TargetConfig

if TYPE_CHECKING:
    from optuna import Trial

    from ..configs.optuna_config import OptunaConfig


class CustomTQDMProgressBar(TQDMProgressBar):
    """Custom TQDM progress bar that hides the version number (v_num)."""

    def get_metrics(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        """Return Lightning progress metrics without the logger version field."""

        items = super().get_metrics(*args, **kwargs)
        items.pop("v_num", None)
        return items


class CustomRichProgressBar(RichProgressBar):
    """Custom Rich progress bar that hides the version number (v_num)."""

    def get_metrics(self, trainer, pl_module):  # type: ignore[no-untyped-def]
        """Return Rich progress metrics without the logger version field."""

        items = super().get_metrics(trainer, pl_module)
        items.pop("v_num", None)
        return items


class TrainerCallbacksConfig(TargetConfig[list[Callback]]):
    """Configure one mutually compatible Lightning callback collection.

    :meth:`setup_target` may adapt checkpoint, early-stopping, and pruning
    flags for an Optuna trial. The returned callback objects are then owned and
    invoked by the external Lightning trainer.
    """

    @property
    def target_type(self) -> type[list]:
        """Factory target for `aria_nbv.utils.base_config.BaseConfig.setup_target`."""
        return list

    use_model_checkpoint: bool = True
    """Attach a model-checkpoint callback using the fields below."""

    checkpoint_monitor: str = "train/loss"
    """Logged metric key used to rank checkpoints."""
    checkpoint_mode: str = "min"
    """Checkpoint ranking direction, conventionally ``"min"`` or ``"max"``."""
    checkpoint_dir: Path | None = None
    """Checkpoint directory; ``None`` resolves through :class:`PathConfig`."""
    checkpoint_filename: str = "epoch={epoch}-step={step}-train-loss={train/loss:.4f}"
    """Lightning format template evaluated from epoch, step, and logged metrics."""
    checkpoint_save_top_k: int = 1
    """Number of monitor-ranked checkpoints retained by Lightning."""
    checkpoint_auto_insert_metric_name: bool = False
    """Let Lightning inject monitor names into the checkpoint filename."""
    checkpoint_save_last: bool | None = None
    """Lightning tri-state policy for maintaining a ``last.ckpt`` alias/copy."""
    checkpoint_every_n_train_steps: int | None = None
    """Optional positive optimizer-step checkpoint cadence."""
    checkpoint_train_time_interval: dict[str, int] | None = None
    """Optional positive wall-clock cadence accepted by `datetime.timedelta`."""
    checkpoint_every_n_epochs: int | None = None
    """Optional positive epoch checkpoint cadence."""
    checkpoint_save_on_train_epoch_end: bool | None = None
    """Optional override for Lightning's train-epoch-end checkpoint timing."""

    use_early_stopping: bool = False
    """Attach an early-stopping callback for the configured monitor."""

    early_stopping_monitor: str = "val_loss"
    """Logged metric key observed by early stopping."""

    early_stopping_mode: str = "min"
    """Early-stopping improvement direction, ``"min"`` or ``"max"``."""

    early_stopping_patience: int = 5
    """Validation checks without improvement allowed before stopping."""

    use_lr_monitor: bool = True
    """Attach learning-rate logging when the trainer has a logger."""

    lr_logging_interval: str = "step"
    """Learning-rate logging cadence passed to Lightning."""

    use_optuna_pruning: bool = False
    """Enable Optuna pruning callback for hyperparameter optimisation runs."""

    use_rich_progress_bar: bool = False
    """Enable the Rich progress bar; mutually exclusive with TQDM."""
    use_tqdm_progress_bar: bool = True
    """Enable the TQDM progress bar; mutually exclusive with Rich."""
    tqdm_refresh_rate: int = 1
    """TQDM refresh cadence in training batches."""

    use_rich_model_summary: bool = True
    """Attach a Rich model-tree summary callback."""

    rich_summary_max_depth: int = 4
    """Maximum module-tree depth rendered by the Rich summary."""

    use_backbone_finetuning: bool = False
    """Attach Lightning's staged backbone-unfreezing callback."""

    backbone_unfreeze_at_epoch: int = 10
    """Zero-based epoch at which the callback unfreezes the backbone."""

    backbone_lambda_func: str | None = None
    """Optional serialized learning-rate lambda consumed by backbone finetuning."""

    backbone_train_bn: bool = True
    """Keep backbone batch-normalization layers trainable after unfreezing."""

    use_timer: bool = False
    """Attach a Lightning wall-clock timer callback."""

    timer_duration: dict[str, int] | None = None
    """Optional duration mapping accepted by `datetime.timedelta`."""

    timer_interval: str = "step"
    """Timer check cadence passed to Lightning."""

    @model_validator(mode="after")
    def _validate_progress_bars_mutually_exclusive(self) -> Self:
        if self.use_rich_progress_bar and self.use_tqdm_progress_bar:
            raise ValueError("use_rich_progress_bar and use_tqdm_progress_bar are mutually exclusive. Enable only one.")
        return self

    @model_validator(mode="after")
    def _validate_checkpoint_schedule(self) -> Self:
        schedule_fields = {
            "checkpoint_every_n_train_steps": self.checkpoint_every_n_train_steps,
            "checkpoint_train_time_interval": self.checkpoint_train_time_interval,
            "checkpoint_every_n_epochs": self.checkpoint_every_n_epochs,
        }
        enabled = [name for name, value in schedule_fields.items() if value is not None]
        if len(enabled) > 1:
            raise ValueError(
                f"ModelCheckpoint schedule params are mutually exclusive; set only one of {', '.join(enabled)}."
            )

        if self.checkpoint_every_n_train_steps is not None and int(self.checkpoint_every_n_train_steps) <= 0:
            raise ValueError("checkpoint_every_n_train_steps must be > 0 when set.")
        if self.checkpoint_every_n_epochs is not None and int(self.checkpoint_every_n_epochs) <= 0:
            raise ValueError("checkpoint_every_n_epochs must be > 0 when set.")
        if self.checkpoint_train_time_interval is not None:
            try:
                interval = timedelta(**self.checkpoint_train_time_interval)
            except Exception as exc:  # noqa: BLE001
                raise ValueError(
                    f"Invalid checkpoint_train_time_interval={self.checkpoint_train_time_interval}. "
                    "Expected a dict accepted by `datetime.timedelta`."
                ) from exc
            if interval.total_seconds() <= 0:
                raise ValueError("checkpoint_train_time_interval must be > 0 seconds when set.")
        return self

    def setup_target(
        self,
        model_name: str | None = None,
        *,
        has_logger: bool = True,
        trial: "Trial | None" = None,
        optuna_config: "OptunaConfig | None" = None,
    ) -> list[Callback]:
        """Build callbacks and adapt trial-specific ownership flags.

        Args:
            model_name: Optional prefix added to checkpoint filenames.
            has_logger: Whether a trainer logger exists; LR monitoring is
                omitted when false.
            trial: Optional Optuna trial that owns pruning decisions.
            optuna_config: Required pruning config when `trial` enables the
                pruning callback.

        Returns:
            Fresh callback list owned by one external Lightning trainer.

        Notes:
            Trial runs disable checkpointing and early stopping to avoid
            competing persistence/termination owners. Outside a trial, stale
            pruning flags are disabled explicitly.
        """

        console = Console.with_prefix(self.__class__.__name__, "setup_target")
        callbacks: list[Callback] = []

        if trial is not None:
            object.__setattr__(self, "use_model_checkpoint", False)
            object.__setattr__(self, "use_early_stopping", False)
            if self.use_optuna_pruning is False:
                console.warn(
                    "Optuna trial provided but use_optuna_pruning is False. Enabling use_optuna_pruning.",
                )
                object.__setattr__(self, "use_optuna_pruning", True)
        elif self.use_optuna_pruning:
            console.warn(
                "use_optuna_pruning=True but no Optuna trial provided; disabling pruning.",
            )
            object.__setattr__(self, "use_optuna_pruning", False)

        if self.use_model_checkpoint:
            dirpath = self.checkpoint_dir if self.checkpoint_dir is not None else PathConfig().checkpoints
            dirpath.mkdir(parents=True, exist_ok=True)

            ckpt_fn = f"{model_name}-{self.checkpoint_filename}" if model_name else self.checkpoint_filename
            callbacks.append(
                ModelCheckpoint(
                    monitor=self.checkpoint_monitor,
                    mode=self.checkpoint_mode,
                    save_top_k=self.checkpoint_save_top_k,
                    filename=ckpt_fn,
                    auto_insert_metric_name=self.checkpoint_auto_insert_metric_name,
                    save_last=self.checkpoint_save_last,
                    every_n_train_steps=self.checkpoint_every_n_train_steps,
                    train_time_interval=(
                        timedelta(**self.checkpoint_train_time_interval)
                        if self.checkpoint_train_time_interval is not None
                        else None
                    ),
                    every_n_epochs=self.checkpoint_every_n_epochs,
                    save_on_train_epoch_end=self.checkpoint_save_on_train_epoch_end,
                    dirpath=dirpath.as_posix(),
                ),
            )
            console.log(
                "ModelCheckpoint active: "
                f"monitor={self.checkpoint_monitor} dir={dirpath} template={ckpt_fn} "
                f"every_n_train_steps={self.checkpoint_every_n_train_steps} "
                f"train_time_interval={self.checkpoint_train_time_interval} "
                f"every_n_epochs={self.checkpoint_every_n_epochs}"
            )

        if self.use_early_stopping:
            callbacks.append(
                EarlyStopping(
                    monitor=self.early_stopping_monitor,
                    mode=self.early_stopping_mode,
                    patience=self.early_stopping_patience,
                ),
            )

        if self.use_lr_monitor and has_logger:
            callbacks.append(LearningRateMonitor(logging_interval=self.lr_logging_interval))

        if self.use_rich_progress_bar:
            callbacks.append(CustomRichProgressBar())

        if self.use_tqdm_progress_bar:
            callbacks.append(CustomTQDMProgressBar(refresh_rate=self.tqdm_refresh_rate))

        if self.use_rich_model_summary:
            callbacks.append(RichModelSummary(max_depth=self.rich_summary_max_depth))

        if self.use_backbone_finetuning:
            callbacks.append(
                BackboneFinetuning(
                    unfreeze_backbone_at_epoch=self.backbone_unfreeze_at_epoch,
                    lambda_func=eval(self.backbone_lambda_func) if self.backbone_lambda_func else None,
                    backbone_initial_ratio_lr=0.1,
                    should_align=True,
                    train_bn=self.backbone_train_bn,
                ),
            )

        if self.use_timer:
            callbacks.append(
                Timer(
                    duration=timedelta(**self.timer_duration) if self.timer_duration else None,
                    interval=self.timer_interval,
                ),
            )

        if self.use_optuna_pruning:
            if optuna_config is None:
                raise ValueError("optuna_config is required when use_optuna_pruning is True.")
            if trial is None:
                raise ValueError("trial is required when use_optuna_pruning is True.")
            callbacks.append(optuna_config.get_pruning_callback(trial))
            console.log(f"Optuna pruning active (monitor={optuna_config.monitor})")

        return callbacks


__all__ = ["TrainerCallbacksConfig"]
