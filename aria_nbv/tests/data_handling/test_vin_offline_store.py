"""Focused round-trip tests for the immutable VIN offline dataset."""

from __future__ import annotations

import json
import pickle
import subprocess
import sys
import tarfile
from dataclasses import asdict
from io import BytesIO
from pathlib import Path
from types import MethodType, SimpleNamespace

import msgspec
import numpy as np
import pytest
import torch

import aria_nbv.data_handling.vin_store.diagnostics as offline_diagnostics
from aria_nbv.data_handling import (
    EfmSnippetView,
    VinOfflineDatasetConfig,
    VinOfflineStoreConfig,
    VinOracleBatch,
    VinSnippetView,
)
from aria_nbv.data_handling.vin_store.diagnostics import (
    collect_vin_offline_dataset_coverage,
    collect_vin_offline_dataset_stats,
    summarize_vin_batch_shapes,
)
from aria_nbv.data_handling.vin_store.format import (
    VinOfflineBlockSpec,
    VinOfflineIndexRecord,
    VinOfflineManifest,
    VinOfflineMaterializedBlocks,
)
from aria_nbv.data_handling.vin_store.source import VinOfflineSourceConfig
from aria_nbv.data_handling.vin_store.store import OFFLINE_DATASET_VERSION, VinOfflineStoreReader
from aria_nbv.data_handling.vin_store.writer import (
    assign_offline_splits,
    flush_prepared_samples_to_shard,
    prepare_vin_offline_sample,
)
from aria_nbv.lightning.aria_nbv_experiment import AriaNBVExperimentConfig
from aria_nbv.lightning.lit_datamodule import VinDataModuleConfig
from aria_nbv.oracle.pipelines.offline_vin import VinOfflineWriter
from aria_nbv.pose_generation.types import CandidateSamplingResult
from aria_nbv.rendering.candidate_depth_renderer import CandidateDepths
from aria_nbv.rri_metrics.rri import RriResult
from aria_nbv.utils import Console, Stage
from aria_nbv.vin.types import EvlBackboneOutput

PoseTW = pytest.importorskip("efm3d.aria.pose").PoseTW
CameraTW = pytest.importorskip("efm3d.aria.camera").CameraTW
ObbTW = pytest.importorskip("efm3d.aria.obb").ObbTW
aria_constants = pytest.importorskip("efm3d.aria.aria_constants")
ARIA_OBB_PADDED = aria_constants.ARIA_OBB_PADDED
ARIA_OBB_SEM_ID_TO_NAME = aria_constants.ARIA_OBB_SEM_ID_TO_NAME
ARIA_POSE_TIME_NS = aria_constants.ARIA_POSE_TIME_NS
ARIA_POSE_T_WORLD_RIG = aria_constants.ARIA_POSE_T_WORLD_RIG
PerspectiveCameras = pytest.importorskip(
    "pytorch3d.renderer.cameras",
).PerspectiveCameras


def _write_sample_index(path: Path, records: list[VinOfflineIndexRecord]) -> None:
    """Write a small sample index without importing internal helpers."""

    payload = "\n".join(json.dumps(asdict(record), sort_keys=True) for record in records)
    if payload:
        payload += "\n"
    path.write_text(payload, encoding="utf-8")


def _read_sample_index_rows(path: Path) -> list[dict[str, object]]:
    """Read the sample index into plain dictionaries for assertions."""

    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _read_indexed_record(shard_dir: Path, block: VinOfflineBlockSpec, *, row: int = 0) -> object:
    """Read one indexed msgpack record from a shard-local block."""

    payload_path, offsets_path = block.paths
    offsets = np.load(shard_dir / offsets_path, allow_pickle=False)
    payload_bytes = (shard_dir / payload_path).read_bytes()
    return msgspec.msgpack.decode(payload_bytes[int(offsets[row]) : int(offsets[row + 1])])


def _make_pose_batch(num: int, *, offset: float = 0.0) -> PoseTW:
    rotation = torch.eye(3, dtype=torch.float32).expand(num, 3, 3).clone()
    translation = torch.zeros((num, 3), dtype=torch.float32)
    translation[:, 0] = offset
    translation[:, 1] = torch.arange(num, dtype=torch.float32)
    return PoseTW.from_Rt(rotation, translation)


def _make_stub_depths(num_candidates: int, *, offset: float = 0.0) -> CandidateDepths:
    depths = torch.full((num_candidates, 4, 4), 1.0 + offset, dtype=torch.float32)
    depths_valid = torch.ones_like(depths, dtype=torch.bool)
    poses = _make_pose_batch(num_candidates, offset=offset)
    ref_pose = _make_pose_batch(1, offset=offset).squeeze(0)
    rotation = torch.eye(3, dtype=torch.float32).expand(num_candidates, 3, 3).clone()
    translation = torch.zeros((num_candidates, 3), dtype=torch.float32)
    focal = torch.full((num_candidates, 2), 50.0, dtype=torch.float32)
    principal = torch.full((num_candidates, 2), 2.0, dtype=torch.float32)
    image_size = torch.full((num_candidates, 2), 4.0, dtype=torch.float32)
    p3d = PerspectiveCameras(
        R=rotation,
        T=translation,
        focal_length=focal,
        principal_point=principal,
        image_size=image_size,
        in_ndc=False,
    )
    return CandidateDepths(
        depths=depths,
        depths_valid_mask=depths_valid,
        poses=poses,
        reference_pose=ref_pose,
        candidate_indices=torch.arange(num_candidates, dtype=torch.long),
        camera=None,
        p3d_cameras=p3d,
    )


def _make_camera_views_for_world_poses(poses_world_cam: PoseTW) -> CameraTW:
    """Build candidate camera views whose extrinsics align with world poses."""

    num = int(poses_world_cam.tensor().shape[0])
    return CameraTW.from_surreal(
        width=torch.full((num,), 4.0, dtype=torch.float32),
        height=torch.full((num,), 4.0, dtype=torch.float32),
        type_str="Pinhole",
        params=torch.tensor([[50.0, 50.0, 2.0, 2.0]], dtype=torch.float32).repeat(num, 1),
        gain=torch.zeros(num, dtype=torch.float32),
        exposure_s=torch.zeros(num, dtype=torch.float32),
        valid_radius=torch.full((num,), 4.0, dtype=torch.float32),
        T_camera_rig=poses_world_cam.inverse(),
    )


def _make_ordered_candidates_and_depths() -> tuple[CandidateSamplingResult, CandidateDepths]:
    """Build a full-shell fixture where valid candidates are shell rows 1 and 3."""

    reference = PoseTW(_make_pose_batch(1).tensor().squeeze(0))
    selected_poses = _make_pose_batch(2, offset=30.0)
    shell_data = _make_pose_batch(4, offset=100.0).tensor().clone()
    shell_data[1] = selected_poses.tensor()[0]
    shell_data[3] = selected_poses.tensor()[1]
    candidates = CandidateSamplingResult(
        views=_make_camera_views_for_world_poses(selected_poses),
        reference_pose=reference,
        mask_valid=torch.tensor([False, True, False, True], dtype=torch.bool),
        masks={},
        shell_poses=PoseTW(shell_data),
    )
    base_depths = _make_stub_depths(2)
    depths = CandidateDepths(
        depths=base_depths.depths,
        depths_valid_mask=base_depths.depths_valid_mask,
        poses=selected_poses,
        reference_pose=reference,
        candidate_indices=torch.tensor([1, 3], dtype=torch.long),
        camera=base_depths.camera,
        p3d_cameras=base_depths.p3d_cameras,
    )
    return candidates, depths


def _make_stub_rri(num_candidates: int) -> RriResult:
    values = torch.linspace(0.1, 0.1 * num_candidates, num_candidates, dtype=torch.float32)
    return RriResult(
        rri=values,
        pm_dist_before=torch.full((num_candidates,), 0.5, dtype=torch.float32),
        pm_dist_after=torch.full((num_candidates,), 0.4, dtype=torch.float32),
        pm_acc_before=torch.full((num_candidates,), 0.3, dtype=torch.float32),
        pm_comp_before=torch.full((num_candidates,), 0.2, dtype=torch.float32),
        pm_acc_after=torch.full((num_candidates,), 0.25, dtype=torch.float32),
        pm_comp_after=torch.full((num_candidates,), 0.15, dtype=torch.float32),
    )


