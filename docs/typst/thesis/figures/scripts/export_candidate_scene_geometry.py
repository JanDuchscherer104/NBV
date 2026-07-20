#!/usr/bin/env python3
"""Export a pinned ASE finite-candidate scene as raster bases plus vector geometry.

The dense ASE mesh is rendered with Open3D's z-buffer. Camera trajectories,
wire frusta, the target OBB, candidate centres, validity, and the selected path
are exported as projected 2D coordinates for editable CeTZ overlays.

Run from the repository root with the package environment::

    EGL_PLATFORM=surfaceless \
    PYTHONPATH=aria_nbv \
    aria_nbv/.venv/bin/python \
      docs/typst/thesis/figures/scripts/export_candidate_scene_geometry.py

The camera-frustum primitive uses the conventional five-vertex wire topology
(one optical centre, four image-plane corners, four perimeter edges, and four
corner rays). Its topology is adapted from Viser's Apache-2.0 implementation:
https://github.com/nerfstudio-project/viser/blob/main/src/viser/client/src/CameraFrustumVariants.tsx
Open3D exposes the same scientific role through
``LineSet.create_camera_visualization``. We deliberately retain wire geometry
only: no opaque frustum faces hide the scene or imply evidence volume.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import open3d as o3d

from aria_nbv.configs import PathConfig
from aria_nbv.data_handling.offline.dataset import (
    VinOfflineDataset,
    VinOfflineDatasetConfig,
)
from aria_nbv.data_handling.offline.store import VinOfflineStoreConfig
from aria_nbv.rollouts.zarr_store import RolloutZarrStoreReader


ROLLOUT_ROW = 73
STEP_ROW = 121
TARGET_ROW = 12
SELECTED_SHELL = 47
SOURCE_SAMPLE_INDEX = 35
SCENE_ID = "81286"
SNIPPET_ID = "AriaSyntheticEnvironment_81286_AtekDataSample_000035"
RENDER_WIDTH_PX = 1500
RENDER_HEIGHT_PX = 920
OBLIQUE_VERTICAL_FOV_DEG = 35.0
OBLIQUE_NEAR_M = 0.1
OBLIQUE_FAR_M = 35.0
OBLIQUE_CENTRE_WORLD = (-7.55, -8.82, 1.05)
OBLIQUE_EYE_WORLD = (-0.15, -17.02, 6.85)
TOP_CENTRE_WORLD = (-8.10, -8.90, 0.75)
TOP_EYE_WORLD = (-8.10, -8.90, 14.75)
TOP_HALF_WIDTH_M = 3.90
TOP_HALF_HEIGHT_M = TOP_HALF_WIDTH_M / (RENDER_WIDTH_PX / RENDER_HEIGHT_PX)
TOP_NEAR_M = 0.1
TOP_FAR_M = 30.0

FRUSTUM_LOCAL = np.asarray(
    [
        [0.0, 0.0, 0.0],
        [-0.60, -0.45, 1.0],
        [0.60, -0.45, 1.0],
        [0.60, 0.45, 1.0],
        [-0.60, 0.45, 1.0],
    ],
    dtype=np.float64,
)
FRUSTUM_EDGES = ((1, 2), (2, 3), (3, 4), (4, 1), (0, 1), (0, 2), (0, 3), (0, 4))
BOX_EDGES = (
    (0, 1),
    (1, 3),
    (3, 2),
    (2, 0),
    (4, 5),
    (5, 7),
    (7, 6),
    (6, 4),
    (0, 4),
    (1, 5),
    (2, 6),
    (3, 7),
)


@dataclass(frozen=True)
class Projection:
    """Fixed render plus its world-to-panel transform."""

    view: np.ndarray
    projection: np.ndarray
    width_px: int
    height_px: int

    def points(self, points_world: np.ndarray) -> list[list[float]]:
        """Project world points to normalized panel coordinates with y upwards."""

        points = np.asarray(points_world, dtype=np.float64).reshape(-1, 3)
        homogeneous = np.concatenate([points, np.ones((points.shape[0], 1))], axis=1)
        clip = (self.projection @ self.view @ homogeneous.T).T
        ndc = clip[:, :3] / clip[:, 3:4]
        panel = np.column_stack(((ndc[:, 0] + 1.0) / 2.0, (ndc[:, 1] + 1.0) / 2.0))
        return np.round(panel, 7).tolist()


def _pose_parts(pose12: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    pose = np.asarray(pose12, dtype=np.float64).reshape(12)
    return pose[:9].reshape(3, 3), pose[9:12]


def _pose_matrix(pose12: np.ndarray) -> np.ndarray:
    rotation, translation = _pose_parts(pose12)
    matrix = np.eye(4, dtype=np.float64)
    matrix[:3, :3] = rotation
    matrix[:3, 3] = translation
    return matrix


def _matrix_pose(matrix: np.ndarray) -> np.ndarray:
    return np.concatenate([matrix[:3, :3].reshape(9), matrix[:3, 3]])


def _frustum_points_world(pose12: np.ndarray, *, scale_m: float) -> np.ndarray:
    rotation, translation = _pose_parts(pose12)
    return (rotation @ (FRUSTUM_LOCAL * scale_m).T).T + translation


def _segments(
    points: np.ndarray, edges: tuple[tuple[int, int], ...]
) -> list[np.ndarray]:
    return [points[np.asarray(edge)] for edge in edges]


def _obb_corners(pose12: np.ndarray, extents: np.ndarray) -> np.ndarray:
    rotation, translation = _pose_parts(pose12)
    half = np.asarray(extents, dtype=np.float64) / 2.0
    local = np.asarray(
        [
            [sx * half[0], sy * half[1], sz * half[2]]
            for sz in (-1.0, 1.0)
            for sy in (-1.0, 1.0)
            for sx in (-1.0, 1.0)
        ],
        dtype=np.float64,
    )
    return (rotation @ local.T).T + translation


def _farthest_shells(
    centres: np.ndarray, mask: np.ndarray, *, count: int, exclude: set[int]
) -> list[int]:
    """Choose deterministic, spatially spread shell rows for the oblique overlay."""

    eligible = [int(i) for i in np.flatnonzero(mask) if int(i) not in exclude]
    if len(eligible) <= count:
        return eligible
    chosen = [eligible[0]]
    while len(chosen) < count:
        remaining = np.asarray([i for i in eligible if i not in chosen], dtype=np.int64)
        distances = np.linalg.norm(
            centres[remaining, None, :] - centres[np.asarray(chosen)][None, :, :],
            axis=2,
        )
        chosen.append(int(remaining[np.argmax(distances.min(axis=1))]))
    return sorted(chosen)


def _crop_mesh(mesh_path: Path) -> o3d.geometry.TriangleMesh:
    mesh = o3d.io.read_triangle_mesh(str(mesh_path), enable_post_processing=False)
    vertices = np.asarray(mesh.vertices)
    triangles = np.asarray(mesh.triangles)
    triangle_vertices = vertices[triangles]
    centres = triangle_vertices.mean(axis=1)
    areas = 0.5 * np.linalg.norm(
        np.cross(
            triangle_vertices[:, 1] - triangle_vertices[:, 0],
            triangle_vertices[:, 2] - triangle_vertices[:, 0],
        ),
        axis=1,
    )
    keep = (
        (centres[:, 0] >= -11.0)
        & (centres[:, 0] <= -3.6)
        & (centres[:, 1] >= -11.3)
        & (centres[:, 1] <= -6.5)
        & (centres[:, 2] >= -0.1)
        & (centres[:, 2] <= 2.9)
        # ASE room envelopes contain a handful of metre-scale ceiling, floor,
        # and wall triangles that occlude every interior object from external
        # cameras. Removing only these large enclosing faces yields an explicit
        # cutaway while preserving the dense reconstructed furniture surfaces.
        & (areas <= 0.08)
    )
    cropped = o3d.geometry.TriangleMesh(
        o3d.utility.Vector3dVector(vertices.copy()),
        o3d.utility.Vector3iVector(triangles[keep].copy()),
    )
    cropped.remove_unreferenced_vertices()
    cropped.compute_vertex_normals()
    return cropped


def _scene_renderer(
    mesh: o3d.geometry.TriangleMesh, *, width_px: int, height_px: int
) -> Any:
    renderer = o3d.visualization.rendering.OffscreenRenderer(width_px, height_px)
    scene = renderer.scene
    scene.set_background(np.asarray([0.965, 0.974, 0.982, 1.0], dtype=np.float32))
    scene.scene.set_sun_light(
        np.asarray([-0.35, -0.45, -0.82]),
        np.asarray([1.0, 0.98, 0.94]),
        58_000,
    )
    scene.scene.enable_sun_light(True)
    material = o3d.visualization.rendering.MaterialRecord()
    material.shader = "defaultLit"
    material.base_color = np.asarray([0.68, 0.73, 0.78, 1.0], dtype=np.float32)
    material.base_roughness = 0.92
    material.base_reflectance = 0.08
    scene.add_geometry("ase_scene_crop", mesh, material)
    return renderer


def _render_oblique(
    renderer: o3d.visualization.rendering.OffscreenRenderer,
    output: Path,
) -> Projection:
    width_px, height_px = RENDER_WIDTH_PX, RENDER_HEIGHT_PX
    centre = np.asarray(OBLIQUE_CENTRE_WORLD, dtype=np.float32)
    eye = np.asarray(OBLIQUE_EYE_WORLD, dtype=np.float32)
    renderer.setup_camera(
        OBLIQUE_VERTICAL_FOV_DEG,
        centre,
        eye,
        np.asarray([0.0, 0.0, 1.0], dtype=np.float32),
        OBLIQUE_NEAR_M,
        OBLIQUE_FAR_M,
    )
    image = renderer.render_to_image()
    o3d.io.write_image(str(output), image, quality=9)
    camera = renderer.scene.camera
    return Projection(
        view=np.asarray(camera.get_view_matrix()),
        projection=np.asarray(camera.get_projection_matrix()),
        width_px=width_px,
        height_px=height_px,
    )


def _render_top(
    renderer: o3d.visualization.rendering.OffscreenRenderer,
    output: Path,
) -> Projection:
    width_px, height_px = RENDER_WIDTH_PX, RENDER_HEIGHT_PX
    centre = np.asarray(TOP_CENTRE_WORLD, dtype=np.float32)
    renderer.scene.camera.look_at(
        centre,
        np.asarray(TOP_EYE_WORLD, dtype=np.float32),
        np.asarray([0.0, 1.0, 0.0], dtype=np.float32),
    )
    renderer.scene.camera.set_projection(
        o3d.visualization.rendering.Camera.Projection.Ortho,
        -TOP_HALF_WIDTH_M,
        TOP_HALF_WIDTH_M,
        -TOP_HALF_HEIGHT_M,
        TOP_HALF_HEIGHT_M,
        TOP_NEAR_M,
        TOP_FAR_M,
    )
    image = renderer.render_to_image()
    o3d.io.write_image(str(output), image, quality=9)
    camera = renderer.scene.camera
    return Projection(
        view=np.asarray(camera.get_view_matrix()),
        projection=np.asarray(camera.get_projection_matrix()),
        width_px=width_px,
        height_px=height_px,
    )


def _project_segments(
    projection: Projection, segments: list[np.ndarray]
) -> list[list[list[float]]]:
    return [projection.points(segment) for segment in segments]


def _load_history(store_dir: Path, repo_root: Path, data_root: Path) -> np.ndarray:
    paths = PathConfig(
        root=repo_root,
        data_root=data_root,
        offline_cache_dir=data_root / "offline_cache",
    )
    dataset = VinOfflineDataset(
        VinOfflineDatasetConfig(
            paths=paths,
            store=VinOfflineStoreConfig(store_dir=store_dir),
            split="all",
            load_backbone=False,
            load_candidates=False,
            load_depths=False,
            load_candidate_pcs=False,
            load_gt_obbs=False,
            load_detected_obbs=False,
            load_trajectory_metadata=False,
            map_location="cpu",
        )
    )
    index = next(
        i
        for i, record in enumerate(dataset._records)
        if int(record.sample_index) == SOURCE_SAMPLE_INDEX
    )
    sample = dataset[index]
    assert sample.scene_id == SCENE_ID and sample.snippet_id == SNIPPET_ID
    return sample.vin_snippet.t_world_rig.tensor().detach().cpu().numpy()


def _panel_payload(
    projection: Projection,
    *,
    target_corners: np.ndarray,
    history_poses: np.ndarray,
    root_pose: np.ndarray,
    candidate_poses: np.ndarray,
    valid: np.ndarray,
    selected_shell: int,
    oblique: bool,
) -> dict[str, Any]:
    history_centres = history_poses[:, 9:12]
    candidate_centres = candidate_poses[:, 9:12]
    payload: dict[str, Any] = {
        "target_obb_segments": _project_segments(
            projection, _segments(target_corners, BOX_EDGES)
        ),
        "target_center": projection.points(target_corners.mean(axis=0, keepdims=True))[
            0
        ],
        "history_path": projection.points(history_centres),
        "root_center": projection.points(root_pose[None, 9:12])[0],
        "root_frustum": _project_segments(
            projection,
            _segments(_frustum_points_world(root_pose, scale_m=0.22), FRUSTUM_EDGES),
        ),
        "selected_path": projection.points(
            np.vstack([root_pose[9:12], candidate_centres[selected_shell]])
        ),
        "selected_frustum": _project_segments(
            projection,
            _segments(
                _frustum_points_world(candidate_poses[selected_shell], scale_m=0.29),
                FRUSTUM_EDGES,
            ),
        ),
        "candidates": [
            {
                "shell": int(shell),
                "center": projection.points(candidate_centres[shell : shell + 1])[0],
                "valid": bool(valid[shell]),
                "selected": bool(shell == selected_shell),
                "family": (
                    "forward_local"
                    if shell < 24
                    else "target_bearing_local"
                    if shell < 48
                    else "lateral_target_bypass"
                ),
            }
            for shell in range(candidate_centres.shape[0])
        ],
    }
    if oblique:
        history_rows = [0, 4, 8, 12, 16]
        valid_shells = _farthest_shells(
            candidate_centres, valid, count=5, exclude={selected_shell}
        )
        invalid_shells = _farthest_shells(
            candidate_centres, ~valid, count=5, exclude=set()
        )
        payload["history_frusta"] = [
            _project_segments(
                projection,
                _segments(
                    _frustum_points_world(history_poses[row], scale_m=0.20),
                    FRUSTUM_EDGES,
                ),
            )
            for row in history_rows
        ]
        payload["valid_frusta"] = [
            {
                "shell": int(shell),
                "segments": _project_segments(
                    projection,
                    _segments(
                        _frustum_points_world(candidate_poses[shell], scale_m=0.18),
                        FRUSTUM_EDGES,
                    ),
                ),
            }
            for shell in valid_shells
        ]
        payload["invalid_frusta"] = [
            {
                "shell": int(shell),
                "segments": _project_segments(
                    projection,
                    _segments(
                        _frustum_points_world(candidate_poses[shell], scale_m=0.18),
                        FRUSTUM_EDGES,
                    ),
                ),
            }
            for shell in invalid_shells
        ]
    return payload


def main() -> None:
    repo_root = Path(__file__).resolve().parents[5]
    data_root = Path(os.environ.get("ARIA_NBV_DATA_ROOT", repo_root / ".data"))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=repo_root)
    parser.add_argument("--data-root", type=Path, default=data_root)
    parser.add_argument(
        "--rollout-store",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--vin-store",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--mesh",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data",
    )
    args = parser.parse_args()

    data_root = args.data_root.expanduser().resolve()
    if args.rollout_store is None:
        args.rollout_store = (
            data_root / "offline_cache/rollouts_v1_realistic_35_train_20260621.zarr"
        )
    if args.vin_store is None:
        args.vin_store = data_root / "offline_cache/vin_offline"
    if args.mesh is None:
        args.mesh = (
            data_root / "ase_meshes_processed/scene_81286_0.1_nocrop_dbbf5c71a22f.ply"
        )

    os.environ.setdefault("EGL_PLATFORM", "surfaceless")
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    oblique_path = output_dir / "candidate_scene_81286_000035_oblique.png"
    top_path = output_dir / "candidate_scene_81286_000035_top.png"
    json_path = output_dir / "candidate_scene_81286_000035.json"

    reader = RolloutZarrStoreReader(args.rollout_store)
    rollout_pose = reader.array("rollouts/root_pose_world")[ROLLOUT_ROW].astype(
        np.float64
    )
    assert int(reader.array("rollouts/target_row_id")[ROLLOUT_ROW]) == TARGET_ROW
    assert int(reader.array("steps/rollout_row_id")[STEP_ROW]) == ROLLOUT_ROW
    assert int(reader.array("steps/selected_shell_index")[STEP_ROW]) == SELECTED_SHELL

    candidate_mask = reader.array("candidates/step_row_id") == STEP_ROW
    shell_order = np.argsort(reader.array("candidates/shell_index")[candidate_mask])
    candidate_poses = reader.array("candidates/pose_world_cam")[candidate_mask][
        shell_order
    ].astype(np.float64)
    valid = reader.array("candidates/actor_action_mask")[candidate_mask][
        shell_order
    ].astype(bool)
    primary_reason = reader.array("candidates/primary_invalid_reason")[candidate_mask][
        shell_order
    ]
    assert candidate_poses.shape == (60, 12)
    assert int(valid.sum()) == 25 and int((~valid).sum()) == 35
    assert np.all(primary_reason[~valid] == 5)

    target_pose = reader.array("targets/target_pose_world_object")[TARGET_ROW].astype(
        np.float64
    )
    target_extents = reader.array("targets/target_extents")[TARGET_ROW].astype(
        np.float64
    )
    target_corners = _obb_corners(target_pose, target_extents)
    history_rig_poses = _load_history(
        args.vin_store,
        args.repo_root.expanduser().resolve(),
        data_root,
    )
    # The VIN trajectory is world<-rig while the rollout root is world<-RGB
    # camera. Recover the fixed rig<-camera extrinsic from the shared root
    # timestamp, then apply it to every logged rig pose for display only.
    rig_from_camera = np.linalg.inv(_pose_matrix(history_rig_poses[-1])) @ _pose_matrix(
        rollout_pose
    )
    history_poses = np.stack(
        [
            _matrix_pose(_pose_matrix(pose) @ rig_from_camera)
            for pose in history_rig_poses
        ],
        axis=0,
    )
    np.testing.assert_allclose(history_poses[-1], rollout_pose, atol=1e-5, rtol=1e-5)

    mesh = _crop_mesh(args.mesh)
    renderer = _scene_renderer(mesh, width_px=1500, height_px=920)
    oblique = _render_oblique(renderer, oblique_path)
    top = _render_top(renderer, top_path)

    selected_diagnostics: dict[str, float] = {}
    diagnostic_rows = reader.array("candidate_diagnostics/candidate_row_id")
    selected_candidate_row = int(
        reader.array("steps/selected_candidate_row_id")[STEP_ROW]
    )
    selected_diag_row = int(
        np.flatnonzero(diagnostic_rows == selected_candidate_row)[0]
    )
    for name in (
        "motion_step_length_m",
        "mesh_distance_m",
        "path_min_clearance_m",
        "target_distance_m",
    ):
        selected_diagnostics[name] = float(
            reader.array(f"candidate_diagnostics/{name}")[selected_diag_row]
        )

    payload = {
        "provenance": {
            "scene_id": SCENE_ID,
            "snippet_id": SNIPPET_ID,
            "source_sample_index": SOURCE_SAMPLE_INDEX,
            "rollout_store": args.rollout_store.name,
            "rollout_row": ROLLOUT_ROW,
            "step_row": STEP_ROW,
            "target_row": TARGET_ROW,
            "target_instance_id": int(
                reader.array("targets/target_inst_id")[TARGET_ROW]
            ),
            "mesh": args.mesh.name,
            "frame": "ASE world; PoseTW world-from-camera/rig; metres",
            "construction": "measured logged trajectory and stored rollout geometry over reconstructed ASE mesh",
            "evidential_role": "auditable finite-candidate contract example, not a performance result",
            "frustum_primitive": "Viser five-vertex wire topology, Apache-2.0; no filled faces",
            "render_backend": f"Open3D {o3d.__version__} offscreen z-buffer; CeTZ overlays remain vector",
            "view_contracts": {
                "oblique": {
                    "projection": "perspective",
                    "vertical_fov_deg": OBLIQUE_VERTICAL_FOV_DEG,
                    "near_m": OBLIQUE_NEAR_M,
                    "far_m": OBLIQUE_FAR_M,
                    "look_at_world_m": OBLIQUE_CENTRE_WORLD,
                    "eye_world_m": OBLIQUE_EYE_WORLD,
                    "up_world": (0.0, 0.0, 1.0),
                    "resolution_px": (RENDER_WIDTH_PX, RENDER_HEIGHT_PX),
                },
                "bird_eye": {
                    "projection": "orthographic",
                    "width_m": 2.0 * TOP_HALF_WIDTH_M,
                    "height_m": 2.0 * TOP_HALF_HEIGHT_M,
                    "near_m": TOP_NEAR_M,
                    "far_m": TOP_FAR_M,
                    "look_at_world_m": TOP_CENTRE_WORLD,
                    "eye_world_m": TOP_EYE_WORLD,
                    "up_world": (0.0, 1.0, 0.0),
                    "resolution_px": (RENDER_WIDTH_PX, RENDER_HEIGHT_PX),
                },
            },
        },
        "counts": {
            "candidates": int(valid.size),
            "valid": int(valid.sum()),
            "invalid_clearance": int((~valid).sum()),
            "forward_local": 24,
            "target_bearing_local": 24,
            "lateral_target_bypass": 12,
        },
        "selected": {
            "shell": SELECTED_SHELL,
            "candidate_row": selected_candidate_row,
            "target_rri": float(
                reader.array("candidates/target_rri")[candidate_mask][shell_order][
                    SELECTED_SHELL
                ]
            ),
            **selected_diagnostics,
        },
        "oblique": {
            "background": oblique_path.name,
            **_panel_payload(
                oblique,
                target_corners=target_corners,
                history_poses=history_poses,
                root_pose=rollout_pose,
                candidate_poses=candidate_poses,
                valid=valid,
                selected_shell=SELECTED_SHELL,
                oblique=True,
            ),
        },
        "top": {
            "background": top_path.name,
            **_panel_payload(
                top,
                target_corners=target_corners,
                history_poses=history_poses,
                root_pose=rollout_pose,
                candidate_poses=candidate_poses,
                valid=valid,
                selected_shell=SELECTED_SHELL,
                oblique=False,
            ),
            "scale_bar": top.points(
                np.asarray(
                    [[-10.70, -10.90, 0.03], [-9.70, -10.90, 0.03]], dtype=np.float64
                )
            ),
        },
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {json_path}")
    print(f"wrote {oblique_path}")
    print(f"wrote {top_path}")


if __name__ == "__main__":
    main()
