"""Rerun logger tests using a fake rerun module."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import numpy as np
import torch
from efm3d.aria.aria_constants import ARIA_SNIPPET_T_WORLD_SNIPPET
from efm3d.aria.pose import PoseTW
from pytorch3d.renderer.cameras import PerspectiveCameras

from aria_nbv.data_handling.vin_store.views import VinSnippetView
from aria_nbv.rerun_inspector._blueprint import log_default_inspector_blueprint
from aria_nbv.rerun_inspector._colors import TARGET_OBB_RGBA
from aria_nbv.rerun_inspector._config import RerunOfflineInspectorConfig
from aria_nbv.rerun_inspector._entities import (
    ENTITY_CANDIDATE_ROOT,
    ENTITY_DEPTH_KEYFRAMES,
    ENTITY_DETECTED_OBBS,
    ENTITY_EFM_VOXEL_EXTENT,
    ENTITY_EFM_VOXELS,
    ENTITY_GT_OBBS,
    ENTITY_MESH,
    ENTITY_METADATA_SAMPLE,
    ENTITY_REFERENCE_POSE,
    ENTITY_RGB_KEYFRAMES,
    ENTITY_SEMIDENSE,
    ENTITY_TRAJECTORY,
    ENTITY_WORLD,
)
from aria_nbv.rerun_inspector._loggers import (
    RerunOfflineLogger,
    _snippet_t_world_snippet,
)
from aria_nbv.rerun_inspector._metadata import OfflineVisualInventory, normalize_visual_inventory


class _Archetype:
    """Simple fake Rerun archetype that stores constructor data."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.args = args
        self.kwargs = kwargs


class _FakeRerun:
    """Fake subset of the Rerun module used by the inspector."""

    Points3D = _Archetype
    LineStrips3D = _Archetype
    Boxes3D = _Archetype
    AnyValues = _Archetype
    TextDocument = _Archetype
    Scalars = _Archetype
    Transform3D = _Archetype
    Mesh3D = _Archetype
    Image = _Archetype
    DepthImage = _Archetype
    Pinhole = _Archetype

    class ViewCoordinates:
        """Fake Rerun view-coordinate constants."""

        RIGHT_HAND_Z_UP = _Archetype("RIGHT_HAND_Z_UP")
        LUF = "LUF"

    class TransformRelation:
        """Fake Rerun transform-relation constants."""

        ParentFromChild = "ParentFromChild"

    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.logged: dict[str, _Archetype] = {}
        self.logged_extras: dict[str, tuple[Any, ...]] = {}
        self.logged_kwargs: dict[str, dict[str, Any]] = {}

    def init(self, *args: Any, **kwargs: Any) -> None:
        self.calls.append(("init", args, kwargs))

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.calls.append(("save", args, kwargs))

    def spawn(self, *args: Any, **kwargs: Any) -> None:
        self.calls.append(("spawn", args, kwargs))

    def connect_grpc(self, *args: Any, **kwargs: Any) -> None:
        self.calls.append(("connect_grpc", args, kwargs))

    def log(self, entity_path: str, entity: _Archetype, *args: Any, **kwargs: Any) -> None:
        self.calls.append(("log", entity_path, args, kwargs))
        self.logged[entity_path] = entity
        self.logged_extras[entity_path] = args
        self.logged_kwargs[entity_path] = kwargs

    def set_time_sequence(self, *args: Any, **kwargs: Any) -> None:
        self.calls.append(("set_time_sequence", args, kwargs))


class _FakeBlueprintRerun(_FakeRerun):
    """Fake Rerun module that captures blueprint payloads."""

    def __init__(self) -> None:
        super().__init__()
        self.blueprints: list[object] = []

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


def _poses(translations: list[list[float]]) -> PoseTW:
    """Build a PoseTW batch from identity rotations and translations."""

    t = torch.tensor(translations, dtype=torch.float32)
    r = torch.eye(3, dtype=torch.float32).expand(t.shape[0], 3, 3)
    return PoseTW.from_Rt(r, t)