def _make_vin_snippet(*, offset: float = 0.0) -> VinSnippetView:
    points_world = torch.tensor(
        [
            [offset + 0.0, 0.0, 0.0, 0.1],
            [offset + 1.0, 0.0, 0.0, 0.2],
            [float("nan"), float("nan"), float("nan"), float("nan")],
            [float("nan"), float("nan"), float("nan"), float("nan")],
        ],
        dtype=torch.float32,
    )
    lengths = torch.tensor([2], dtype=torch.int64)
    return VinSnippetView(
        points_world=points_world,
        lengths=lengths,
        t_world_rig=_make_pose_batch(2, offset=offset),
        t_world_snippet=_make_pose_batch(1, offset=offset),
    )


def test_vin_snippet_view_preserves_compact_and_documented_repr() -> None:
    """Keep the moved VIN DTO's established representation modes."""

    snippet = _make_vin_snippet()

    assert "'doc'" not in repr(snippet)  # noqa: S101
    documented = snippet.repr_with_docstrings()
    assert "'doc'" in documented  # noqa: S101
    assert "valid point-prefix length" in documented  # noqa: S101


def _make_obb_tensor(num: int = 2, *, offset: float = 0.0) -> ObbTW:
    """Build a compact, valid ObbTW payload."""

    bb3 = torch.tensor([[-0.5, 0.5, -0.25, 0.25, -0.1, 0.9]], dtype=torch.float32).repeat(num, 1)
    bb2 = torch.full((num, 4), -1.0, dtype=torch.float32)
    pose = _make_pose_batch(num, offset=offset)
    sem_id = torch.arange(num, dtype=torch.float32).reshape(num, 1)
    inst_id = torch.arange(num, dtype=torch.float32).reshape(num, 1) + 10.0
    prob = torch.full((num, 1), 0.9, dtype=torch.float32)
    moveable = torch.zeros((num, 1), dtype=torch.float32)
    return ObbTW.from_lmc(
        bb3_object=bb3,
        bb2_rgb=bb2,
        bb2_slaml=bb2,
        bb2_slamr=bb2,
        T_world_object=pose,
        sem_id=sem_id,
        inst_id=inst_id,
        prob=prob,
        moveable=moveable,
    )


