"""Reproducible experiment boundary for target-conditioned ``Q_H`` training.

The module composes :class:`QhDataModule`, :class:`QhLightningModule`, and
Lightning's [Trainer](https://lightning.ai/docs/pytorch/stable/common/trainer.html)
without widening the scene-wise one-step experiment. It admits every configured
corpus stage, creates an immutable preflight manifest, and records the terminal
loop result separately. It owns run-level seeding, paths, checkpoint admission,
provenance, and one-loop dispatch; lower modules retain data, model, optimizer,
and Trainer policy.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping
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
    """Run root containing checkpoints and create-only lifecycle artifacts."""

    ckpt_path: Path | None = None
    """Full-state parent checkpoint; required for standalone validation or test."""

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
        horizon mismatch, incompatible checkpoint, or provenance-write failure
        therefore fails before :class:`QhLightningModule` or Lightning Trainer
        exists.
        External ``torchrun`` launches one CLI process per rank; only launcher
        rank zero writes the manifest, without requiring an initialized process
        group.
        """

        resolved_stage = Stage.from_str(setup_stage) if setup_stage is not None else self.stage
        if resolved_stage is Stage.VAL and not self.trainer_config.enable_validation:
            raise ValueError("Q_H validation requires trainer_config.enable_validation=true.")
        checkpoint_path = self._resolved_checkpoint_path(resolved_stage)
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
        launcher_rank = _launcher_rank()

        scorer_horizon = self.module_config.scorer.horizon
        if scorer_horizon != data.training_horizon:
            raise ValueError(
                f"Q_H scorer horizon {scorer_horizon} does not match "
                f"training rollout corpus maximum {data.training_horizon}."
            )
        checkpoint = _admit_checkpoint(
            checkpoint_path,
            module_config=self.module_config,
            learning_contract=data.learning_contract,
        )
        if launcher_rank == 0:
            out_dir.mkdir(parents=True, exist_ok=True)
            _create_json(
                out_dir / "run_manifest.json",
                self._run_manifest(
                    data,
                    resolved_stage,
                    launcher_rank=launcher_rank,
                    checkpoint=checkpoint,
                ),
            )

        module = self.module_config.setup_target(learning_contract=data.learning_contract)
        trainer = self.trainer_config.setup_target()
        return trainer, module, data

    def setup_target_and_run(self, stage: Stage | str | None = None) -> pl.Trainer:
        """Construct runtime owners and dispatch exactly one Lightning loop."""

        resolved_stage = Stage.from_str(stage) if stage is not None else self.stage
        trainer, module, data = self.setup_target(resolved_stage)
        checkpoint_path = self._resolved_checkpoint_path(resolved_stage)
        checkpoint = None if checkpoint_path is None else str(checkpoint_path)
        checkpoint_reference = _checkpoint_reference(checkpoint_path)
        error: BaseException | None = None
        try:
            match resolved_stage:
                case Stage.TRAIN:
                    trainer.fit(module, datamodule=data, ckpt_path=checkpoint)
                case Stage.VAL:
                    trainer.validate(module, datamodule=data, ckpt_path=checkpoint)
                case Stage.TEST:
                    trainer.test(module, datamodule=data, ckpt_path=checkpoint)
        except BaseException as caught:
            error = caught
        finally:
            if trainer.is_global_zero:
                try:
                    _create_json(
                        self.out_dir.expanduser().resolve() / "run_result.json",
                        self._run_result(
                            trainer,
                            data,
                            resolved_stage,
                            checkpoint=checkpoint_reference,
                            error=error,
                        ),
                    )
                except BaseException as result_error:
                    if error is None:
                        raise
                    error.add_note(f"Failed to create run_result.json: {result_error}")
        if error is not None:
            raise error
        return trainer

    def _resolved_checkpoint_path(self, stage: Stage) -> Path | None:
        """Resolve and require the parent checkpoint for standalone evaluation."""

        if self.ckpt_path is None:
            if stage in (Stage.VAL, Stage.TEST):
                raise ValueError(f"Q_H standalone stage={stage!s} requires ckpt_path to a full-state checkpoint.")
            return None
        checkpoint = self.ckpt_path.expanduser().resolve()
        if not checkpoint.is_file():
            raise ValueError(f"Q_H checkpoint does not exist or is not a file: {checkpoint}.")
        return checkpoint

    def _run_manifest(
        self,
        data: QhDataModule,
        stage: Stage,
        *,
        launcher_rank: int,
        checkpoint: dict[str, str] | None,
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
        effective_config = self.model_copy(update={"stage": stage})
        return {
            "config": effective_config.model_dump_jsonable(),
            "config_hash": stable_config_hash(effective_config),
            "run": {
                "stage": str(stage),
                "seed": self.seed,
                "launcher_rank": launcher_rank,
                "launcher_kind": launcher_kind,
                "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
                "configured_devices": self.trainer_config.devices,
                "batch_size_per_rank": data.batch_size,
                "container_image": os.environ.get("LRZ_CONTAINER_IMAGE"),
            },
            "checkpoint": checkpoint,
            "corpus": data.provenance,
            "runtime": runtime,
        }

    def _run_result(
        self,
        trainer: pl.Trainer,
        data: QhDataModule,
        stage: Stage,
        *,
        checkpoint: dict[str, str] | None,
        error: BaseException | None,
    ) -> dict[str, object]:
        """Build terminal evidence from the initialized Trainer's actual topology."""

        world_size = int(trainer.world_size)
        dataset = data.dataset_for_stage(stage)
        if dataset is None:
            raise RuntimeError(f"Q_H stage={stage!s} lost its admitted dataset before result recording.")
        padding_rows = distributed_padding_rows(dataset, world_size=world_size)
        emitted_rows = len(dataset) + padding_rows
        effective_config = self.model_copy(update={"stage": stage})
        return {
            "status": "success" if error is None else "failure",
            "config_hash": stable_config_hash(effective_config),
            "run": {
                "stage": str(stage),
                "world_size": world_size,
                "global_step": int(trainer.global_step),
                "batch_size_per_rank": data.batch_size,
                "effective_emitted_batch_size": data.batch_size * world_size,
                "padding_rows": padding_rows,
                "padding_fraction": 0.0 if emitted_rows == 0 else padding_rows / emitted_rows,
            },
            "checkpoint": {
                "parent": checkpoint,
                "evaluated": checkpoint if stage in (Stage.VAL, Stage.TEST) else None,
                "best": _trainer_checkpoint_reference(trainer, "best_model_path") if stage is Stage.TRAIN else None,
                "last": _trainer_checkpoint_reference(trainer, "last_model_path") if stage is Stage.TRAIN else None,
            },
            "error": None
            if error is None
            else {
                "type": f"{type(error).__module__}.{type(error).__qualname__}",
                "message": str(error),
            },
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


def _admit_checkpoint(
    path: Path | None,
    *,
    module_config: QhLightningModuleConfig,
    learning_contract: dict[str, object],
) -> dict[str, str] | None:
    """Load one Lightning checkpoint and reject semantic contract drift."""

    if path is None:
        return None
    try:
        payload = torch.load(path, map_location="cpu", weights_only=True)
    except Exception as error:
        raise ValueError(f"Q_H checkpoint is not a readable full-state Lightning checkpoint: {path}.") from error
    if not isinstance(payload, Mapping) or not isinstance(payload.get("state_dict"), Mapping):
        raise ValueError(f"Q_H checkpoint is not a readable full-state Lightning checkpoint: {path}.")
    hyper_parameters = payload.get("hyper_parameters")
    expected = {
        "config": module_config.model_dump_jsonable(),
        "learning_contract": learning_contract,
    }
    if not isinstance(hyper_parameters, Mapping) or dict(hyper_parameters) != expected:
        raise ValueError(
            "Q_H checkpoint hyper_parameters do not match the current module config "
            f"and corpus learning contract: {path}."
        )
    return _checkpoint_reference(path)


def _checkpoint_reference(path: Path | None) -> dict[str, str] | None:
    """Return a content-addressed parent reference for one checkpoint."""

    if path is None:
        return None
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return {"parent_reference": str(path), "sha256": digest.hexdigest()}


def _trainer_checkpoint_reference(trainer: pl.Trainer, attribute: str) -> dict[str, str] | None:
    """Content-address a checkpoint path exposed by Lightning's callback."""

    callback = getattr(trainer, "checkpoint_callback", None)
    raw_path = None if callback is None else getattr(callback, attribute, None)
    if not raw_path:
        return None
    path = Path(raw_path).expanduser().resolve()
    return _checkpoint_reference(path) if path.is_file() else None


def _create_json(path: Path, payload: dict[str, object]) -> None:
    """Atomically create one JSON artifact without overwriting prior evidence."""

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
        os.link(temporary, path)
    except BaseException:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise
    temporary.unlink()


__all__ = ["QhExperimentConfig", "QhExperimentTarget"]