def _sample(
    num_points: int = 24,
    *,
    candidate_count: int = 3,
    validity: list[bool] | None = None,
) -> SimpleNamespace:
    """Build a minimal VinOfflineSample-like object."""

    semidense = torch.arange(num_points * 3, dtype=torch.float32).reshape(num_points, 3)
    candidate_points = torch.arange(3 * 5 * 3, dtype=torch.float32).reshape(3, 5, 3)
    mask_valid = torch.tensor([True, False, True] if validity is None else validity)
    return SimpleNamespace(
        sample_key="sample-0",
        scene_id="scene",
        snippet_id="snippet",
        vin_snippet=SimpleNamespace(
            points_world=semidense,
            lengths=torch.tensor([num_points]),
            t_world_rig=_poses([[0.0, 0.0, 0.0], [0.5, 0.0, 0.0], [1.0, 0.0, 0.0]]),
            t_world_snippet=_poses([[0.0, 0.0, 0.0]]),
        ),
        reference_pose_world_rig=_poses([[0.25, 0.5, 0.75]]),
        oracle=SimpleNamespace(
            candidate_poses_world_cam=_poses([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0]]),
            candidate_count=candidate_count,
            rri=torch.tensor([0.1, 0.9, 0.3], dtype=torch.float32),
            p3d_cameras=PerspectiveCameras(
                R=torch.eye(3, dtype=torch.float32).expand(3, 3, 3).clone(),
                T=torch.zeros(3, 3, dtype=torch.float32),
                focal_length=torch.full((3, 2), 2.0, dtype=torch.float32),
                principal_point=torch.full((3, 2), 2.0, dtype=torch.float32),
                image_size=torch.full((3, 2), 4.0, dtype=torch.float32),
                in_ndc=False,
            ),
        ),
        candidates=SimpleNamespace(mask_valid=mask_valid),
        candidate_pcs=SimpleNamespace(points=candidate_points, lengths=torch.tensor([3, 4, 5])),
        depths=SimpleNamespace(depths=torch.ones((3, 4, 4), dtype=torch.float32)),
        efm_snippet_view=None,
    )


def _obb_tensor(offset: float = 0.0, *, sem_id: int = 0, inst_id: int = 1, prob: float = 0.8) -> torch.Tensor:
    """Build one EFM-layout OBB tensor for line-strip logging."""

    data = torch.full((1, 34), -1.0, dtype=torch.float32)
    data[0, :6] = torch.tensor([-0.5, 0.5, -0.25, 0.25, -0.1, 0.9], dtype=torch.float32)
    data[0, 18:27] = torch.eye(3, dtype=torch.float32).reshape(-1)
    data[0, 27:30] = torch.tensor([offset, 0.0, 0.0], dtype=torch.float32)
    data[0, 30] = float(sem_id)
    data[0, 31] = float(inst_id)
    data[0, 32] = float(prob)
    return data


def _minimal_context_cfg() -> RerunOfflineInspectorConfig:
    """Return a config that logs semidense context without candidate/reference layers."""

    cfg = RerunOfflineInspectorConfig()
    cfg.primitives.log_reference_pose = False
    cfg.primitives.log_candidate_frusta = False
    cfg.primitives.log_top_oracle_frustum = False
    cfg.primitives.log_invalid_frusta = False
    cfg.primitives.log_candidate_centers = False
    return cfg


def test_rerun_snippet_gauge_uses_persisted_vin_pose_when_raw_efm_is_absent() -> None:
    """Rerun uses VIN's canonical gauge instead of the first rig trajectory pose."""

    snippet = VinSnippetView(
        points_world=torch.zeros((0, 4), dtype=torch.float32),
        lengths=torch.zeros((1,), dtype=torch.int64),
        t_world_rig=_poses([[99.0, 0.0, 0.0]]),
        t_world_snippet=_poses([[7.0, 0.0, 0.0]]),
    )
    sample = SimpleNamespace(vin_snippet=snippet, efm_snippet_view=None)

    gauge = _snippet_t_world_snippet(sample)

    assert gauge is not None
    assert tuple(gauge.tensor().shape) == (1, 12)
    assert gauge.tensor()[0, 9].item() == 7.0


def _minimal_candidate_cfg() -> RerunOfflineInspectorConfig:
    """Return a config for selected candidate/detail tests without context layers."""

    cfg = _minimal_context_cfg()
    cfg.primitives.log_semidense = False
    return cfg


def _minimal_keyframe_cfg() -> RerunOfflineInspectorConfig:
    """Return a config that logs only opt-in ASE keyframe media."""

    cfg = _minimal_candidate_cfg()
    cfg.primitives.log_rgb_keyframes = True
    cfg.primitives.log_depth_keyframes = True
    return cfg