def _make_source_sample(*, offset: float = 0.0) -> EfmSnippetView:
    """Build a minimal EFM snippet carrying compact GT modalities."""

    efm = {
        ARIA_POSE_T_WORLD_RIG: _make_pose_batch(2, offset=offset),
        ARIA_POSE_TIME_NS: torch.tensor([100, 200], dtype=torch.int64),
        "pose/gravity_in_world": torch.tensor([0.0, 0.0, -9.81], dtype=torch.float32),
        ARIA_OBB_PADDED: ObbTW(_make_obb_tensor(2, offset=offset).tensor().unsqueeze(0).repeat(2, 1, 1)),
        ARIA_OBB_SEM_ID_TO_NAME: {0: "chair", 1: "table", 28: "window"},
    }
    return EfmSnippetView(
        efm=efm,
        scene_id="scene-a",
        snippet_id="snippet-000",
        mesh=None,
        crop_bounds=(
            torch.tensor([-1.0, -1.0, -1.0], dtype=torch.float32),
            torch.tensor([1.0, 1.0, 1.0], dtype=torch.float32),
        ),
        mesh_verts=torch.tensor(
            [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
            dtype=torch.float32,
        )
        + offset,
        mesh_faces=torch.tensor([[0, 1, 2]], dtype=torch.int64),
    )


def _make_stub_backbone() -> EvlBackboneOutput:
    """Build a small EVL backbone payload with both head and internal fields."""

    t_world_voxel = _make_pose_batch(1, offset=0.0)
    voxel_extent = torch.tensor([-1.0, 1.0, -1.0, 1.0, -1.0, 1.0], dtype=torch.float32)
    scalar_grid = torch.ones((1, 1, 2, 2, 2), dtype=torch.float32)
    return EvlBackboneOutput(
        t_world_voxel=t_world_voxel,
        voxel_extent=voxel_extent,
        voxel_feat=torch.full((1, 4, 2, 2, 2), 2.0, dtype=torch.float32),
        occ_feat=torch.full((1, 4, 2, 2, 2), 3.0, dtype=torch.float32),
        obb_feat=torch.full((1, 4, 2, 2, 2), 4.0, dtype=torch.float32),
        occ_pr=scalar_grid,
        occ_input=scalar_grid * 2.0,
        free_input=scalar_grid * 3.0,
        counts=torch.ones((1, 2, 2, 2), dtype=torch.int64),
        counts_m=torch.ones((1, 2, 2, 2), dtype=torch.int64) * 2,
        voxel_select_t=torch.zeros((1, 1), dtype=torch.int64),
        cent_pr=scalar_grid * 4.0,
        bbox_pr=torch.ones((1, 7, 2, 2, 2), dtype=torch.float32),
        clas_pr=torch.ones((1, 3, 2, 2, 2), dtype=torch.float32),
        cent_pr_nms=scalar_grid * 5.0,
        obb_pred_viz=ObbTW(_make_obb_tensor(2, offset=0.25).tensor().unsqueeze(0)),
        obb_pred_sem_id_to_name={0: "chair", 1: "table", 2: "lamp"},
        obb_pred_probs_full_viz=[torch.full((3,), 1.0 / 3.0, dtype=torch.float32) for _ in range(2)],
        pts_world=torch.zeros((1, 8, 3), dtype=torch.float32),
        feat2d_upsampled={"rgb": torch.ones((1, 1, 2, 2, 2), dtype=torch.float32)},
        token2d={"rgb": torch.ones((1, 1, 2, 2, 2), dtype=torch.float32)},
    )


class _DumpConfig:
    """Tiny config double exposing the writer's manifest dump method."""

    def model_dump_cache(self, *, exclude_none: bool = False) -> dict[str, object]:  # noqa: ARG002
        """Return an empty stable config payload."""

        return {}


def test_prepare_vin_offline_sample_filters_backbone_blocks_and_payload() -> None:
    """Writer keep-lists should prune numeric blocks and rich backbone payloads."""

    row = prepare_vin_offline_sample(
        scene_id="scene-a",
        snippet_id="snippet-000",
        vin_snippet=_make_vin_snippet(offset=0.0),
        candidates=None,
        depths=_make_stub_depths(2, offset=0.0),
        rri=_make_stub_rri(2),
        candidate_pcs=None,
        backbone_out=_make_stub_backbone(),
        max_candidates=4,
        include_depths=True,
        include_candidate_pcs=False,
        include_backbone=True,
        include_diagnostic_payloads=True,
        backbone_numeric_keep_fields={"t_world_voxel", "voxel_extent", "occ_pr", "counts"},
        backbone_payload_keep_fields={"t_world_voxel", "voxel_extent", "occ_pr", "bbox_pr"},
        sample_key="sample-0",
    )

    assert "backbone.t_world_voxel" in row.numeric_blocks  # noqa: S101
    assert "backbone.voxel_extent" in row.numeric_blocks  # noqa: S101
    assert "backbone.occ_pr" in row.numeric_blocks  # noqa: S101
    assert "backbone.counts" in row.numeric_blocks  # noqa: S101
    assert "backbone.occ_input" not in row.numeric_blocks  # noqa: S101
    assert "backbone.cent_pr" not in row.numeric_blocks  # noqa: S101
    payload = row.record_blocks["backbone.payload"]
    assert set(payload) == {"t_world_voxel", "voxel_extent", "occ_pr", "bbox_pr"}  # noqa: S101
    assert "voxel_feat" not in payload  # noqa: S101
    assert "feat2d_upsampled" not in payload  # noqa: S101


def test_prepare_vin_offline_sample_uses_compact_ase_atek_default_key() -> None:
    row = prepare_vin_offline_sample(
        scene_id="81286",
        snippet_id="AriaSyntheticEnvironment_81286_AtekDataSample_000000",
        vin_snippet=_make_vin_snippet(offset=0.0),
        candidates=None,
        depths=_make_stub_depths(2, offset=0.0),
        rri=_make_stub_rri(2),
        candidate_pcs=None,
        backbone_out=None,
        max_candidates=4,
        include_depths=True,
        include_candidate_pcs=False,
        include_backbone=False,
        include_diagnostic_payloads=False,
    )

    assert row.sample_key == "ASE_81286_Atek_000000"  # noqa: S101
    assert row.snippet_id == "ASE_81286_Atek_000000"  # noqa: S101


def test_prepare_vin_offline_sample_preserves_candidate_label_order_in_payloads(tmp_path: Path) -> None:
    """Numeric blocks and rich payloads should share one candidate ordering."""

    candidates, depths = _make_ordered_candidates_and_depths()
    row = prepare_vin_offline_sample(
        scene_id="scene-a",
        snippet_id="snippet-000",
        vin_snippet=_make_vin_snippet(offset=0.0),
        candidates=candidates,
        depths=depths,
        rri=_make_stub_rri(2),
        candidate_pcs=None,
        backbone_out=None,
        max_candidates=4,
        include_depths=True,
        include_candidate_pcs=False,
        include_backbone=False,
        include_diagnostic_payloads=True,
        sample_key="sample-0",
    )

    assert row.numeric_blocks["oracle.candidate_indices"].tolist() == [1, 3, -1, -1]  # noqa: S101
    assert row.numeric_blocks["oracle.rri"][:2].tolist() == pytest.approx([0.1, 0.2])  # noqa: S101
    assert np.isnan(row.numeric_blocks["oracle.rri"][2:]).all()  # noqa: S101
    assert np.allclose(  # noqa: S101
        row.numeric_blocks["oracle.candidate_poses_world_cam"][:2],
        depths.poses.tensor().numpy(),
    )

    shard_dir = tmp_path / "shard-000000"
    shard_spec, _ = flush_prepared_samples_to_shard(
        shard_index=0,
        shard_dir=shard_dir,
        rows=[row],
    )
    decoded_depths = CandidateDepths.from_serializable(
        _read_indexed_record(shard_dir, shard_spec.blocks["oracle.depths_payload"]),
        device=torch.device("cpu"),
    )
    decoded_candidates = CandidateSamplingResult.from_serializable(
        _read_indexed_record(shard_dir, shard_spec.blocks["oracle.candidates"]),
        device=torch.device("cpu"),
    )

    assert decoded_depths.candidate_indices.tolist() == [1, 3]  # noqa: S101
    assert decoded_candidates.candidate_shell_indices().tolist() == [1, 3]  # noqa: S101
    assert torch.allclose(decoded_depths.poses.tensor(), decoded_candidates.poses_world_cam().tensor())  # noqa: S101


def test_prepare_vin_offline_sample_rejects_candidate_index_drift() -> None:
    """Writer should reject candidates and labels that no longer share order."""

    candidates, depths = _make_ordered_candidates_and_depths()
    depths.candidate_indices = torch.tensor([0, 1], dtype=torch.long)

    with pytest.raises(ValueError, match="candidate_indices"):
        prepare_vin_offline_sample(
            scene_id="scene-a",
            snippet_id="snippet-000",
            vin_snippet=_make_vin_snippet(offset=0.0),
            candidates=candidates,
            depths=depths,
            rri=_make_stub_rri(2),
            candidate_pcs=None,
            backbone_out=None,
            max_candidates=4,
            include_depths=True,
            include_candidate_pcs=False,
            include_backbone=False,
            include_diagnostic_payloads=True,
            sample_key="sample-0",
        )


def test_prepare_vin_offline_sample_rejects_label_length_drift() -> None:
    """Oracle RRI vectors must have the same length as rendered candidates."""

    candidates, depths = _make_ordered_candidates_and_depths()

    with pytest.raises(ValueError, match="oracle.rri length 1"):
        prepare_vin_offline_sample(
            scene_id="scene-a",
            snippet_id="snippet-000",
            vin_snippet=_make_vin_snippet(offset=0.0),
            candidates=candidates,
            depths=depths,
            rri=_make_stub_rri(1),
            candidate_pcs=None,
            backbone_out=None,
            max_candidates=4,
            include_depths=True,
            include_candidate_pcs=False,
            include_backbone=False,
            include_diagnostic_payloads=True,
            sample_key="sample-0",
        )


def test_flush_vin_offline_payloads_normalizes_numpy_scalars(tmp_path: Path) -> None:
    """Diagnostic payloads from EVL may include NumPy scalar metadata."""

    backbone = _make_stub_backbone()
    backbone.obb_pred_sem_id_to_name = [np.str_("chair"), np.str_("table")]
    row = prepare_vin_offline_sample(
        scene_id="scene-a",
        snippet_id="snippet-000",
        vin_snippet=_make_vin_snippet(offset=0.0),
        candidates=None,
        depths=_make_stub_depths(2, offset=0.0),
        rri=_make_stub_rri(2),
        candidate_pcs=None,
        backbone_out=backbone,
        max_candidates=4,
        include_depths=True,
        include_candidate_pcs=False,
        include_backbone=True,
        include_diagnostic_payloads=True,
        backbone_numeric_keep_fields={"t_world_voxel", "voxel_extent", "occ_pr", "counts"},
        backbone_payload_keep_fields={"obb_pred_sem_id_to_name"},
        sample_key="sample-0",
    )

    shard_spec, _ = flush_prepared_samples_to_shard(
        shard_index=0,
        shard_dir=tmp_path / "shard-000000",
        rows=[row],
    )

    block = shard_spec.blocks["backbone.payload"]
    payload_path, offsets_path = block.paths
    offsets = np.load(tmp_path / "shard-000000" / offsets_path, allow_pickle=False)
    payload_bytes = (tmp_path / "shard-000000" / payload_path).read_bytes()
    payload = msgspec.msgpack.decode(payload_bytes[int(offsets[0]) : int(offsets[1])])
    assert payload["obb_pred_sem_id_to_name"] == {0: "chair", 1: "table"}  # noqa: S101
    assert all(isinstance(name, str) for name in payload["obb_pred_sem_id_to_name"].values())  # noqa: S101


def test_vin_offline_writer_finalizes_prepared_rows_on_keyboard_interrupt(tmp_path: Path) -> None:
    """Ctrl-C should produce a valid partial store for already prepared rows."""

    store_cfg = VinOfflineStoreConfig(store_dir=tmp_path / "vin_offline")
    config = SimpleNamespace(
        store=store_cfg,
        dataset=_DumpConfig(),
        labeler=_DumpConfig(),
        backbone=None,
        include_backbone=False,
        include_depths=True,
        include_pointclouds=False,
        include_diagnostic_payloads=False,
        include_gt_obbs=False,
        include_detected_obbs=False,
        include_trajectory_metadata=False,
        backbone_numeric_keep_fields=None,
        backbone_payload_keep_fields=None,
        vin_pad_points=4,
        semidense_max_points=None,
        semidense_include_obs_count=False,
        max_candidates=4,
        samples_per_shard=16,
        max_samples=None,
        train_val_split=0.5,
        overwrite=False,
        num_failures_allowed=0,
    )
    writer = VinOfflineWriter.__new__(VinOfflineWriter)
    writer.config = config
    writer.console = Console.with_prefix("test-vin-offline-writer")
    writer._dataset = [
        SimpleNamespace(scene_id="scene-a", snippet_id="snippet-000"),
        SimpleNamespace(scene_id="scene-b", snippet_id="snippet-001"),
        SimpleNamespace(scene_id="scene-c", snippet_id="snippet-002"),
    ]

    class _InterruptingLabeler:
        def __init__(self) -> None:
            self.count = 0

        def run(self, sample: object) -> object:  # noqa: ARG002
            self.count += 1
            if self.count == 3:
                raise KeyboardInterrupt
            return SimpleNamespace()

    writer._labeler = _InterruptingLabeler()
    writer._backbone = None

    def _prepare_stub_row(
        self: VinOfflineWriter,  # noqa: ARG001
        *,
        sample: object,
        label_batch: object,  # noqa: ARG001
        backbone_out: object,  # noqa: ARG001
        max_candidates: int,
    ) -> object:
        offset = 0.0 if sample.snippet_id.endswith("000") else 10.0
        return prepare_vin_offline_sample(
            scene_id=sample.scene_id,
            snippet_id=sample.snippet_id,
            vin_snippet=_make_vin_snippet(offset=offset),
            candidates=None,
            depths=_make_stub_depths(2, offset=offset),
            rri=_make_stub_rri(2),
            candidate_pcs=None,
            backbone_out=None,
            max_candidates=max_candidates,
            include_depths=True,
            include_candidate_pcs=False,
            include_backbone=False,
            include_diagnostic_payloads=False,
        )

    writer._prepare_row = MethodType(_prepare_stub_row, writer)

    manifest = writer.run()

    assert store_cfg.manifest_path.exists()  # noqa: S101
    assert store_cfg.sample_index_path.exists()  # noqa: S101
    assert not (tmp_path / "vin_offline.tmp").exists()  # noqa: S101
    assert manifest.stats["num_samples"] == 2  # noqa: S101
    assert manifest.stats["interrupted"] is True  # noqa: S101
    assert manifest.provenance["finalized_after_interrupt"] is True  # noqa: S101
    assert len(_read_sample_index_rows(store_cfg.sample_index_path)) == 2  # noqa: S101


def _write_test_store(
    tmp_path: Path,
    *,
    include_diagnostic_payloads: bool = False,
    include_backbone: bool = False,
    dataset_config: dict[str, object] | None = None,
) -> VinOfflineStoreConfig:
    """Create a small immutable VIN offline store for reader tests."""

    store_cfg = VinOfflineStoreConfig(store_dir=tmp_path / "vin_offline")
    store_cfg.store_dir.mkdir(parents=True, exist_ok=True)
    store_cfg.shards_dir.mkdir(parents=True, exist_ok=True)

    prepared_rows = [
        prepare_vin_offline_sample(
            scene_id="scene-a",
            snippet_id="snippet-000",
            vin_snippet=_make_vin_snippet(offset=0.0),
            candidates=None,
            depths=_make_stub_depths(2, offset=0.0),
            rri=_make_stub_rri(2),
            candidate_pcs=None,
            backbone_out=_make_stub_backbone() if include_backbone else None,
            max_candidates=4,
            source_sample=_make_source_sample(offset=0.0),
            include_depths=True,
            include_candidate_pcs=False,
            include_backbone=include_backbone,
            include_diagnostic_payloads=include_diagnostic_payloads,
            sample_key="sample-0",
        ),
        prepare_vin_offline_sample(
            scene_id="scene-b",
            snippet_id="snippet-001",
            vin_snippet=_make_vin_snippet(offset=10.0),
            candidates=None,
            depths=_make_stub_depths(3, offset=10.0),
            rri=_make_stub_rri(3),
            candidate_pcs=None,
            backbone_out=_make_stub_backbone() if include_backbone else None,
            max_candidates=4,
            source_sample=_make_source_sample(offset=10.0),
            include_depths=True,
            include_candidate_pcs=False,
            include_backbone=include_backbone,
            include_diagnostic_payloads=include_diagnostic_payloads,
            sample_key="sample-1",
        ),
        prepare_vin_offline_sample(
            scene_id="scene-c",
            snippet_id="snippet-002",
            vin_snippet=_make_vin_snippet(offset=20.0),
            candidates=None,
            depths=_make_stub_depths(2, offset=20.0),
            rri=_make_stub_rri(2),
            candidate_pcs=None,
            backbone_out=_make_stub_backbone() if include_backbone else None,
            max_candidates=4,
            source_sample=_make_source_sample(offset=20.0),
            include_depths=True,
            include_candidate_pcs=False,
            include_backbone=include_backbone,
            include_diagnostic_payloads=include_diagnostic_payloads,
            sample_key="sample-2",
        ),
    ]

    shard_dir = store_cfg.shards_dir / "shard-000000"
    shard_spec, local_records = flush_prepared_samples_to_shard(
        shard_index=0,
        shard_dir=shard_dir,
        rows=prepared_rows,
    )
    index_records = [
        VinOfflineIndexRecord(
            sample_index=0,
            sample_key=local_records[0].sample_key,
            scene_id=local_records[0].scene_id,
            snippet_id=local_records[0].snippet_id,
            split="train",
            shard_id=local_records[0].shard_id,
            row=local_records[0].row,
        ),
        VinOfflineIndexRecord(
            sample_index=1,
            sample_key=local_records[1].sample_key,
            scene_id=local_records[1].scene_id,
            snippet_id=local_records[1].snippet_id,
            split="train",
            shard_id=local_records[1].shard_id,
            row=local_records[1].row,
        ),
        VinOfflineIndexRecord(
            sample_index=2,
            sample_key=local_records[2].sample_key,
            scene_id=local_records[2].scene_id,
            snippet_id=local_records[2].snippet_id,
            split="val",
            shard_id=local_records[2].shard_id,
            row=local_records[2].row,
        ),
    ]
    manifest = VinOfflineManifest(
        version=OFFLINE_DATASET_VERSION,
        created_at="2026-03-29T00:00:00Z",
        source={"dataset_config": dataset_config or {}},
        oracle={"max_candidates": 4},
        vin={"pad_points": 4},
        materialized_blocks=VinOfflineMaterializedBlocks(
            backbone=include_backbone,
            depths=True,
            candidate_pcs=False,
            gt_obbs=True,
            detected_obbs=include_backbone,
            trajectory=True,
        ),
        stats={"num_samples": 3},
        provenance={},
        shards=[shard_spec],
    )
    manifest.write(store_cfg.manifest_path)
    _write_sample_index(store_cfg.sample_index_path, index_records)
    store_cfg.splits_dir.mkdir(parents=True, exist_ok=True)
    np.save(
        store_cfg.split_path("all"),
        torch.tensor([0, 1, 2], dtype=torch.long).numpy(),
        allow_pickle=False,
    )
    np.save(
        store_cfg.split_path("train"),
        torch.tensor([0, 1], dtype=torch.long).numpy(),
        allow_pickle=False,
    )
    np.save(
        store_cfg.split_path("val"),
        torch.tensor([2], dtype=torch.long).numpy(),
        allow_pickle=False,
    )
    return store_cfg


def _supports_worker_tensor_sharing() -> bool:
    """Return whether this host can move worker tensors back to the parent."""

    script = """
import torch
from torch.utils.data import DataLoader, Dataset

class _Dataset(Dataset):
    def __len__(self):
        return 1

    def __getitem__(self, index):
        return torch.tensor([index], dtype=torch.float32)

torch.multiprocessing.set_sharing_strategy("file_system")
loader = DataLoader(_Dataset(), batch_size=1, num_workers=1, persistent_workers=True)
batch = next(iter(loader))
assert batch.shape == (1, 1)
"""
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", script],  # noqa: S607
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )
    return result.returncode == 0


