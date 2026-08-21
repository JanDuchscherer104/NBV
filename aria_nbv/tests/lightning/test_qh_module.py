"""Objective, masking, and transaction tests for the retained Q_H module."""

# ruff: noqa: S101

from __future__ import annotations

from copy import deepcopy
from dataclasses import fields, replace

import pytest
import torch
from efm3d.aria.pose import PoseTW
from pydantic import ValidationError
from torch import nn
from torch.utils.data import Dataset

from aria_nbv.data_handling.qh_data import (
    QhActorTensors,
    QhBatch,
    QhChain,
    collate_qh_chains,
)
from aria_nbv.data_handling.qh_data.views import QhActorStateContract, QhStaticContext
from aria_nbv.lightning.qh_module import QhLightningModule, QhLightningModuleConfig
from aria_nbv.rollouts.qh_geometry import QhGeometryContract
from aria_nbv.rollouts.qh_reader import QhDataContract
from aria_nbv.utils.fingerprints import stable_msgspec_hash
from tests.data_handling.test_qh import _chain, _snippet


class _TableScorer(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.current = nn.Parameter(torch.tensor([1.0, 2.0, 3.0, 4.0]))
        self.next = nn.Parameter(torch.tensor([1.0, 3.0, 2.0, 4.0]))
        self.calls = 0

    def forward(self, actor: QhActorTensors) -> torch.Tensor:
        self.calls += 1
        width = actor.action_mask.shape[-1]
        current = self.current[:width].view(1, 1, width)
        successor = self.next[:width].view(1, 1, width)
        return torch.where(actor.horizon_remaining.unsqueeze(-1).eq(1), successor, current).expand(
            *actor.action_mask.shape
        )


class _BadShapeScorer(nn.Module):
    def forward(self, actor: QhActorTensors) -> torch.Tensor:
        return torch.zeros((*actor.action_mask.shape[:2], actor.action_mask.shape[-1] + 1))


_CONTRACT = QhDataContract("qh-v1", "v1_observed", "reward", "return", "td", 0.95, "reasons-v1", "vin-v1")
_ACTOR_CONTRACT = QhActorStateContract("evl_v1", "none", "test-actor-manifest", (), experiment_profile="qh_cf0_v1")
_CF0_ACTOR_HASH = stable_msgspec_hash(_ACTOR_CONTRACT)
_LEARNING_CONTRACT_HASH = stable_msgspec_hash(_CONTRACT)


def _cf0_chain(chain: QhChain) -> QhChain:
    """Attach the compact EVL carrier required by the deployable CF0 module."""

    static_context = QhStaticContext(
        vin_snippet=_snippet(),
        t_world_voxel=PoseTW(),
        voxel_extent=torch.ones(6),
        occ_pr=torch.ones(1, 1, 1, 1),
        occ_input=torch.ones(1, 1, 1, 1),
        free_input=torch.ones(1, 1, 1, 1),
        counts=torch.ones(1, 1, 1, dtype=torch.int64),
        cent_pr=torch.ones(1, 1, 1, 1),
        pts_world=torch.ones(1, 3),
        evl_presence=torch.ones(8, dtype=torch.bool),
    )
    return replace(chain, actor=replace(chain.actor, static_context=static_context))


class _ChainDataset(Dataset[QhChain]):
    def __init__(
        self,
        chains: list[QhChain],
        *,
        scene: str = "train-scene",
        actor_state_contract: QhActorStateContract = _ACTOR_CONTRACT,
    ) -> None:
        self.chains = chains
        self.scenes = frozenset({scene})
        self.max_horizon = max(chain.num_steps for chain in chains)
        self.contract = _CONTRACT
        self.actor_state_contract = actor_state_contract
        self.provenance: dict[str, object] = {"scene": scene}

    def __len__(self) -> int:
        return len(self.chains)

    def __getitem__(self, index: int) -> QhChain:
        return _cf0_chain(self.chains[index])


def _training_chain(*, bootstrap: bool = True) -> QhChain:
    chain = _cf0_chain(_chain(steps=2, width=3))
    supervision = replace(
        chain.supervision,
        candidate_reward=torch.tensor([[0.0, 0.5, 0.0], [2.0, 0.0, 0.0]]),
        selected_index=torch.tensor([1, 0]),
        discount=torch.tensor([0.9, 0.0]),
        terminal=torch.tensor([not bootstrap, True]),
    )
    return replace(chain, supervision=supervision)


def _batch(*, bootstrap: bool = True) -> QhBatch:
    return collate_qh_chains([_training_chain(bootstrap=bootstrap)])


def _module(sync_interval: int = 2) -> QhLightningModule:
    return QhLightningModule(
        QhLightningModuleConfig(
            target_sync_interval=sync_interval,
            lr_scheduler=None,
            actor_state_contract_hash=_CF0_ACTOR_HASH,
            learning_contract_hash=_LEARNING_CONTRACT_HASH,
        ),
        scorer=_TableScorer(),
    )


def _install_manual_step(module: QhLightningModule, monkeypatch: pytest.MonkeyPatch, *, lr: float = 0.1) -> None:
    optimizer = torch.optim.SGD(module.online_scorer.parameters(), lr=lr)
    monkeypatch.setattr(module, "optimizers", lambda: optimizer)
    monkeypatch.setattr(module, "manual_backward", lambda loss: loss.backward())
    monkeypatch.setattr(module, "_step_learning_rate_schedulers", lambda: None)
    monkeypatch.setattr(module, "log", lambda *args, **kwargs: None)


def test_scorer_is_required_and_not_part_of_config() -> None:
    with pytest.raises(TypeError, match="scorer"):
        QhLightningModule(  # type: ignore[call-arg]
            QhLightningModuleConfig(
                lr_scheduler=None,
                actor_state_contract_hash=_CF0_ACTOR_HASH,
                learning_contract_hash=_LEARNING_CONTRACT_HASH,
            )
        )


def test_named_cfplus_rejects_deployable_module_before_scorer_construction() -> None:
    config = QhLightningModuleConfig(
        lr_scheduler=None,
        experiment_profile="qh_cfplus_gt_depth_v1",
        root_evl_profile="evl_v1",
        selected_observation_protocol="cf_gt",
        actor_state_contract_hash="actor",
        learning_contract_hash=_LEARNING_CONTRACT_HASH,
    )
    with pytest.raises(ValueError, match="rejects privileged"):
        QhLightningModule(config, scorer=_TableScorer())


def test_named_cfplus_allows_explicit_privileged_module() -> None:
    module = QhLightningModule(
        QhLightningModuleConfig(
            lr_scheduler=None,
            experiment_profile="qh_cfplus_gt_depth_v1",
            root_evl_profile="evl_v1",
            selected_observation_protocol="cf_gt",
            privileged=True,
            actor_state_contract_hash="actor",
            learning_contract_hash=_LEARNING_CONTRACT_HASH,
            geometry_contract_hash="geometry",
        ),
        scorer=_TableScorer(),
    )
    assert module.config.experiment_profile == "qh_cfplus_gt_depth_v1"


def test_module_rejects_unnamed_cf_gt_before_scorer_construction() -> None:
    config = QhLightningModuleConfig(
        lr_scheduler=None,
        selected_observation_protocol="cf_gt",
        actor_state_contract_hash=_CF0_ACTOR_HASH,
        learning_contract_hash=_LEARNING_CONTRACT_HASH,
    )
    with pytest.raises(ValueError, match="requires qh_cfplus_gt_depth_v1"):
        QhLightningModule(config, scorer=_TableScorer())


def test_named_cf0_requires_actor_state_contract_hash() -> None:
    with pytest.raises(ValidationError, match="actor_state_contract_hash"):
        QhLightningModuleConfig(lr_scheduler=None, learning_contract_hash=_LEARNING_CONTRACT_HASH)


def test_named_cf0_requires_learning_contract_hash() -> None:
    with pytest.raises(ValidationError, match="learning_contract_hash"):
        QhLightningModuleConfig(lr_scheduler=None, actor_state_contract_hash=_CF0_ACTOR_HASH)


def test_named_cfplus_requires_geometry_contract_hash() -> None:
    with pytest.raises(ValueError, match="geometry_contract_hash"):
        QhLightningModule(
            QhLightningModuleConfig(
                lr_scheduler=None,
                experiment_profile="qh_cfplus_gt_depth_v1",
                root_evl_profile="evl_v1",
                selected_observation_protocol="cf_gt",
                privileged=True,
                actor_state_contract_hash="actor",
                learning_contract_hash=_LEARNING_CONTRACT_HASH,
            ),
            scorer=_TableScorer(),
        )


def test_module_rejects_actor_contract_hash_mismatch_before_training() -> None:
    module = QhLightningModule(
        QhLightningModuleConfig(
            lr_scheduler=None,
            actor_state_contract_hash="expected",
            learning_contract_hash=_LEARNING_CONTRACT_HASH,
        ),
        scorer=_TableScorer(),
    )
    with pytest.raises(ValueError, match="actor-state contract hashes"):
        module._validate_datamodule_contract(
            type("Data", (), {"experiment_profile": "qh_cf0_v1", "actor_state_contract_hash": "actual"})()
        )


def test_module_rejects_every_learning_contract_field_mutation() -> None:
    geometry = QhGeometryContract(
        projection_model="linear_pinhole_screen",
        linearization="camera_z_metres",
        camera_pose="root_from_camera",
        depth_semantics="camera_z_m",
        focal_px=(100.0, 100.0),
        principal_point_px=(120.0, 120.0),
        image_size_hw=(240, 240),
        camera_axes="left_up_forward",
        camera_forward="+z",
        camera_handedness="right",
        pixel_convention="half_pixel_centers_in_ndc_false",
        in_ndc=False,
        znear_m=0.001,
        zfar_m=20.0,
        invalid_fill_value=0.0,
        dtype="float16",
        renderer="Pytorch3DDepthRenderer",
        source_role="selected_successor_state_history",
        selected_identity="selected_depth.step_row_id",
    )
    mutations = {
        "schema_version": "other-schema",
        "target_protocol": "v0_gt_input",
        "reward_metric": "other-reward",
        "return_semantics": "other-return",
        "td_semantics": "other-td",
        "discount_gamma": 0.5,
        "reason_code_version": "other-reasons",
        "actor_store_version": "other-actor-store",
        "selected_depth_enabled": True,
        "selected_depth_role": "selected_successor_state_history",
        "selected_depth_renderer": "Pytorch3DDepthRenderer",
        "selected_depth_image_size_hw": (240, 240),
        "selected_depth_dtype": "float16",
        "selected_depth_units": "m",
        "selected_depth_znear_m": 0.001,
        "selected_depth_zfar_m": 20.0,
        "selected_depth_source_resolution": "exact_output_size",
        "selected_depth_projection_model": "linear_pinhole_screen",
        "selected_depth_value_semantics": "camera_z_m",
        "selected_depth_pixel_convention": "half_pixel_centers_in_ndc_false",
        "selected_depth_camera_axes": "left_up_forward",
        "selected_depth_pose_convention": "root_from_camera",
        "selected_depth_geometry": geometry,
    }
    assert set(mutations) == {field.name for field in fields(QhDataContract)}
    module = _module()

    for field_name, value in mutations.items():
        changed_hash = stable_msgspec_hash(replace(_CONTRACT, **{field_name: value}))
        assert changed_hash != _LEARNING_CONTRACT_HASH
        data = type(
            "Data",
            (),
            {
                "experiment_profile": "qh_cf0_v1",
                "actor_state_contract_hash": _CF0_ACTOR_HASH,
                "learning_contract_hash": changed_hash,
            },
        )()
        with pytest.raises(ValueError, match="learning contract hashes"):
            module._validate_datamodule_contract(data)


def test_predict_start_uses_the_same_exact_datamodule_admission() -> None:
    data = type(
        "Data",
        (),
        {
            "experiment_profile": "qh_cf0_v1",
            "actor_state_contract_hash": _CF0_ACTOR_HASH,
            "learning_contract_hash": _LEARNING_CONTRACT_HASH,
            "geometry_contract_hash": None,
        },
    )()
    trainer = type("Trainer", (), {"datamodule": data})()
    matching = _module()
    matching._trainer = trainer  # noqa: SLF001

    matching.on_predict_start()

    mismatching = QhLightningModule(
        QhLightningModuleConfig(
            lr_scheduler=None,
            actor_state_contract_hash=_CF0_ACTOR_HASH,
            learning_contract_hash="other-learning-contract",
        ),
        scorer=_TableScorer(),
    )
    mismatching._trainer = trainer  # noqa: SLF001
    with pytest.raises(ValueError, match="learning contract hashes"):
        mismatching.on_predict_start()


def test_cfplus_geometry_hash_survives_config_reload_and_rejects_drift() -> None:
    """Reloaded module hparams keep geometry admission bound before fit."""

    actor = replace(
        _ACTOR_CONTRACT,
        root_evl_profile="evl_v1",
        selected_observation_protocol="cf_gt",
        experiment_profile="qh_cfplus_gt_depth_v1",
        geometry_contract_hash="geom-v1",
    )
    config = QhLightningModuleConfig(
        lr_scheduler=None,
        experiment_profile="qh_cfplus_gt_depth_v1",
        root_evl_profile="evl_v1",
        selected_observation_protocol="cf_gt",
        privileged=True,
        actor_state_contract_hash=stable_msgspec_hash(actor),
        learning_contract_hash=_LEARNING_CONTRACT_HASH,
        geometry_contract_hash="geom-v1",
    )
    reloaded = QhLightningModuleConfig.model_validate(config.model_dump())
    assert reloaded.learning_contract_hash == _LEARNING_CONTRACT_HASH
    module = QhLightningModule(reloaded, scorer=_TableScorer())
    module._validate_datamodule_contract(
        type(
            "Data",
            (),
            {
                "experiment_profile": "qh_cfplus_gt_depth_v1",
                "actor_state_contract_hash": stable_msgspec_hash(actor),
                "learning_contract_hash": _LEARNING_CONTRACT_HASH,
                "geometry_contract_hash": "geom-v1",
            },
        )()
    )
    with pytest.raises(ValueError, match="geometry hashes"):
        module._validate_datamodule_contract(
            type(
                "Data",
                (),
                {
                    "experiment_profile": "qh_cfplus_gt_depth_v1",
                    "actor_state_contract_hash": stable_msgspec_hash(actor),
                    "learning_contract_hash": _LEARNING_CONTRACT_HASH,
                    "geometry_contract_hash": "tampered",
                },
            )()
        )
    assert stable_msgspec_hash(_ACTOR_CONTRACT) != "expected"


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf"), "inf"])
def test_huber_delta_rejects_nonfinite_values(value: float | str) -> None:
    with pytest.raises(ValidationError) as error:
        QhLightningModuleConfig(
            huber_delta=value,
            actor_state_contract_hash=_CF0_ACTOR_HASH,
            learning_contract_hash=_LEARNING_CONTRACT_HASH,
        )

    assert error.value.errors()[0]["loc"] == ("huber_delta",)


def test_forward_consumes_actor_tensors_and_requires_exact_batch_shape() -> None:
    batch = collate_qh_chains([_cf0_chain(_chain(steps=1, width=3)), _cf0_chain(_chain(steps=2, width=3, offset=10))])
    module = _module()

    values = module(batch.actor)

    assert values.shape == (2, 2, 3)
    assert module.online_scorer.calls == 1
    with pytest.raises(ValueError, match=r"must return shape \(2, 2, 3\)"):
        QhLightningModule(module.config, scorer=_BadShapeScorer())(batch.actor)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (
        ("root_evl_profile", "evl_v1", "root_evl_profile"),
        ("selected_observation_protocol", "cf_gt", "selected_observation_protocol"),
    ),
)
def test_scorer_rejects_missing_declared_actor_carrier(field: str, value: str, message: str) -> None:
    config_values = {field: value}
    if field == "selected_observation_protocol":
        config_values.update(
            experiment_profile="qh_cfplus_gt_depth_v1",
            root_evl_profile="evl_v1",
            privileged=True,
            actor_state_contract_hash="actor",
            geometry_contract_hash="geometry",
        )
    config = QhLightningModuleConfig(
        lr_scheduler=None,
        actor_state_contract_hash=config_values.pop("actor_state_contract_hash", _CF0_ACTOR_HASH),
        learning_contract_hash=_LEARNING_CONTRACT_HASH,
        **config_values,
    )
    module = QhLightningModule(config, scorer=_TableScorer())
    batch = _batch()
    if field == "root_evl_profile":
        batch = replace(batch, actor=replace(batch.actor, static_context=None))
    if field == "selected_observation_protocol":
        batch = replace(
            batch,
            actor=replace(
                batch.actor,
                static_context=QhStaticContext(
                    vin_snippet=_snippet(),
                    t_world_voxel=PoseTW(),
                    voxel_extent=torch.ones(6),
                    occ_pr=torch.ones(1, 1, 1, 1),
                    occ_input=torch.ones(1, 1, 1, 1),
                    free_input=torch.ones(1, 1, 1, 1),
                    counts=torch.ones(1, 1, 1, dtype=torch.int64),
                    cent_pr=torch.ones(1, 1, 1, 1),
                    pts_world=torch.ones(1, 3),
                    evl_presence=torch.ones(8, dtype=torch.bool),
                ),
            ),
        )

    with pytest.raises(ValueError, match=message):
        module(batch.actor)

    assert module.hparams["config"][field] == value


