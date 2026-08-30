"""Tests for oracle target-task sampling."""

# ruff: noqa: S101

from __future__ import annotations

from collections.abc import Callable
from dataclasses import fields
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
import torch

pytest.importorskip("efm3d")

from efm3d.aria.aria_constants import ARIA_SNIPPET_T_WORLD_SNIPPET
from efm3d.aria.obb import ObbTW
from efm3d.aria.pose import PoseTW
from pytorch3d.renderer.cameras import PerspectiveCameras

from aria_nbv.data_handling import VinSnippetView
from aria_nbv.data_handling.ase_efm.views import EfmSnippetView
from aria_nbv.data_handling.vin_store.batch import CompactObbBlock
from aria_nbv.data_handling.vin_store.dataset import VinOfflineOracleBlock, VinOfflineSample
from aria_nbv.oracle import target_selection as target_selection_module
from aria_nbv.oracle.pipelines.campaign import CudaRolloutCampaign, CudaRolloutCampaignConfig
from aria_nbv.oracle.pipelines.rollout_dataset import RolloutDatasetWriter
from aria_nbv.oracle.target_selection import (
    ORACLE_TARGET_TASK_SOURCE,
    OracleMatchReason,
    OracleTargetTask,
    OracleTargetTaskSampler,
    OracleTargetTaskSamplerConfig,
    TargetTaskIdentityStatus,
    match_observed_target_descriptors,
)
from aria_nbv.targets import ObservedTargetDescriptor, TargetDescriptor
from aria_nbv.targets.selection import observed_target_descriptors


def _poses(translations: list[list[float]]) -> PoseTW:
    rotation = torch.eye(3, dtype=torch.float32).expand(len(translations), 3, 3).clone()
    return cast(PoseTW, PoseTW.from_Rt(rotation, torch.tensor(translations, dtype=torch.float32)))


def _pose_to(pose: PoseTW, *, device: str) -> PoseTW:
    to_device: Callable[..., Any] = pose.to
    return cast(PoseTW, to_device(device=device))


def _obb_block(
    centers: list[list[float]],
    *,
    sem_ids: list[int] | None = None,
    inst_ids: list[int] | None = None,
    probs: list[float] | None = None,
    box_size: float = 100.0,
    bb2: torch.Tensor | None = None,
) -> CompactObbBlock:
    count = len(centers)
    sem = sem_ids or [0] * count
    inst = inst_ids or list(range(count))
    conf = probs or [0.9] * count
    bb3 = torch.tensor([[-0.5, 0.5, -0.5, 0.5, -0.5, 0.5]] * count, dtype=torch.float32)
    bb2 = (
        bb2.to(dtype=torch.float32)
        if bb2 is not None
        else torch.tensor([[10.0, 10.0 + box_size, 10.0, 10.0 + box_size]] * count, dtype=torch.float32)
    )
    obbs = ObbTW.from_lmc(
        bb3_object=bb3,
        bb2_rgb=bb2,
        bb2_slaml=bb2,
        bb2_slamr=bb2,
        T_world_object=_poses(centers),
        sem_id=torch.tensor(sem, dtype=torch.int64),
        inst_id=torch.tensor(inst, dtype=torch.int64),
        prob=torch.tensor(conf, dtype=torch.float32),
    )
    return CompactObbBlock(obbs=obbs.tensor(), sem_id_to_name={0: "chair", 1: "table", 2: "sofa"})


def _cameras(count: int = 1) -> PerspectiveCameras:
    return PerspectiveCameras(
        R=torch.eye(3, dtype=torch.float32).expand(count, 3, 3).clone(),
        T=torch.zeros(count, 3, dtype=torch.float32),
        focal_length=torch.full((count, 2), 50.0, dtype=torch.float32),
        principal_point=torch.full((count, 2), 2.0, dtype=torch.float32),
        image_size=torch.full((count, 2), 4.0, dtype=torch.float32),
        in_ndc=False,
    )


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA required for mixed-device regression.")
def test_world_obb_normalization_aligns_transform_device(monkeypatch: pytest.MonkeyPatch) -> None:
    block = _obb_block([[0.0, 0.0, 0.0]])
    transform = _pose_to(_poses([[1.0, 0.0, 0.0]]), device="cuda")
    monkeypatch.setattr(target_selection_module, "snippet_t_world_snippet", lambda _sample: transform)

    sample = cast(VinOfflineSample, SimpleNamespace())
    result = target_selection_module._world_obbs_for_sample(ObbTW(block.obbs), sample)

    to_tensor: Callable[[], Any] = result.tensor
    assert cast(torch.Tensor, to_tensor()).device.type == "cpu"


