"""Rerun rollout-Zarr logger tests using a fake Rerun module."""

# ruff: noqa: S101

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import numpy as np
import pytest
import torch
import zarr

pytest.importorskip("efm3d")

from aria_nbv.rerun_inspector._config import RerunOfflineInspectorConfig
from aria_nbv.rerun_inspector._entities import ENTITY_WORLD
from aria_nbv.rerun_inspector._layers import resolve_rollout_layer_config
from aria_nbv.rerun_inspector._rollout_zarr import (
    ENTITY_ROLLOUT_DIAGNOSTICS_ROOT,
    ENTITY_ROLLOUT_INVALID_FRACTION,
    ENTITY_ROLLOUT_METADATA,
    ENTITY_ROLLOUT_ROOT,
    ENTITY_ROLLOUT_RRI_ROOT,
    ENTITY_ROLLOUT_SELECTED_POSITION_ID,
    ENTITY_ROLLOUT_SELECTED_TARGET_ROOT_GAIN,
    RerunRolloutZarrLogger,
    _candidate_rri_summary,
    _plot_step_payload,
    _resolve_plot_rollout_rows,
)
from aria_nbv.rollouts.audits import candidate_policy_entropy
from aria_nbv.rollouts.read_model import rollout_at, rollout_steps
from aria_nbv.rollouts.zarr_store import write_rollout_zarr_store
from tests.rollout_fixtures import build_rollout_records

if TYPE_CHECKING:
    from pathlib import Path