def test_exact_double_q_target_and_huber_loss() -> None:
    module = _module()
    module.target_scorer.next.data.copy_(torch.tensor([10.0, 20.0, 30.0, 40.0]))

    loss, targets, admitted = module.compute_fitted_q_loss(_batch())

    assert admitted.tolist() == [[True, True]]
    assert torch.allclose(targets, torch.tensor([[18.5, 2.0]]))
    assert loss.item() == pytest.approx(8.25)


def test_terminal_rows_do_not_bootstrap() -> None:
    batch = _batch(bootstrap=False)

    _loss, targets, _admitted = _module().compute_fitted_q_loss(batch)

    selected_reward = batch.supervision.candidate_reward.gather(
        -1, batch.supervision.selected_index.unsqueeze(-1)
    ).squeeze(-1)
    assert torch.equal(targets, selected_reward)


def test_bootstrap_argmax_uses_shifted_action_and_label_support() -> None:
    module = _module()
    module.online_scorer.next.data.copy_(torch.tensor([5.0, 1_000_000.0, 7.0, 0.0]))
    module.target_scorer.next.data.copy_(torch.tensor([10.0, 1_000_000.0, 30.0, 0.0]))
    batch = _batch()
    labels = batch.supervision.label_mask.clone()
    labels[:, 1] = torch.tensor([True, False, True])
    batch = replace(batch, supervision=replace(batch.supervision, label_mask=labels))

    _loss, targets, admitted = module.compute_fitted_q_loss(batch)

    assert admitted.tolist() == [[True, True]]
    assert targets[0, 0].item() == pytest.approx(0.5 + 0.9 * 30.0)