def _make_split_record(sample_key: str, row: int) -> VinOfflineIndexRecord:
    """Build one lightweight index record for split-assignment tests."""

    return VinOfflineIndexRecord(
        sample_index=-1,
        sample_key=sample_key,
        scene_id=f"scene-{sample_key}",
        snippet_id=f"snippet-{sample_key}",
        split="all",
        shard_id="shard-000000",
        row=row,
    )


def test_assign_splits_is_stable_by_sample_key() -> None:
    """Split membership should be stable across input order permutations."""

    records_a = [
        _make_split_record("alpha", 0),
        _make_split_record("beta", 1),
        _make_split_record("gamma", 2),
        _make_split_record("delta", 3),
        _make_split_record("epsilon", 4),
    ]
    records_b = [
        _make_split_record("gamma", 0),
        _make_split_record("alpha", 1),
        _make_split_record("epsilon", 2),
        _make_split_record("delta", 3),
        _make_split_record("beta", 4),
    ]

    splits_a = assign_offline_splits(records=records_a, val_fraction=0.4)
    splits_b = assign_offline_splits(records=records_b, val_fraction=0.4)

    val_keys_a = {records_a[int(idx)].sample_key for idx in splits_a["val"]}
    val_keys_b = {records_b[int(idx)].sample_key for idx in splits_b["val"]}
    train_keys_a = {records_a[int(idx)].sample_key for idx in splits_a["train"]}
    train_keys_b = {records_b[int(idx)].sample_key for idx in splits_b["train"]}

    assert val_keys_a == val_keys_b  # noqa: S101
    assert train_keys_a == train_keys_b  # noqa: S101

    val_idx_a = {int(idx) for idx in splits_a["val"]}
    train_idx_a = {int(idx) for idx in splits_a["train"]}
    assert [records_a[int(idx)].sample_key for idx in splits_a["val"]] == [  # noqa: S101
        record.sample_key for idx, record in enumerate(records_a) if idx in val_idx_a
    ]
    assert [records_a[int(idx)].sample_key for idx in splits_a["train"]] == [  # noqa: S101
        record.sample_key for idx, record in enumerate(records_a) if idx in train_idx_a
    ]