class _Archetype:
    """Simple fake Rerun archetype that stores constructor data."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.args = args
        self.kwargs = kwargs


class _FakeRerun:
    """Fake subset of the Rerun module used by the rollout inspector."""

    Points3D = _Archetype
    LineStrips3D = _Archetype
    TextDocument = _Archetype
    Scalars = _Archetype
    SeriesLines = _Archetype
    SeriesPoints = _Archetype
    Transform3D = _Archetype
    Pinhole = _Archetype
    DepthImage = _Archetype
    AnyValues = _Archetype
    Boxes3D = _Archetype

    class ViewCoordinates:
        """Fake Rerun view-coordinate constants."""

        RIGHT_HAND_Z_UP = _Archetype("RIGHT_HAND_Z_UP")
        LUF = _Archetype("LUF")

    class TransformRelation:
        """Fake transform relation constants."""

        ParentFromChild = "ParentFromChild"

    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.logged: dict[str, _Archetype] = {}
        self.logged_extras: dict[str, tuple[Any, ...]] = {}
        self.blueprints: list[object] = []

    def init(self, *args: Any, **kwargs: Any) -> None:
        self.calls.append(("init", args, kwargs))

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.calls.append(("save", args, kwargs))

    def spawn(self, *args: Any, **kwargs: Any) -> None:
        self.calls.append(("spawn", args, kwargs))

    def connect_grpc(self, *args: Any, **kwargs: Any) -> None:
        self.calls.append(("connect_grpc", args, kwargs))

    def set_time(self, *args: Any, **kwargs: Any) -> None:
        self.calls.append(("set_time", args, kwargs))

    def set_time_sequence(self, *args: Any, **kwargs: Any) -> None:
        self.calls.append(("set_time_sequence", args, kwargs))

    def log(self, entity_path: str, entity: _Archetype, *args: Any, **kwargs: Any) -> None:
        self.calls.append(("log", entity_path, args, kwargs))
        self.logged[entity_path] = entity
        self.logged_extras[entity_path] = args

    def send_blueprint(self, blueprint: object, *args: Any, **kwargs: Any) -> None:
        self.calls.append(("send_blueprint", args, kwargs))
        self.blueprints.append(blueprint)


def _world_view_from_blueprint(blueprint: object) -> object:
    """Extract the world Spatial3DView from a captured blueprint."""

    pending = [blueprint.root_container]  # type: ignore[attr-defined]
    while pending:
        part = pending.pop()
        if getattr(part, "name", None) == "World":
            return part
        pending.extend(getattr(part, "contents", ()) or ())
    raise AssertionError("World Spatial3DView not found in blueprint.")


def _world_view_contents_from_blueprint(blueprint: object) -> list[str]:
    """Extract the world Spatial3DView contents from a captured blueprint."""

    return list(_world_view_from_blueprint(blueprint).contents)  # type: ignore[attr-defined]


def _world_view_overrides_from_blueprint(blueprint: object) -> dict[str, object]:
    """Extract the world Spatial3DView overrides from a captured blueprint."""

    return dict(_world_view_from_blueprint(blueprint).overrides)  # type: ignore[attr-defined]


def _fixture_rollout_store(tmp_path: Path, *, selected_depth_enabled: bool = True) -> Path:
    records = build_rollout_records(horizon=2, num_samples=6, seed=13)
    if len(records) > 1:
        base = records[0].lineage
        sibling = records[1].lineage
        sibling.source = base.source
        sibling.target.target_row_id = base.target.target_row_id
        sibling.target.target_id = base.target.target_id
        sibling.target.target_source_index = base.target.target_source_index
        sibling.target.matched_gt_target_row_id = base.target.matched_gt_target_row_id
        sibling.target.matched_gt_target_id = base.target.matched_gt_target_id
    for record in records:
        for chain_id, trajectory in enumerate(record.evaluated.result.trajectories):
            for step in trajectory.steps:
                candidate_valid = step.candidates.mask_valid.clone()
                invalid = torch.zeros_like(candidate_valid, dtype=torch.bool)
                invalid[::4] = True
                invalid[int(step.selected_shell_index)] = False
                compact_invalid = invalid[candidate_valid]
                candidate_valid[invalid] = False
                step.candidates.mask_valid = candidate_valid
                step.candidates.masks["FixtureInvalidRule"] = candidate_valid
                evaluated_step = record.evaluated.step(chain_id, step.step_index)
                assert evaluated_step is not None
                _reset_target_eval_candidate_rows(evaluated_step)
                _mask_vector(step.selection_scores, invalid, fill=float("nan"))
                _mask_vector(step.selection_logits, invalid, fill=float("nan"))
                _mask_vector(step.selection_probabilities, invalid, fill=0.0, renormalize=True, valid=candidate_valid)
                _mask_vector(
                    step.selection_log_probabilities,
                    invalid,
                    fill=float("-inf"),
                    log_from=step.selection_probabilities,
                )
                for values in evaluated_step.evaluation.labels.metrics.values():
                    _mask_vector(values, compact_invalid, fill=float("nan"))
                evidence = evaluated_step.evaluation.evidence
                if evidence.selected_depth_m is not None and evidence.selected_depth_valid_mask is not None:
                    evidence.selected_depth_m[0, 0] = 42.0
                    evidence.selected_depth_valid_mask[0, 0] = False

    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr",
        records,
        target_protocol_version="v0_gt_input",
        source_offline_store_version="7",
        split_manifest_hash="fixture-split-manifest",
        selected_depth_enabled=selected_depth_enabled,
    )
    return result.store_dir


def _reset_target_eval_candidate_rows(step: Any) -> None:
    """Realign fixture target-eval compact rows after mutating candidate validity."""

    valid_count = int(step.transition.candidates.mask_valid.detach().cpu().to(dtype=torch.bool).sum().item())
    evidence = step.evaluation.evidence
    evidence.target_eval_candidate_points_world = torch.zeros((valid_count, 2, 3), dtype=torch.float32)
    evidence.target_eval_candidate_point_lengths = torch.full((valid_count,), 2, dtype=torch.long)
    for valid_index in range(valid_count):
        evidence.target_eval_candidate_points_world[valid_index, :, :] = torch.tensor(
            [[float(valid_index), 0.0, 0.0], [float(valid_index), 0.1, 0.0]],
            dtype=torch.float32,
        )


def _mask_vector(
    values: torch.Tensor | None,
    invalid: torch.Tensor,
    *,
    fill: float,
    renormalize: bool = False,
    valid: torch.Tensor | None = None,
    log_from: torch.Tensor | None = None,
) -> None:
    if values is None:
        return
    if log_from is not None:
        values.copy_(torch.log(log_from.clamp_min(torch.finfo(log_from.dtype).tiny)))
        values[~torch.isfinite(log_from) | (log_from <= 0.0)] = fill
    values[invalid] = fill
    if renormalize and valid is not None:
        denom = values[valid].sum()
        if float(denom.item()) > 0.0:
            values[valid] = values[valid] / denom


def test_rollout_zarr_logger_logs_multistep_candidate_layers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store_dir = _fixture_rollout_store(tmp_path)
    cfg = RerunOfflineInspectorConfig()
    cfg.output.save_path = tmp_path / "rollout.rrd"
    cfg.selection.rollout_context_mode = "off"
    fake = _FakeRerun()
    monkeypatch.setattr(
        "aria_nbv.rerun_inspector._rollout_zarr.RolloutZarrStoreReader.q_h_view",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("q_h_view must not be loaded eagerly")),
    )
    logger = RerunRolloutZarrLogger(cfg, rr_module=fake)

    logger.start()
    assert fake.blueprints == []
    rows = logger.log_store(store_dir=store_dir, rollout_index=0)

    assert [call[0] for call in fake.calls[:2]] == ["init", "save"]
    assert rows.rollout_row_id == 0
    assert rows.chain_id == 0
    assert rows.step_row_positions.shape[0] == 2
    assert ENTITY_WORLD in fake.logged
    assert ENTITY_ROLLOUT_METADATA in fake.logged
    chain_root = f"{ENTITY_ROLLOUT_ROOT}/rollout_{rows.rollout_row_id:06d}/chain_{rows.chain_id:06d}"
    target_root = f"{chain_root}/target"
    assert f"{target_root}/actor_visible_obb" in fake.logged
    assert f"{target_root}/center" in fake.logged
    assert f"{target_root}/metadata" in fake.logged
    target_metadata = json.loads(fake.logged[f"{target_root}/metadata"].args[0])
    assert target_metadata["target_row_id"] == 0
    assert target_metadata["source_row_id"] == 0
    assert target_metadata["target_id"] == "fixture-target-0"
    assert target_metadata["matched_gt_target_id"] == "fixture-gt-target-0"
    assert target_metadata["target_effective_support_count"] == pytest.approx(12.0)
    assert target_metadata["target_visibility_score"] == pytest.approx(0.8)
    assert len(fake.blueprints) == 1
    rollout_contents = _world_view_contents_from_blueprint(fake.blueprints[-1])
    rollout_overrides = _world_view_overrides_from_blueprint(fake.blueprints[-1])
    assert rollout_contents == ["+ /world/**"]
    assert all(not rule.startswith("- ") for rule in rollout_contents)
    assert "/world/efm/obbs/detected" not in rollout_overrides
    assert f"/{chain_root}/step_000/valid" in rollout_overrides
    assert f"/{chain_root}/step_000/invalid" in rollout_overrides
    assert f"/{chain_root}/step_001/valid" in rollout_overrides
    assert f"/{chain_root}/step_001/invalid" in rollout_overrides
    assert f"/{chain_root}/step_000/selected" in rollout_overrides
    assert all(override.visible.as_arrow_array().to_pylist() == [False] for override in rollout_overrides.values())
    selected_path_entity = f"{chain_root}/selected_path"
    assert selected_path_entity in fake.logged
    assert "world/rollout/selected_path" not in fake.logged
    assert not any(path.startswith("world/rollout/step/") for path in fake.logged)
    assert any(f"{chain_root}/step_" in path and "/valid/candidate_shell_" in path for path in fake.logged)
    assert any(f"{chain_root}/step_" in path and "/invalid/candidate_shell_" in path for path in fake.logged)
    assert any(f"{chain_root}/step_" in path and "/selected/candidate_shell_" in path for path in fake.logged)
    assert any(
        f"{chain_root}/step_" in path and "/groups/position_family/forward_local" in path for path in fake.logged
    )
    assert any(f"{chain_root}/step_" in path and "/groups/invalid_reason/valid" in path for path in fake.logged)

    depth_calls = [
        call
        for call in fake.calls
        if call[0] == "log"
        and str(call[1]).startswith(f"{chain_root}/step_")
        and "/selected/candidate_shell_" in str(call[1])
        and str(call[1]).endswith("/camera/depth")
    ]
    assert len(depth_calls) == rows.step_row_positions.shape[0]
    assert {str(call[1]).split("/selected/", maxsplit=1)[0].rsplit("/", maxsplit=1)[-1] for call in depth_calls} == {
        "step_000",
        "step_001",
    }
    depth_path = str(depth_calls[0][1])
    camera_path = depth_path.removesuffix("/depth")
    assert f"/{depth_path}" in rollout_overrides
    assert f"/{camera_path}/points" in rollout_overrides
    depth_image = fake.logged[depth_path]
    assert depth_image.kwargs["meter"] == 1.0
    assert depth_image.kwargs["colormap"] == "turbo"
    assert depth_image.kwargs["point_fill_ratio"] == pytest.approx(0.2)
    depth_array = np.asarray(depth_image.args[0])
    assert depth_array.shape == (240, 240)
    assert np.isnan(depth_array[0, 0])
    assert not any(str(call[1]).endswith("/camera/points") for call in fake.calls if call[0] == "log")

    pinhole = fake.logged_extras[camera_path][0]
    assert pinhole.kwargs["resolution"] == [240.0, 240.0]
    assert pinhole.kwargs["focal_length"] == [120.0, 120.0]
    assert pinhole.kwargs["principal_point"] == [120.0, 120.0]

    timeline_calls = [call for call in fake.calls if call[0] == "set_time"]
    assert ("rollout_step",) in [call[1] for call in timeline_calls]
    assert [call[2]["sequence"] for call in timeline_calls[-2:]] == [0, 1]
    assert not [call for call in fake.calls if call[0] == "set_time_sequence"]

    plot_paths = [path for path in fake.logged if path.startswith("plots/rollout/")]
    assert any(path.startswith(f"{ENTITY_ROLLOUT_RRI_ROOT}/") for path in plot_paths)
    assert any(path.startswith(f"{ENTITY_ROLLOUT_DIAGNOSTICS_ROOT}/") for path in plot_paths)
    assert any("/candidate_top_01" in path for path in plot_paths)
    assert any("/candidate_fanout_mean" in path for path in plot_paths)
    assert ENTITY_ROLLOUT_SELECTED_TARGET_ROOT_GAIN in fake.logged
    assert ENTITY_ROLLOUT_INVALID_FRACTION in fake.logged
    assert ENTITY_ROLLOUT_SELECTED_POSITION_ID in fake.logged
    descriptor_calls = [
        call
        for call in fake.calls
        if call[0] == "log" and str(call[1]).startswith("plots/rollout/") and call[3].get("static") is True
    ]
    assert descriptor_calls
    assert isinstance(fake.logged[descriptor_calls[0][1]], _Archetype)
    assert isinstance(descriptor_calls[0][2][0], _Archetype)

    camera_calls = [
        call
        for call in fake.calls
        if call[0] == "log"
        and str(call[1]).startswith(f"{chain_root}/step_")
        and "/valid/candidate_shell_" in str(call[1])
    ]
    assert camera_calls
    assert len(camera_calls[0][2]) == 2
    assert "labels" not in camera_calls[0][2][0].kwargs
    camera_metadata = camera_calls[0][2][1].kwargs
    assert camera_metadata["candidate_row_id"] >= 0
    assert camera_metadata["step_row_id"] == int(rows.step_row_positions[0])
    assert camera_metadata["compact_valid_index"] >= 0
    assert camera_metadata["mixture_component_name"]
    assert camera_metadata["position_mode_name"] == "forward_local"
    assert camera_metadata["position_id"] >= 0
    assert camera_metadata["sampler_probability"] > 0.0
    assert camera_metadata["target_root_gain"] != camera_metadata["target_rri"]
    assert camera_metadata["target_rri_rank"] > 0
    assert camera_metadata["target_rri_rank_total"] > 0
    assert camera_metadata["selection_probability"] >= 0.0
    assert camera_metadata["mesh_distance_m"] > 0.0
    assert camera_metadata["path_min_clearance_m"] > 0.0
    assert camera_metadata["motion_step_length_m"] > 0.0
    assert camera_metadata["target_distance_m"] > 0.0
    assert camera_metadata["primary_invalid_reason_name"] == "VALID"
    assert "rollout_row_id" not in camera_metadata
    assert "chain_id" not in camera_metadata
    assert "step_index" not in camera_metadata
    assert "shell_index" not in camera_metadata
    assert "candidate_status" not in camera_metadata
    assert "sampling_strategy_id" not in camera_metadata
    assert "mixture_id" not in camera_metadata
    assert "selection_logit" not in camera_metadata
    assert "selection_entropy" not in camera_metadata
    assert "invalid_reason_bitset" not in camera_metadata

    metadata = json.loads(fake.logged[ENTITY_ROLLOUT_METADATA].args[0])
    assert metadata["validation"]["ok"]
    assert metadata["manifest"]["schema_version"]
    assert metadata["manifest"]["source_coverage"]["num_source_rows"] >= 1
    assert metadata["selected"]["rollout_row_id"] == 0
    assert metadata["selected"]["chain_id"] == 0
    assert metadata["target"]["target_id"] == "fixture-target-0"
    assert metadata["context"]["mode"] == "off"

    step_metadata_paths = [
        path for path in fake.logged if path.startswith(f"{ENTITY_ROLLOUT_METADATA}/rollout_000000/chain_000000/step_")
    ]
    assert sorted(step_metadata_paths) == [
        f"{ENTITY_ROLLOUT_METADATA}/rollout_000000/chain_000000/step_000",
        f"{ENTITY_ROLLOUT_METADATA}/rollout_000000/chain_000000/step_001",
    ]
    step_metadata = json.loads(fake.logged[step_metadata_paths[0]].args[0])
    assert step_metadata["rollout_row_id"] == rows.rollout_row_id
    assert step_metadata["chain_id"] == rows.chain_id
    assert step_metadata["step_row_id"] == int(rows.step_row_positions[0])
    assert step_metadata["step_index"] == 0
    assert step_metadata["q_h"]["state_row_found"]
    assert step_metadata["q_h"]["selected_transition_available"]
    assert step_metadata["invalid_candidate_count"] > 0
    assert step_metadata["invalid_fraction"] > 0.0
    assert step_metadata["selected_position_family"] == "forward_local"
    assert step_metadata["selected_target_root_gain"] != step_metadata["selected_target_rri"]
    assert step_metadata["candidate_counts_by_position"]["forward_local"]["total"] > 0
    assert "VALID" in step_metadata["candidate_counts_by_invalid_reason"]
    assert "display_validity_trusted" not in step_metadata
    assert "stored_invalid_candidate_count" not in step_metadata
    assert step_metadata["selected_depth"]["available"]
    assert step_metadata["selected_depth"]["representation"] == "depth_image"
    assert step_metadata["selected_depth"]["depth_entity"].startswith(f"{chain_root}/step_000/selected/")
    assert step_metadata["selected_depth"]["depth_entity"].endswith("/camera/depth")
    assert step_metadata["selected_depth"]["points_entity"] is None

    selected_path = fake.logged[selected_path_entity]
    assert len(selected_path.args[0]) == 2
    np.testing.assert_equal(np.asarray(selected_path.args[0][0]).shape, (2, 3))
    assert len(selected_path.kwargs["colors"]) == 2
    assert selected_path.kwargs["colors"][0] != selected_path.kwargs["colors"][1]


def test_rollout_zarr_logger_can_log_selected_depth_as_point_cloud(tmp_path: Path) -> None:
    store_dir = _fixture_rollout_store(tmp_path)
    cfg = RerunOfflineInspectorConfig()
    cfg.output.save_path = tmp_path / "rollout.rrd"
    cfg.selection.rollout_context_mode = "off"
    cfg.rollout_depths.representation = "point_cloud"
    cfg.rollout_depths.max_points = 8
    cfg.rollout_depths.point_radius = 0.012
    fake = _FakeRerun()

    logger = RerunRolloutZarrLogger(cfg, rr_module=fake)
    logger.start()
    rows = logger.log_store(store_dir=store_dir, rollout_index=0)

    chain_root = f"{ENTITY_ROLLOUT_ROOT}/rollout_{rows.rollout_row_id:06d}/chain_{rows.chain_id:06d}"
    point_calls = [
        call
        for call in fake.calls
        if call[0] == "log"
        and str(call[1]).startswith(f"{chain_root}/step_")
        and "/selected/candidate_shell_" in str(call[1])
        and str(call[1]).endswith("/camera/points")
    ]
    assert len(point_calls) == rows.step_row_positions.shape[0]
    assert not any(str(call[1]).endswith("/camera/depth") for call in fake.calls if call[0] == "log")

    points_path = str(point_calls[0][1])
    points = np.asarray(fake.logged[points_path].args[0])
    assert points.shape == (8, 3)
    assert np.isfinite(points).all()
    assert not np.any(points[:, 2] == 42.0)
    assert fake.logged[points_path].kwargs["radii"] == pytest.approx(0.012)

    step_metadata = json.loads(fake.logged[f"{ENTITY_ROLLOUT_METADATA}/rollout_000000/chain_000000/step_000"].args[0])
    assert step_metadata["selected_depth"]["representation"] == "point_cloud"
    assert step_metadata["selected_depth"]["depth_entity"] is None
    assert step_metadata["selected_depth"]["points_entity"].endswith("/camera/points")


def test_rollout_zarr_logger_can_log_selected_depth_as_depth_and_points(tmp_path: Path) -> None:
    store_dir = _fixture_rollout_store(tmp_path)
    cfg = RerunOfflineInspectorConfig()
    cfg.output.save_path = tmp_path / "rollout.rrd"
    cfg.selection.rollout_context_mode = "off"
    cfg.rollout_depths.representation = "both"
    cfg.rollout_depths.max_points = 3
    fake = _FakeRerun()

    logger = RerunRolloutZarrLogger(cfg, rr_module=fake)
    logger.start()
    rows = logger.log_store(store_dir=store_dir, rollout_index=0)

    depth_paths = [str(call[1]) for call in fake.calls if call[0] == "log" and str(call[1]).endswith("/camera/depth")]
    point_paths = [str(call[1]) for call in fake.calls if call[0] == "log" and str(call[1]).endswith("/camera/points")]
    assert len(depth_paths) == rows.step_row_positions.shape[0]
    assert len(point_paths) == rows.step_row_positions.shape[0]
    assert all(np.asarray(fake.logged[path].args[0]).shape == (3, 3) for path in point_paths)


def test_rollout_zarr_logger_warns_when_selected_depth_is_unavailable(tmp_path: Path) -> None:
    store_dir = _fixture_rollout_store(tmp_path, selected_depth_enabled=False)
    cfg = RerunOfflineInspectorConfig()
    cfg.output.save_path = tmp_path / "rollout.rrd"
    cfg.selection.rollout_context_mode = "off"
    fake = _FakeRerun()

    logger = RerunRolloutZarrLogger(cfg, rr_module=fake)
    logger.start()
    rows = logger.log_store(store_dir=store_dir, rollout_index=0)

    assert not any(str(call[1]).endswith("/camera/depth") for call in fake.calls if call[0] == "log")
    step_metadata = json.loads(
        fake.logged[
            f"{ENTITY_ROLLOUT_METADATA}/rollout_{rows.rollout_row_id:06d}/chain_{rows.chain_id:06d}/step_000"
        ].args[0]
    )
    assert not step_metadata["selected_depth"]["available"]
    assert step_metadata["selected_depth"]["warnings"]

    cfg.rollout_depths.require_selected_depth = True
    required_logger = RerunRolloutZarrLogger(cfg, rr_module=_FakeRerun())
    required_logger.start()
    with pytest.raises(ValueError, match="selected_depth unavailable"):
        required_logger.log_store(store_dir=store_dir, rollout_index=0)


def test_rollout_zarr_logger_uses_persisted_target_center(tmp_path: Path) -> None:
    store_dir = _fixture_rollout_store(tmp_path)
    root = zarr.open_group(store_dir, mode="a")
    persisted_center = np.asarray([9.0, 8.0, 7.0], dtype=np.float32)
    root["targets/target_center_world"][0] = persisted_center
    root["targets/target_pose_world_object"][0, 9:12] = np.asarray([1.0, 2.0, 3.0], dtype=np.float32)

    cfg = RerunOfflineInspectorConfig()
    cfg.output.save_path = tmp_path / "rollout.rrd"
    cfg.selection.rollout_context_mode = "off"
    fake = _FakeRerun()
    rows = RerunRolloutZarrLogger(cfg, rr_module=fake).log_store(store_dir=store_dir, rollout_index=0)

    target_root = f"{ENTITY_ROLLOUT_ROOT}/rollout_{rows.rollout_row_id:06d}/chain_{rows.chain_id:06d}/target"
    logged_center = np.asarray(fake.logged[f"{target_root}/center"].args[0], dtype=np.float32).reshape(3)
    np.testing.assert_allclose(logged_center, persisted_center)
    metadata = json.loads(fake.logged[f"{target_root}/metadata"].args[0])
    np.testing.assert_allclose(metadata["target_center_world"], persisted_center)


def test_rollout_plot_helpers_resolve_sibling_branches_and_topk(tmp_path: Path) -> None:
    store_dir = _fixture_rollout_store(tmp_path)
    from aria_nbv.rollouts import RolloutZarrStoreReader

    reader = RolloutZarrStoreReader(store_dir)
    selected = _resolve_plot_rollout_rows(
        reader,
        selected_rows=rollout_at(reader, 0),
        branch_scope="same_source_target",
    )

    assert len(selected) > 1
    assert selected[0].rollout_row_id == 0
    first_step = _plot_step_payload(rollout_steps(reader, selected[0])[0], candidate_top_k=5)
    assert first_step.valid_candidate_count > 0
    assert len(first_step.top_candidate_target_rri) <= 5
    assert np.isfinite(first_step.selected_target_rri)


def test_candidate_rri_summary_keeps_invalid_nan_rows_out_of_fanout() -> None:
    summary = _candidate_rri_summary(
        target_rri=np.asarray([np.nan, 0.1, 0.3, np.nan], dtype=np.float32),
        scene_rri=np.asarray([np.nan, 0.2, 0.4, np.nan], dtype=np.float32),
        probabilities=np.asarray([0.0, 0.25, 0.75, 0.0], dtype=np.float32),
        entropy=0.5,
        valid_mask=np.asarray([False, True, True, False]),
        selected_mask=np.asarray([False, False, True, False]),
        top_k=2,
    )

    assert summary.valid_candidate_count == 2
    assert summary.selected_target_rri == pytest.approx(0.3)
    assert summary.selected_scene_rri == pytest.approx(0.4)
    assert summary.top_candidate_target_rri == pytest.approx((0.3, 0.1))
    assert summary.candidate_min_target_rri == pytest.approx(0.1)
    assert summary.candidate_mean_target_rri == pytest.approx(0.2)
    assert summary.candidate_max_target_rri == pytest.approx(0.3)


def test_candidate_rri_summary_all_invalid_has_no_fake_low_rri() -> None:
    summary = _candidate_rri_summary(
        target_rri=np.asarray([np.nan, np.nan], dtype=np.float32),
        scene_rri=np.asarray([np.nan, np.nan], dtype=np.float32),
        probabilities=np.asarray([0.0, 0.0], dtype=np.float32),
        entropy=float("nan"),
        valid_mask=np.asarray([False, False]),
        selected_mask=np.asarray([False, False]),
        top_k=5,
    )

    assert summary.valid_candidate_count == 0
    assert summary.top_candidate_target_rri == ()
    assert np.isnan(summary.candidate_min_target_rri)
    assert np.isnan(summary.candidate_mean_target_rri)
    assert np.isnan(summary.candidate_max_target_rri)
    assert np.isnan(summary.selected_target_rri)


def test_rollout_plot_entropy_uses_canonical_policy_audit(tmp_path: Path) -> None:
    store_dir = _fixture_rollout_store(tmp_path)
    from aria_nbv.rollouts import RolloutZarrStoreReader

    reader = RolloutZarrStoreReader(store_dir)
    step = rollout_steps(reader, rollout_at(reader, 0))[0]
    payload = _plot_step_payload(step, candidate_top_k=5)
    expected = candidate_policy_entropy(
        torch.from_numpy(step.selection_probabilities),
        torch.from_numpy(step.actor_action_mask),
    )

    assert payload.selected_entropy == pytest.approx(float(expected.item()))


def test_rollout_zarr_logger_logs_matching_static_context(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Auto context should reuse the normal VIN sample logger when rollout lineage resolves."""

    store_dir = _fixture_rollout_store(tmp_path)
    cfg = RerunOfflineInspectorConfig()
    cfg.output.save_path = tmp_path / "rollout.rrd"
    fake = _FakeRerun()
    calls: list[tuple[str, object]] = []

    monkeypatch.setattr(
        "aria_nbv.rerun_inspector._rollout_zarr.select_rerun_sample",
        lambda **kwargs: (
            calls.append(("select", kwargs["selection"]))
            or type("Selected", (), {"sample": object(), "description": "scene_id=fixture_box snippet_id=smoke"})()
        ),
    )
    monkeypatch.setattr(
        "aria_nbv.rerun_inspector._rollout_zarr.collect_visual_inventory",
        lambda sample: calls.append(("inventory", sample)) or object(),
    )
    monkeypatch.setattr(
        "aria_nbv.rerun_inspector._rollout_zarr.validate_required_inventory",
        lambda config, inventory: calls.append(("validate", inventory)),
    )

    class _FakeOfflineLogger:
        def __init__(
            self,
            config: RerunOfflineInspectorConfig,
            *,
            rr_module: object | None = None,
            target_obb_hint: str | None = None,
        ) -> None:
            del target_obb_hint
            calls.append(("logger_init", rr_module))

        def log_sample(self, *, sample: object, inventory: object, selection: str) -> None:
            calls.append(("log_sample", selection))

        def log_metadata(self, *, sample: object, inventory: object, selection: str) -> None:
            calls.append(("log_metadata", selection))

    monkeypatch.setattr("aria_nbv.rerun_inspector._rollout_zarr.RerunOfflineLogger", _FakeOfflineLogger)

    logger = RerunRolloutZarrLogger(cfg, rr_module=fake)
    logger.start()
    logger.log_store(store_dir=store_dir, rollout_index=0)

    assert [name for name, _ in calls] == [
        "select",
        "inventory",
        "validate",
        "logger_init",
        "log_sample",
        "log_metadata",
    ]
    selection = calls[0][1]
    assert selection.scene_id == "fixture_box"
    assert selection.snippet_id == "smoke"