def test_nonterminal_row_with_actor_successor_but_no_label_support_is_excluded() -> None:
    module = _module()
    module.target_scorer.next.data.copy_(torch.tensor([1_000_000.0, 20.0, 30.0, 0.0]))
    batch = _batch()
    labels = batch.supervision.label_mask.clone()
    labels[:, 1] = False
    batch = replace(batch, supervision=replace(batch.supervision, label_mask=labels))

    _loss, targets, admitted = module.compute_fitted_q_loss(batch)

    assert admitted.tolist() == [[False, False]]
    assert targets[0, 0] == 0.5


def test_nonterminal_row_without_actor_successor_keeps_immediate_reward_target() -> None:
    batch = _batch()
    action_mask = batch.actor.action_mask.clone()
    action_mask[:, 1] = False
    batch = replace(batch, actor=replace(batch.actor, action_mask=action_mask))

    _loss, targets, admitted = _module().compute_fitted_q_loss(batch)

    assert admitted.tolist() == [[True, False]]
    assert targets[0, 0] == 0.5


def test_mixed_supported_and_unsupported_rows_train_only_supported_queries() -> None:
    supported = _training_chain()
    unsupported = _training_chain()
    labels = unsupported.supervision.label_mask.clone()
    labels[1] = False
    unsupported = replace(unsupported, supervision=replace(unsupported.supervision, label_mask=labels))
    batch = collate_qh_chains([supported, unsupported])

    module = _module()
    loss, _targets, admitted = module.compute_fitted_q_loss(batch)
    supported_loss, _targets, _admitted = module.compute_fitted_q_loss(collate_qh_chains([supported]))

    assert admitted.tolist() == [[True, True], [False, False]]
    assert loss.item() == pytest.approx(supported_loss.item())


