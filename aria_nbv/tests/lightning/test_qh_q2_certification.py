"""Bounded population evidence for learned recursive exact-``Q_2`` controls."""

# ruff: noqa: S101

from __future__ import annotations

from dataclasses import asdict, replace

import pytest
import torch

from aria_nbv.data_handling.qh_data import collate_qh_chains
from aria_nbv.lightning.qh_q2_certification import (
    QhDecoderSupport,
    QhExactQ2CertificationSpec,
    QhExactQ2Certifier,
)
from tests.lightning.test_qh_module import _ChainDataset, _module, _training_chain

_ORDERED_STORE_MANIFEST_SHA256 = "1" * 64


def _dataset(count: int = 4, *, scene_count: int = 2) -> _ChainDataset:
    """Return complete dense-valid chains with explicit generation lineage."""

    chains = []
    for index in range(count):
        chain = _training_chain()
        chains.append(
            replace(
                chain,
                key=replace(
                    chain.key,
                    store_index=index % 2,
                    rollout_row_id=index,
                    source_sample_index=index,
                    scene_id=f"scene-{index % scene_count}",
                    target_row_id=index % scene_count,
                    configured_horizon=2,
                    candidate_width_min=3,
                    candidate_width_max=3,
                    candidate_config_hash="candidate-v1",
                    rollout_config_hash="rollout-v1",
                    selection_policy="q_h",
                ),
            )
        )
    return _ChainDataset(chains, scene="held-out")


def test_exact_q2_certifier_is_bounded_deterministic_and_semantically_explicit() -> None:
    module = _module()
    module.online_scorer.next.data.copy_(torch.tensor([2.0, 0.0, 0.0, 0.0]))
    module.target_scorer.next.data.copy_(torch.tensor([2.0, 0.0, 0.0, 0.0]))
    spec = QhExactQ2CertificationSpec(
        absolute_tolerance=0.0,
        relative_tolerance=0.0,
        minimum_independent_units=5,
        minimum_exact_rows_per_independent_unit=1,
        independent_unit_aggregation="all_units_v1",
        minimum_population_coverage=0.5,
        max_selected_chains=5,
        max_chains_per_stratum=1,
        selection_seed=17,
    )
    certifier = QhExactQ2Certifier(spec)
    dataset = _dataset(10, scene_count=5)

    first = certifier.certify(
        module=module,
        dataset=dataset,
        device=torch.device("cpu"),
        ordered_store_manifest_sha256=_ORDERED_STORE_MANIFEST_SHA256,
    )
    second = certifier.certify(
        module=module,
        dataset=dataset,
        device=torch.device("cpu"),
        ordered_store_manifest_sha256=_ORDERED_STORE_MANIFEST_SHA256,
    )

    census = first["population_census"]
    assert census["population_chain_count"] == 10
    assert census["selected_chain_count"] == 5
    assert census["selected_chain_fraction"] == pytest.approx(0.5)
    assert census["near_exhaustive"] is False
    assert census["chains"] == [
        {"dataset_index": index, "identity": asdict(dataset.chain_identity(index))} for index in range(len(dataset))
    ]
    assert first["selected_chain_support"] == second["selected_chain_support"]
    assert first["factual_selected_action_exact_q2_rows"] == second["factual_selected_action_exact_q2_rows"]
    assert first["aggregate"] == {
        "factual_selected_action_exact_q2_row_count": 5,
        "within_tolerance_count": 5,
        "within_tolerance_fraction": 1.0,
        "mean_absolute_error": 0.0,
        "root_mean_squared_error": 0.0,
        "max_absolute_error": 0.0,
        "max_relative_error": 0.0,
        "minimum_support_met": True,
        "tolerance_passed": True,
    }
    assert first["learned_recursion_passed"] is True
    assert first["schema_version"] == "qh-exact-q2-certification-v5"
    assert sum(row["factual_selected_action_exact_q2_row_count"] for row in first["support_stratum_aggregates"]) == 5
    assert first["evidence_semantics"] == {
        "quantity": "learned_recursive_q2_target_error_against_factual_dense_successor_control",
        "implementation_recursion_parity": False,
        "endpoint_policy_evidence": False,
        "longer_horizon_claim": False,
    }
    assert {row["candidate_branch_bin"] for row in first["factual_selected_action_exact_q2_rows"]} == {"2-4"}
    for row in first["factual_selected_action_exact_q2_rows"]:
        assert row["immediate_reward"] == pytest.approx(0.5)
        assert row["discount"] == pytest.approx(0.9)
        assert row["terminal"] is False
        assert row["successor_action_count"] == row["successor_backup_count"] == 3
        assert row["successor_candidate_count"] == 3
        assert row["successor_reward_ledger"] == [
            {"candidate_index": 0, "reward": 2.0},
            {"candidate_index": 1, "reward": 0.0},
            {"candidate_index": 2, "reward": 0.0},
        ]
        assert row["successor_max_reward"] == pytest.approx(2.0)
        assert row["exact_target"] == pytest.approx(
            row["immediate_reward"] + row["discount"] * row["successor_max_reward"]
        )
    assert first["independent_unit_gate"] == {
        "independent_unit_semantics": "ordered-store-manifest-and-scene-v1",
        "aggregation": "all_units_v1",
        "population_independent_unit_count": 5,
        "selected_independent_unit_count": 5,
        "supported_independent_unit_count": 5,
        "passing_independent_unit_count": 5,
        "minimum_independent_units": 5,
        "minimum_exact_rows_per_independent_unit": 1,
        "minimum_independent_units_met": True,
        "all_selected_units_passed": True,
        "passed": True,
    }
    assert first["evidence_denominators"] == {
        "factual_state_count": 10,
        "states_with_materialized_successors_count": 5,
        "states_with_complete_hard_valid_successor_labels_count": 5,
        "factual_selected_action_exact_q2_row_count": 5,
    }