def _sample(
    *,
    detected_obbs: CompactObbBlock | None = None,
    gt_obbs: CompactObbBlock | None = None,
    backbone_out: Any | None = None,
    points: list[list[float]] | None = None,
) -> VinOfflineSample:
    point_tensor = torch.tensor(points or [], dtype=torch.float32).reshape(-1, 3)
    vin_snippet = VinSnippetView(
        points_world=point_tensor,
        lengths=torch.tensor([point_tensor.shape[0]], dtype=torch.int64),
        t_world_rig=_poses([[0.0, 0.0, 0.0]]),
        t_world_snippet=_poses([[0.0, 0.0, 0.0]]),
    )
    oracle = VinOfflineOracleBlock(
        candidate_poses_world_cam=_poses([[0.0, 0.0, 0.0]]),
        reference_pose_world_rig=_poses([[0.0, 0.0, 0.0]]),
        candidate_count=1,
        rri=torch.zeros(1, dtype=torch.float32),
        pm_dist_before=torch.zeros(1, dtype=torch.float32),
        pm_dist_after=torch.zeros(1, dtype=torch.float32),
        pm_acc_before=torch.zeros(1, dtype=torch.float32),
        pm_comp_before=torch.zeros(1, dtype=torch.float32),
        pm_acc_after=torch.zeros(1, dtype=torch.float32),
        pm_comp_after=torch.zeros(1, dtype=torch.float32),
        p3d_cameras=_cameras(),
    )
    return VinOfflineSample(
        sample_key="scene/snippet/0",
        scene_id="scene",
        snippet_id="snippet",
        vin_snippet=vin_snippet,
        oracle=oracle,
        detected_obbs=detected_obbs,
        gt_obbs=gt_obbs,
        backbone_out=backbone_out,
    )


def _oracle_sampler(**kwargs: Any) -> OracleTargetTaskSampler:
    return OracleTargetTaskSampler(OracleTargetTaskSamplerConfig(**kwargs))


def test_oracle_target_task_sampler_config_has_only_selection_controls() -> None:
    assert set(OracleTargetTaskSamplerConfig.model_fields) == {
        "max_targets_per_sample",
        "policy",
        "seed",
    }


def test_oracle_target_task_sampler_selects_seeded_uniform_cap() -> None:
    sample = _sample(
        gt_obbs=_obb_block(
            [[0.0, 0.0, 0.0], [3.0, 0.0, 0.0], [6.0, 0.0, 0.0], [9.0, 0.0, 0.0]],
            sem_ids=[0, 1, 2, 0],
            inst_ids=[10, 11, 12, 13],
        )
    )

    first = _oracle_sampler(max_targets_per_sample=3, seed=7).sample(sample)
    second = _oracle_sampler(max_targets_per_sample=3, seed=7).sample(sample)

    assert first.source == ORACLE_TARGET_TASK_SOURCE
    assert len(first.rows) == 4
    assert first.diagnostic_summary()["num_identity_valid"] == 4
    assert len(first.selected_rows) == 3
    assert [row.target_id for row in first.selected_rows] == [row.target_id for row in second.selected_rows]
    assert all(row.selection_probability == pytest.approx(3.0 / 4.0) for row in first.selected_rows)
    assert all(row.identity_status == TargetTaskIdentityStatus.MATCHED.value for row in first.selected_rows)
    assert all(row.target_id.startswith(f"scene:snippet:{ORACLE_TARGET_TASK_SOURCE}:") for row in first.rows)
    assert all(row.descriptor.target_id != row.target_id for row in first.rows)


def test_oracle_target_task_sampler_keeps_duplicate_gt_geometry_as_distinct_tasks() -> None:
    sample = _sample(
        gt_obbs=_obb_block(
            [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [4.0, 0.0, 0.0]],
            sem_ids=[0, 0, 1],
            inst_ids=[10, 11, 12],
        )
    )

    result = _oracle_sampler(max_targets_per_sample=3, seed=0).sample(sample)

    assert len(result.rows) == 3
    assert result.diagnostic_summary()["num_identity_valid"] == 3
    assert len(result.selected_rows) == 3
    assert all(row.identity_status == TargetTaskIdentityStatus.MATCHED.value for row in result.rows)
    assert len({row.source_index for row in result.rows}) == 3
    assert "num_ambiguous_identity" not in result.diagnostic_summary()