def test_default_blueprint_hides_heavy_context_and_requested_world_subtrees() -> None:
    fake = _FakeBlueprintRerun()

    log_default_inspector_blueprint(
        fake,
        hidden_world_paths=(
            "world/rollout/rollout_000000/chain_000000/step_000/valid",
            "/world/rollout/rollout_000000/chain_000000/step_000/invalid",
        ),
    )

    assert len(fake.blueprints) == 1
    contents = _world_view_contents_from_blueprint(fake.blueprints[0])
    overrides = _world_view_overrides_from_blueprint(fake.blueprints[0])
    assert contents == ["+ /world/**"]
    assert all(not rule.startswith("- ") for rule in contents)
    assert f"/{ENTITY_CANDIDATE_ROOT}" in overrides
    assert f"/{ENTITY_EFM_VOXELS}" in overrides
    assert f"/{ENTITY_GT_OBBS}" in overrides
    assert "/world/rollout/rollout_000000/chain_000000/step_000/valid" in overrides
    assert "/world/rollout/rollout_000000/chain_000000/step_000/invalid" in overrides
    assert all(override.visible.as_arrow_array().to_pylist() == [False] for override in overrides.values())
    assert fake.calls[0][0] == "send_blueprint"
    assert fake.calls[0][2] == {"make_active": True, "make_default": True}


def test_logger_initializes_save_sink_before_logging(tmp_path) -> None:
    """Rerun 0.22.1 sink setup should happen before any entity log calls."""

    cfg = RerunOfflineInspectorConfig()
    cfg.output.save_path = tmp_path / "out.rrd"
    fake = _FakeRerun()
    logger = RerunOfflineLogger(cfg, rr_module=fake)

    logger.start()
    logger.log_sample(
        sample=_sample(),
        inventory=OfflineVisualInventory(has_candidate_validity=True, has_candidate_points=True),
        selection="split=val index=0",
    )
    logger.log_metadata(
        sample=_sample(),
        inventory=OfflineVisualInventory(has_candidate_validity=True, has_candidate_points=True),
        selection="split=val index=0",
    )

    assert [call[0] for call in fake.calls[:2]] == ["init", "save"]  # noqa: S101
    assert fake.calls[2][0:2] == ("log", ENTITY_WORLD)  # noqa: S101
    first_log = next(idx for idx, call in enumerate(fake.calls) if call[0] == "log")
    assert first_log > 1  # noqa: S101
    assert ENTITY_WORLD in fake.logged  # noqa: S101
    assert ENTITY_SEMIDENSE in fake.logged  # noqa: S101
    assert ENTITY_REFERENCE_POSE in fake.logged  # noqa: S101
    assert fake.logged[ENTITY_REFERENCE_POSE].kwargs["relation"] == "ParentFromChild"  # noqa: S101
    assert f"{ENTITY_CANDIDATE_ROOT}/valid/candidate_000/camera" in fake.logged  # noqa: S101
    assert f"{ENTITY_CANDIDATE_ROOT}/invalid/candidate_001/camera" in fake.logged  # noqa: S101
    assert f"{ENTITY_CANDIDATE_ROOT}/valid/candidate_002/camera" in fake.logged  # noqa: S101
    assert f"{ENTITY_CANDIDATE_ROOT}/valid/candidate_002/center" in fake.logged  # noqa: S101
    assert not any(path.startswith("metadata/candidates") for path in fake.logged)  # noqa: S101
    assert not any(path.startswith("plots/candidates") for path in fake.logged)  # noqa: S101
    assert ENTITY_METADATA_SAMPLE in fake.logged  # noqa: S101


def test_defaults_keep_candidate_point_clouds_opt_in() -> None:
    """Candidate point-cloud loading/logging should be disabled by default."""

    cfg = RerunOfflineInspectorConfig()

    assert not cfg.dataset.offline.load_candidate_pcs  # noqa: S101
    assert not cfg.primitives.log_candidate_points  # noqa: S101
    assert cfg.performance.max_semidense_points == 50_000  # noqa: S101
    assert cfg.performance.max_candidate_points == 20_000  # noqa: S101

    fake = _FakeRerun()
    RerunOfflineLogger(cfg, rr_module=fake).log_sample(
        sample=_sample(),
        inventory=OfflineVisualInventory(has_candidate_validity=True, has_candidate_points=True),
        selection="sample_key=sample-0",
    )
    assert not any(path.endswith("/points") for path in fake.logged)  # noqa: S101


