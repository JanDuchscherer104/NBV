"""Dense-valid fitted-Q admission and padding contracts."""

# ruff: noqa: S101

from __future__ import annotations

from dataclasses import replace

import pytest
import torch

from aria_nbv.data_handling.qh_data import collate_qh_chains
from aria_nbv.lightning.qh_datamodule import QhDataModule
from aria_nbv.rollouts.qh_reader import QhDataContract
from tests.data_handling.test_qh import _chain
from tests.lightning.test_qh_datamodule import _ACTOR_CONTRACT, _StructuralDataset


def _dense_contract() -> QhDataContract:
    return QhDataContract(
        schema_version="qh-v1",
        target_protocol="v1_observed",
        reward_metric="target-root-gain",
        return_semantics="finite-horizon",
        td_semantics="fitted-q",
        discount_gamma=0.95,
        reason_code_version="reasons-v1",
        actor_store_version="vin-v1",
        oracle_query_mode="dense_valid",
        label_support_semantics="equals_action_on_realized_steps_v1",
    )


def test_dense_valid_collation_canonicalizes_exact_actor_support() -> None:
    short = _chain(steps=1, width=2)
    long = _chain(steps=2, width=3, offset=20)
    action_mask = long.actor.action_mask.clone()
    action_mask[0, -1] = False
    label_mask = long.supervision.label_mask.clone()
    label_mask[0, -1] = False
    long = replace(
        long,
        actor=replace(long.actor, action_mask=action_mask),
        supervision=replace(long.supervision, label_mask=label_mask),
    )

    batch = collate_qh_chains(
        [short, long],
        objective_profile="qh_dense_valid_fitted_q_v1",
    )
    expected = batch.actor.action_mask & batch.actor.step_mask.unsqueeze(-1)

    assert torch.equal(batch.supervision.label_mask, expected)
    assert torch.isfinite(batch.supervision.candidate_reward[expected]).all()
    assert torch.isfinite(batch.supervision.one_step_target_rri[expected]).all()
    assert torch.isnan(batch.supervision.candidate_reward[~expected]).all()
    assert torch.isnan(batch.supervision.one_step_target_rri[~expected]).all()


def test_dense_valid_collation_rejects_missing_or_nonfinite_supported_labels() -> None:
    chain = _chain(steps=1, width=2)
    missing = chain.supervision.label_mask.clone()
    missing[0, 1] = False
    with pytest.raises(ValueError, match="label_mask must equal"):
        collate_qh_chains(
            [replace(chain, supervision=replace(chain.supervision, label_mask=missing))],
            objective_profile="qh_dense_valid_fitted_q_v1",
        )

    reward = chain.supervision.candidate_reward.clone()
    reward[0, 1] = float("nan")
    with pytest.raises(ValueError, match="candidate_reward must be finite"):
        collate_qh_chains(
            [replace(chain, supervision=replace(chain.supervision, candidate_reward=reward))],
            objective_profile="qh_dense_valid_fitted_q_v1",
        )


def test_legacy_collation_keeps_finite_zero_reward_padding() -> None:
    batch = collate_qh_chains([_chain(steps=1, width=2), _chain(steps=2, width=3)])
    expected = batch.actor.action_mask & batch.actor.step_mask.unsqueeze(-1)

    assert torch.equal(
        batch.supervision.candidate_reward[~expected], torch.zeros_like(batch.supervision.candidate_reward[~expected])
    )


def test_collation_rejects_unknown_objective_profile() -> None:
    with pytest.raises(ValueError, match="unsupported objective_profile"):
        collate_qh_chains([_chain(steps=1, width=2)], objective_profile="unknown")  # type: ignore[arg-type]


def test_datamodule_dense_objective_requires_exact_data_contract() -> None:
    dense = _StructuralDataset(
        "train",
        contract=_dense_contract(),
        actor_state_contract=_ACTOR_CONTRACT,
    )
    data = QhDataModule(
        train=dense,  # type: ignore[arg-type]
        seed=7,
        objective_profile="qh_dense_valid_fitted_q_v1",
    )
    assert data.learning_contract.objective_profile == "qh_dense_valid_fitted_q_v1"

    legacy = replace(_dense_contract(), oracle_query_mode="legacy_unspecified")
    with pytest.raises(ValueError, match="dense-valid.*requires"):
        QhDataModule(
            train=_StructuralDataset("legacy", contract=legacy),  # type: ignore[arg-type]
            seed=7,
            objective_profile="qh_dense_valid_fitted_q_v1",
        )