def test_collect_vin_offline_dataset_stats_summarizes_store(tmp_path: Path) -> None:
    """Immutable offline diagnostics should summarize coverage and tensor stats."""

    store_cfg = _write_test_store(tmp_path)

    stats = collect_vin_offline_dataset_stats(store_cfg, max_samples=2)

    assert stats.num_samples == 3  # noqa: S101
    assert stats.sampled_samples == 2  # noqa: S101
    assert stats.split_counts == {"train": 2, "val": 1}  # noqa: S101
    assert stats.num_scenes == 3  # noqa: S101
    assert stats.candidate_count.count == 2  # noqa: S101
    assert stats.rri.count == 5  # noqa: S101
    assert stats.vin_points.mean == 2.0  # noqa: S101
    assert stats.numeric_bytes > 0  # noqa: S101
    assert stats.candidate_count_values == [2.0, 3.0]  # noqa: S101
    assert len(stats.rri_values) == 5  # noqa: S101
    assert len(stats.vin_point_values) == 2  # noqa: S101


def test_collect_vin_offline_dataset_stats_reports_blocks_and_sample_rows(tmp_path: Path) -> None:
    """Offline diagnostics should expose render-ready block and row summaries."""

    store_cfg = _write_test_store(tmp_path)

    stats = collect_vin_offline_dataset_stats(store_cfg, max_samples=1)

    block_by_name = {block.name: block for block in stats.block_diagnostics}
    assert "oracle.rri" in block_by_name  # noqa: S101
    rri_block = block_by_name["oracle.rri"]
    assert rri_block.kind == "zarr_array"  # noqa: S101
    assert rri_block.dtype == "float32"  # noqa: S101
    assert rri_block.shape == [3, 4]  # noqa: S101
    assert rri_block.estimated_bytes == 3 * 4 * np.dtype("float32").itemsize  # noqa: S101

    assert len(stats.sample_summaries) == 1  # noqa: S101
    row = stats.sample_summaries[0]
    assert row.scene_id == "scene-a"  # noqa: S101
    assert row.snippet_id == "snippet-000"  # noqa: S101
    assert row.split == "train"  # noqa: S101
    assert row.candidate_count == 2  # noqa: S101
    assert row.rri.count == 2  # noqa: S101
    assert row.rri.mean == pytest.approx(0.15)  # noqa: S101
    assert row.vin_points.mean == 2.0  # noqa: S101


def test_collect_vin_offline_dataset_stats_reports_thesis_diagnostics(tmp_path: Path) -> None:
    """Immutable diagnostics should expose RRI components, poses, memory, and backbone stats."""

    store_cfg = _write_test_store(tmp_path, include_backbone=True)

    stats = collect_vin_offline_dataset_stats(store_cfg, max_samples=1)

    assert stats.rri_component_summaries["pm_acc_after"].count == 2  # noqa: S101
    assert stats.rri_component_summaries["pm_acc_after"].mean == pytest.approx(0.25)  # noqa: S101
    assert stats.rri_component_values["pm_comp_after"] == pytest.approx([0.15, 0.15])  # noqa: S101

    assert stats.candidate_pose_values["offset_x"] == pytest.approx([0.0, 0.0])  # noqa: S101
    assert stats.candidate_pose_values["offset_y"] == pytest.approx([0.0, 1.0])  # noqa: S101
    assert stats.candidate_pose_summaries["radius_m"].maximum == pytest.approx(1.0)  # noqa: S101
    assert stats.candidate_pose_summaries["rotation_delta_deg"].maximum == pytest.approx(0.0)  # noqa: S101

    memory_by_component = {row.component: row for row in stats.memory_diagnostics}
    assert {"backbone", "oracle_rri", "vin_snippet", "pose_camera", "total"} <= set(memory_by_component)  # noqa: S101
    assert memory_by_component["total"].mean_mib > memory_by_component["oracle_rri"].mean_mib  # noqa: S101

    backbone_by_field = {row.field: row for row in stats.backbone_diagnostics}
    assert backbone_by_field["occ_pr"].shape == [1, 1, 2, 2, 2]  # noqa: S101
    assert backbone_by_field["occ_pr"].mean == pytest.approx(1.0)  # noqa: S101
    assert backbone_by_field["counts"].nz_frac == pytest.approx(1.0)  # noqa: S101


def test_store_reader_decodes_typed_root_evl_evidence_for_qh_context(tmp_path: Path) -> None:
    """The lean store reader should expose persisted actor EVL fields without oracle payloads."""

    store_cfg = _write_test_store(tmp_path, include_backbone=True)
    reader = VinOfflineStoreReader(store_cfg)
    evidence = reader.read_backbone_evidence(reader.sample_index[0])

    assert evidence is not None  # noqa: S101
    assert evidence.t_world_voxel.tensor().shape == (1, 12)  # noqa: S101
    assert evidence.voxel_extent.shape == (6,)  # noqa: S101
    assert evidence.occ_pr is not None and evidence.occ_pr.shape == (1, 1, 2, 2, 2)  # noqa: S101
    assert evidence.occ_input is not None  # noqa: S101
    assert evidence.free_input is not None  # noqa: S101
    assert evidence.counts is not None  # noqa: S101
    assert evidence.cent_pr is not None  # noqa: S101
    assert evidence.pts_world is not None  # noqa: S101


def test_collect_vin_offline_dataset_stats_reports_batch_shape_preview(tmp_path: Path) -> None:
    """Offline stats should preview the lean model-facing VIN batch path."""

    store_cfg = _write_test_store(tmp_path, include_backbone=True)

    stats = collect_vin_offline_dataset_stats(store_cfg, max_samples=1)

    assert stats.batch_shapes["candidate_poses_world_cam"] == "(4, 12)"  # noqa: S101
    assert stats.batch_shapes["rri"] == "(4,)"  # noqa: S101
    assert stats.batch_shapes["vin_snippet.points_world"] == "(4, 4)"  # noqa: S101
    assert stats.batch_shapes["backbone.occ_pr"] == "(1, 1, 2, 2, 2)"  # noqa: S101


def test_summarize_vin_batch_shapes_preserves_exact_unbatched_mapping(tmp_path: Path) -> None:
    """The diagnostics owner should preserve the exact unbatched shape mapping."""

    store_cfg = _write_test_store(tmp_path, include_backbone=True)
    dataset = VinOfflineDatasetConfig(
        store=store_cfg,
        split="all",
        limit=1,
        load_candidates=False,
        load_depths=False,
        load_candidate_pcs=False,
        return_format="vin_batch",
        map_location=torch.device("cpu"),
    ).setup_target()

    assert summarize_vin_batch_shapes(dataset[0]) == {  # noqa: S101
        "candidate_poses_world_cam": "(4, 12)",
        "reference_pose_world_rig": "(12,)",
        "rri": "(4,)",
        "pm_dist_before": "(4,)",
        "pm_dist_after": "(4,)",
        "pm_acc_before": "(4,)",
        "pm_comp_before": "(4,)",
        "pm_acc_after": "(4,)",
        "pm_comp_after": "(4,)",
        "p3d_cameras.R": "(4, 3, 3)",
        "p3d_cameras.T": "(4, 3)",
        "p3d_cameras.focal_length": "(4, 2)",
        "p3d_cameras.principal_point": "(4, 2)",
        "p3d_cameras.image_size": "(4, 2)",
        "candidate_count": "()",
        "p3d_cameras.batch_mode": "flat (B*N)",
        "p3d_cameras.R_grouped": "(1, 4, 3, 3)",
        "p3d_cameras.T_grouped": "(1, 4, 3)",
        "p3d_cameras.focal_length_grouped": "(1, 4, 2)",
        "p3d_cameras.principal_point_grouped": "(1, 4, 2)",
        "p3d_cameras.image_size_grouped": "(1, 4, 2)",
        "vin_snippet.points_world": "(4, 4)",
        "vin_snippet.lengths": "(1,)",
        "vin_snippet.t_world_rig": "(2, 12)",
        "backbone.voxel_extent": "(6,)",
        "backbone.occ_pr": "(1, 1, 2, 2, 2)",
        "backbone.occ_input": "(1, 1, 2, 2, 2)",
        "backbone.free_input": "(1, 1, 2, 2, 2)",
        "backbone.counts": "(1, 2, 2, 2)",
        "backbone.cent_pr": "(1, 1, 2, 2, 2)",
        "backbone.pts_world": "(1, 8, 3)",
        "gt_obbs.obbs": "(2, 2, 34)",
        "detected_obbs.obbs": "(1, 2, 34)",
        "detected_obbs.probs": "(2, 3)",
        "trajectory.time_ns": "(2,)",
        "trajectory.gravity_in_world": "(3,)",
    }