def test_normalized_inventory_preserves_worker_b_diagnostics() -> None:
    """Worker-B warnings/errors/metadata should survive into Rerun metadata."""

    cfg = RerunOfflineInspectorConfig()
    worker_b_inventory = SimpleNamespace(
        has_semidense_points=True,
        has_candidate_mask=True,
        has_candidate_pcs=True,
        warnings=("candidate point clouds missing",),
        errors=("sample.oracle.rri missing",),
        metadata={"vin_snippet.valid_semidense_points": 42},
    )
    inventory = normalize_visual_inventory(worker_b_inventory)
    fake = _FakeRerun()

    RerunOfflineLogger(cfg, rr_module=fake).log_metadata(
        sample=_sample(),
        inventory=inventory,
        selection="sample_key=sample-0",
    )

    document = json.loads(fake.logged[ENTITY_METADATA_SAMPLE].args[0])
    details = document["inventory"]["details"]
    assert details["warnings"] == ["candidate point clouds missing"]  # noqa: S101
    assert details["errors"] == ["sample.oracle.rri missing"]  # noqa: S101
    assert details["metadata"]["vin_snippet.valid_semidense_points"] == 42  # noqa: S101


def test_metadata_compacts_old_ase_atek_identifiers() -> None:
    cfg = RerunOfflineInspectorConfig()
    sample = _sample()
    sample.sample_key = "81286::AriaSyntheticEnvironment_81286_AtekDataSample_000000"
    sample.scene_id = "81286"
    sample.snippet_id = "AriaSyntheticEnvironment_81286_AtekDataSample_000000"
    fake = _FakeRerun()

    RerunOfflineLogger(cfg, rr_module=fake).log_metadata(
        sample=sample,
        inventory=OfflineVisualInventory(),
        selection="scene_id=81286 snippet_id=AriaSyntheticEnvironment_81286_AtekDataSample_000000",
    )

    document = json.loads(fake.logged[ENTITY_METADATA_SAMPLE].args[0])
    assert document["sample"]["sample_key"] == "81286::ASE_81286_Atek_000000"  # noqa: S101
    assert document["sample"]["snippet_id"] == "ASE_81286_Atek_000000"  # noqa: S101
    assert "AriaSyntheticEnvironment" not in fake.logged[ENTITY_METADATA_SAMPLE].args[0]  # noqa: S101


def test_worker_b_candidate_pcs_semidense_flag_does_not_disable_required_semidense() -> None:
    """Worker-B candidate-pc semidense absence should not reject VIN semidense."""

    inventory = normalize_visual_inventory(
        {
            "has_semidense_points": False,
            "has_candidate_pcs": False,
            "metadata": {"vin_snippet.valid_semidense_points": 9},
        },
    )

    assert inventory.has_semidense  # noqa: S101
    assert not inventory.has_candidate_points  # noqa: S101
    assert inventory.details is not None  # noqa: S101
    assert inventory.details["candidate_pcs_has_semidense_points"] is False  # noqa: S101
    assert inventory.details["metadata"]["vin_snippet.valid_semidense_points"] == 9  # noqa: S101


def test_semidense_downsampling_is_deterministic(tmp_path) -> None:
    """Configured seed should make semidense downsampling repeatable."""

    cfg = _minimal_context_cfg()
    cfg.output.save_path = tmp_path / "out.rrd"
    cfg.performance.max_semidense_points = 8
    cfg.performance.seed = 123
    sample = _sample(num_points=80)

    fake_a = _FakeRerun()
    fake_b = _FakeRerun()
    RerunOfflineLogger(cfg, rr_module=fake_a).log_sample(
        sample=sample,
        inventory=OfflineVisualInventory(),
        selection="sample_key=sample-0",
    )
    RerunOfflineLogger(cfg, rr_module=fake_b).log_sample(
        sample=sample,
        inventory=OfflineVisualInventory(),
        selection="sample_key=sample-0",
    )

    points_a = np.asarray(fake_a.logged[ENTITY_SEMIDENSE].args[0])
    points_b = np.asarray(fake_b.logged[ENTITY_SEMIDENSE].args[0])
    assert points_a.shape == (8, 3)  # noqa: S101
    np.testing.assert_array_equal(points_a, points_b)


def test_semidense_logging_uses_valid_xyz_prefix() -> None:
    """VIN semidense logging should handle padded point features with extra channels."""

    cfg = _minimal_context_cfg()
    points = torch.arange(5 * 4, dtype=torch.float32).reshape(5, 4)
    sample = _sample()
    sample.vin_snippet = SimpleNamespace(points_world=points, lengths=torch.tensor([3]))
    fake = _FakeRerun()

    RerunOfflineLogger(cfg, rr_module=fake).log_sample(
        sample=sample,
        inventory=OfflineVisualInventory(),
        selection="sample_key=sample-0",
    )

    logged = np.asarray(fake.logged[ENTITY_SEMIDENSE].args[0])
    assert logged.shape == (3, 3)  # noqa: S101
    np.testing.assert_array_equal(logged, points[:3, :3].numpy())