def test_rollout_zarr_logger_required_context_uses_rollout_lineage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Required context should use rollout scene/snippet lineage when no explicit selector is set."""

    store_dir = _fixture_rollout_store(tmp_path)
    cfg = RerunOfflineInspectorConfig()
    cfg.output.save_path = tmp_path / "rollout.rrd"
    cfg.selection.rollout_context_mode = "required"
    cfg.selection.split = "val"
    cfg.selection.index = 3
    fake = _FakeRerun()
    calls: list[tuple[str, object]] = []

    monkeypatch.setattr(
        "aria_nbv.rerun_inspector._rollout_zarr.select_rerun_sample",
        lambda **kwargs: (
            calls.append(("select", kwargs["selection"]))
            or type("Selected", (), {"sample": object(), "description": "split=val index=3"})()
        ),
    )
    monkeypatch.setattr(
        "aria_nbv.rerun_inspector._rollout_zarr.collect_visual_inventory",
        lambda sample: object(),
    )
    monkeypatch.setattr(
        "aria_nbv.rerun_inspector._rollout_zarr.validate_required_inventory",
        lambda config, inventory: None,
    )

    class _FakeOfflineLogger:
        def __init__(
            self,
            config: RerunOfflineInspectorConfig,
            *,
            rr_module: object | None = None,
            target_obb_hint: str | None = None,
        ) -> None:
            del config, rr_module, target_obb_hint

        def log_sample(self, *, sample: object, inventory: object, selection: str) -> None:
            calls.append(("log_sample", selection))

        def log_metadata(self, *, sample: object, inventory: object, selection: str) -> None:
            calls.append(("log_metadata", selection))

    monkeypatch.setattr("aria_nbv.rerun_inspector._rollout_zarr.RerunOfflineLogger", _FakeOfflineLogger)

    logger = RerunRolloutZarrLogger(cfg, rr_module=fake)
    logger.start()
    logger.log_store(store_dir=store_dir, rollout_index=0)

    assert [name for name, _ in calls] == ["select", "log_sample", "log_metadata"]
    selection = calls[0][1]
    assert selection.scene_id == "fixture_box"
    assert selection.snippet_id == "smoke"


def test_minimal_layer_policy_excludes_candidates_depth_and_scalars(tmp_path: Path) -> None:
    """Excluded groups must not create entities in the saved recording."""

    store_dir = _fixture_rollout_store(tmp_path)
    cfg = RerunOfflineInspectorConfig()
    cfg.selection.rollout_context_mode = "off"
    cfg.rollout_layers = resolve_rollout_layer_config("Minimal selected path")
    fake = _FakeRerun()

    rows = RerunRolloutZarrLogger(cfg, rr_module=fake).log_store(store_dir=store_dir, rollout_index=0)

    chain_root = f"{ENTITY_ROLLOUT_ROOT}/rollout_{rows.rollout_row_id:06d}/chain_{rows.chain_id:06d}"
    assert f"{chain_root}/selected_path" in fake.logged
    assert f"{chain_root}/target/center" in fake.logged
    assert not any("/candidate_shell_" in path for path in fake.logged)
    assert not any("/depth" in path or "/points" in path for path in fake.logged)
    assert not any(path.startswith(ENTITY_ROLLOUT_RRI_ROOT) for path in fake.logged)
    assert not any(path.startswith(ENTITY_ROLLOUT_DIAGNOSTICS_ROOT) for path in fake.logged)


def test_included_hidden_candidates_are_blueprint_hidden_and_invalid_are_absent(tmp_path: Path) -> None:
    """Inclusion controls logging while visibility controls only the blueprint."""

    store_dir = _fixture_rollout_store(tmp_path)
    cfg = RerunOfflineInspectorConfig()
    cfg.selection.rollout_context_mode = "off"
    cfg.rollout_layers = resolve_rollout_layer_config(
        "Candidate debugging",
        {
            "rollout_candidates": {"included": True, "visible": False},
            "invalid_candidates": {"included": False, "visible": False},
        },
    )
    fake = _FakeRerun()

    rows = RerunRolloutZarrLogger(cfg, rr_module=fake).log_store(store_dir=store_dir, rollout_index=0)

    chain_root = f"{ENTITY_ROLLOUT_ROOT}/rollout_{rows.rollout_row_id:06d}/chain_{rows.chain_id:06d}"
    assert any(f"{chain_root}/step_" in path and "/valid/" in path for path in fake.logged)
    assert not any(f"{chain_root}/step_" in path and "/invalid/" in path for path in fake.logged)
    overrides = _world_view_overrides_from_blueprint(fake.blueprints[-1])
    assert any(path.startswith(f"/{chain_root}/step_") and path.endswith("/valid") for path in overrides)