def test_summarize_vin_batch_shapes_preserves_exact_batched_mapping(tmp_path: Path) -> None:
    """The diagnostics owner should preserve the exact collated shape mapping."""

    store_cfg = _write_test_store(tmp_path, include_backbone=True)
    dataset = VinOfflineDatasetConfig(
        store=store_cfg,
        split="all",
        limit=1,
        load_candidates=False,
        load_depths=False,
        load_candidate_pcs=False,
        return_format="vin_batch",
        map_location=torch.device("cpu"),
    ).setup_target()
    batch = VinOracleBatch.collate([dataset[0], dataset[0]])

    assert summarize_vin_batch_shapes(batch) == {  # noqa: S101
        "candidate_poses_world_cam": "(2, 4, 12)",
        "reference_pose_world_rig": "(2, 12)",
        "rri": "(2, 4)",
        "pm_dist_before": "(2, 4)",
        "pm_dist_after": "(2, 4)",
        "pm_acc_before": "(2, 4)",
        "pm_comp_before": "(2, 4)",
        "pm_acc_after": "(2, 4)",
        "pm_comp_after": "(2, 4)",
        "p3d_cameras.R": "(8, 3, 3)",
        "p3d_cameras.T": "(8, 3)",
        "p3d_cameras.focal_length": "(8, 2)",
        "p3d_cameras.principal_point": "(8, 2)",
        "p3d_cameras.image_size": "(8, 2)",
        "candidate_count": "(2,)",
        "p3d_cameras.batch_mode": "flat (B*N)",
        "p3d_cameras.R_grouped": "(2, 4, 3, 3)",
        "p3d_cameras.T_grouped": "(2, 4, 3)",
        "p3d_cameras.focal_length_grouped": "(2, 4, 2)",
        "p3d_cameras.principal_point_grouped": "(2, 4, 2)",
        "p3d_cameras.image_size_grouped": "(2, 4, 2)",
        "vin_snippet.points_world": "(2, 4, 4)",
        "vin_snippet.lengths": "(2,)",
        "vin_snippet.t_world_rig": "(2, 2, 12)",
        "backbone.voxel_extent": "(2, 6)",
        "backbone.occ_pr": "(2, 1, 2, 2, 2)",
        "backbone.occ_input": "(2, 1, 2, 2, 2)",
        "backbone.free_input": "(2, 1, 2, 2, 2)",
        "backbone.counts": "(2, 2, 2, 2)",
        "backbone.cent_pr": "(2, 1, 2, 2, 2)",
        "backbone.pts_world": "(2, 8, 3)",
        "gt_obbs.obbs": "(2, 2, 2, 34)",
        "detected_obbs.obbs": "(2, 2, 34)",
        "detected_obbs.probs": "(2, 2, 3)",
        "trajectory.time_ns": "(2, 2)",
        "trajectory.gravity_in_world": "(2, 3)",
    }


def test_batch_shape_preview_delegates_to_diagnostics_owner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Store previews should call the module-level diagnostic summarizer."""

    store_cfg = _write_test_store(tmp_path)
    observed: list[VinOracleBatch] = []

    def _summarize(batch: VinOracleBatch) -> dict[str, str]:
        observed.append(batch)
        return {"owner": "offline.diagnostics"}

    monkeypatch.setattr(offline_diagnostics, "summarize_vin_batch_shapes", _summarize)

    assert offline_diagnostics._batch_shape_preview(store_cfg) == {  # noqa: SLF001, S101
        "owner": "offline.diagnostics"
    }
    assert len(observed) == 1  # noqa: S101
    assert not hasattr(VinOracleBatch, "shape_summary")  # noqa: S101


def _write_member(archive: tarfile.TarFile, name: str) -> None:
    """Write one tiny tar member for coverage tests."""

    payload = b"x"
    info = tarfile.TarInfo(name=name)
    info.size = len(payload)
    archive.addfile(info, BytesIO(payload))


def test_collect_vin_offline_dataset_coverage_scans_raw_tar_headers(tmp_path: Path) -> None:
    """Coverage diagnostics should compare raw tar sample keys with immutable store rows."""

    tar_path = tmp_path / "raw_samples.tar"
    with tarfile.open(tar_path, mode="w") as archive:
        _write_member(archive, "scene-a/snippet-000.rgb.pth")
        _write_member(archive, "scene-b/snippet-001.rgb.pth")
        _write_member(archive, "scene-d/snippet-003.rgb.pth")
    store_cfg = _write_test_store(tmp_path, dataset_config={"tar_urls": [tar_path.as_posix()]})

    coverage = collect_vin_offline_dataset_coverage(store_cfg)

    assert coverage.tar_shards_scanned == 1  # noqa: S101
    assert coverage.dataset_snippets == 3  # noqa: S101
    assert coverage.store_snippets == 3  # noqa: S101
    assert coverage.covered_snippets == 2  # noqa: S101
    assert coverage.missing_in_store == 1  # noqa: S101
    assert coverage.outside_dataset == 1  # noqa: S101
    assert coverage.coverage == pytest.approx(2.0 / 3.0)  # noqa: S101
    assert ("scene-d", "snippet-003") in coverage.missing_examples  # noqa: S101
    assert ("scene-c", "snippet-002") in coverage.outside_examples  # noqa: S101


def test_vin_offline_dataset_round_trip(tmp_path: Path) -> None:
    store_cfg = _write_test_store(tmp_path)

    sample_dataset = VinOfflineDatasetConfig(
        store=store_cfg,
        return_format="sample",
        split="all",
    ).setup_target()
    assert len(sample_dataset) == 3  # noqa: S101
    first = sample_dataset[0]
    assert first.scene_id == "scene-a"  # noqa: S101
    assert first.oracle.candidate_count == 2  # noqa: S101
    assert first.source_shard_id == "shard-000000"  # noqa: S101
    assert first.source_shard_row == 0  # noqa: S101
    assert int(first.oracle.rri.shape[0]) == 4  # noqa: S101
    assert torch.isnan(first.oracle.rri[2:]).all()  # noqa: S101
    assert int(first.vin_snippet.lengths[0].item()) == 2  # noqa: S101
    assert first.gt_obbs is not None  # noqa: S101
    assert first.gt_obbs.obbs.shape == (2, 2, 34)  # noqa: S101
    assert first.gt_obbs.sem_id_to_name == {0: "chair", 1: "table", 28: "window"}  # noqa: S101
    assert first.detected_obbs is None  # noqa: S101
    assert first.trajectory is not None  # noqa: S101
    assert torch.equal(first.trajectory.time_ns, torch.tensor([100, 200], dtype=torch.int64))  # noqa: S101
    assert first.trajectory.gravity_in_world is not None  # noqa: S101
    assert first.trajectory.gravity_in_world.tolist() == pytest.approx([0.0, 0.0, -9.81])  # noqa: S101

    stored_manifest = VinOfflineManifest.read(store_cfg.manifest_path)
    assert stored_manifest.version == OFFLINE_DATASET_VERSION  # noqa: S101
    assert stored_manifest.materialized_blocks.gt_obbs is True  # noqa: S101
    assert stored_manifest.materialized_blocks.detected_obbs is False  # noqa: S101

    assert stored_manifest.materialized_blocks.trajectory is True  # noqa: S101
    assert stored_manifest.shards[0].shard_id == "shard-000000"  # noqa: S101
    assert stored_manifest.shards[0].blocks["vin.points_world"].kind == "zarr_array"  # noqa: S101
    assert stored_manifest.shards[0].blocks["gt.obbs"].kind == "zarr_array"  # noqa: S101
    assert stored_manifest.shards[0].blocks["vin.trajectory.time_ns"].kind == "zarr_array"  # noqa: S101
    assert "gt.mesh.verts" not in stored_manifest.shards[0].blocks  # noqa: S101
    assert "gt.mesh.faces" not in stored_manifest.shards[0].blocks  # noqa: S101
    assert "oracle.depths_payload" not in stored_manifest.shards[0].blocks  # noqa: S101

    sample_index_rows = _read_sample_index_rows(store_cfg.sample_index_path)
    assert sample_index_rows[0]["split"] == "train"  # noqa: S101
    assert sample_index_rows[1]["split"] == "train"  # noqa: S101
    assert sample_index_rows[2]["split"] == "val"  # noqa: S101

    batch_dataset = VinOfflineDatasetConfig(
        store=store_cfg,
        return_format="vin_batch",
        split="train",
    ).setup_target()
    batch = batch_dataset[0]
    assert isinstance(batch, VinOracleBatch)  # noqa: S101
    assert batch.scene_id == "scene-a"  # noqa: S101
    assert not hasattr(batch, "source_shard_id")  # noqa: S101
    assert int(batch.rri.shape[0]) == 4  # noqa: S101
    assert int(batch.resolved_candidate_count().item()) == 2  # noqa: S101
    assert batch.candidate_valid_mask().tolist() == [True, True, False, False]  # noqa: S101
    assert batch.gt_obbs is not None  # noqa: S101
    assert batch.gt_obbs.obbs.shape == (2, 2, 34)  # noqa: S101
    assert batch.trajectory is not None  # noqa: S101
    assert torch.equal(batch.trajectory.time_ns, torch.tensor([100, 200], dtype=torch.int64))  # noqa: S101


def test_actor_snippet_reader_matches_one_step_sample_and_reads_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One-step samples should use one shared typed actor-snippet read."""

    store_cfg = _write_test_store(tmp_path)
    dataset = VinOfflineDatasetConfig(store=store_cfg, return_format="sample", split="all").setup_target()
    record = dataset._records[0]
    direct = dataset._store.read_actor_snippet(record)
    reads: list[VinOfflineIndexRecord] = []
    original = dataset._store.read_actor_snippet

    def _record_read(
        requested: VinOfflineIndexRecord,
        *,
        device: str | torch.device = "cpu",
    ) -> VinSnippetView:
        reads.append(requested)
        return original(requested, device=device)

    monkeypatch.setattr(dataset._store, "read_actor_snippet", _record_read)
    sample = dataset[0]

    assert reads == [record]  # noqa: S101
    torch.testing.assert_close(sample.vin_snippet.points_world, direct.points_world, equal_nan=True)
    assert torch.equal(sample.vin_snippet.lengths, direct.lengths)  # noqa: S101
    assert torch.equal(sample.vin_snippet.t_world_rig.tensor(), direct.t_world_rig.tensor())  # noqa: S101
    assert sample.vin_snippet.points_world.dtype is torch.float32  # noqa: S101
    assert sample.vin_snippet.lengths.dtype is torch.int64  # noqa: S101