def test_candidate_points_are_logged_only_when_inventory_reports_present() -> None:
    """Candidate point clouds are optional and gated by inventory."""

    cfg = _minimal_candidate_cfg()
    cfg.primitives.log_candidate_points = True
    sample = _sample()

    missing = _FakeRerun()
    RerunOfflineLogger(cfg, rr_module=missing).log_sample(
        sample=sample,
        inventory=OfflineVisualInventory(has_candidate_points=False),
        selection="sample_key=sample-0",
    )
    assert not any(path.endswith("/points") for path in missing.logged)  # noqa: S101

    present = _FakeRerun()
    RerunOfflineLogger(cfg, rr_module=present).log_sample(
        sample=sample,
        inventory=OfflineVisualInventory(has_candidate_points=True),
        selection="sample_key=sample-0",
    )
    assert f"{ENTITY_CANDIDATE_ROOT}/valid/candidate_002/points" in present.logged  # noqa: S101


def test_selected_candidate_index_overrides_detail_layers() -> None:
    """Explicit selected candidate index should control selected-only modalities."""

    cfg = _minimal_candidate_cfg()
    cfg.candidate.selected_index = 0
    cfg.primitives.log_candidate_points = True
    cfg.primitives.log_candidate_depths = True
    sample = _sample()
    fake = _FakeRerun()

    RerunOfflineLogger(cfg, rr_module=fake).log_sample(
        sample=sample,
        inventory=OfflineVisualInventory(has_candidate_points=True, has_candidate_depths=True),
        selection="sample_key=sample-0",
    )

    assert f"{ENTITY_CANDIDATE_ROOT}/valid/candidate_000/points" in fake.logged  # noqa: S101
    assert f"{ENTITY_CANDIDATE_ROOT}/valid/candidate_000/camera/depth" in fake.logged  # noqa: S101
    assert f"{ENTITY_CANDIDATE_ROOT}/valid/candidate_002/points" not in fake.logged  # noqa: S101


def test_zero_candidate_samples_log_no_candidate_layers() -> None:
    """A no-candidate sample should not visualize padded candidate poses."""

    cfg = _minimal_candidate_cfg()
    sample = _sample(candidate_count=0, validity=[False, False, False])
    fake = _FakeRerun()

    RerunOfflineLogger(cfg, rr_module=fake).log_sample(
        sample=sample,
        inventory=OfflineVisualInventory(has_candidate_validity=True),
        selection="sample_key=sample-0",
    )

    assert not any(path.startswith(ENTITY_CANDIDATE_ROOT) for path in fake.logged)  # noqa: S101


def test_all_invalid_candidates_do_not_log_top_oracle_frustum() -> None:
    """Top-oracle visualization should be omitted when every candidate is invalid."""

    cfg = _minimal_candidate_cfg()
    cfg.primitives.log_candidate_frusta = True
    sample = _sample(validity=[False, False, False])
    fake = _FakeRerun()

    RerunOfflineLogger(cfg, rr_module=fake).log_sample(
        sample=sample,
        inventory=OfflineVisualInventory(has_candidate_validity=True),
        selection="sample_key=sample-0",
    )

    assert f"{ENTITY_CANDIDATE_ROOT}/invalid/candidate_000/camera" in fake.logged  # noqa: S101
    assert f"{ENTITY_CANDIDATE_ROOT}/invalid/candidate_001/camera" in fake.logged  # noqa: S101
    assert f"{ENTITY_CANDIDATE_ROOT}/invalid/candidate_002/camera" in fake.logged  # noqa: S101
    assert not any(path.endswith("/center") for path in fake.logged)  # noqa: S101


