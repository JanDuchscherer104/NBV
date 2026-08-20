"""Observable contracts for horizon-agnostic ``Q_H`` chain batches."""

# ruff: noqa: S101

from __future__ import annotations

import ast
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import torch
from efm3d.aria.pose import PoseTW

import aria_nbv.data_handling.qh_data.dataset as qh_dataset_module
from aria_nbv.data_handling.qh_data import (
    QhActorTensors,
    QhChain,
    QhDataset,
    QhDatasetConfig,
    collate_qh_chains,
)
from aria_nbv.data_handling.qh_data.dataset import _tensor_chain
from aria_nbv.data_handling.qh_data.views import QhAudit, QhChainKey, QhStaticContext, QhSupervision
from aria_nbv.data_handling.vin_store.format import VinOfflineIndexRecord
from aria_nbv.data_handling.vin_store.views import VinSnippetView
from aria_nbv.rollouts.qh_reader import QhDataContract, _QhSourceRef
from aria_nbv.rollouts.shard_manifest import build_rollout_split_manifest_hash
from aria_nbv.utils import Stage
from aria_nbv.utils.fingerprints import stable_msgspec_hash
from aria_nbv.utils.rich_summary import capture_tree, rich_summary, summarize


def test_qh_datamodel_fields_have_inline_contract_docs_without_external_shape_types() -> None:
    """Keep every Q_H DTO/config field documented without a shared typing dependency."""

    package = Path(__file__).resolve().parents[2] / "aria_nbv" / "data_handling" / "qh_data"
    expected_classes = {
        "views.py": {"QhActorTensors", "QhSupervision", "QhChainKey", "QhChain"},
        "batching.py": {"QhBatch"},
        "dataset.py": {"QhDatasetConfig"},
    }
    missing: list[str] = []
    for filename, class_names in expected_classes.items():
        source = (package / filename).read_text(encoding="utf-8")
        assert "jax" + "typing" not in source
        tree = ast.parse(source, filename=filename)
        classes = {node.name: node for node in tree.body if isinstance(node, ast.ClassDef)}
        for class_name in class_names:
            body = classes[class_name].body
            for index, statement in enumerate(body):
                if not isinstance(statement, ast.AnnAssign) or not isinstance(statement.target, ast.Name):
                    continue
                following = body[index + 1] if index + 1 < len(body) else None
                documented = (
                    isinstance(following, ast.Expr)
                    and isinstance(following.value, ast.Constant)
                    and isinstance(following.value.value, str)
                    and bool(following.value.value.strip())
                )
                if not documented:
                    missing.append(f"{filename}:{class_name}.{statement.target.id}")
    assert not missing


def test_qh_batch_transfer_constructs_owned_dtos_without_reflective_traversal() -> None:
    """Keep batch transfer explicit when owned DTO fields change."""

    source_path = Path(__file__).resolve().parents[2] / "aria_nbv" / "data_handling" / "qh_data" / "batching.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    transform_batch = next(
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_transform_batch"
    )
    calls = [node for node in ast.walk(transform_batch) if isinstance(node, ast.Call)]

    assert not any(isinstance(call.func, ast.Name) and call.func.id in {"fields", "getattr"} for call in calls)
    assert not any(keyword.arg is None for call in calls for keyword in call.keywords)


