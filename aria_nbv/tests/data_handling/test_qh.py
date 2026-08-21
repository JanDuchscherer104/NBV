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
from efm3d.aria.camera import CameraTW
from efm3d.aria.pose import PoseTW

import aria_nbv.data_handling.qh_data.dataset as qh_dataset_module
from aria_nbv.data_handling.qh_data import (
    QhActorTensors,
    QhChain,
    QhDataset,
    QhDatasetConfig,
    collate_qh_chains,
)
from aria_nbv.data_handling.qh_data.batching import _gather_candidates
from aria_nbv.data_handling.qh_data.dataset import _require_named_profile_store
from aria_nbv.data_handling.qh_data.materialization import _tensor_chain
from aria_nbv.data_handling.qh_data.views import (
    QhActorStateContract,
    QhAudit,
    QhChainKey,
    QhSelectedObservationPrefix,
    QhStaticContext,
    QhSupervision,
)
from aria_nbv.data_handling.vin_store.format import VinOfflineIndexRecord
from aria_nbv.data_handling.vin_store.store import VinOfflineStoreReader
from aria_nbv.data_handling.vin_store.views import VinSnippetView
from aria_nbv.lightning.qh_datamodule import QhDataModule
from aria_nbv.lightning.qh_module import QhLightningModule, QhLightningModuleConfig
from aria_nbv.oracle.pipelines.offline_vin import _compact_evl_block_signature, _point_feature_schema
from aria_nbv.rollouts.qh_reader import QhDataContract, QhRolloutReader, _QhSourceRef
from aria_nbv.rollouts.shard_manifest import build_rollout_split_manifest_hash
from aria_nbv.rollouts.zarr_store import write_rollout_zarr_store
from aria_nbv.utils import Stage
from aria_nbv.utils.fingerprints import stable_msgspec_hash
from aria_nbv.utils.rich_summary import capture_tree, rich_summary, summarize
from aria_nbv.vin.types import EvlBackboneOutput
from tests.data_handling.test_vin_offline_store import _write_test_store
from tests.rollout_fixtures import build_rollout_records


def test_qh_datamodel_fields_have_inline_contract_docs_without_external_shape_types() -> None:
    """Keep every Q_H DTO/config field documented without a shared typing dependency."""

    package = Path(__file__).resolve().parents[2] / "aria_nbv" / "data_handling" / "qh_data"
    expected_classes = {
        "views.py": {"QhActorStateContract", "QhActorTensors", "QhSupervision", "QhChainKey", "QhChain"},
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


def test_qh_pose_fields_preserve_frame_aware_public_types() -> None:
    """Keep SE(3) views typed as poses instead of exposing raw storage tensors."""

    assert QhStaticContext.__annotations__["t_world_voxel"] == "PoseTW | None"
    assert QhSelectedObservationPrefix.__annotations__["camera"] == "CameraTW"
    assert QhSelectedObservationPrefix.__annotations__["camera_pose_relative_root"] == "PoseTW"
    for field in (
        "root_pose_world",
        "target_pose_relative_root",
        "candidate_pose_relative_root",
        "history_pose_relative_root",
    ):
        assert QhActorTensors.__annotations__[field] == "PoseTW"


@pytest.mark.parametrize(
    ("profile", "root_evl", "selected", "geometry"),
    (
        ("qh_cf0_v1", "evl_v1", "none", None),
        ("qh_cfplus_gt_depth_v1", "evl_v1", "cf_gt", "geometry-v1"),
    ),
)
def test_named_profile_batch_and_module_admission_preserve_actor_allowlist(
    profile: str, root_evl: str, selected: str, geometry: str | None
) -> None:
    """Both named roles survive batch transfer while supervision stays outside actor inputs."""

    actor_contract = replace(
        QhActorStateContract("none", "none", "test-actor-manifest", ()),
        root_evl_profile=root_evl,
        selected_observation_protocol=selected,
        experiment_profile=profile,
        geometry_contract_hash=geometry,
    )

    class _ProfileDataset:
        contract = QhDataContract("8", "v0", "gain", "return", "td", 0.95, "reason", "7")
        scenes = frozenset({"scene-profile"})
        max_horizon = 2
        provenance: dict[str, object] = {}

        def __len__(self) -> int:
            return 1

        def __getitem__(self, index: int) -> QhChain:
            assert index == 0
            return _chain(steps=2, width=3)

        @property
        def actor_state_contract(self) -> QhActorStateContract:
            return actor_contract

    dataset = _ProfileDataset()
    data = QhDataModule(train=dataset, seed=7, experiment_profile=profile)  # type: ignore[arg-type]
    batch = next(iter(data.train_dataloader())).to("cpu")
    assert batch.actor.vin_snippet is not None
    assert not hasattr(batch.actor, "one_step_target_rri")

    class _Scorer(torch.nn.Module):
        def forward(self, actor: QhActorTensors) -> torch.Tensor:
            return torch.zeros_like(actor.action_mask, dtype=torch.float32)

    module = QhLightningModule(
        QhLightningModuleConfig(
            lr_scheduler=None,
            experiment_profile=profile,
            privileged=profile == "qh_cfplus_gt_depth_v1",
            root_evl_profile=root_evl,
            selected_observation_protocol=selected,
            actor_state_contract_hash=data.actor_state_contract_hash,
            geometry_contract_hash=geometry,
        ),
        scorer=_Scorer(),
    )
    module._validate_datamodule_contract(data)


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
            root_pose_world=PoseTW(),
            target_pose_relative_root=PoseTW(),
            target_extents=torch.ones(3),
            candidate_pose_relative_root=PoseTW(poses),
            candidate_mask=torch.ones(steps, width, dtype=torch.bool),
            action_mask=torch.ones(steps, width, dtype=torch.bool),
            history_pose_relative_root=PoseTW(history),
            history_mask=history_mask,
            horizon_remaining=torch.arange(steps, 0, -1),
            step_mask=torch.ones(steps, dtype=torch.bool),
        ),
        supervision=QhSupervision(
            label_mask=torch.ones(steps, width, dtype=torch.bool),
            candidate_reward=torch.arange(offset, offset + steps * width, dtype=torch.float32).reshape(steps, width),
            one_step_target_rri=torch.arange(offset + 100, offset + 100 + steps * width, dtype=torch.float32).reshape(
                steps, width
            ),
            selected_index=selected,
            discount=discount,
            terminal=terminal,
        ),
        key=QhChainKey(offset, offset, offset, f"scene-{offset}", offset),
    )