@pytest.mark.parametrize("failure", ["missing", "record_block"])
def test_actor_snippet_reader_rejects_invalid_required_blocks(tmp_path: Path, failure: str) -> None:
    """Required actor evidence must fail with immutable-store rebuild guidance."""

    store_cfg = _write_test_store(tmp_path)
    manifest = VinOfflineManifest.read(store_cfg.manifest_path)
    if failure == "missing":
        del manifest.shards[0].blocks["vin.lengths"]
        match = "Required actor block 'vin.lengths'.*Rebuild"
    else:
        manifest.shards[0].blocks["vin.lengths"].kind = "msgpack_indexed_records"
        match = "Actor block 'vin.lengths'.*numeric Zarr array.*Rebuild"
    manifest.write(store_cfg.manifest_path)
    reader = VinOfflineStoreReader(store_cfg)

    with pytest.raises(ValueError, match=match):
        reader.read_actor_snippet(reader.sample_index[0])


def test_actor_snippet_reader_drops_worker_handles_when_pickled(tmp_path: Path) -> None:
    """Reader pickling should preserve metadata but discard process-owned handles."""

    store_cfg = _write_test_store(tmp_path)
    reader = VinOfflineStoreReader(store_cfg)
    expected = reader.read_actor_snippet(reader.sample_index[0])
    assert reader._opened  # noqa: S101

    restored = pickle.loads(pickle.dumps(reader))

    assert restored._opened == {}  # noqa: S101
    assert restored._opened_pid is None  # noqa: S101
    actual = restored.read_actor_snippet(restored.sample_index[0])
    torch.testing.assert_close(actual.points_world, expected.points_world, equal_nan=True)
    assert torch.equal(actual.lengths, expected.lengths)  # noqa: S101
    assert torch.equal(actual.t_world_rig.tensor(), expected.t_world_rig.tensor())  # noqa: S101


def test_vin_offline_dataset_get_by_scene_snippet_accepts_compact_ase_atek_ids(tmp_path: Path) -> None:
    store_cfg = _write_test_store(tmp_path)
    records = VinOfflineIndexRecord.read_many(store_cfg.sample_index_path)
    records[0].sample_key = "81286::AriaSyntheticEnvironment_81286_AtekDataSample_000000"
    records[0].scene_id = "81286"
    records[0].snippet_id = "AriaSyntheticEnvironment_81286_AtekDataSample_000000"
    _write_sample_index(store_cfg.sample_index_path, records)

    dataset = VinOfflineDatasetConfig(
        store=store_cfg,
        return_format="sample",
        split="all",
    ).setup_target()

    found = dataset.get_by_scene_snippet(scene_id="81286", snippet_id="ASE_81286_Atek_000000")

    assert found is not None  # noqa: S101
    assert found.scene_id == "81286"  # noqa: S101


def test_vin_offline_store_persists_detected_obbs_for_training(tmp_path: Path) -> None:
    """Detected OBB tensors/probabilities should be numeric collatable blocks."""

    store_cfg = _write_test_store(tmp_path, include_backbone=True)
    sample_dataset = VinOfflineDatasetConfig(
        store=store_cfg,
        return_format="sample",
        split="all",
    ).setup_target()

    first = sample_dataset[0]
    assert first.detected_obbs is not None  # noqa: S101
    assert first.detected_obbs.obbs.shape == (1, 2, 34)  # noqa: S101
    assert first.detected_obbs.probs is not None  # noqa: S101
    assert first.detected_obbs.probs.shape == (2, 3)  # noqa: S101
    assert first.detected_obbs.sem_id_to_name == {0: "chair", 1: "table", 2: "lamp"}  # noqa: S101

    batch_dataset = VinOfflineDatasetConfig(
        store=store_cfg,
        return_format="vin_batch",
        split="train",
    ).setup_target()
    batched = VinOracleBatch.collate([batch_dataset[0], batch_dataset[1]])
    assert batched.gt_obbs is not None  # noqa: S101
    assert batched.gt_obbs.obbs.shape == (2, 2, 2, 34)  # noqa: S101
    assert batched.detected_obbs is not None  # noqa: S101
    assert batched.detected_obbs.obbs.shape == (2, 2, 34)  # noqa: S101
    assert batched.detected_obbs.probs is not None  # noqa: S101
    assert batched.detected_obbs.probs.shape == (2, 2, 3)  # noqa: S101
    assert batched.trajectory is not None  # noqa: S101
    assert batched.trajectory.time_ns is not None  # noqa: S101
    assert batched.trajectory.time_ns.shape == (2, 2)  # noqa: S101


def test_vin_offline_store_writes_indexed_record_blocks(tmp_path: Path) -> None:
    """Optional record blocks should use indexed payload blobs plus offsets."""

    store_cfg = _write_test_store(tmp_path, include_diagnostic_payloads=True)
    manifest = VinOfflineManifest.read(store_cfg.manifest_path)
    block = manifest.shards[0].blocks["oracle.depths_payload"]

    assert block.kind == "msgpack_indexed_records"  # noqa: S101
    assert block.paths == [  # noqa: S101
        VinOfflineBlockSpec.msgpack_records_path("oracle.depths_payload"),
        VinOfflineBlockSpec.msgpack_records_offsets_path("oracle.depths_payload"),
    ]
    shard_dir = store_cfg.store_dir / manifest.shards[0].relative_dir
    assert (shard_dir / block.paths[0]).is_file()  # noqa: S101
    assert (shard_dir / block.paths[1]).is_file()  # noqa: S101
    offsets = np.load(shard_dir / block.paths[1], allow_pickle=False)
    assert offsets.tolist()[0] == 0  # noqa: S101
    assert offsets.shape == (4,)  # noqa: S101
    assert np.all(np.diff(offsets) > 0)  # noqa: S101


