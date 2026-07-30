"""Observable contracts for horizon-agnostic ``Q_H`` chain batches."""

# ruff: noqa: S101

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import torch
from efm3d.aria.pose import PoseTW

from aria_nbv.data_handling.offline.format import VinOfflineIndexRecord
from aria_nbv.data_handling.qh import (
    QhActorTensors,
    QhChain,
    QhChainKey,
    QhDataset,
    QhSupervision,
    collate_qh_chains,
)
from aria_nbv.data_handling.raw.views import VinSnippetView
from aria_nbv.rollouts.qh_reader import QhDataContract, _QhSourceRef
from aria_nbv.rollouts.shard_manifest import build_rollout_split_manifest_hash
from aria_nbv.utils import Stage
from aria_nbv.utils.fingerprints import stable_msgspec_hash


def _snippet(points: int = 2) -> VinSnippetView:
    return VinSnippetView(
        points_world=torch.arange(points * 3, dtype=torch.float32).reshape(points, 3),
        lengths=torch.tensor([points]),
        t_world_rig=PoseTW(torch.stack([PoseTW().tensor()])),
    )


def _chain(*, steps: int, width: int, offset: int = 0) -> QhChain:
    poses = torch.arange(steps * width * 12, dtype=torch.float32).reshape(steps, width, 12) + offset
    selected = torch.arange(steps).remainder(width)
    selected_pose = poses[torch.arange(steps), selected]
    history_mask = torch.arange(steps)[:, None] > torch.arange(steps)
    history = torch.where(history_mask[..., None], selected_pose[None], 0)
    terminal = torch.arange(steps) == steps - 1
    discount = torch.full((steps,), 0.95)
    discount[-1] = 0
    return QhChain(
        actor=QhActorTensors(
            vin_snippet=_snippet(steps),
            root_pose_world=PoseTW().tensor(),
            target_pose_relative_root=PoseTW().tensor(),
            target_extents=torch.ones(3),
            candidate_pose_relative_root=poses,
            candidate_mask=torch.ones(steps, width, dtype=torch.bool),
            action_mask=torch.ones(steps, width, dtype=torch.bool),
            history_pose_relative_root=history,
            history_mask=history_mask,
            horizon_remaining=torch.arange(steps, 0, -1),
            step_mask=torch.ones(steps, dtype=torch.bool),
        ),
        supervision=QhSupervision(
            label_mask=torch.ones(steps, width, dtype=torch.bool),
            candidate_reward=torch.arange(offset, offset + steps * width, dtype=torch.float32).reshape(steps, width),
            selected_index=selected,
            discount=discount,
            terminal=terminal,
        ),
        key=QhChainKey(offset, offset, offset, f"scene-{offset}", offset),
    )


def test_collate_mixed_horizons_and_widths_preserves_five_masks_and_causal_history() -> None:
    chains = [_chain(steps=1, width=2), _chain(steps=3, width=1, offset=10), _chain(steps=4, width=3, offset=20)]
    batch = collate_qh_chains(chains)

    assert batch.actor.candidate_pose_relative_root.shape == (3, 4, 3, 12)
    assert batch.actor.step_mask.tolist() == [
        [True, False, False, False],
        [True, True, True, False],
        [True, True, True, True],
    ]
    assert batch.actor.horizon_remaining.tolist() == [[1, 0, 0, 0], [3, 2, 1, 0], [4, 3, 2, 1]]
    assert not batch.actor.candidate_mask[1, :, 1:].any()
    assert not batch.actor.action_mask[0, 1:].any()
    assert not batch.supervision.label_mask[0, 1:].any()
    assert not batch.actor.history_mask[:, 0].any()
    assert not batch.actor.history_mask[0].any()
    assert batch.actor.history_mask[2, 3].tolist() == [True, True, True, False]
    assert torch.equal(batch.num_steps, torch.tensor([1, 3, 4]))


def test_masks_distinguish_materialized_invalid_actions_from_padding() -> None:
    first = _chain(steps=1, width=2)
    first = replace(
        first,
        actor=replace(first.actor, action_mask=torch.tensor([[True, False]])),
        supervision=replace(first.supervision, label_mask=torch.tensor([[True, False]])),
    )
    batch = collate_qh_chains([first, _chain(steps=2, width=3, offset=10)])

    assert batch.actor.candidate_mask[0, 0, 1]
    assert not batch.actor.action_mask[0, 0, 1]
    assert not batch.supervision.label_mask[0, 0, 1]
    assert not batch.actor.candidate_mask[0, 1:].any()
    assert not (batch.supervision.label_mask & ~batch.actor.action_mask).any()
    assert not (batch.actor.action_mask & ~batch.actor.candidate_mask).any()