def test_candidate_gather_uses_candidate_axis_for_sixty_vector_rows() -> None:
    """Selected poses must not clamp factual indices to the pose feature width."""

    indices = torch.tensor([0, 11, 12, 59], dtype=torch.int64)
    scalar = torch.arange(4 * 60, dtype=torch.float32).reshape(4, 60)
    vector = torch.arange(4 * 60 * 12, dtype=torch.float32).reshape(4, 60, 12)

    assert torch.equal(_gather_candidates(scalar, indices), scalar[torch.arange(4), indices])
    assert torch.equal(_gather_candidates(vector, indices), vector[torch.arange(4), indices])


def test_candidate_gather_rejects_unsupported_ranks_and_invalid_indices() -> None:
    values = torch.zeros(2, 3, 4, 5)
    with pytest.raises(ValueError, match="unsupported.*rank|values.ndim"):
        _gather_candidates(values, torch.zeros(2, dtype=torch.int64))
    with pytest.raises(ValueError, match="out-of-range.*candidate width 4"):
        _gather_candidates(torch.zeros(2, 4), torch.tensor([4, 0]))


def test_sixty_candidate_identity_survives_materialization_collation_and_transfer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A full-width chain keeps candidate 59 distinct through every tensor seam."""

    steps, width = 5, 60
    identity = PoseTW().tensor().numpy()
    poses = np.repeat(identity[None, None, :], steps * width, axis=0).reshape(steps, width, -1)
    poses[..., -3] = np.arange(width, dtype=np.float32)[None, :]
    stored = _stored(_source_ref())
    stored.candidate_pose_relative_root = tuple(poses[row] for row in range(steps))
    stored.action_mask = tuple(np.ones(width, dtype=np.bool_) for _ in range(steps))
    stored.label_mask = tuple(np.ones(width, dtype=np.bool_) for _ in range(steps))
    stored.candidate_reward = tuple(np.ones(width, dtype=np.float32) for _ in range(steps))
    stored.one_step_target_rri = tuple(np.ones(width, dtype=np.float32) for _ in range(steps))
    stored.selected_index = np.array([0, 11, 12, 59, 0], dtype=np.int64)
    stored.horizon_remaining = np.arange(steps, 0, -1)
    stored.discount = np.full(steps, 0.95, dtype=np.float32)
    stored.terminal = np.array([False, False, False, False, True])

    chain = _tensor_chain(stored, _snippet())
    batch = collate_qh_chains([chain, _chain(steps=2, width=3)])
    selected = batch.actor.history_pose_relative_root.tensor()[0, 4, 3, -3]
    assert selected.item() == pytest.approx(59.0)
    monkeypatch.setattr(torch.Tensor, "pin_memory", lambda value: value)
    pinned = batch.pin_memory()
    assert pinned.actor.history_pose_relative_root.tensor()[0, 4, 3, -3].item() == pytest.approx(59.0)
    transferred = batch.to("cpu")
    assert transferred.actor.history_pose_relative_root.tensor()[0, 4, 3, -3].item() == pytest.approx(59.0)


def test_materialization_rejects_invalid_factual_index_with_chain_context() -> None:
    stored = _stored(_source_ref())
    stored.selected_index = np.array([0, 1], dtype=np.int64)
    with pytest.raises(ValueError, match="store_index=0.*rollout_row_id=4.*step=1.*candidate_width=1"):
        _tensor_chain(stored, _snippet())


def test_collate_mixed_horizons_and_widths_preserves_five_masks_and_causal_history() -> None:
    chains = [_chain(steps=1, width=2), _chain(steps=3, width=1, offset=10), _chain(steps=4, width=3, offset=20)]
    batch = collate_qh_chains(chains)

    assert batch.actor.candidate_pose_relative_root.tensor().shape == (3, 4, 3, 12)
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
    shards: tuple[object, ...] = ()


_RECORD = VinOfflineIndexRecord(0, "sample-0", "scene-0", "snippet-0", "train", "shard-0", 0)


class _ActorReader:
    manifest = _Manifest()
    record = _RECORD
    config = SimpleNamespace(store_dir=Path("/tmp/vin"))

    def __init__(self, backbone: EvlBackboneOutput | None = None) -> None:
        self.backbone = backbone
        self.backbone_reads = 0

    def get_split_records(self, _split: Stage | None) -> list[VinOfflineIndexRecord]:
        return [self.record]

    def read_actor_snippet(self, record: VinOfflineIndexRecord, *, device: str = "cpu") -> VinSnippetView:
        assert record is self.record and device == "cpu"
        return _snippet()

    def read_backbone_evidence(self, record: VinOfflineIndexRecord, *, device: str = "cpu") -> EvlBackboneOutput | None:
        assert record is self.record and device == "cpu"
        self.backbone_reads += 1
        return self.backbone


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
        one_step_target_rri=(np.array([0.2, np.nan], dtype=np.float32), np.array([0.3], dtype=np.float32)),
        selected_index=np.array([0, 0]),
        horizon_remaining=np.array([2, 1]),
        discount=np.array([0.95, 0], dtype=np.float32),
        terminal=np.array([False, True]),
        selected_depth_m=None,
        selected_depth_valid_mask=None,
        selected_depth_focal_px=None,
        selected_depth_principal_point_px=None,
        selected_depth_image_size_hw=None,
        selected_depth_renderer=None,
        store_index=0,
        rollout_row_id=4,
        target_row_id=5,
        source_ref=source_ref,
    )


class _RolloutReader:
    max_horizon = 2
    contract = QhDataContract("8", "v0_gt_input", "gain", "return", "td", 0.95, "reason", "7")
    provenance = {"stores": []}
    store_dirs = (Path("/tmp/rollouts.zarr"),)

    def __init__(
        self,
        source_ref: _QhSourceRef,
        campaign_split: Stage | None = None,
        *,
        include_selected_depth: bool = False,
    ) -> None:
        self.source_refs = (source_ref,)
        self.scenes = frozenset({source_ref.scene_id})
        self.stored = _stored(source_ref)
        self.campaign_split = campaign_split
        self.include_selected_depth = include_selected_depth

    def __len__(self) -> int:
        return 1

    def __getitem__(self, index: int) -> SimpleNamespace:
        del index
        return self.stored


def test_dataset_joins_exact_source_and_emits_no_provenance() -> None:
    actor_reader = _ActorReader()
    dataset = QhDataset(  # type: ignore[arg-type]
        rollout_reader=_RolloutReader(_source_ref()), actor_reader=actor_reader
    )
    chain = dataset[0]

    assert chain.key == QhChainKey(0, 4, 0, "scene-0", 5)
    assert isinstance(chain.actor.root_pose_world, PoseTW)
    assert isinstance(chain.actor.target_pose_relative_root, PoseTW)
    assert isinstance(chain.actor.candidate_pose_relative_root, PoseTW)
    assert isinstance(chain.actor.history_pose_relative_root, PoseTW)
    assert chain.actor.target_pose_relative_root.tensor()[-3:].tolist() == pytest.approx([1, 2, 3])
    assert chain.actor.history_mask.tolist() == [[False, False], [True, False]]
    assert chain.actor.horizon_remaining.tolist() == [2, 1]
    assert chain.supervision.one_step_target_rri[:, 0].tolist() == pytest.approx([0.2, 0.3])
    assert torch.isnan(chain.supervision.one_step_target_rri[0, 1])
    assert not hasattr(chain.actor, "one_step_target_rri")
    assert chain.actor.static_context is None
    assert actor_reader.backbone_reads == 0


def test_rich_dataset_normalizes_one_source_axis_before_batching() -> None:
    scalar_grid = torch.ones((1, 1, 2, 2, 2), dtype=torch.float32)
    actor_reader = _ActorReader(
        EvlBackboneOutput(
            t_world_voxel=PoseTW(torch.zeros((1, 12), dtype=torch.float32)),
            voxel_extent=torch.ones(6),
            occ_pr=scalar_grid,
            occ_input=scalar_grid,
            free_input=scalar_grid,
            counts=torch.ones((1, 2, 2, 2), dtype=torch.int64),
            cent_pr=scalar_grid,
            pts_world=torch.ones((1, 8, 3), dtype=torch.float32),
        )
    )
    rollout_reader = _RolloutReader(_source_ref(), include_selected_depth=True)
    rollout_reader.stored.selected_depth_m = np.ones((2, 2, 3), dtype=np.float16)
    rollout_reader.stored.selected_depth_valid_mask = np.ones((2, 2, 3), dtype=np.bool_)
    rollout_reader.stored.selected_depth_focal_px = np.ones((2, 2), dtype=np.float32)
    rollout_reader.stored.selected_depth_principal_point_px = np.ones((2, 2), dtype=np.float32)
    rollout_reader.stored.selected_depth_image_size_hw = np.tile(np.array([2, 3]), (2, 1))
    rollout_reader.stored.selected_depth_renderer = "Pytorch3DDepthRenderer"
    dataset = QhDataset(  # type: ignore[arg-type]
        rollout_reader=rollout_reader,
        actor_reader=actor_reader,
        root_evl_profile="evl_v1",
        selected_observation_protocol="cf_gt",
    )

    chain = dataset[0]
    context = chain.actor.static_context
    assert context is not None
    assert context.t_world_voxel is not None and context.t_world_voxel.tensor().shape == (12,)
    assert context.occ_pr is not None and context.occ_pr.shape == (1, 2, 2, 2)
    assert context.counts is not None and context.counts.shape == (2, 2, 2)
    assert context.pts_world is not None and context.pts_world.shape == (8, 3)
    batch = collate_qh_chains([chain, chain])
    batch_context = batch.actor.static_context
    assert batch_context is not None
    assert batch_context.vin_snippet is batch.actor.vin_snippet
    assert batch_context.t_world_voxel is not None and batch_context.t_world_voxel.tensor().shape == (2, 12)
    assert batch_context.occ_pr is not None and batch_context.occ_pr.shape == (2, 1, 2, 2, 2)
    assert batch_context.counts is not None and batch_context.counts.shape == (2, 2, 2, 2)
    assert batch_context.pts_world is not None and batch_context.pts_world.shape == (2, 8, 3)
    moved = batch.to("cpu")
    assert moved.actor.static_context is not None
    assert moved.actor.static_context.vin_snippet is moved.actor.vin_snippet
    assert actor_reader.backbone_reads == 1


def test_root_evl_profile_does_not_require_selected_observations() -> None:
    """Immutable root EVL is independently usable without privileged CF-GT depth."""

    scalar_grid = torch.ones((1, 1, 2, 2, 2), dtype=torch.float32)
    actor_reader = _ActorReader(
        EvlBackboneOutput(
            t_world_voxel=PoseTW(torch.zeros((1, 12), dtype=torch.float32)),
            voxel_extent=torch.ones(6),
            occ_pr=scalar_grid,
            occ_input=scalar_grid,
            free_input=scalar_grid,
            counts=torch.ones((1, 2, 2, 2), dtype=torch.int64),
            cent_pr=scalar_grid,
            pts_world=torch.ones((1, 8, 3), dtype=torch.float32),
        )
    )
    dataset = QhDataset(  # type: ignore[arg-type]
        rollout_reader=_RolloutReader(_source_ref()),
        actor_reader=actor_reader,
        root_evl_profile="evl_v1",
    )

    chain = dataset[0]

    assert chain.actor.static_context is not None
    assert chain.actor.selected_observation_prefix is None
    assert dataset.actor_state_contract.root_evl_profile == "evl_v1"
    assert dataset.actor_state_contract.selected_observation_protocol == "none"


def test_selected_observation_protocol_does_not_require_root_evl() -> None:
    """Privileged selected observations are independently opt-in from root EVL."""

    rollout_reader = _RolloutReader(_source_ref(), include_selected_depth=True)
    rollout_reader.stored.selected_depth_m = np.ones((2, 2, 3), dtype=np.float16)
    rollout_reader.stored.selected_depth_valid_mask = np.ones((2, 2, 3), dtype=np.bool_)
    rollout_reader.stored.selected_depth_focal_px = np.ones((2, 2), dtype=np.float32)
    rollout_reader.stored.selected_depth_principal_point_px = np.ones((2, 2), dtype=np.float32)
    rollout_reader.stored.selected_depth_image_size_hw = np.tile(np.array([2, 3]), (2, 1))
    rollout_reader.stored.selected_depth_renderer = "Pytorch3DDepthRenderer"
    dataset = QhDataset(  # type: ignore[arg-type]
        rollout_reader=rollout_reader,
        actor_reader=_ActorReader(),
        selected_observation_protocol="cf_gt",
    )

    chain = dataset[0]

    assert chain.actor.static_context is None
    assert chain.actor.selected_observation_prefix is not None
    assert dataset.actor_state_contract.root_evl_profile == "none"
    assert dataset.actor_state_contract.selected_observation_protocol == "cf_gt"


def test_rich_dataset_rejects_non_singleton_source_axis() -> None:
    actor_reader = _ActorReader(
        EvlBackboneOutput(
            t_world_voxel=PoseTW(torch.zeros((2, 12), dtype=torch.float32)),
            voxel_extent=torch.ones(6),
        )
    )
    dataset = QhDataset(  # type: ignore[arg-type]
        rollout_reader=_RolloutReader(_source_ref()),
        actor_reader=actor_reader,
        root_evl_profile="evl_v1",
    )

    with pytest.raises(ValueError, match="source batch axis must have size 1"):
        _ = dataset[0]


def test_audit_reads_renderer_metadata_without_loading_rich_payloads() -> None:
    actor_reader = _ActorReader()
    rollout_reader = _RolloutReader(_source_ref())
    rollout_reader.stored.selected_depth_renderer = "Pytorch3DDepthRenderer"
    dataset = QhDataset(  # type: ignore[arg-type]
        rollout_reader=rollout_reader,
        actor_reader=actor_reader,
        include_audit=True,
    )

    chain = dataset[0]
    assert chain.audit is not None
    assert chain.audit.selected_depth_renderer == "Pytorch3DDepthRenderer"
    assert chain.actor.selected_observation_prefix is None
    assert actor_reader.backbone_reads == 0


def test_collate_rejects_incompatible_root_evl_geometry() -> None:
    first_context = QhStaticContext(
        vin_snippet=_snippet(),
        t_world_voxel=PoseTW(),
        voxel_extent=torch.ones(6),
        occ_pr=torch.ones(1, 2, 2, 2),
        occ_input=None,
        free_input=None,
        counts=None,
        cent_pr=None,
        pts_world=None,
        evl_presence=torch.tensor([True, True, True, False, False, False, False, False]),
    )
    second_context = replace(first_context, occ_pr=torch.ones(1, 2, 2, 3))
    first = _chain(steps=1, width=1)
    second = _chain(steps=1, width=1, offset=1)
    first = replace(first, actor=replace(first.actor, static_context=first_context))
    second = replace(second, actor=replace(second.actor, static_context=second_context))

    with pytest.raises(ValueError, match="one root EVL field 'occ_pr' shape"):
        collate_qh_chains([first, second])


def test_collate_rejects_incompatible_selected_depth_geometry() -> None:
    def rich_chain(height: int) -> QhChain:
        stored = _stored(_source_ref())
        stored.selected_depth_m = np.ones((2, height, 3), dtype=np.float16)
        stored.selected_depth_valid_mask = np.ones((2, height, 3), dtype=np.bool_)
        stored.selected_depth_focal_px = np.ones((2, 2), dtype=np.float32)
        stored.selected_depth_principal_point_px = np.ones((2, 2), dtype=np.float32)
        stored.selected_depth_image_size_hw = np.tile(np.array([height, 3]), (2, 1))
        stored.selected_depth_renderer = "Pytorch3DDepthRenderer"
        return _tensor_chain(stored, _snippet(), selected_observation_protocol="cf_gt")

    with pytest.raises(ValueError, match="one raster geometry"):
        collate_qh_chains([rich_chain(2), rich_chain(3)])


def test_dataset_rejects_split_inconsistent_with_unfiltered_reader() -> None:
    with pytest.raises(ValueError, match="must match rollout_reader.campaign_split"):
        QhDataset(  # type: ignore[arg-type]
            rollout_reader=_RolloutReader(_source_ref()),
            actor_reader=_ActorReader(),
            split=Stage.VAL,
        )


def test_dataset_rejects_selected_observation_protocol_reader_mismatch() -> None:
    with pytest.raises(ValueError, match="must match rollout-reader loading"):
        QhDataset(  # type: ignore[arg-type]
            rollout_reader=_RolloutReader(_source_ref()),
            actor_reader=_ActorReader(),
            selected_observation_protocol="cf_gt",
        )


def test_dataset_rejects_unnamed_cf_gt_before_reader_materialization() -> None:
    with pytest.raises(ValueError, match="requires qh_cfplus_gt_depth_v1"):
        QhDataset(  # type: ignore[arg-type]
            rollout_reader=_RolloutReader(_source_ref(), include_selected_depth=True),
            actor_reader=_ActorReader(),
            selected_observation_protocol="cf_gt",
        )


def test_dataset_config_rejects_unnamed_cf_gt_before_reader_construction(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="requires qh_cfplus_gt_depth_v1"):
        QhDatasetConfig(
            rollout_store_dirs=(tmp_path / "rollouts.zarr",),
            selected_observation_protocol="cf_gt",
        ).setup_target()


def test_dataset_config_setup_target_forwards_learning_split_to_reader(tmp_path: Path, monkeypatch) -> None:
    captured: dict[str, object] = {}

    class _Reader:
        def __init__(self, store_dirs, *, campaign_split, include_selected_depth):
            captured["store_dirs"] = store_dirs
            captured["campaign_split"] = campaign_split
            captured["include_selected_depth"] = include_selected_depth

    monkeypatch.setattr(qh_dataset_module, "QhRolloutReader", _Reader)
    monkeypatch.setattr(qh_dataset_module, "VinOfflineStoreReader", lambda actor: "actor-reader")
    monkeypatch.setattr(qh_dataset_module, "QhDataset", lambda **kwargs: kwargs)

    result = QhDatasetConfig(rollout_store_dirs=(tmp_path / "rollouts.zarr",), split="val").setup_target()

    assert captured == {
        "store_dirs": (tmp_path / "rollouts.zarr",),
        "campaign_split": Stage.VAL,
        "include_selected_depth": False,
    }
    assert result["split"] is Stage.VAL
    assert result["root_evl_profile"] == "none"
    assert result["selected_observation_protocol"] == "none"


def test_named_cf0_requires_root_evl_and_does_not_load_selected_depth(tmp_path: Path, monkeypatch) -> None:
    config = QhDatasetConfig(
        rollout_store_dirs=(tmp_path / "rollouts.zarr",),
        experiment_profile="qh_cf0_v1",
    )
    with pytest.raises(ValueError, match="requires compact root EVL"):
        config.setup_target()

    captured: dict[str, object] = {}

    class _Reader:
        def __init__(self, store_dirs, *, campaign_split, include_selected_depth):
            captured["include_selected_depth"] = include_selected_depth

    monkeypatch.setattr(qh_dataset_module, "QhRolloutReader", _Reader)
    monkeypatch.setattr(qh_dataset_module, "VinOfflineStoreReader", lambda actor: "actor-reader")
    monkeypatch.setattr(qh_dataset_module, "QhDataset", lambda **kwargs: kwargs)
    result = QhDatasetConfig(
        rollout_store_dirs=(tmp_path / "rollouts.zarr",),
        experiment_profile="qh_cf0_v1",
        root_evl_profile="evl_v1",
    ).setup_target()
    assert captured["include_selected_depth"] is False
    assert result["experiment_profile"] == "qh_cf0_v1"


@pytest.mark.parametrize(
    "mutation",
    [
        ("x_m", "renamed", "m"),
        ("inv_dist_std", "m", "m"),
        ("x_m", "float64", "m"),
    ],
)
def test_named_profile_admission_rejects_point_schema_mutations(mutation: tuple[str, str, str]) -> None:
    schema = [
        {"name": "x_m", "dtype": "float32", "unit": "m", "version": "vin_points_v1"},
        {"name": "y_m", "dtype": "float32", "unit": "m", "version": "vin_points_v1"},
        {"name": "z_m", "dtype": "float32", "unit": "m", "version": "vin_points_v1"},
        {"name": "inv_dist_std", "dtype": "float32", "unit": "m^-1", "version": "vin_points_v1"},
    ]
    field, value, unit = mutation
    schema[next(index for index, item in enumerate(schema) if item["name"] == field)] = {
        "name": value if value in {"renamed", "m"} else field,
        "dtype": value if value == "float64" else "float32",
        "unit": unit,
        "version": "vin_points_v1",
    }
    manifest = SimpleNamespace(
        version=9,
        vin={
            "include_obs_count": False,
            "point_feature_schema": schema,
            "point_feature_schema_hash": stable_msgspec_hash(schema),
            "backbone_block_signature": [],
        },
        shards=[],
    )
    with pytest.raises(ValueError, match="canonical|semantics|units"):
        _require_named_profile_store(SimpleNamespace(manifest=manifest))


def test_named_profile_rejects_v8_with_rebuild_guidance() -> None:
    manifest = SimpleNamespace(version=8, vin={}, shards=[])
    with pytest.raises(ValueError, match="version 9|Rebuild"):
        _require_named_profile_store(SimpleNamespace(manifest=manifest))


@pytest.mark.parametrize("mutation", ["dtype", "shape"])
def test_named_profile_rejects_declared_evl_signature_drift(tmp_path: Path, mutation: str) -> None:
    config = _write_test_store(tmp_path / "vin", include_backbone=True)
    reader = VinOfflineStoreReader(config)
    signature = _compact_evl_block_signature(reader.manifest.shards)
    signature[0][mutation] = "float64" if mutation == "dtype" else [999]
    reader.manifest.vin.update(
        point_feature_schema=_point_feature_schema(include_obs_count=False),
        point_feature_schema_hash=stable_msgspec_hash(_point_feature_schema(include_obs_count=False)),
        include_inv_dist_std=True,
        include_obs_count=False,
        backbone_block_signature=signature,
    )
    with pytest.raises(ValueError, match="EVL|signature|shape|dtype"):
        _require_named_profile_store(reader)


def test_rich_chain_prefix_is_strictly_causal_and_audit_stays_cpu_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CF-GT selected depth may enter only the later states that causally acquired it."""

    stored = _stored(_source_ref())
    stored.selected_depth_m = np.arange(2 * 2 * 3, dtype=np.float16).reshape(2, 2, 3)
    stored.selected_depth_valid_mask = np.ones((2, 2, 3), dtype=np.bool_)
    stored.selected_depth_focal_px = np.tile(np.array([10, 12], dtype=np.float32), (2, 1))
    stored.selected_depth_principal_point_px = np.tile(np.array([0.75, 1.25], dtype=np.float32), (2, 1))
    stored.selected_depth_image_size_hw = np.tile(np.array([2, 3], dtype=np.int64), (2, 1))
    stored.selected_depth_renderer = "Pytorch3DDepthRenderer"
    context = QhStaticContext(
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
    audit = QhAudit("/tmp/rollouts.zarr", "7", "manifest", "Pytorch3DDepthRenderer")

    chain = _tensor_chain(
        stored,
        _snippet(),
        static_context=context,
        selected_observation_protocol="cf_gt",
        audit=audit,
    )
    prefix = chain.actor.selected_observation_prefix
    assert prefix is not None
    assert isinstance(prefix.camera, CameraTW)
    assert prefix.camera.is_linear
    assert prefix.camera.tensor().shape == (2, 2, 22)
    assert prefix.camera.size[1, 0].tolist() == pytest.approx([3.0, 2.0])
    assert prefix.camera.f[1, 0].tolist() == pytest.approx([10.0, 12.0])
    assert prefix.camera.c[1, 0].tolist() == pytest.approx([0.75, 1.25])
    assert torch.allclose(prefix.camera.T_camera_rig[1, 0].tensor(), PoseTW().tensor())
    assert isinstance(prefix.camera_pose_relative_root, PoseTW)
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
    assert batch.audits == (audit,)
    assert batch.audits[0] is audit
    monkeypatch.setattr(torch.Tensor, "pin_memory", lambda value: value)
    assert batch.pin_memory().audits[0] is audit


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
    chain = _tensor_chain(stored, _snippet(), static_context=context, selected_observation_protocol="cf_gt")
    batch = collate_qh_chains([chain, chain])

    def summary(actor: QhActorTensors) -> dict[str, object]:
        static = actor.static_context
        prefix = actor.selected_observation_prefix
        assert static is not None and prefix is not None
        return {
            "candidate_pose_relative_root": summarize(actor.candidate_pose_relative_root.tensor()),
            "history_pose_relative_root": summarize(actor.history_pose_relative_root.tensor()),
            "step_mask": summarize(actor.step_mask),
            "vin_points_world": summarize(actor.vin_snippet.points_world),
            "evl_occ_pr": summarize(static.occ_pr),
            "evl_presence": summarize(static.evl_presence),
            "selected_depth_m": summarize(prefix.depth_m),
            "selected_depth_valid_mask": summarize(prefix.valid_mask),
            "selected_depth_camera": summarize(prefix.camera.tensor()),
            "selected_depth_camera_pose_relative_root": summarize(prefix.camera_pose_relative_root.tensor()),
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
        root_evl_profile="evl_v1",
    )
    with pytest.raises(ValueError, match="requires every EVL evidence field"):
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


@pytest.mark.parametrize("profile", ["qh_cf0_v1", "qh_cfplus_gt_depth_v1"])
def test_named_profiles_use_written_vin_and_rollout_artifacts(
    tmp_path: Path, profile: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    actor_config = _write_test_store(tmp_path / "vin", include_backbone=True)
    actor_reader = VinOfflineStoreReader(actor_config)
    manifest = actor_reader.manifest
    schema = _point_feature_schema(include_obs_count=False)
    manifest.vin.update(
        point_feature_schema=schema,
        point_feature_schema_hash=stable_msgspec_hash(schema),
        include_inv_dist_std=True,
        include_obs_count=False,
        backbone_block_signature=_compact_evl_block_signature(manifest.shards),
    )
    manifest.write(actor_config.manifest_path)
    actor_reader = VinOfflineStoreReader(actor_config)
    actor_record = actor_reader.get_split_records(Stage.VAL)[0]
    rollout = build_rollout_records(horizon=2, num_samples=6, seed=7)[0]
    source = rollout.lineage.source
    source.source_sample_index = actor_record.sample_index
    source.source_sample_key = actor_record.sample_key
    source.scene_id = actor_record.scene_id
    source.snippet_id = actor_record.snippet_id
    source.source_shard_id = actor_record.shard_id
    source.source_shard_row = actor_record.row
    source.split = actor_record.split
    source.source_cache_version = "9"
    source.source_offline_store_manifest_hash = stable_msgspec_hash(actor_reader.manifest)
    split_hash = build_rollout_split_manifest_hash(
        source_manifest_hash=source.source_offline_store_manifest_hash,
        split=source.split,
        records=[
            {
                "order": 0,
                "sample_index": actor_record.sample_index,
                "sample_key": actor_record.sample_key,
                "scene_id": actor_record.scene_id,
                "snippet_id": actor_record.snippet_id,
                "split": actor_record.split,
                "source_shard_id": actor_record.shard_id,
                "source_shard_row": actor_record.row,
            }
        ],
    )
    source.split_manifest_hash = split_hash
    rollout_store = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr",
        [rollout],
        source_offline_store_version="9",
        split_manifest_hash=split_hash,
        selected_depth_enabled=True,
    ).store_dir
    rich = profile == "qh_cfplus_gt_depth_v1"
    reader = QhRolloutReader((rollout_store,), include_selected_depth=rich)
    dataset = QhDataset(
        rollout_reader=reader,
        actor_reader=actor_reader,
        root_evl_profile="evl_v1",
        selected_observation_protocol="cf_gt" if rich else "none",
        experiment_profile=profile,
        include_audit=True,
    )
    data = QhDataModule(train=dataset, seed=7, experiment_profile=profile)
    batch = next(iter(data.train_dataloader()))
    monkeypatch.setattr(torch.Tensor, "pin_memory", lambda value: value)
    batch = batch.pin_memory().to("cpu")
    assert batch.audits[0] is not None
    for field in ("one_step_target_rri", "candidate_reward", "selected_index", "discount", "terminal", "label_mask"):
        assert hasattr(batch.supervision, field)
        assert not hasattr(batch.actor, field)
    assert batch.audits[0] is not None
    assert not hasattr(batch.actor, "audit")
    config = QhLightningModuleConfig(
        root_evl_profile="evl_v1",
        selected_observation_protocol="cf_gt" if rich else "none",
        experiment_profile=profile,
        privileged=rich,
        actor_state_contract_hash=data.actor_state_contract_hash,
        geometry_contract_hash=data.geometry_contract_hash,
        lr_scheduler=None,
    )
    module = QhLightningModule(config, scorer=torch.nn.Identity())
    module._validate_datamodule_contract(data)
