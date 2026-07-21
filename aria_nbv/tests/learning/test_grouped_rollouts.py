from __future__ import annotations

import math

import pytest
import torch
import zarr

from aria_nbv.learning.grouped_rollouts import (
    ActorTargetQuery,
    NormalizedDecisionRow,
    can_share_later_rollout,
    exact_pose_key,
    group_decision_rows,
    grouped_rollout_training_batches,
)
from aria_nbv.rollouts import RolloutZarrStoreReader
from aria_nbv.rollouts.zarr_store import write_rollout_zarr_store
from tests.rollout_fixtures import build_rollout_records


def _pose(x: float = 0.0) -> tuple[float, ...]:
    return (1.0, 0.0, 0.0, x, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0)


def _row(
    *,
    state: str,
    target: str,
    candidate: int,
    pose: tuple[float, ...],
    scene: str = "scene",
    source: int = 7,
    utility: float = 1.0,
    action: bool = True,
    label: bool = True,
) -> NormalizedDecisionRow:
    return NormalizedDecisionRow(
        scene_id=scene,
        source_row_id=source,
        state_fingerprint=state,
        target_id=target,
        candidate_id=candidate,
        candidate_pose_world=pose,
        target_utility=utility,
        actor_action_mask=action,
        oracle_label_mask=label,
    )


def test_grouping_never_uses_source_row_as_state_identity() -> None:
    views = group_decision_rows(
        [
            _row(state="reconstruction-a", target="chair", candidate=11, pose=_pose()),
            _row(state="reconstruction-b", target="chair", candidate=12, pose=_pose()),
        ]
    )

    assert [view.state_fingerprint for view in views] == ["reconstruction-a", "reconstruction-b"]
    assert [view.source_row_ids for view in views] == [(7,), (7,)]


def test_grouping_empty_input() -> None:
    assert group_decision_rows(()) == ()


def test_group_preserves_identities_and_deduplicates_pose_union() -> None:
    pose_a, pose_b, pose_c = _pose(0.0), _pose(1.0), _pose(2.0)
    (view,) = group_decision_rows(
        [
            _row(state="state", target="chair", candidate=11, pose=pose_a, utility=0.8),
            _row(state="state", target="chair", candidate=12, pose=pose_b, action=False),
            _row(state="state", target="table", candidate=21, pose=pose_a, utility=0.5),
            _row(state="state", target="table", candidate=22, pose=pose_c, label=False),
        ]
    )

    assert view.target_ids == ("chair", "table")
    assert view.candidate_poses_world == (pose_a, pose_b, pose_c)
    assert view.candidate_ids == ((11, 12, None), (21, None, 22))
    assert view.actor_action_mask == ((True, False, False), (True, False, True))
    assert view.utility_mask == ((True, False, False), (True, False, False))
    assert view.target_utilities[0][0] == 0.8
    assert view.target_utilities[1][0] == 0.5
    assert math.isnan(view.target_utilities[0][1])
    assert math.isnan(view.target_utilities[1][2])
    assert len(view.acquisition_keys) == 3
    assert all(key.scene_id == "scene" for key in view.acquisition_keys)
    assert all(key.state_fingerprint == "state" for key in view.acquisition_keys)


def test_grouping_is_deterministic_across_shuffled_input() -> None:
    rows = [
        _row(state="state", target="table", candidate=31, pose=_pose(2.0)),
        _row(state="state", target="chair", candidate=12, pose=_pose(1.0)),
        _row(state="state", target="chair", candidate=11, pose=_pose(0.0)),
    ]

    direct = group_decision_rows(rows)
    shuffled = group_decision_rows(list(reversed(rows)))

    assert direct == shuffled


def test_pose_dedup_uses_exact_float32_bits() -> None:
    positive_zero = _pose(0.0)
    negative_zero = _pose(-0.0)

    assert exact_pose_key(positive_zero) != exact_pose_key(negative_zero)
    (view,) = group_decision_rows(
        [
            _row(state="state", target="chair", candidate=1, pose=positive_zero),
            _row(state="state", target="table", candidate=2, pose=negative_zero),
        ]
    )
    assert len(view.acquisition_keys) == 2