def test_derived_selected_and_successor_masks_share_exact_support() -> None:
    batch = collate_qh_chains([_chain(steps=3, width=2)])
    action = batch.actor.action_mask.clone()
    labels = batch.supervision.label_mask.clone()
    labels[0, 1, 0] = False
    reward = batch.supervision.candidate_reward.clone()
    reward[0, 0, 0] = torch.nan
    batch = replace(
        batch,
        actor=replace(batch.actor, action_mask=action),
        supervision=replace(batch.supervision, label_mask=labels, candidate_reward=reward),
    )

    expected_successor = torch.zeros_like(action)
    expected_successor[:, :-1] = (action & labels)[:, 1:]
    expected_actions = torch.zeros_like(action)
    expected_actions[:, :-1] = action[:, 1:]
    assert torch.equal(batch.successor_backup_mask, expected_successor)
    assert torch.equal(batch.successor_action_mask, expected_actions)
    assert batch.actor_successor_present.tolist() == [[True, True, False]]
    assert batch.successor_present.tolist() == [[True, True, False]]
    assert batch.selected_train_mask.tolist() == [[False, True, True]]
    assert batch.bootstrap_mask.tolist() == [[False, True, False]]


@dataclass
class _Manifest:
    version: int = 7


_RECORD = VinOfflineIndexRecord(0, "sample-0", "scene-0", "snippet-0", "train", "shard-0", 0)


class _ActorReader:
    manifest = _Manifest()
    record = _RECORD
    config = SimpleNamespace(store_dir=Path("/tmp/vin"))

    def get_split_records(self, _split: Stage | None) -> list[VinOfflineIndexRecord]:
        return [self.record]

    def read_actor_snippet(self, record: VinOfflineIndexRecord, *, device: str = "cpu") -> VinSnippetView:
        assert record is self.record and device == "cpu"
        return _snippet()


def _source_ref(**changes: object) -> _QhSourceRef:
    manifest_hash = stable_msgspec_hash(_ActorReader.manifest)
    record = asdict(_RECORD)
    record["source_shard_id"] = record.pop("shard_id")
    record["source_shard_row"] = record.pop("row")
    split_hash = build_rollout_split_manifest_hash(
        source_manifest_hash=manifest_hash,
        split="train",
        records=[{"order": 0, **record}],
    )
    values = {
        "source_sample_index": 0,
        "source_sample_key": "sample-0",
        "source_shard_id": "shard-0",
        "source_shard_row": 0,
        "scene_id": "scene-0",
        "snippet_id": "snippet-0",
        "split": Stage.TRAIN,
        "actor_store_version": "7",
        "source_manifest_hash": manifest_hash,
        "split_manifest_hash": split_hash,
    }
    values.update(changes)
    return _QhSourceRef(**values)  # type: ignore[arg-type]


def _stored(source_ref: _QhSourceRef) -> SimpleNamespace:
    identity = PoseTW().tensor().numpy()
    target = identity.copy()
    target[-3:] = np.array([1, 2, 3], dtype=np.float32)
    return SimpleNamespace(
        root_pose_world=identity,
        target_pose_world_object=target,
        target_extents=np.ones(3, dtype=np.float32),
        candidate_pose_relative_root=(np.stack([identity, identity]), np.stack([identity])),
        action_mask=(np.array([True, False]), np.array([True])),
        label_mask=(np.array([True, False]), np.array([True])),
        candidate_reward=(np.array([0.4, 0.0], dtype=np.float32), np.array([0.6], dtype=np.float32)),
        selected_index=np.array([0, 0]),
        horizon_remaining=np.array([2, 1]),
        discount=np.array([0.95, 0], dtype=np.float32),
        terminal=np.array([False, True]),
        store_index=0,
        rollout_row_id=4,
        target_row_id=5,
        source_ref=source_ref,
    )


class _RolloutReader:
    max_horizon = 2
    contract = QhDataContract("8", "v0_gt_input", "gain", "return", "td", 0.95, "reason", "7")
    provenance = {"stores": []}

    def __init__(self, source_ref: _QhSourceRef) -> None:
        self.source_refs = (source_ref,)
        self.scenes = frozenset({source_ref.scene_id})
        self.stored = _stored(source_ref)

    def __len__(self) -> int:
        return 1

    def __getitem__(self, index: int) -> SimpleNamespace:
        del index
        return self.stored


def test_dataset_joins_exact_source_and_emits_no_provenance() -> None:
    dataset = QhDataset(  # type: ignore[arg-type]
        rollout_reader=_RolloutReader(_source_ref()), actor_reader=_ActorReader()
    )
    chain = dataset[0]

    assert chain.key == QhChainKey(0, 4, 0, "scene-0", 5)
    assert chain.actor.target_pose_relative_root[-3:].tolist() == pytest.approx([1, 2, 3])
    assert chain.actor.history_mask.tolist() == [[False, False], [True, False]]
    assert chain.actor.horizon_remaining.tolist() == [2, 1]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_sample_index", 1),
        ("source_sample_key", "wrong"),
        ("source_shard_id", "wrong"),
        ("source_shard_row", 1),
        ("scene_id", "wrong"),
        ("snippet_id", "wrong"),
        ("split", Stage.VAL),
        ("actor_store_version", "wrong"),
        ("source_manifest_hash", "wrong"),
        ("split_manifest_hash", "wrong"),
    ],
)
def test_dataset_rejects_each_source_identity_mismatch(field: str, value: object) -> None:
    with pytest.raises(
        (KeyError, ValueError),
        match="absent from split|does not match rollout chain|split manifest does not match",
    ):
        QhDataset(
            rollout_reader=_RolloutReader(_source_ref(**{field: value})),  # type: ignore[arg-type]
            actor_reader=_ActorReader(),  # type: ignore[arg-type]
        )