def test_compact_modalities_log_to_stable_entity_paths() -> None:
    """Compact OBBs, trajectory, and candidate depths should have fixed Rerun paths."""

    cfg = _minimal_candidate_cfg()
    cfg.primitives.log_candidate_depths = True
    sample = _sample()
    sample.gt_obbs = SimpleNamespace(obbs=_obb_tensor(0.0))
    sample.detected_obbs = SimpleNamespace(obbs=_obb_tensor(1.0))
    sample.trajectory = SimpleNamespace(time_ns=torch.tensor([100, 200, 300], dtype=torch.int64))
    fake = _FakeRerun()

    RerunOfflineLogger(cfg, rr_module=fake).log_sample(
        sample=sample,
        inventory=OfflineVisualInventory(
            has_gt_obbs=True,
            has_detected_obbs=True,
            has_trajectory=True,
            has_candidate_depths=True,
        ),
        selection="sample_key=sample-0",
    )

    assert ENTITY_GT_OBBS in fake.logged  # noqa: S101
    assert ENTITY_DETECTED_OBBS in fake.logged  # noqa: S101
    assert ENTITY_TRAJECTORY in fake.logged  # noqa: S101
    invalid_raw_top_path = f"{ENTITY_CANDIDATE_ROOT}/invalid/candidate_001/camera"
    camera_path = f"{ENTITY_CANDIDATE_ROOT}/valid/candidate_002/camera"
    depth_path = f"{ENTITY_CANDIDATE_ROOT}/valid/candidate_002/camera/depth"
    first_path = f"{ENTITY_CANDIDATE_ROOT}/valid/candidate_000/camera"
    assert first_path not in fake.logged  # noqa: S101
    assert depth_path in fake.logged  # noqa: S101
    assert invalid_raw_top_path not in fake.logged  # noqa: S101
    assert fake.logged[camera_path].kwargs["relation"] == "ParentFromChild"  # noqa: S101
    assert fake.logged_extras[camera_path][0].kwargs["camera_xyz"] == "LUF"  # noqa: S101
    assert fake.logged[depth_path].kwargs["meter"] == 1.0  # noqa: S101
    assert np.asarray(fake.logged[ENTITY_GT_OBBS].kwargs["centers"]).shape == (1, 3)  # noqa: S101
    assert (
        fake.logged[ENTITY_GT_OBBS].kwargs["colors"][0][:3] != fake.logged[ENTITY_DETECTED_OBBS].kwargs["colors"][0][:3]
    )  # noqa: E501, S101


def test_mesh_logging_uses_mesh3d_with_configured_alpha() -> None:
    """GT mesh should use Rerun Mesh3D with configured albedo alpha."""

    cfg = _minimal_candidate_cfg()
    cfg.geometry.mesh_alpha = 48
    sample = _sample()
    sample.efm_snippet_view = SimpleNamespace(
        mesh_verts=torch.tensor([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], dtype=torch.float32),
        mesh_faces=torch.tensor([[0, 1, 2]], dtype=torch.int64),
    )
    fake = _FakeRerun()

    RerunOfflineLogger(cfg, rr_module=fake).log_sample(
        sample=sample,
        inventory=OfflineVisualInventory(has_mesh=True),
        selection="sample_key=sample-0",
    )

    assert ENTITY_MESH in fake.logged  # noqa: S101
    np.testing.assert_array_equal(
        fake.logged[ENTITY_MESH].kwargs["vertex_positions"], sample.efm_snippet_view.mesh_verts
    )
    np.testing.assert_array_equal(
        fake.logged[ENTITY_MESH].kwargs["triangle_indices"],
        sample.efm_snippet_view.mesh_faces.to(dtype=torch.uint32),
    )
    assert fake.logged[ENTITY_MESH].kwargs["albedo_factor"] == [130, 138, 150, 48]  # noqa: S101


def test_obbs_are_transformed_from_snippet_to_world_before_logging() -> None:
    """Snippet-frame OBB payloads should be drawn under world after applying T_world_snippet."""

    cfg = _minimal_candidate_cfg()
    sample = _sample()
    sample.gt_obbs = SimpleNamespace(obbs=_obb_tensor(0.0))
    sample.efm_snippet_view = SimpleNamespace(efm={ARIA_SNIPPET_T_WORLD_SNIPPET: _poses([[10.0, 0.0, 0.0]])})
    fake = _FakeRerun()

    RerunOfflineLogger(cfg, rr_module=fake).log_sample(
        sample=sample,
        inventory=OfflineVisualInventory(has_gt_obbs=True),
        selection="sample_key=sample-0",
    )

    centers = np.asarray(fake.logged[ENTITY_GT_OBBS].kwargs["centers"], dtype=np.float32)
    assert np.allclose(centers[0], np.asarray([10.0, 0.0, 0.4], dtype=np.float32))  # noqa: S101


