"""Regression tests for Lightning trainer construction."""

from __future__ import annotations

# ruff: noqa: S101
from aria_nbv.lightning.lit_trainer_callbacks import TrainerCallbacksConfig
from aria_nbv.lightning.lit_trainer_factory import TrainerFactoryConfig


def test_trainer_factory_disables_default_logger_when_wandb_disabled() -> None:
    """`use_wandb=False` should not fall back to Lightning's TensorBoard logger."""
    cfg = TrainerFactoryConfig(
        use_wandb=False,
        enable_validation=False,
        max_epochs=1,
        callbacks=TrainerCallbacksConfig(
            use_model_checkpoint=False,
            use_lr_monitor=True,
            use_tqdm_progress_bar=False,
            use_rich_model_summary=False,
        ),
    )

    trainer = cfg.setup_target()

    assert trainer.logger is None
    assert trainer.loggers == []
    assert all(callback.__class__.__name__ != "LearningRateMonitor" for callback in trainer.callbacks)
    assert all(callback.__class__.__name__ != "ModelCheckpoint" for callback in trainer.callbacks)
    assert trainer.checkpoint_callback is None


def test_trainer_factory_forwards_sampler_replacement_policy() -> None:
    """Dedicated data modules can retain their explicit distributed samplers."""

    assert TrainerFactoryConfig().use_distributed_sampler is True
    cfg = TrainerFactoryConfig(
        use_distributed_sampler=False,
        use_wandb=False,
        enable_validation=False,
        max_epochs=1,
        callbacks=TrainerCallbacksConfig(
            use_model_checkpoint=False,
            use_lr_monitor=False,
            use_tqdm_progress_bar=False,
            use_rich_model_summary=False,
        ),
    )

    trainer = cfg.setup_target()

    assert trainer._accelerator_connector.use_distributed_sampler is False  # noqa: SLF001
