"""One-epoch CUDA optimization proofs for privileged Q_H decoder/carrier pairs."""

# ruff: noqa: S101

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Literal

import pytest
import pytorch_lightning as pl
import torch
from torch.utils.data import DataLoader, Dataset

from aria_nbv.data_handling.qh_data import QhBatch
from aria_nbv.lightning.lit_trainer_callbacks import TrainerCallbacksConfig
from aria_nbv.lightning.lit_trainer_factory import TrainerFactoryConfig
from aria_nbv.lightning.qh_experiment import QhCheckpointSelectionSpec, QhFitRequest
from aria_nbv.lightning.qh_module import QhLightningModule, QhLightningModuleConfig
from aria_nbv.vin.models.target_finite_horizon import TargetFiniteHorizonScorerConfig
from aria_nbv.vin.modules.qh_scene_encoders import QhSelectedSurfacePointSceneEncoderConfig
from aria_nbv.vin.modules.qh_value_decoders import (
    QhCoralValueDecoderConfig,
    QhPredeclaredPhysicalCoralSupport,
)
from tests.lightning.test_qh_experiment import (
    _coral_experiment,
    _DatasetConfig,
    _dense_dataset,
    _experiment,
)
from tests.lightning.test_qh_module import _CONTRACT, _batch
from tests.vin.test_target_finite_horizon import _cfplus_actor


class _RepeatedBatchDataset(Dataset[QhBatch]):
    """Expose one immutable batch twice so S1's staged gradient path can open."""

    def __init__(self) -> None:
        batch = _batch()
        self.batch = replace(batch, actor=_cfplus_actor(steps=2, width=3))

    def __len__(self) -> int:
        return 2

    def __getitem__(self, index: int) -> QhBatch:
        del index
        return self.batch


class _PrivilegedBatchDataModule(pl.LightningDataModule):
    """Bind the minimum lifecycle contract around an in-memory CF+ batch."""

    experiment_profile = "qh_cfplus_gt_depth_v1"
    actor_state_contract_hash = "cuda-smoke-cfplus-actor-v1"
    learning_contract_hash = "cuda-smoke-dense-q1-v1"
    geometry_contract_hash = "cuda-smoke-selected-depth-geometry-v1"
    learning_contract = SimpleNamespace(data_contract=_CONTRACT)

    def __init__(self) -> None:
        super().__init__()
        self.dataset = _RepeatedBatchDataset()

    def train_dataloader(self) -> DataLoader:
        """Return two optimizer transactions within one epoch."""

        return DataLoader(self.dataset, batch_size=None, num_workers=0)

    def val_dataloader(self) -> DataLoader:
        """Return one held-out transaction over the same smoke fixture."""

        return DataLoader(self.dataset, batch_size=None, num_workers=0)


def _scorer_config(
    *,
    decoder: Literal["regression", "coral"],
    carrier: Literal["h0", "s1"],
) -> TargetFiniteHorizonScorerConfig:
    """Return one closed CF+ scorer variant without changing value semantics."""

    value_decoder = None
    if decoder == "coral":
        value_decoder = QhCoralValueDecoderConfig(
            support=QhPredeclaredPhysicalCoralSupport.create(
                source_population_digest="cuda-smoke-population-v1",
                ordered_input_digest="cuda-smoke-physical-rule-input-v1",
                physical_rule="symmetric-root-gain-support-v1",
                bin_edges=(-0.5, 0.5),
                bin_values=(-1.0, 0.0, 1.0),
            ),
            preinit_bias=False,
        )
    updates: dict[str, object] = {}
    if value_decoder is not None:
        updates["value_decoder"] = value_decoder
    if carrier == "s1":
        updates.update(
            representation_semantics="root_moments_plus_selected_surface_points_identity_start_v1",
            scene_encoder=QhSelectedSurfacePointSceneEncoderConfig(
                pixel_stride=1,
                view_chunk_size=1,
                point_hidden_dim=16,
                coordinate_scale_m=2.0,
            ),
        )
    return TargetFiniteHorizonScorerConfig(
        hidden_dim=32,
        dropout=0.0,
        max_horizon=2,
        experiment_profile="qh_cfplus_gt_depth_v1",
        **updates,
    )


