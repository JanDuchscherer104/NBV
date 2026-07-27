"""Reproducible experiment boundary for target-conditioned ``Q_H`` training.

The module composes :class:`QhDataModule`, :class:`QhLightningModule`, and
Lightning's [Trainer](https://lightning.ai/docs/pytorch/stable/common/trainer.html)
without widening the scene-wise one-step experiment. It admits every configured
corpus stage and atomically records the resolved run identity before model or Trainer state.
It owns run-level seeding, paths, provenance, and one-loop dispatch; lower
modules retain data, model, optimizer, and Trainer policy.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

import pytorch_lightning as pl
import torch
from pydantic import Field, field_validator, model_validator

from ..rollouts.manifest import collect_runtime_provenance
from ..utils import Stage, TargetConfig
from ..utils.fingerprints import stable_config_hash
from .lit_trainer_factory import TrainerFactoryConfig
from .qh_datamodule import QhDataModule, QhDataModuleConfig, distributed_padding_rows
from .qh_module import QhLightningModule, QhLightningModuleConfig

QhExperimentTarget = tuple[pl.Trainer, QhLightningModule, QhDataModule]


def _default_trainer_config() -> TrainerFactoryConfig:
    """Return the manual-optimization-safe ``Q_H`` Trainer defaults."""

    return TrainerFactoryConfig(
        gradient_clip_val=None,
        accumulate_grad_batches=1,
    )


class QhExperimentConfig(TargetConfig[QhExperimentTarget]):
    """Own one target-conditioned finite-horizon Lightning run.

    The field names and :meth:`setup_target_and_run` lifecycle intentionally
    match :class:`aria_nbv.lightning.aria_nbv_experiment.AriaNBVExperimentConfig`.
    ``Q_H`` remains a separate deep module because its admitted multi-step
    corpus and manual fitted-Q optimizer differ
    from scene-wise one-step RRI training.
    """

    stage: Stage = Stage.TRAIN
    """Single Lightning loop to execute: train, validation, or held-out test."""

    seed: int = Field(default=0, ge=0, le=2**32 - 1)
    """Seed shared by Lightning, the DataLoader generator, and train sampler."""

    out_dir: Path = Field(default_factory=lambda: Path(".logs") / "qh")
    """Run root containing checkpoints and the atomic ``run_manifest.json``."""

    ckpt_path: Path | None = None
    """Optional full-state checkpoint forwarded unchanged to the selected loop."""

    trainer_config: TrainerFactoryConfig = Field(default_factory=_default_trainer_config)
    """Trainer policy; default distributed sampling is required."""

    datamodule_config: QhDataModuleConfig
    """All-stage corpus factories and deterministic DataLoader policy."""

    module_config: QhLightningModuleConfig = Field(default_factory=QhLightningModuleConfig)
    """Finite-candidate scorer, fitted-Q loss, optimizer, and target lifecycle."""

    @field_validator("stage", mode="before")
    @classmethod
    def _coerce_stage(cls, value: Any) -> Stage:
        return Stage.from_str(value)

    @property
    def target_type(self) -> type[tuple]:
        """Tuple runtime returned by :meth:`setup_target`."""

        return tuple

    @model_validator(mode="after")
    def _validate_trainer_ownership(self) -> "QhExperimentConfig":
        trainer = self.trainer_config
        if trainer.use_distributed_sampler is not True:
            raise ValueError("Q_H requires Lightning's default distributed sampler replacement.")
        if trainer.gradient_clip_val not in (None, 0, 0.0):
            raise ValueError("Q_H manual optimization requires trainer_config.gradient_clip_val to be None or zero.")
        if trainer.accumulate_grad_batches != 1:
            raise ValueError("Q_H manual optimization requires trainer_config.accumulate_grad_batches=1.")
        if self.stage is Stage.VAL and not trainer.enable_validation:
            raise ValueError("Q_H stage='val' requires trainer_config.enable_validation=true.")
        return self

    def setup_target(self, setup_stage: Stage | str | None = None) -> QhExperimentTarget:
        """Admit the requested stage and persist provenance before construction.

        Corpus setup is metadata-only. A missing validation or test stage,
        horizon mismatch, or provenance-write failure therefore fails before
        :class:`QhLightningModule` or Lightning Trainer exists.
        External ``torchrun`` launches one CLI process per rank; only launcher
        rank zero writes the manifest, without requiring an initialized process
        group.
        """

        resolved_stage = Stage.from_str(setup_stage) if setup_stage is not None else self.stage
        if resolved_stage is Stage.VAL and not self.trainer_config.enable_validation:
            raise ValueError("Q_H validation requires trainer_config.enable_validation=true.")
        pl.seed_everything(self.seed, workers=False)
        out_dir = self.out_dir.expanduser().resolve()
        if self.trainer_config.default_root_dir is None:
            object.__setattr__(self.trainer_config, "default_root_dir", out_dir)
        if self.trainer_config.callbacks.checkpoint_dir is None:
            object.__setattr__(self.trainer_config.callbacks, "checkpoint_dir", out_dir / "checkpoints")

        data = self.datamodule_config.setup_target(seed=self.seed)
        requested_dataset = data.dataset_for_stage(resolved_stage)
        if requested_dataset is None:
            raise ValueError(f"Q_H stage={resolved_stage!s} requires a configured {resolved_stage!s} corpus.")
        launched_world_size = _positive_env_int("WORLD_SIZE", default=1)
        launcher_rank = _launcher_rank()

        scorer_horizon = self.module_config.scorer.horizon
        if scorer_horizon != data.training_horizon:
            raise ValueError(
                f"Q_H scorer horizon {scorer_horizon} does not match "
                f"training rollout corpus maximum {data.training_horizon}."
            )
        if launcher_rank == 0:
            out_dir.mkdir(parents=True, exist_ok=True)
            _atomic_write_json(
                out_dir / "run_manifest.json",
                self._run_manifest(
                    data,
                    resolved_stage,
                    launcher_rank=launcher_rank,
                    launched_world_size=launched_world_size,
                ),
            )

        module = self.module_config.setup_target()
        trainer = self.trainer_config.setup_target()
        return trainer, module, data

    def setup_target_and_run(self, stage: Stage | str | None = None) -> pl.Trainer:
        """Construct runtime owners and dispatch exactly one Lightning loop."""

        resolved_stage = Stage.from_str(stage) if stage is not None else self.stage
        trainer, module, data = self.setup_target(resolved_stage)
        checkpoint = None if self.ckpt_path is None else str(self.ckpt_path.expanduser().resolve())
        match resolved_stage:
            case Stage.TRAIN:
                trainer.fit(module, datamodule=data, ckpt_path=checkpoint)
            case Stage.VAL:
                trainer.validate(module, datamodule=data, ckpt_path=checkpoint)
            case Stage.TEST:
                trainer.test(module, datamodule=data, ckpt_path=checkpoint)
        return trainer

    def _run_manifest(
        self,
        data: QhDataModule,
        stage: Stage,
        *,
        launcher_rank: int,
        launched_world_size: int,
    ) -> dict[str, object]:
        """Build the JSON run identity from already admitted metadata."""

        runtime = collect_runtime_provenance(cwd=Path.cwd())
        runtime["lightning"] = pl.__version__
        runtime["cuda"] = {
            "available": torch.cuda.is_available(),
            "runtime_version": torch.version.cuda,
        }
        launcher_kind = "local"
        if "RANK" in os.environ or "WORLD_SIZE" in os.environ:
            launcher_kind = "torchrun"
        if os.environ.get("SLURM_JOB_ID"):
            launcher_kind = "slurm-torchrun"
        padding_rows = distributed_padding_rows(data.train_dataset, world_size=launched_world_size)
        emitted_rows = len(data.train_dataset) + padding_rows
        return {
            "config": self.model_dump_jsonable(),
            "config_hash": stable_config_hash(self),
            "run": {
                "stage": str(stage),
                "seed": self.seed,
                "launcher_rank": launcher_rank,
                "launcher_kind": launcher_kind,
                "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
                "launched_world_size": launched_world_size,
                "configured_devices": self.trainer_config.devices,
                "batch_size_per_rank": data.batch_size,
                "effective_emitted_batch_size": data.batch_size * launched_world_size,
                "training_padding_rows": padding_rows,
                "training_padding_fraction": 0.0 if emitted_rows == 0 else padding_rows / emitted_rows,
                "container_image": os.environ.get("LRZ_CONTAINER_IMAGE"),
            },
            "corpus": data.provenance,
            "runtime": runtime,
        }


def _launcher_rank() -> int:
    """Return the pre-DDP launcher rank from TorchRun or Slurm variables."""

    return _positive_env_int("RANK", default=_positive_env_int("SLURM_PROCID", default=0), allow_zero=True)


def _positive_env_int(name: str, *, default: int, allow_zero: bool = False) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    value = int(raw)
    minimum = 0 if allow_zero else 1
    if value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}, got {raw!r}.")
    return value


def _atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    """Atomically replace one plain JSON artifact on the destination filesystem."""

    temporary: Path | None = None
    try:
        with NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
        ) as stream:
            temporary = Path(stream.name)
            json.dump(payload, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise


__all__ = ["QhExperimentConfig", "QhExperimentTarget"]