@pytest.mark.parametrize("nonfinite", [float("nan"), float("inf"), float("-inf")])
def test_selected_online_value_must_be_finite(nonfinite: float) -> None:
    module = _module()
    module.online_scorer.current.data[1] = nonfinite

    with pytest.raises(ValueError, match="selected online predictions"):
        module.compute_fitted_q_loss(_batch())


@pytest.mark.parametrize("scorer_name", ["online_scorer", "target_scorer"])
@pytest.mark.parametrize("nonfinite", [float("nan"), float("inf"), float("-inf")])
def test_supported_successor_values_must_be_finite(scorer_name: str, nonfinite: float) -> None:
    module = _module()
    scorer = getattr(module, scorer_name)
    scorer.next.data[2 if scorer_name == "online_scorer" else 1] = nonfinite
    expected = "online successor predictions" if scorer_name == "online_scorer" else "target successor predictions"

    with pytest.raises(ValueError, match=expected):
        module.compute_fitted_q_loss(_batch())


def test_nonfinite_unsupported_successor_values_are_ignored() -> None:
    module = _module()
    module.online_scorer.next.data[1] = float("nan")
    module.target_scorer.next.data[1] = float("nan")
    batch = _batch()
    labels = batch.supervision.label_mask.clone()
    labels[:, 1, 1] = False
    batch = replace(batch, supervision=replace(batch.supervision, label_mask=labels))

    loss, targets, admitted = module.compute_fitted_q_loss(batch)

    assert torch.isfinite(loss)
    assert torch.isfinite(targets[admitted]).all()