def _snippet(points: int = 2) -> VinSnippetView:
    return VinSnippetView(
        points_world=torch.arange(points * 3, dtype=torch.float32).reshape(points, 3),
        lengths=torch.tensor([points]),
        t_world_rig=PoseTW(torch.stack([PoseTW().tensor()])),
        t_world_snippet=PoseTW(torch.stack([PoseTW().tensor()])),
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

    def __init__(self, source_ref: _QhSourceRef, campaign_split: Stage | None = None) -> None:
        self.source_refs = (source_ref,)
        self.scenes = frozenset({source_ref.scene_id})
        self.stored = _stored(source_ref)
        self.campaign_split = campaign_split

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


def test_dataset_rejects_split_inconsistent_with_unfiltered_reader() -> None:
    with pytest.raises(ValueError, match="must match rollout_reader.campaign_split"):
        QhDataset(  # type: ignore[arg-type]
            rollout_reader=_RolloutReader(_source_ref()),
            actor_reader=_ActorReader(),
            split=Stage.VAL,
        )


def test_dataset_config_setup_target_forwards_learning_split_to_reader(tmp_path: Path, monkeypatch) -> None:
    captured: dict[str, object] = {}

    class _Reader:
        def __init__(self, store_dirs, *, campaign_split):
            captured["store_dirs"] = store_dirs
            captured["campaign_split"] = campaign_split

    monkeypatch.setattr(qh_dataset_module, "QhRolloutReader", _Reader)
    monkeypatch.setattr(qh_dataset_module, "VinOfflineStoreReader", lambda actor: "actor-reader")
    monkeypatch.setattr(qh_dataset_module, "QhDataset", lambda **kwargs: kwargs)

    result = QhDatasetConfig(rollout_store_dirs=(tmp_path / "rollouts.zarr",), split="val").setup_target()

    assert captured == {
        "store_dirs": (tmp_path / "rollouts.zarr",),
        "campaign_split": Stage.VAL,
    }
    assert result["split"] is Stage.VAL


def test_rich_chain_prefix_is_strictly_causal_and_audit_stays_cpu_only() -> None:
    """CF-GT selected depth may enter only the later states that causally acquired it."""

    stored = _stored(_source_ref())
    stored.selected_depth_m = np.arange(2 * 2 * 3, dtype=np.float16).reshape(2, 2, 3)
    stored.selected_depth_valid_mask = np.ones((2, 2, 3), dtype=np.bool_)
    stored.selected_depth_focal_px = np.full((2, 2), 10, dtype=np.float32)
    stored.selected_depth_principal_point_px = np.full((2, 2), 1, dtype=np.float32)
    stored.selected_depth_image_size_hw = np.tile(np.array([2, 3], dtype=np.int64), (2, 1))
    stored.selected_depth_renderer = "Pytorch3DDepthRenderer"
    context = QhStaticContext(
        vin_snippet=_snippet(),
        t_world_voxel=PoseTW().tensor(),
        voxel_extent=torch.ones(6),
        occ_pr=torch.ones(1, 1, 1, 1),
        occ_input=torch.ones(1, 1, 1, 1),
        free_input=torch.ones(1, 1, 1, 1),
        counts=torch.ones(1, 1, 1, dtype=torch.int64),
        cent_pr=torch.ones(1, 1, 1, 1),
        pts_world=torch.ones(1, 3),
        evl_presence=torch.ones(8, dtype=torch.bool),
    )
    audit = QhAudit("/tmp/rollouts.zarr", "7", "manifest", "Pytorch3DDepthRenderer")

    chain = _tensor_chain(stored, _snippet(), static_context=context, require_rich_modalities=True, audit=audit)
    prefix = chain.actor.selected_observation_prefix
    assert prefix is not None
    assert prefix.source_protocol == "cf_gt"
    assert not prefix.prefix_mask[0].any()
    assert prefix.prefix_mask.tolist() == [[False, False], [True, False]]
    assert not prefix.valid_mask[0].any()
    assert torch.equal(prefix.depth_m[1, 0], torch.from_numpy(stored.selected_depth_m[0]))
    assert not prefix.valid_mask[1, 1].any()

    batch = collate_qh_chains([chain]).to("cpu")
    assert batch.actor.static_context is not None
    assert batch.actor.selected_observation_prefix is not None
    assert batch.actor.selected_observation_prefix.prefix_mask.tolist() == [[[False, False], [True, False]]]
    assert chain.audit is audit


def test_rich_summary_reports_chain_and_batch_qh_axes() -> None:
    """Keep the documented Q_H chain and padded-batch axes executable."""

    stored = _stored(_source_ref())
    stored.selected_depth_m = np.arange(2 * 2 * 3, dtype=np.float16).reshape(2, 2, 3)
    stored.selected_depth_valid_mask = np.ones((2, 2, 3), dtype=np.bool_)
    stored.selected_depth_focal_px = np.full((2, 2), 10, dtype=np.float32)
    stored.selected_depth_principal_point_px = np.full((2, 2), 1, dtype=np.float32)
    stored.selected_depth_image_size_hw = np.tile(np.array([2, 3], dtype=np.int64), (2, 1))
    stored.selected_depth_renderer = "Pytorch3DDepthRenderer"
    context = QhStaticContext(
        vin_snippet=_snippet(),
        t_world_voxel=PoseTW().tensor(),
        voxel_extent=torch.ones(6),
        occ_pr=torch.ones(1, 1, 1, 1),
        occ_input=torch.ones(1, 1, 1, 1),
        free_input=torch.ones(1, 1, 1, 1),
        counts=torch.ones(1, 1, 1, dtype=torch.int64),
        cent_pr=torch.ones(1, 1, 1, 1),
        pts_world=torch.ones(1, 3),
        evl_presence=torch.ones(8, dtype=torch.bool),
    )
    chain = _tensor_chain(stored, _snippet(), static_context=context, require_rich_modalities=True)
    batch = collate_qh_chains([chain, chain])

    def summary(actor: QhActorTensors) -> dict[str, object]:
        static = actor.static_context
        prefix = actor.selected_observation_prefix
        assert static is not None and prefix is not None
        return {
            "candidate_pose_relative_root": summarize(actor.candidate_pose_relative_root),
            "history_pose_relative_root": summarize(actor.history_pose_relative_root),
            "step_mask": summarize(actor.step_mask),
            "vin_points_world": summarize(actor.vin_snippet.points_world),
            "evl_occ_pr": summarize(static.occ_pr),
            "evl_presence": summarize(static.evl_presence),
            "selected_depth_m": summarize(prefix.depth_m),
            "selected_depth_valid_mask": summarize(prefix.valid_mask),
            "selected_depth_camera_pose_relative_root": summarize(prefix.camera_pose_relative_root),
            "selected_depth_prefix_mask": summarize(prefix.prefix_mask),
        }

    rendered = capture_tree(
        rich_summary({"chain": summary(chain.actor), "batch": summary(batch.actor)}, is_print=False)
    )
    assert "candidate_pose_relative_root" in rendered
    assert "(2, 2, 12)" in rendered
    assert "(2, 2, 2, 12)" in rendered
    assert "selected_depth_m" in rendered
    assert "(2, 2, 2, 3)" in rendered
    assert "(2, 2, 2, 2, 3)" in rendered
    assert "evl_occ_pr" in rendered
    assert "(1, 1, 1, 1)" in rendered
    assert "(2, 1, 1, 1, 1)" in rendered


def test_rich_dataset_rejects_actor_store_without_root_evl_evidence() -> None:
    """Legacy source stores remain diagnostic-only and cannot silently enter rich training."""

    dataset = QhDataset(  # type: ignore[arg-type]
        rollout_reader=_RolloutReader(_source_ref()),
        actor_reader=_ActorReader(),
        require_rich_modalities=True,
    )
    with pytest.raises(ValueError, match="requires every root EVL evidence field"):
        _ = dataset[0]


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