def test_obb_labels_include_class_names_and_unknown_fallback() -> None:
    """GT and detected OBB labels should expose class names when maps exist."""

    cfg = _minimal_candidate_cfg()
    sample = _sample()
    sample.gt_obbs = SimpleNamespace(
        obbs=_obb_tensor(0.0, sem_id=28, inst_id=8, prob=0.7),
        sem_id_to_name={28: "window"},
    )
    sample.detected_obbs = SimpleNamespace(
        obbs=_obb_tensor(1.0, sem_id=99, inst_id=2, prob=0.4),
        sem_id_to_name={0: "table"},
    )
    fake = _FakeRerun()

    RerunOfflineLogger(cfg, rr_module=fake, target_obb_hint="inst_id=8").log_sample(
        sample=sample,
        inventory=OfflineVisualInventory(has_gt_obbs=True, has_detected_obbs=True),
        selection="sample_key=sample-0",
    )

    gt_label = fake.logged[ENTITY_GT_OBBS].kwargs["labels"][0]
    detected_labels = fake.logged_extras[ENTITY_DETECTED_OBBS][0].kwargs["obb_label"]
    assert gt_label == "class=window | sem_id=28 | inst_id=8 | prob=0.700"  # noqa: S101
    assert detected_labels == ["class=<unknown> | sem_id=99 | inst_id=2 | prob=0.400"]  # noqa: S101
    assert "labels" not in fake.logged[ENTITY_DETECTED_OBBS].kwargs  # noqa: S101
    assert fake.logged[ENTITY_GT_OBBS].kwargs["colors"][0] == TARGET_OBB_RGBA.tolist()  # noqa: S101
    assert fake.logged_extras[ENTITY_GT_OBBS][0].kwargs["obb_is_target"] == [True]  # noqa: S101


def test_target_obb_hint_accepts_rollout_target_id_tokens() -> None:
    """Rollout target ids use compact ``sem=...`` and ``inst=...`` tokens."""

    cfg = _minimal_candidate_cfg()
    sample = _sample()
    sample.gt_obbs = SimpleNamespace(
        obbs=_obb_tensor(0.0, sem_id=28, inst_id=34, prob=1.0),
        sem_id_to_name={},
    )
    fake = _FakeRerun()

    RerunOfflineLogger(
        cfg,
        rr_module=fake,
        target_obb_hint="scene:snippet:gt_obbs:sem=28:inst=34:idx=0",
    ).log_sample(
        sample=sample,
        inventory=OfflineVisualInventory(has_gt_obbs=True),
        selection="sample_key=sample-0",
    )

    assert fake.logged_extras[ENTITY_GT_OBBS][0].kwargs["obb_is_target"] == [True]  # noqa: S101


def test_efm_voxel_fields_log_thresholded_points() -> None:
    """Curated EFM voxel fields should map tensor axes as D->z, H->y, W->x."""

    cfg = _minimal_candidate_cfg()
    cfg.efm_voxels.log_occ_pr = True
    cfg.efm_voxels.occ_threshold = 0.5
    cfg.efm_voxels.cent_threshold = 0.5
    cfg.efm_voxels.cent_nms_threshold = 0.5
    cfg.efm_voxels.max_points_per_field = 10
    field = torch.zeros((1, 1, 2, 3, 4), dtype=torch.float32)
    field[0, 0, 0, 1, 3] = 0.9
    field[0, 0, 1, 2, 0] = 0.7
    sample = _sample()
    sample.backbone_out = SimpleNamespace(
        t_world_voxel=_poses([[1.0, 2.0, 3.0]]),
        voxel_extent=torch.tensor([10.0, 18.0, 20.0, 26.0, 30.0, 34.0], dtype=torch.float32),
        occ_pr=field,
        cent_pr=field,
        cent_pr_nms=field,
    )
    fake = _FakeRerun()

    RerunOfflineLogger(cfg, rr_module=fake).log_sample(
        sample=sample,
        inventory=OfflineVisualInventory(),
        selection="sample_key=sample-0",
    )

    for name in ("occ_pr", "cent_pr", "cent_pr_nms"):
        entity = f"{ENTITY_EFM_VOXELS}/{name}"
        assert entity in fake.logged  # noqa: S101
        np.testing.assert_allclose(
            np.asarray(fake.logged[entity].args[0]),
            np.asarray([[18.0, 25.0, 34.0], [12.0, 27.0, 36.0]], dtype=np.float32),
        )
    assert ENTITY_EFM_VOXEL_EXTENT in fake.logged  # noqa: S101


