"""Config-as-factory composition for finite-horizon ``Q_H`` experiments.

The module wires the dedicated :class:`QhDataModule`,
:class:`QhLightningModule`, and Lightning Trainer without widening the
scene-wise one-step experiment contract.
"""

from __future__ import annotations

from pathlib import Path

import pytorch_lightning as pl
from pydantic import Field, model_validator

from ..utils import TargetConfig
from .lit_trainer_factory import TrainerFactoryConfig
from .qh_data import QhDataModule, QhDataModuleConfig
from .qh_module import QhLightningModule, QhLightningModuleConfig

QhExperimentTarget = tuple[pl.Trainer, QhLightningModule, QhDataModule]


class QhExperimentConfig(TargetConfig[QhExperimentTarget]):
    """Own one reproducible fitted-Q training run and its three factories."""

    seed: int = 0
    """Global Lightning/PyTorch/DataLoader seed."""

    output_dir: Path = Field(default_factory=lambda: Path(".logs") / "qh")
    """Run root for logs and checkpoints."""

    resume_checkpoint: Path | None = None
    """Optional full-state Lightning checkpoint passed to `Trainer.fit`."""

    trainer: TrainerFactoryConfig = Field(default_factory=lambda: TrainerFactoryConfig(use_distributed_sampler=False))
    """Trainer factory; Lightning sampler replacement must remain disabled."""

    data: QhDataModuleConfig
    """Dedicated transition-data and distributed-sampler configuration."""

    module: QhLightningModuleConfig = Field(default_factory=QhLightningModuleConfig)
    """Dedicated scorer, fitted-Q objective, optimizer, and target lifecycle."""

    @property
    def target_type(self) -> type[tuple]:
        """Tuple runtime returned by :meth:`setup_target`."""

        return tuple

    @model_validator(mode="after")
    def _validate_sampler_ownership(self) -> "QhExperimentConfig":
        if self.trainer.use_distributed_sampler is not False:
            raise ValueError("Q_H requires trainer.use_distributed_sampler=false; QhDataModule owns all samplers.")
        return self

    def setup_target(self) -> QhExperimentTarget:
        """Admit the fit corpus, then construct the module and Trainer.

        The configured :attr:`QhLightningModuleConfig.scorer` horizon must
        equal :attr:`QhDataModule.training_horizon`. This composition check
        runs after bounded reader preflight but before module or Trainer
        construction, preventing inconsistent remaining-budget normalization.
        """

        pl.seed_everything(self.seed, workers=True)
        output_dir = self.output_dir.expanduser().resolve()
        if self.trainer.default_root_dir is None:
            object.__setattr__(self.trainer, "default_root_dir", output_dir)
        if self.trainer.callbacks.checkpoint_dir is None:
            object.__setattr__(self.trainer.callbacks, "checkpoint_dir", output_dir / "checkpoints")
        data = self.data.setup_target()
        data.setup("fit")
        scorer_horizon = self.module.scorer.horizon
        if scorer_horizon != data.training_horizon:
            raise ValueError(
                f"Q_H scorer horizon {scorer_horizon} does not match "
                f"training rollout corpus maximum {data.training_horizon}."
            )
        module = self.module.setup_target()
        trainer = self.trainer.setup_target()
        return trainer, module, data

    def run(self) -> QhExperimentTarget:
        """Construct and fit, forwarding resume exclusively through `ckpt_path`."""

        trainer, module, data = self.setup_target()
        checkpoint = None if self.resume_checkpoint is None else str(self.resume_checkpoint.expanduser().resolve())
        trainer.fit(module, datamodule=data, ckpt_path=checkpoint)
        return trainer, module, data


__all__ = ["QhExperimentConfig", "QhExperimentTarget"]