def test_exact_q2_successor_reward_ledger_is_canonical_for_negative_ties() -> None:
    chain = _dataset(1, scene_count=1).chains[0]
    chain = replace(
        chain,
        supervision=replace(
            chain.supervision,
            candidate_reward=torch.tensor([[0.0, 0.5, 0.0], [-2.0, -2.0, -3.0]]),
        ),
    )

    evidence = QhExactQ2Certifier(
        QhExactQ2CertificationSpec(
            absolute_tolerance=100.0,
            relative_tolerance=0.0,
            minimum_independent_units=5,
            minimum_exact_rows_per_independent_unit=1,
            independent_unit_aggregation="all_units_v1",
            minimum_population_coverage=1.0,
        )
    ).certify(
        module=_module(),
        dataset=_ChainDataset([chain], scene="held-out"),
        device=torch.device("cpu"),
        ordered_store_manifest_sha256=_ORDERED_STORE_MANIFEST_SHA256,
    )

    row = evidence["factual_selected_action_exact_q2_rows"][0]
    assert row["successor_reward_ledger"] == [
        {"candidate_index": 0, "reward": -2.0},
        {"candidate_index": 1, "reward": -2.0},
        {"candidate_index": 2, "reward": -3.0},
    ]
    assert row["successor_max_reward"] == -2.0


def test_exact_q2_certifier_rejects_different_action_and_backup_candidates() -> None:
    dataset = _dataset(1, scene_count=1)
    chain = dataset.chains[0]
    supervision = replace(
        chain.supervision,
        label_mask=torch.tensor([[True, True, True], [False, True, True]]),
    )
    batch = collate_qh_chains([replace(chain, supervision=supervision)])
    certifier = QhExactQ2Certifier(
        QhExactQ2CertificationSpec(
            absolute_tolerance=100.0,
            relative_tolerance=0.0,
            minimum_independent_units=5,
            minimum_exact_rows_per_independent_unit=1,
            independent_unit_aggregation="all_units_v1",
            minimum_population_coverage=1.0,
        )
    )

    with pytest.raises(ValueError, match="every hard-valid successor reward"):
        certifier._row_evidence(
            batch=batch,
            identity=dataset.chain_identity(0),
            dataset_index=0,
            selection_rank=0,
            step_indices=torch.tensor([0]),
            recursive_targets=torch.tensor([[2.3, 0.0]]),
            exact_targets=torch.tensor([[2.3, 0.0]]),
            ordered_store_manifest_sha256=_ORDERED_STORE_MANIFEST_SHA256,
        )


@pytest.mark.parametrize("materialized_width, declared_width", [(2, 3), (3, 2)])
def test_exact_q2_certifier_rejects_materialized_width_outside_declared_range(
    materialized_width: int,
    declared_width: int,
) -> None:
    dataset = _dataset(1, scene_count=1)
    chain = dataset.chains[0]
    candidate_mask = chain.actor.candidate_mask.clone()
    action_mask = chain.actor.action_mask.clone()
    label_mask = chain.supervision.label_mask.clone()
    candidate_mask[1, materialized_width:] = False
    action_mask[1, materialized_width:] = False
    label_mask[1, materialized_width:] = False
    chain = replace(
        chain,
        key=replace(
            chain.key,
            candidate_width_min=declared_width,
            candidate_width_max=declared_width,
        ),
        actor=replace(
            chain.actor,
            candidate_mask=candidate_mask,
            action_mask=action_mask,
        ),
        supervision=replace(chain.supervision, label_mask=label_mask),
    )
    certifier = QhExactQ2Certifier(
        QhExactQ2CertificationSpec(
            absolute_tolerance=100.0,
            relative_tolerance=0.0,
            minimum_independent_units=5,
            minimum_exact_rows_per_independent_unit=1,
            independent_unit_aggregation="all_units_v1",
            minimum_population_coverage=1.0,
        )
    )

    with pytest.raises(ValueError, match="declared candidate-width range"):
        certifier.certify(
            module=_module(),
            dataset=_ChainDataset([chain], scene="held-out"),
            device=torch.device("cpu"),
            ordered_store_manifest_sha256=_ORDERED_STORE_MANIFEST_SHA256,
        )