def test_vin_offline_store_reads_indexed_record_blocks(
    tmp_path: Path,
) -> None:
    """Indexed record blocks should load one row directly from the shard blob."""

    store_cfg = _write_test_store(tmp_path, include_diagnostic_payloads=True)
    reader = VinOfflineStoreReader(store_cfg)
    record = reader.get_split_records(None)[1]
    payload = reader.read_optional_record(record, "oracle.depths_payload")
    assert payload is not None  # noqa: S101
    decoded = CandidateDepths.from_serializable(payload, device=torch.device("cpu"))
    assert decoded.candidate_indices.tolist() == [0, 1, 2]  # noqa: S101
    assert tuple(decoded.depths.shape) == (3, 4, 4)  # noqa: S101


def test_vin_offline_store_rejects_unsupported_manifest_version(tmp_path: Path) -> None:
    """Runtime readers should only accept the current immutable store version."""

    store_cfg = _write_test_store(tmp_path, include_diagnostic_payloads=True)
    manifest = VinOfflineManifest.read(store_cfg.manifest_path)
    manifest.version = OFFLINE_DATASET_VERSION - 1
    manifest.write(store_cfg.manifest_path)

    with pytest.raises(ValueError, match="Unsupported VIN offline dataset version"):
        VinOfflineStoreReader(store_cfg)


def test_vin_offline_manifest_omits_counterfactual_placeholders(tmp_path: Path) -> None:
    """The current store schema should not advertise unwritten counterfactual blocks."""

    store_cfg = _write_test_store(tmp_path)
    manifest_payload = json.loads(store_cfg.manifest_path.read_text(encoding="utf-8"))

    assert OFFLINE_DATASET_VERSION == 8  # noqa: S101
    assert "counterfactuals" not in manifest_payload  # noqa: S101
    assert "counterfactuals" not in manifest_payload["materialized_blocks"]  # noqa: S101


def test_vin_offline_store_rejects_unsupported_record_block_kind(tmp_path: Path) -> None:
    """Runtime readers should reject unsupported optional-record block encodings."""

    store_cfg = _write_test_store(tmp_path, include_diagnostic_payloads=True)
    manifest = VinOfflineManifest.read(store_cfg.manifest_path)
    manifest.shards[0].blocks["oracle.depths_payload"].kind = "msgpack_records"
    manifest.write(store_cfg.manifest_path)

    reader = VinOfflineStoreReader(store_cfg)
    record = reader.get_split_records(None)[1]
    with pytest.raises(ValueError, match="Unsupported VIN offline block kind"):
        reader.read_optional_record(record, "oracle.depths_payload")


def test_vin_offline_dataset_vin_batch_skips_optional_record_reads(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """VIN-batch reads should not decode optional diagnostic record payloads."""

    store_cfg = _write_test_store(tmp_path)
    dataset = VinOfflineDatasetConfig(
        store=store_cfg,
        return_format="vin_batch",
        split="train",
    ).setup_target()

    original_read_optional_record = dataset._store.read_optional_record

    def _raise_if_diagnostic_record(record: object, block_name: str) -> object:
        if block_name not in {"gt.obb_sem_id_to_name", "detected.obb_sem_id_to_name"}:
            raise AssertionError(f"vin_batch path should not touch diagnostic record block {block_name!r}")
        return original_read_optional_record(record, block_name)

    monkeypatch.setattr(dataset._store, "read_optional_record", _raise_if_diagnostic_record)
    batch = dataset[0]
    assert isinstance(batch, VinOracleBatch)  # noqa: S101


def test_vin_offline_datamodule_supports_worker_batching(tmp_path: Path) -> None:
    """Exercise multi-worker batching against the immutable VIN store."""

    if not _supports_worker_tensor_sharing():
        pytest.skip("Host multiprocessing backend does not support worker tensor sharing.")

    store_cfg = _write_test_store(tmp_path)
    prior_strategy = torch.multiprocessing.get_sharing_strategy()
    torch.multiprocessing.set_sharing_strategy("file_system")
    dm_cfg = VinDataModuleConfig(
        source=VinOfflineSourceConfig(
            offline=VinOfflineDatasetConfig(store=store_cfg),
            train_split="train",
            val_split="val",
        ),
        batch_size=2,
        shuffle=False,
        num_workers=1,
        persistent_workers=True,
        use_train_as_val=False,
    )
    try:
        datamodule = dm_cfg.setup_target()
        datamodule.setup(stage=Stage.TRAIN)

        train_loader = datamodule.train_dataloader()
        train_batch = next(iter(train_loader))
        repeated_train_batch = next(iter(train_loader))
        val_batch = next(iter(datamodule.val_dataloader()))
        assert isinstance(train_batch, VinOracleBatch)  # noqa: S101
        assert train_batch.rri.shape == (2, 4)  # noqa: S101
        assert torch.equal(train_batch.candidate_count, torch.tensor([2, 3], dtype=torch.int64))  # noqa: S101
        assert torch.equal(
            train_batch.candidate_valid_mask(),
            torch.tensor(
                [
                    [True, True, False, False],
                    [True, True, True, False],
                ],
                dtype=torch.bool,
            ),
        )  # noqa: S101
        assert train_batch.scene_id == ["scene-a", "scene-b"]  # noqa: S101
        assert set(repeated_train_batch.scene_id) == set(train_batch.scene_id)  # noqa: S101

        assert isinstance(val_batch, VinOracleBatch)  # noqa: S101
        assert val_batch.rri.shape == (1, 4)  # noqa: S101
        assert torch.equal(val_batch.candidate_count, torch.tensor([2], dtype=torch.int64))  # noqa: S101
        assert val_batch.scene_id == ["scene-c"]  # noqa: S101
    finally:
        torch.multiprocessing.set_sharing_strategy(prior_strategy)


def test_vin_offline_source_config_disables_diagnostic_blocks_for_vin_batches(tmp_path: Path) -> None:
    """The canonical offline source should expose the lean VIN-batch runtime path."""

    store_cfg = _write_test_store(tmp_path)
    dataset = VinOfflineSourceConfig(
        offline=VinOfflineDatasetConfig(store=store_cfg),
        train_split="train",
        val_split="val",
    ).setup_target(split=Stage.TRAIN)

    assert dataset.config.return_format == "vin_batch"  # noqa: S101
    assert dataset.config.load_candidates is False  # noqa: S101
    assert dataset.config.load_depths is False  # noqa: S101
    assert dataset.config.load_candidate_pcs is False  # noqa: S101
    assert dataset.config.load_gt_obbs is True  # noqa: S101
    assert dataset.config.load_detected_obbs is True  # noqa: S101
    assert dataset.config.load_trajectory_metadata is True  # noqa: S101


def test_fit_binner_offline_config_selects_all_stored_rows(tmp_path: Path) -> None:
    """The shipped binner config should preserve its all-stage source selection."""

    config_path = Path(__file__).resolve().parents[3] / ".configs" / "fit_binner_offline.toml"
    experiment_config = AriaNBVExperimentConfig.from_toml(config_path)
    source = experiment_config.datamodule_config.source

    assert isinstance(source, VinOfflineSourceConfig)  # noqa: S101
    assert source.train_split is None  # noqa: S101
    assert source.val_split is None  # noqa: S101

    store_config = _write_test_store(tmp_path)
    source.offline = VinOfflineDatasetConfig(store=store_config)
    dataset = source.setup_target(split=Stage.TRAIN)

    assert dataset.config.split is None  # noqa: S101
    assert len(dataset) == len(VinOfflineStoreReader(store_config).get_split_records(None))  # noqa: S101


def test_vin_offline_source_normalizes_stage_strings() -> None:
    """Source split text should normalize to all rows or canonical stages."""

    all_rows = VinOfflineSourceConfig(train_split="all", val_split=None, test_split="all")
    concrete = VinOfflineSourceConfig(train_split="fit", val_split="validate", test_split="test")

    assert all_rows.train_split is None  # noqa: S101
    assert all_rows.val_split is None  # noqa: S101
    assert all_rows.test_split is None  # noqa: S101
    assert concrete.train_split is Stage.TRAIN  # noqa: S101
    assert concrete.val_split is Stage.VAL  # noqa: S101
    assert concrete.test_split is Stage.TEST  # noqa: S101