def test_all_unsupported_batch_is_exact_optimizer_noop_with_diagnostic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _module()
    batch = _batch()
    labels = batch.supervision.label_mask.clone()
    labels[:, 1] = False
    batch = replace(batch, supervision=replace(batch.supervision, label_mask=labels))
    logged: dict[str, torch.Tensor] = {}
    monkeypatch.setattr(module, "log", lambda name, value, **kwargs: logged.__setitem__(name, value.detach()))

    result = module.training_step(batch, 0)

    assert result is None
    assert module.online_scorer.calls == 0
    assert module.target_scorer.calls == 0
    assert module.optimizer_updates.item() == 0
    assert logged["train/unsupported_backup_rows"].item() == 1
    assert logged["train/unsupported_backup_fraction"].item() == 1


@pytest.mark.parametrize("sync_interval", [1, 2])
def test_target_sync_copies_post_update_online_weights(sync_interval: int, monkeypatch: pytest.MonkeyPatch) -> None:
    module = _module(sync_interval)
    _install_manual_step(module, monkeypatch)
    initial_target = deepcopy(module.target_scorer.state_dict())

    for update in range(sync_interval):
        module.training_step(_batch(), update)
        if update + 1 < sync_interval:
            assert all(
                torch.equal(value, module.target_scorer.state_dict()[name]) for name, value in initial_target.items()
            )

    assert module.optimizer_updates.item() == sync_interval
    online_state = module.online_scorer.state_dict()
    target_state = module.target_scorer.state_dict()
    assert any(not torch.equal(value, initial_target[name]) for name, value in online_state.items())
    assert all(torch.equal(value, target_state[name]) for name, value in online_state.items())


