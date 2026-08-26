"""Stage-admission contracts for finite-horizon ``Q_H`` loaders."""

# ruff: noqa: S101

from __future__ import annotations

from dataclasses import replace
from typing import Any, Literal

import pytest
from torch.utils.data import Dataset, SequentialSampler

import aria_nbv.lightning.qh_datamodule as qh_datamodule
from aria_nbv.data_handling.qh_data import QhChain
from aria_nbv.data_handling.qh_data.views import QhActorStateContract
from aria_nbv.rollouts.qh_reader import QhDataContract
from aria_nbv.utils.fingerprints import stable_msgspec_hash

_CONTRACT = QhDataContract(
    schema_version="qh-v1",
    target_protocol="v1_observed",
    reward_metric="target-root-gain",
    return_semantics="finite-horizon",
    td_semantics="fitted-q",
    discount_gamma=0.95,
    reason_code_version="reasons-v1",
    actor_store_version="vin-v1",
)
_ACTOR_CONTRACT = QhActorStateContract("none", "none", "actor-manifest", ())


class _StructuralDataset(Dataset[QhChain]):
    def __init__(
        self,
        scene: str,
        *,
        size: int = 1,
        max_horizon: int = 1,
        contract: QhDataContract = _CONTRACT,
        actor_state_contract: QhActorStateContract = _ACTOR_CONTRACT,
    ) -> None:
        self.size = size
        self.scenes = frozenset({scene})
        self.max_horizon = max_horizon
        self.contract = contract
        self.actor_state_contract = actor_state_contract
        self.provenance: dict[str, Any] = {"scene": scene}

    def __len__(self) -> int:
        return self.size

    def __getitem__(self, index: int) -> QhChain:
        raise IndexError(f"Structural admission fixture has no materialized chain at {index}.")


def test_datamodule_rejects_stage_datasets_with_differing_maximum_horizons() -> None:
    with pytest.raises(ValueError, match="share one maximum horizon"):
        qh_datamodule.QhDataModule(
            train=_StructuralDataset("train", max_horizon=4),
            val=_StructuralDataset("val", max_horizon=2),
            test=_StructuralDataset("test", max_horizon=3),
            seed=7,
        )


def test_learning_contract_hash_binds_maximum_horizon_and_weighting() -> None:
    short = qh_datamodule.QhDataModule(train=_StructuralDataset("short", max_horizon=2), seed=7)
    long = qh_datamodule.QhDataModule(train=_StructuralDataset("long", max_horizon=3), seed=7)

    assert short.learning_contract.horizon_weighting == qh_datamodule.QH_HORIZON_WEIGHTING
    assert short.learning_contract_hash != long.learning_contract_hash


def test_datamodule_rejects_an_empty_configured_stage() -> None:
    with pytest.raises(ValueError, match="at least one chain"):
        qh_datamodule.QhDataModule(train=_StructuralDataset("train"), val=_StructuralDataset("val", size=0), seed=7)


def test_datamodule_rejects_pairwise_scene_overlap() -> None:
    with pytest.raises(ValueError, match="train/test.*overlap scenes"):
        qh_datamodule.QhDataModule(train=_StructuralDataset("shared"), test=_StructuralDataset("shared"), seed=7)


def test_datamodule_rejects_different_semantic_contracts() -> None:
    with pytest.raises(ValueError, match="incompatible learning semantics"):
        qh_datamodule.QhDataModule(
            train=_StructuralDataset("train"),
            val=_StructuralDataset("val", contract=replace(_CONTRACT, reward_metric="scene-rri")),
            seed=7,
        )