@pytest.mark.skipif(not torch.cuda.is_available(), reason="one-epoch Q_H smoke requires CUDA")
@pytest.mark.parametrize("decoder", ["regression", "coral"])
@pytest.mark.parametrize("carrier", ["h0", "s1"])
def test_qh_privileged_decoder_carrier_pair_trains_one_cuda_epoch(
    decoder: Literal["regression", "coral"],
    carrier: Literal["h0", "s1"],
) -> None:
    """Prove real updates for H0/S1 with continuous regression or CORAL.

    The fixture is an optimization smoke, not scientific evidence: train and
    validation deliberately reuse one in-memory CF+ population. Two batches
    are necessary for identity-start S1 because the first update opens only
    the final residual projection and the second can reach the point MLP.
    Bundle publication is intentionally absent because CF+ is privileged and
    non-deployable; deployable CF0 bundle reconstruction is covered separately.
    """

    torch.manual_seed(41)
    scorer = _scorer_config(decoder=decoder, carrier=carrier).setup_target()
    module = QhLightningModule(
        QhLightningModuleConfig(
            lr_scheduler=None,
            max_horizon=2,
            experiment_profile="qh_cfplus_gt_depth_v1",
            selected_observation_protocol="cf_gt",
            privileged=True,
            actor_state_contract_hash=_PrivilegedBatchDataModule.actor_state_contract_hash,
            learning_contract_hash=_PrivilegedBatchDataModule.learning_contract_hash,
            geometry_contract_hash=_PrivilegedBatchDataModule.geometry_contract_hash,
        ),
        scorer=scorer,
    )
    initial = deepcopy(module.online_scorer.state_dict())
    trainer = TrainerFactoryConfig(
        accelerator="gpu",
        devices=1,
        max_epochs=1,
        deterministic=True,
        use_wandb=False,
        enable_validation=True,
        limit_train_batches=2,
        limit_val_batches=1,
        num_sanity_val_steps=0,
        gradient_clip_val=None,
        callbacks=TrainerCallbacksConfig(
            use_model_checkpoint=False,
            use_lr_monitor=False,
            use_tqdm_progress_bar=False,
            use_rich_model_summary=False,
        ),
    ).setup_target()

    trainer.fit(module, datamodule=_PrivilegedBatchDataModule())

    assert module.optimizer_updates.item() == 2
    assert torch.isfinite(module.validation_loss_sum)
    assert any(
        not torch.equal(value.cpu(), initial[name].cpu()) for name, value in module.online_scorer.state_dict().items()
    )
    smoke_batch = _RepeatedBatchDataset().batch.to(module.device, non_blocking=False)
    objective = module.compute_learning_objective(smoke_batch)
    assert torch.isfinite(objective.loss)
    output = module(smoke_batch.actor)
    assert (output.value_auxiliary is not None) is (decoder == "coral")
    if carrier == "s1":
        assert torch.count_nonzero(module.online_scorer.scene_encoder.point_update.weight) > 0
        assert any(
            name.startswith("scene_encoder.point_encoder.") and not torch.equal(value.cpu(), initial[name].cpu())
            for name, value in module.online_scorer.state_dict().items()
        )


@pytest.mark.skipif(not torch.cuda.is_available(), reason="one-epoch Q_H smoke requires CUDA")
@pytest.mark.parametrize("decoder", ["regression", "coral"])
def test_qh_deployable_decoder_trains_and_reloads_cuda_bundle(
    decoder: Literal["regression", "coral"],
    tmp_path: Path,
) -> None:
    """Prove one CF0 epoch, immutable receipts, and exact-head bundle reload."""

    base = (_coral_experiment() if decoder == "coral" else _experiment()).config
    trainer = TrainerFactoryConfig(
        accelerator="gpu",
        devices=1,
        max_epochs=1,
        deterministic=True,
        use_wandb=False,
        enable_validation=True,
        limit_train_batches=1,
        limit_val_batches=1,
        num_sanity_val_steps=0,
        gradient_clip_val=None,
        callbacks=base.trainer.callbacks,
    )
    experiment = base.model_copy(deep=True, update={"trainer": trainer}).setup_target()
    request = QhFitRequest(
        train=_DatasetConfig(tmp_path / "train.zarr", _dense_dataset("train", 0)),  # type: ignore[arg-type]
        validation=_DatasetConfig(tmp_path / "val.zarr", _dense_dataset("validation", 20)),  # type: ignore[arg-type]
        test=_DatasetConfig(tmp_path / "test.zarr", _dense_dataset("test", 40)),  # type: ignore[arg-type]
        warm_start_from=None,
        checkpoint_selection=QhCheckpointSelectionSpec(),
        seed=41,
        output_bundle_dir=tmp_path / f"{decoder}-bundle",
    )

    result = experiment.fit(request)
    runtime = experiment.load_for_inference(result.bundle, device="cuda")
    training_receipt = json.loads(result.training_receipt_path.read_text(encoding="utf-8"))
    manifest = json.loads((result.bundle.bundle_path / "manifest.json").read_text(encoding="utf-8"))

    assert training_receipt["optimizer_updates"] >= 1
    assert runtime.scorer.training is False
    assert runtime.scorer.config.value_decoder.kind == decoder
    assert manifest["dependencies"]["pytorch3d_vcs_commit"] == "b6a77ad7aaf41ed90fca80ce6a2bac3c462a7881"