@pytest.mark.parametrize("reward", [float("inf"), float("nan"), 1e100])
def test_exact_q2_certifier_rejects_nonfinite_successor_ledger_rewards(reward: float) -> None:
    dataset = _dataset(1, scene_count=1)
    chain = dataset.chains[0]
    candidate_reward = chain.supervision.candidate_reward.to(torch.float64).clone()
    candidate_reward[1, 0] = reward
    chain = replace(
        chain,
        supervision=replace(chain.supervision, candidate_reward=candidate_reward),
    )
    batch = collate_qh_chains([chain])
    certifier = QhExactQ2Certifier(
        QhExactQ2CertificationSpec(
            absolute_tolerance=100.0,
            relative_tolerance=0.0,
            minimum_independent_units=5,
            minimum_exact_rows_per_independent_unit=1,
            independent_unit_aggregation="all_units_v1",
            minimum_population_coverage=1.0,
        )
    )

    with pytest.raises(ValueError, match="successor reward ledger"):
        certifier._row_evidence(
            batch=batch,
            identity=dataset.chain_identity(0),
            dataset_index=0,
            selection_rank=0,
            step_indices=torch.tensor([0]),
            recursive_targets=torch.tensor([[0.0, 0.0]]),
            exact_targets=torch.tensor([[0.0, 0.0]]),
            ordered_store_manifest_sha256=_ORDERED_STORE_MANIFEST_SHA256,
        )


def test_exact_q2_certifier_reports_coral_support_saturation_separately() -> None:
    module = _module()
    evidence = QhExactQ2Certifier(
        QhExactQ2CertificationSpec(
            absolute_tolerance=100.0,
            relative_tolerance=0.0,
            minimum_independent_units=5,
            minimum_exact_rows_per_independent_unit=1,
            independent_unit_aggregation="all_units_v1",
            minimum_population_coverage=1.0,
        )
    ).certify(
        module=module,
        dataset=_dataset(5, scene_count=5),
        device=torch.device("cpu"),
        ordered_store_manifest_sha256=_ORDERED_STORE_MANIFEST_SHA256,
        decoder_support=QhDecoderSupport(
            kind="coral",
            lower_representative=-1.0,
            upper_representative=1.0,
            lower_edge=-0.5,
            upper_edge=0.5,
        ),
    )

    support = evidence["decoder_support"]
    assert support["applicable"] is True
    assert support["factual_selected_action_exact_q2_row_count"] == 5
    assert support["above_representative_count"] == 5
    assert support["outside_representative_fraction"] == 1.0
    assert support["upper_outer_class_count"] == 5
    assert support["outer_class_fraction"] == 1.0


def test_exact_q2_certifier_rejects_an_entirely_unsupported_selected_stratum() -> None:
    supported = _dataset(1).chains[0]
    unsupported = _training_chain(bootstrap=False)
    unsupported = replace(
        unsupported,
        key=replace(
            unsupported.key,
            store_index=1,
            rollout_row_id=1,
            source_sample_index=1,
            scene_id="unsupported-scene",
            target_row_id=1,
            configured_horizon=2,
            candidate_width_min=3,
            candidate_width_max=3,
            candidate_config_hash="candidate-v1",
            rollout_config_hash="rollout-v1",
            selection_policy="q_h",
        ),
    )
    dataset = _ChainDataset([supported, unsupported], scene="held-out")
    module = _module()
    module.online_scorer.next.data.copy_(torch.tensor([2.0, 0.0, 0.0, 0.0]))
    module.target_scorer.next.data.copy_(torch.tensor([2.0, 0.0, 0.0, 0.0]))

    evidence = QhExactQ2Certifier(
        QhExactQ2CertificationSpec(
            absolute_tolerance=0.0,
            relative_tolerance=0.0,
            minimum_independent_units=5,
            minimum_exact_rows_per_independent_unit=1,
            independent_unit_aggregation="all_units_v1",
            minimum_population_coverage=1.0,
        )
    ).certify(
        module=module,
        dataset=dataset,
        device=torch.device("cpu"),
        ordered_store_manifest_sha256=_ORDERED_STORE_MANIFEST_SHA256,
    )

    assert evidence["aggregate"]["tolerance_passed"] is True
    assert evidence["support_coverage_passed"] is False
    assert any(row["factual_selected_action_exact_q2_row_count"] == 0 for row in evidence["support_stratum_aggregates"])
    assert evidence["learned_recursion_passed"] is False