@pytest.mark.parametrize(
    ("field_name", "value"),
    (
        ("candidate_config_hashes", ("candidate-v2",)),
        ("rollout_config_hashes", ("rollout-v2",)),
        ("selection_policies", ("softmax-v2",)),
    ),
)
def test_datamodule_allows_different_stage_population_identity(
    field_name: Literal["candidate_config_hashes", "rollout_config_hashes", "selection_policies"],
    value: tuple[str, ...],
) -> None:
    if field_name == "candidate_config_hashes":
        contract = replace(_CONTRACT, candidate_config_hashes=value)
    elif field_name == "rollout_config_hashes":
        contract = replace(_CONTRACT, rollout_config_hashes=value)
    else:
        contract = replace(_CONTRACT, selection_policies=value)
    data = qh_datamodule.QhDataModule(
        train=_StructuralDataset("train"),
        val=_StructuralDataset("val", contract=contract),
        seed=7,
    )

    assert data.learning_contract.data_contract == _CONTRACT


@pytest.mark.parametrize(
    "actor_contract",
    (
        replace(_ACTOR_CONTRACT, root_evl_profile="evl_v1"),
        replace(_ACTOR_CONTRACT, selected_observation_protocol="cf_gt"),
        replace(_ACTOR_CONTRACT, actor_manifest_hash="other-manifest"),
        replace(
            _ACTOR_CONTRACT,
            evl_block_signature=(("backbone.occ_pr", "float32", (1, 4, 4, 4)),),
        ),
        replace(_ACTOR_CONTRACT, free_input_provenance="native_evl_v1"),
    ),
)
def test_datamodule_rejects_incompatible_actor_state_contracts(
    actor_contract: QhActorStateContract,
) -> None:
    with pytest.raises(ValueError, match="incompatible actor-state contract"):
        qh_datamodule.QhDataModule(
            train=_StructuralDataset("train"),
            val=_StructuralDataset("val", actor_state_contract=actor_contract),
            seed=7,
        )


def test_datamodule_uses_seeded_train_shuffle_and_sequential_evaluation() -> None:
    stages = {
        "train": _StructuralDataset("train", size=8),
        "val": _StructuralDataset("val", size=2),
        "test": _StructuralDataset("test", size=2),
    }
    first = qh_datamodule.QhDataModule(train=stages["train"], val=stages["val"], test=stages["test"], seed=13)
    second = qh_datamodule.QhDataModule(train=stages["train"], val=stages["val"], test=stages["test"], seed=13)

    assert list(first.train_dataloader().sampler) == list(second.train_dataloader().sampler)
    val_loader = first.val_dataloader()
    test_loader = first.test_dataloader()
    assert not isinstance(val_loader, list)
    assert not isinstance(test_loader, list)
    assert isinstance(val_loader.sampler, SequentialSampler)
    assert isinstance(test_loader.sampler, SequentialSampler)


def test_datamodule_requires_exact_named_experiment_profile() -> None:
    actor = replace(_ACTOR_CONTRACT, root_evl_profile="evl_v1", experiment_profile="qh_cf0_v1")
    qh = _StructuralDataset("train", actor_state_contract=actor)
    data = qh_datamodule.QhDataModule(train=qh, seed=7, experiment_profile="qh_cf0_v1")
    assert data.experiment_profile == "qh_cf0_v1"
    assert data.learning_contract == qh_datamodule.QhLearningContract(data_contract=_CONTRACT, max_horizon=1)
    assert data.learning_contract_hash == stable_msgspec_hash(data.learning_contract)
    assert data.actor_state_contract_hash == stable_msgspec_hash(actor)
    with pytest.raises(ValueError, match="experiment profile|selected_observation_protocol"):
        qh_datamodule.QhDataModule(train=qh, seed=7, experiment_profile="qh_cfplus_gt_depth_v1")


def test_named_cf0_datamodule_rejects_legacy_v0_contract() -> None:
    actor = replace(_ACTOR_CONTRACT, root_evl_profile="evl_v1", experiment_profile="qh_cf0_v1")
    qh = _StructuralDataset(
        "train",
        contract=replace(_CONTRACT, target_protocol="v0_gt_input"),
        actor_state_contract=actor,
    )

    with pytest.raises(ValueError, match="requires target_protocol='v1_observed'"):
        qh_datamodule.QhDataModule(train=qh, seed=7, experiment_profile="qh_cf0_v1")