def test_single_device_validation_logs_exact_weighted_loss_and_only_infrastructure_metrics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _module()
    module.target_scorer.next.data.copy_(torch.tensor([10.0, 20.0, 30.0, 40.0]))
    logged: dict[str, torch.Tensor] = {}
    monkeypatch.setattr(module, "log", lambda name, value, **kwargs: logged.__setitem__(name, value.detach()))

    module.on_validation_epoch_start()
    module.validation_step(_batch(), 0)
    module.on_validation_epoch_end()

    assert logged["val/loss"].item() == pytest.approx(8.25)
    assert logged["val/admitted_rows"].item() == 2
    assert set(logged) == {
        "val/loss",
        "val/admitted_rows",
        "val/bootstrap_fraction",
        "val/terminal_fraction",
        "val/no_successor_fraction",
        "val/nonfinite_valid_values",
        "val/unsupported_backup_rows",
        "val/unsupported_backup_fraction",
    }


def test_target_is_independent_frozen_forced_to_eval_and_excluded_from_optimizer() -> None:
    module = _module()

    assert module.target_scorer is not module.online_scorer
    assert all(not parameter.requires_grad for parameter in module.target_scorer.parameters())
    module.train()
    assert module.online_scorer.training is True
    assert module.target_scorer.training is False
    optimizer = module.configure_optimizers()
    assert isinstance(optimizer, torch.optim.Optimizer)
    optimized = {id(parameter) for group in optimizer.param_groups for parameter in group["params"]}

    assert optimized == {id(parameter) for parameter in module.online_scorer.parameters()}
    assert optimized.isdisjoint({id(parameter) for parameter in module.target_scorer.parameters()})