def test_exact_q2_rows_from_repeated_scenes_cannot_satisfy_five_unit_gate() -> None:
    module = _module()
    evidence = QhExactQ2Certifier(
        QhExactQ2CertificationSpec(
            absolute_tolerance=100.0,
            relative_tolerance=0.0,
            minimum_independent_units=5,
            minimum_exact_rows_per_independent_unit=1,
            independent_unit_aggregation="all_units_v1",
            minimum_population_coverage=1.0,
        )
    ).certify(
        module=module,
        dataset=_dataset(8),
        device=torch.device("cpu"),
        ordered_store_manifest_sha256=_ORDERED_STORE_MANIFEST_SHA256,
    )

    assert evidence["aggregate"]["factual_selected_action_exact_q2_row_count"] == 8
    assert evidence["independent_unit_gate"]["population_independent_unit_count"] == 2
    assert evidence["independent_unit_gate"]["minimum_independent_units_met"] is False
    assert evidence["learned_recursion_passed"] is False


def test_exact_q2_certifier_rejects_unbound_ordered_store_manifest_identity() -> None:
    certifier = QhExactQ2Certifier(
        QhExactQ2CertificationSpec(
            absolute_tolerance=0.0,
            relative_tolerance=0.0,
            minimum_independent_units=5,
            minimum_exact_rows_per_independent_unit=1,
            independent_unit_aggregation="all_units_v1",
        )
    )

    with pytest.raises(ValueError, match="SHA-256"):
        certifier.certify(
            module=_module(),
            dataset=_dataset(1),
            device=torch.device("cpu"),
            ordered_store_manifest_sha256="unbound",
        )


def test_exact_q2_certifier_fails_closed_on_incomplete_lineage() -> None:
    dataset = _dataset(1)
    dataset.chains[0] = replace(
        dataset.chains[0],
        key=replace(dataset.chains[0].key, candidate_config_hash=""),
    )

    with pytest.raises(ValueError, match="candidate_config_hash"):
        QhExactQ2Certifier(
            QhExactQ2CertificationSpec(
                absolute_tolerance=1e-5,
                relative_tolerance=1e-5,
                minimum_independent_units=5,
                minimum_exact_rows_per_independent_unit=1,
                independent_unit_aggregation="all_units_v1",
            )
        ).certify(
            module=_module(),
            dataset=dataset,
            device=torch.device("cpu"),
            ordered_store_manifest_sha256=_ORDERED_STORE_MANIFEST_SHA256,
        )


def test_exact_q2_certifier_rejects_derived_metrics_outside_float32() -> None:
    spec = QhExactQ2CertificationSpec(
        absolute_tolerance=0.0,
        relative_tolerance=float(torch.finfo(torch.float32).max),
        minimum_independent_units=5,
        minimum_exact_rows_per_independent_unit=1,
        independent_unit_aggregation="all_units_v1",
    )

    with pytest.raises(ValueError, match="finite float32 domain"):
        QhExactQ2Certifier(spec).certify(
            module=_module(),
            dataset=_dataset(1),
            device=torch.device("cpu"),
            ordered_store_manifest_sha256=_ORDERED_STORE_MANIFEST_SHA256,
        )


@pytest.mark.parametrize(
    "update",
    [
        {"absolute_tolerance": -1.0},
        {"absolute_tolerance": True},
        {"relative_tolerance": float("nan")},
        {"relative_tolerance": 1e308},
        {"relative_tolerance": True},
        {"minimum_independent_units": 4},
        {"minimum_exact_rows_per_independent_unit": 0},
        {"independent_unit_aggregation": "mean_units_v1"},
        {"minimum_population_coverage": 0.0},
        {"max_selected_chains": 0},
        {"positive_headroom_threshold": 0.0},
    ],
)
def test_exact_q2_certification_spec_rejects_invalid_gates(update: dict[str, object]) -> None:
    arguments: dict[str, object] = {
        "absolute_tolerance": 0.0,
        "relative_tolerance": 0.0,
        "minimum_independent_units": 5,
        "minimum_exact_rows_per_independent_unit": 1,
        "independent_unit_aggregation": "all_units_v1",
    }
    arguments.update(update)
    with pytest.raises(ValueError):
        QhExactQ2CertificationSpec(**arguments)  # type: ignore[arg-type]