def test_oracle_target_task_sampler_retains_nonfinite_auxiliary_payload_as_invalid() -> None:
    sample = _sample(gt_obbs=_obb_block([[0.0, 0.0, 0.0]], probs=[float("nan")]))

    result = _oracle_sampler(max_targets_per_sample=1).sample(sample)

    assert len(result.rows) == 1
    assert result.rows[0].identity_status == TargetTaskIdentityStatus.INVALID_GEOMETRY.value
    assert result.selected_rows == ()
    assert result.diagnostic_summary()["num_invalid_geometry"] == 1


def test_oracle_target_task_contains_only_domain_fields() -> None:
    sample = _sample(
        gt_obbs=_obb_block([[0.0, 0.0, 0.0]], probs=[0.05], box_size=0.0),
        points=[],
    )

    row = _oracle_sampler(max_targets_per_sample=1).sample(sample).selected_rows[0]

    assert {field.name for field in fields(OracleTargetTask)} == {
        "source_index",
        "target_row_id",
        "target_id",
        "descriptor",
        "inst_id",
        "confidence",
        "identity_status",
        "selected_rank",
        "selection_probability",
        "obb_data",
    }
    assert row.identity_status == TargetTaskIdentityStatus.MATCHED.value
    assert row.confidence == pytest.approx(0.05)


def test_oracle_target_task_sampler_rejects_non_offline_sample_input() -> None:
    sample = _sample(gt_obbs=_obb_block([[0.0, 0.0, 0.0]]))

    assert not hasattr(sample, "to_vin_oracle_batch")
    with pytest.raises(TypeError, match="VinOfflineSample"):
        _oracle_sampler().sample(sample.vin_snippet)  # type: ignore[arg-type]


def test_observed_descriptor_extraction_is_actor_only_and_deterministic() -> None:
    detected = _obb_block(
        [[2.0, 0.0, 0.0], [4.0, 0.0, 0.0]],
        sem_ids=[1, 0],
        inst_ids=[22, 11],
    )
    sample = _sample(detected_obbs=detected, gt_obbs=_obb_block([[99.0, 0.0, 0.0]], sem_ids=[2]))

    first = observed_target_descriptors(sample)
    second = observed_target_descriptors(sample)

    assert first == second
    assert [descriptor.source_row for descriptor in first] == [0, 1]
    assert [descriptor.target_id for descriptor in first] == [
        "scene/snippet/0:detected:0:22",
        "scene/snippet/0:detected:1:11",
    ]
    assert all(descriptor.descriptor_hash for descriptor in first)
    assert all(not hasattr(descriptor, "gt_match_row") for descriptor in first)


def test_observed_descriptor_transforms_snippet_obb_to_world_and_reference_frame() -> None:
    sample = _sample(detected_obbs=_obb_block([[2.0, 0.0, 0.0]], sem_ids=[1]), gt_obbs=None)
    sample.vin_snippet.t_world_rig = _poses([[10.0, 0.0, 0.0]])
    sample.vin_snippet.t_world_snippet = _poses([[10.0, 0.0, 0.0]])
    sample.oracle.reference_pose_world_rig = _poses([[11.0, 0.0, 0.0]])

    observed = observed_target_descriptors(sample)[0]

    assert observed.descriptor is not None
    assert observed.descriptor.center_world == pytest.approx((12.0, 0.0, 0.0))
    assert observed.descriptor.relative_pose_reference_object[9:12] == pytest.approx((1.0, 0.0, 0.0))
    assert observed.obb_data is not None
    assert ObbTW(torch.tensor(observed.obb_data)).T_world_object.t.reshape(-1).tolist() == pytest.approx(
        [12.0, 0.0, 0.0]
    )


def test_observed_descriptor_prefers_exact_efm_snippet_transform_over_trajectory() -> None:
    sample = _sample(detected_obbs=_obb_block([[2.0, 0.0, 0.0]], sem_ids=[1]), gt_obbs=None)
    sample.vin_snippet.t_world_rig = _poses([[10.0, 0.0, 0.0]])
    sample.efm_snippet_view = EfmSnippetView(
        efm={ARIA_SNIPPET_T_WORLD_SNIPPET: _poses([[20.0, 0.0, 0.0]])},
        scene_id=sample.scene_id,
        snippet_id=sample.snippet_id,
    )
    sample.oracle.reference_pose_world_rig = _poses([[21.0, 0.0, 0.0]])

    observed = observed_target_descriptors(sample)[0]

    assert observed.descriptor is not None
    assert observed.descriptor.center_world == pytest.approx((22.0, 0.0, 0.0))
    assert observed.descriptor.relative_pose_reference_object[9:12] == pytest.approx((1.0, 0.0, 0.0))