def test_efm_voxel_extent_logs_posed_native_box() -> None:
    """The EFM voxel extent should be logged as a world-space oriented box."""

    cfg = _minimal_candidate_cfg()
    cfg.efm_voxels.log_occ_pr = False
    cfg.efm_voxels.log_cent_pr = False
    cfg.efm_voxels.log_cent_pr_nms = False
    sample = _sample()
    sample.backbone_out = SimpleNamespace(
        t_world_voxel=_poses([[1.0, 2.0, 3.0]]),
        voxel_extent=torch.tensor([0.0, 2.0, -2.0, 2.0, 4.0, 8.0], dtype=torch.float32),
    )
    fake = _FakeRerun()

    RerunOfflineLogger(cfg, rr_module=fake).log_sample(
        sample=sample,
        inventory=OfflineVisualInventory(),
        selection="sample_key=sample-0",
    )

    box = fake.logged[ENTITY_EFM_VOXEL_EXTENT]
    assert fake.logged_extras[ENTITY_EFM_VOXEL_EXTENT] == ()  # noqa: S101
    np.testing.assert_allclose(np.asarray(box.kwargs["centers"]), np.asarray([[2.0, 2.0, 9.0]], dtype=np.float32))
    np.testing.assert_allclose(np.asarray(box.kwargs["half_sizes"]), np.asarray([[1.0, 2.0, 2.0]], dtype=np.float32))
    np.testing.assert_allclose(
        np.asarray(box.kwargs["quaternions"]), np.asarray([[0.0, 0.0, 0.0, 1.0]], dtype=np.float32)
    )


def test_ase_keyframes_are_rotated_and_logged_under_camera_entities() -> None:
    """ASE image/depth keyframes should use display CW90 camera media paths."""

    cfg = _minimal_keyframe_cfg()
    image = torch.tensor(
        [
            [
                [[0.0, 0.5, 1.0], [0.25, 0.75, 1.0]],
                [[0.0, 0.5, 1.0], [0.25, 0.75, 1.0]],
                [[0.0, 0.5, 1.0], [0.25, 0.75, 1.0]],
            ]
        ],
        dtype=torch.float32,
    )
    depth = torch.tensor([[[[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]]], dtype=torch.float32)
    camera = SimpleNamespace(images=image, distance_m=depth)
    sample = _sample()
    sample.efm_snippet_view = SimpleNamespace(camera_rgb=camera)
    camera_tw = SimpleNamespace(
        size=torch.tensor([[3.0, 2.0]], dtype=torch.float32),
        f=torch.tensor([[2.0, 2.0]], dtype=torch.float32),
        c=torch.tensor([[1.5, 1.0]], dtype=torch.float32),
    )
    fake = _FakeRerun()
    logger = RerunOfflineLogger(cfg, rr_module=fake)
    logger._live_keyframe_contexts = lambda sample, frame_indices: [(0, _poses([[0.0, 0.0, 0.0]]), camera_tw)]  # type: ignore[method-assign]

    logger.log_sample(
        sample=sample,
        inventory=OfflineVisualInventory(has_rgb_keyframes=True, has_depth_keyframes=True),
        selection="sample_key=sample-0",
    )

    camera_path = f"{ENTITY_RGB_KEYFRAMES}/frame_000/camera"
    image_path = f"{camera_path}/image"
    depth_path = f"{camera_path}/depth"
    assert camera_path in fake.logged  # noqa: S101
    assert image_path in fake.logged  # noqa: S101
    assert depth_path in fake.logged  # noqa: S101
    assert not any(path.startswith("media/ase") for path in fake.logged)  # noqa: S101
    assert np.asarray(fake.logged[image_path].args[0]).shape == (3, 2, 3)  # noqa: S101
    np.testing.assert_array_equal(
        np.asarray(fake.logged[depth_path].args[0]),
        np.asarray([[4.0, 1.0], [5.0, 2.0], [6.0, 3.0]], dtype=np.float32),
    )


def test_missing_keyframe_context_is_reported_in_metadata() -> None:
    """Requested live keyframes should not become orphan images without camera context."""

    cfg = _minimal_keyframe_cfg()
    sample = _sample()
    fake = _FakeRerun()
    logger = RerunOfflineLogger(cfg, rr_module=fake)

    logger.log_sample(
        sample=sample,
        inventory=OfflineVisualInventory(has_rgb_keyframes=True, has_depth_keyframes=True),
        selection="sample_key=sample-0",
    )
    logger.log_metadata(
        sample=sample,
        inventory=OfflineVisualInventory(has_rgb_keyframes=True, has_depth_keyframes=True),
        selection="sample_key=sample-0",
    )

    document = json.loads(fake.logged[ENTITY_METADATA_SAMPLE].args[0])
    assert not any(path.startswith(ENTITY_RGB_KEYFRAMES) for path in fake.logged)  # noqa: S101
    assert not any(path.startswith(ENTITY_DEPTH_KEYFRAMES) for path in fake.logged)  # noqa: S101
    assert "RGB keyframes skipped: sample has no attached EFM snippet." in document["runtime_warnings"]  # noqa: S101
    assert "Depth keyframes skipped: sample has no attached EFM snippet." in document["runtime_warnings"]  # noqa: S101