def test_later_rollout_sharing_requires_exact_state_and_candidate_set() -> None:
    def view(state: str, poses: tuple[tuple[float, ...], ...]):
        return group_decision_rows(
            [_row(state=state, target="chair", candidate=index, pose=pose) for index, pose in enumerate(poses)]
        )[0]

    reference = view("state-a", (_pose(0.0), _pose(1.0)))
    reordered = view("state-a", (_pose(1.0), _pose(0.0)))
    divergent_state = view("state-b", (_pose(0.0), _pose(1.0)))
    divergent_candidates = view("state-a", (_pose(0.0), _pose(2.0)))

    assert can_share_later_rollout(reference, reordered)
    assert not can_share_later_rollout(reference, divergent_state)
    assert not can_share_later_rollout(reference, divergent_candidates)


def test_later_rollout_sharing_never_crosses_scenes() -> None:
    """Matching local state hashes and poses do not identify a global scene."""

    left = group_decision_rows([_row(state="state", target="chair", candidate=1, pose=_pose(), scene="a")])[0]
    right = group_decision_rows([_row(state="state", target="chair", candidate=1, pose=_pose(), scene="b")])[0]

    assert left.state_fingerprint == right.state_fingerprint
    assert left.candidate_set_key == right.candidate_set_key
    assert not can_share_later_rollout(left, right)


def test_rollout_store_derives_multi_target_tensor_batch(tmp_path) -> None:
    """Two persisted targets over one exact source state become one [1,T,C] view."""

    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr",
        build_rollout_records(horizon=1, num_samples=4, seed=8)[:2],
        selected_depth_enabled=False,
    )
    writable = zarr.open_group(result.store_dir, mode="a")
    writable["rollouts/source_row_id"][1] = writable["rollouts/source_row_id"][0]
    reader = RolloutZarrStoreReader(result.store_dir)

    actor_targets = {
        target_row_id: ActorTargetQuery(
            target_row_id,
            (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, float(target_row_id), 0.0, 0.0),
            (0.4, 0.5, 0.6),
            0.25,
        )
        for target_row_id in (0, 1)
    }
    batches = grouped_rollout_training_batches(reader, actor_targets=actor_targets)

    assert len(batches) == 1
    batch = batches[0]
    assert batch.target_row_ids == (0, 1)
    assert (batch.scene_id, batch.snippet_id, batch.source_row_id) == ("fixture_box", "smoke", 0)
    assert batch.targets_world_query.shape == (1, 2, 3, 4)
    assert batch.target_features.shape == (1, 2, 4)
    assert batch.candidates_world_camera.shape == (1, 8, 3, 4)
    assert batch.target_utilities.shape == batch.pair_valid.shape == (1, 2, 8)
    assert batch.pair_valid.sum(dim=2).tolist() == [[8, 8]]
    labels = batch.ordinal_labels(torch.tensor([0.0, 0.5]))
    assert labels.shape == batch.pair_valid.shape
    assert torch.all((labels[batch.pair_valid] >= 0) & (labels[batch.pair_valid] <= 2))


def test_rollout_store_rejects_oracle_target_geometry_as_model_input(tmp_path) -> None:
    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr",
        build_rollout_records(horizon=1, num_samples=2, seed=4)[:1],
        selected_depth_enabled=False,
    )

    try:
        grouped_rollout_training_batches(RolloutZarrStoreReader(result.store_dir))
    except ValueError as error:
        assert "non-actor source" in str(error)
        assert "ActorTargetQuery" in str(error)
    else:
        raise AssertionError("expected Oracle target-query leakage rejection")


def test_rollout_store_rejects_excessive_candidate_set(tmp_path) -> None:
    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr",
        build_rollout_records(horizon=1, num_samples=4, seed=11)[:1],
        selected_depth_enabled=False,
    )
    reader = RolloutZarrStoreReader(result.store_dir)
    actor_targets = {
        target_row_id: ActorTargetQuery(
            target_row_id,
            (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, float(target_row_id), 0.0, 0.0),
            (0.4, 0.5, 0.6),
            0.25,
        )
        for target_row_id in (0,)
    }

    with pytest.raises(ValueError, match="candidate set exceeds"):
        grouped_rollout_training_batches(
            reader,
            actor_targets=actor_targets,
            max_candidates_per_state=1,
        )