def test_invalid_observed_geometry_is_retained_with_explicit_match_reason() -> None:
    detected = _obb_block([[2.0, 0.0, 0.0]], sem_ids=[1])
    detected.obbs[0, 0:2] = 0.0
    observed = observed_target_descriptors(_sample(detected_obbs=detected, gt_obbs=None))

    assert len(observed) == 1
    assert observed[0].descriptor is None
    matched = match_observed_target_descriptors(list(observed), [])
    assert matched[0].admitted is False
    assert matched[0].reason is OracleMatchReason.INVALID_GEOMETRY


def test_campaign_source_audit_enumerates_admitted_and_rejected_observed_targets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sample = _sample(
        detected_obbs=_obb_block([[2.0, 0.0, 0.0], [4.0, 0.0, 0.0]], sem_ids=[1, 2]),
        gt_obbs=_obb_block([[2.0, 0.0, 0.0]], sem_ids=[1]),
    )
    source_row = SimpleNamespace(sample_key=sample.sample_key, to_jsonable=lambda: {"scene_id": sample.scene_id})
    manifest = SimpleNamespace(rows=(source_row,))
    writer_config = SimpleNamespace(
        source=SimpleNamespace(setup_target=lambda: [sample]),
        sample_keys=None,
        oracle_target_task_sampler=OracleTargetTaskSamplerConfig(max_targets_per_sample=1),
        selected_source_manifest_rows=lambda _manifest: (source_row,),
    )
    monkeypatch.setattr(RolloutDatasetWriter, "_apply_source_manifest", staticmethod(lambda *_args, **_kwargs: None))
    campaign = CudaRolloutCampaign(CudaRolloutCampaignConfig(output_root=tmp_path))

    audited = campaign.audit_source_manifest(writer_config, manifest)

    assert len(audited) == 2
    assert [row["target_id"] for row in audited] == [
        "scene/snippet/0:detected:0:0",
        "scene/snippet/0:detected:1:1",
    ]
    assert audited[0]["admitted"] is True
    assert audited[0]["gt_match_count"] == 1
    assert audited[0]["explicit_target_config"]["explicit_target_hash"] == audited[0]["explicit_target_hash"]
    assert audited[1]["admitted"] is False
    assert audited[1]["reason"] == OracleMatchReason.WRONG_CLASS.value
    assert "explicit_target_config" not in audited[1]


def test_campaign_source_audit_rejects_missing_match_rows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sample = _sample(
        detected_obbs=_obb_block([[2.0, 0.0, 0.0]], sem_ids=[1]),
        gt_obbs=_obb_block([[2.0, 0.0, 0.0]], sem_ids=[1]),
    )
    source_row = SimpleNamespace(sample_key=sample.sample_key, to_jsonable=lambda: {"scene_id": sample.scene_id})
    manifest = SimpleNamespace(rows=(source_row,))
    writer_config = SimpleNamespace(
        source=SimpleNamespace(setup_target=lambda: [sample]),
        sample_keys=None,
        oracle_target_task_sampler=OracleTargetTaskSamplerConfig(max_targets_per_sample=1),
        selected_source_manifest_rows=lambda _manifest: (source_row,),
    )
    monkeypatch.setattr(RolloutDatasetWriter, "_apply_source_manifest", staticmethod(lambda *_args, **_kwargs: None))
    monkeypatch.setattr(target_selection_module, "match_observed_target_descriptors", lambda *_args, **_kwargs: ())
    campaign = CudaRolloutCampaign(CudaRolloutCampaignConfig(output_root=tmp_path))

    with pytest.raises(ValueError, match="one result per observed target"):
        campaign.audit_source_manifest(writer_config, manifest)


def _observed_descriptor(*, source_row: int, sem_id: int = 1) -> ObservedTargetDescriptor:
    descriptor = TargetDescriptor(
        sem_id=sem_id,
        class_name="chair" if sem_id == 1 else "table",
        pose_world_object=(1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0),
        extents_m=(1.0, 1.0, 1.0),
        relative_pose_reference_object=(1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0),
    )
    return ObservedTargetDescriptor(
        sample_key="scene/snippet/0",
        source="detected_obbs",
        source_row=source_row,
        target_id=f"detected:{source_row}",
        descriptor=descriptor,
        confidence=0.9,
        inst_id=source_row,
    )


@pytest.mark.parametrize(
    ("iou", "admitted", "reason"),
    [
        (0.20, False, OracleMatchReason.BELOW_IOU_THRESHOLD),
        (0.2001, True, OracleMatchReason.ADMITTED),
    ],
)
def test_observed_gt_matching_uses_strict_iou_threshold(iou: float, admitted: bool, reason: OracleMatchReason) -> None:
    descriptor = _observed_descriptor(source_row=0)
    result = match_observed_target_descriptors(
        [descriptor],
        [SimpleNamespace(descriptor=SimpleNamespace(sem_id=1), target_id="gt-0")],
        iou_fn=lambda _descriptor, _row: iou,
    )[0]

    assert result.admitted is admitted
    assert result.reason is reason
    assert result.oriented_iou == pytest.approx(iou)


def test_observed_gt_matching_preserves_gt_source_row_identity() -> None:
    descriptor = _observed_descriptor(source_row=0)
    gt_row = SimpleNamespace(descriptor=SimpleNamespace(sem_id=1), target_id="gt-7", source_index=7)

    result = match_observed_target_descriptors([descriptor], [gt_row], iou_fn=lambda *_args: 0.8)[0]

    assert result.admitted is True
    assert result.gt_match_row == 7


@pytest.mark.parametrize(
    ("gt_rows", "reason"),
    [
        ([SimpleNamespace(descriptor=SimpleNamespace(sem_id=2), target_id="wrong")], OracleMatchReason.WRONG_CLASS),
        ([], OracleMatchReason.NO_MATCH),
        (
            [SimpleNamespace(descriptor=SimpleNamespace(sem_id=1), target_id="invalid")],
            OracleMatchReason.INVALID_GEOMETRY,
        ),
    ],
)
def test_observed_gt_matching_reports_rejection_reason(gt_rows: list[Any], reason: OracleMatchReason) -> None:
    descriptor = _observed_descriptor(source_row=0)
    iou_fn = (
        None if reason is not OracleMatchReason.INVALID_GEOMETRY else lambda *_args: (_ for _ in ()).throw(ValueError())
    )
    result = match_observed_target_descriptors([descriptor], gt_rows, iou_fn=iou_fn)[0]

    assert result.admitted is False
    assert result.reason is reason


def test_observed_gt_matching_returns_all_admitted_descriptors_in_source_order() -> None:
    descriptors = [_observed_descriptor(source_row=4), _observed_descriptor(source_row=1)]
    rows = [SimpleNamespace(descriptor=SimpleNamespace(sem_id=1), target_id="gt")]

    result = match_observed_target_descriptors(descriptors, cast(Any, rows), iou_fn=lambda *_args: 0.8)

    assert [item.descriptor.source_row for item in result] == [1, 4]
    assert all(item.admitted for item in result)


def test_observed_gt_matching_marks_equal_best_qualified_matches_ambiguous() -> None:
    descriptor = _observed_descriptor(source_row=0)
    rows = [
        SimpleNamespace(descriptor=SimpleNamespace(sem_id=1), target_id="gt-0"),
        SimpleNamespace(descriptor=SimpleNamespace(sem_id=1), target_id="gt-1"),
    ]

    result = match_observed_target_descriptors([descriptor], cast(Any, rows), iou_fn=lambda *_args: 0.8)[0]

    assert result.admitted is False
    assert result.reason is OracleMatchReason.AMBIGUOUS
    assert result.gt_match_id == "gt-0"


@pytest.mark.parametrize("iou", [float("nan"), float("inf"), -0.01, 1.01])
def test_observed_gt_matching_rejects_nonfinite_or_out_of_range_iou_as_invalid_geometry(iou: float) -> None:
    descriptor = _observed_descriptor(source_row=0)
    row = SimpleNamespace(descriptor=SimpleNamespace(sem_id=1), target_id="invalid")

    result = match_observed_target_descriptors([descriptor], [row], iou_fn=lambda *_args: iou)[0]

    assert result.admitted is False
    assert result.reason is OracleMatchReason.INVALID_GEOMETRY
