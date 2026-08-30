#!/usr/bin/env python3
"""Export a pinned ASE finite-candidate scene as raster bases plus vector geometry.

The processed ASE ground-truth mesh is rendered with Open3D's z-buffer.
Physical RGB history, calibrated valid-domain frusta, the target OBB, candidate
centres, validity, family provenance, and the selected path are exported as
projected 2D coordinates for editable CeTZ overlays.

Run from the repository root with the package environment::

    EGL_PLATFORM=surfaceless \
    PYTHONPATH=aria_nbv \
    aria_nbv/.venv/bin/python \
      docs/typst/thesis/figures/scripts/export_candidate_scene_geometry.py

For the Fisheye624 camera, raster corners fall outside the calibrated valid
domain. The exporter therefore samples an ordered polygon just inside the
valid-radius ellipse, asserts that ``CameraTW.unproject`` accepts every point,
and draws four cardinal spokes. No opaque faces hide the scene or imply a
rectilinear image plane.
"""

from __future__ import annotations

import argparse
import io
import json
import math
import os
import tarfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import open3d as o3d
import torch
from efm3d.aria import CameraTW, PoseTW

from aria_nbv.rollouts.read_model import decode_position_id
from aria_nbv.rollouts.zarr_store import RolloutZarrStoreReader


ROLLOUT_ROW = 73
STEP_ROW = 121
TARGET_ROW = 12
SELECTED_SHELL = 47
SOURCE_SAMPLE_INDEX = 35
SCENE_ID = "81286"
SNIPPET_ID = "AriaSyntheticEnvironment_81286_AtekDataSample_000035"
RAW_SHARD_RELATIVE = Path("ase_efm/81286/shards-0004.tar")
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
OBLIQUE_CROP_PX = (245, 150, 1255, 750)
VALID_SUPPORT_SAMPLES = 8
VALID_SUPPORT_MARGIN_PX = 0.25
HISTORY_ROWS = (0, 10)
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
        # cutaway while preserving the processed ground-truth furniture surfaces.
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
    crop_output: Path,
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
    _write_oblique_crop(image, crop_output)
    camera = renderer.scene.camera
    return Projection(
        view=np.asarray(camera.get_view_matrix()),
        projection=np.asarray(camera.get_projection_matrix()),
        width_px=width_px,
        height_px=height_px,
    )


def _write_oblique_crop(image: o3d.geometry.Image, output: Path) -> None:
    """Write the fixed, subdued publication crop from the full oblique raster."""

    xmin, ymin, xmax, ymax = OBLIQUE_CROP_PX
    crop = np.asarray(image)[ymin:ymax, xmin:xmax].astype(np.float32)
    # Subdue the mesh so vector geometry owns the explanatory hierarchy.
    crop = np.clip(0.72 * crop + 67.0, 0.0, 255.0).astype(np.uint8)
    o3d.io.write_image(str(output), o3d.geometry.Image(crop), quality=9)


def _crop_oblique_raster(source: Path, output: Path) -> None:
    """Regenerate the publication crop from a previously rendered full raster."""

    image = o3d.io.read_image(str(source))
    if np.asarray(image).shape[:2] != (RENDER_HEIGHT_PX, RENDER_WIDTH_PX):
        raise ValueError(f"Unexpected oblique raster shape: {np.asarray(image).shape}")
    _write_oblique_crop(image, output)


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


def _tar_tensor(archive: tarfile.TarFile, suffix: str) -> torch.Tensor:
    member = archive.getmember(f"{SNIPPET_ID}.{suffix}")
    stream = archive.extractfile(member)
    if stream is None:
        raise FileNotFoundError(member.name)
    return torch.load(io.BytesIO(stream.read()), map_location="cpu", weights_only=True)


def _load_camera_and_rgb_history(
    raw_shard: Path,
) -> tuple[CameraTW, np.ndarray, np.ndarray]:
    """Load the pinned camera plus world-from-device and world-from-RGB histories."""

    with tarfile.open(raw_shard) as archive:
        params = _tar_tensor(archive, "mfcd#camera-rgb+projection_params.pth").float()
        valid_radius = _tar_tensor(
            archive, "mfcd#camera-rgb+camera_valid_radius.pth"
        ).float()
        device_from_camera = _tar_tensor(
            archive, "mfcd#camera-rgb+t_device_camera.pth"
        ).float()
        world_from_device = _tar_tensor(archive, "mtd#ts_world_device.pth").float()

    camera = CameraTW.from_surreal(
        width=torch.tensor([240.0]),
        height=torch.tensor([240.0]),
        type_str="CameraModelType.FISHEYE624",
        params=params.unsqueeze(0),
        valid_radius=valid_radius,
        T_camera_rig=PoseTW.from_matrix3x4(device_from_camera).inverse(),
    ).float()

    device_from_camera_matrix = np.eye(4, dtype=np.float64)
    device_from_camera_matrix[:3] = device_from_camera.double().numpy()
    device_history = []
    rgb_history = []
    for pose in world_from_device.double().numpy():
        world_from_device_matrix = np.eye(4, dtype=np.float64)
        world_from_device_matrix[:3] = pose
        device_history.append(_matrix_pose(world_from_device_matrix))
        rgb_history.append(
            _matrix_pose(world_from_device_matrix @ device_from_camera_matrix)
        )
    return camera, np.stack(device_history), np.stack(rgb_history)


def _valid_support_outline_camera(camera: CameraTW, *, depth_m: float) -> np.ndarray:
    """Unproject an all-valid polygon inside the fisheye calibration domain."""

    center = camera.c.reshape(-1, 2)[0]
    radii = camera.valid_radius.reshape(-1, 2)[0] - VALID_SUPPORT_MARGIN_PX
    size = camera.size.reshape(-1, 2)[0]
    angles = torch.arange(
        VALID_SUPPORT_SAMPLES,
        device=center.device,
        dtype=center.dtype,
    ) * (2.0 * math.pi / VALID_SUPPORT_SAMPLES)
    pixels = torch.stack(
        (
            center[0] + radii[0] * torch.cos(angles),
            center[1] + radii[1] * torch.sin(angles),
        ),
        dim=-1,
    )
    pixels = torch.minimum(
        torch.maximum(pixels, torch.zeros_like(pixels)),
        size.unsqueeze(0) - 1.0,
    )
    radial_fraction = torch.sqrt(
        (((pixels - center) / camera.valid_radius.reshape(-1, 2)[0]) ** 2).sum(dim=-1)
    )
    rays, valid = camera.unproject(pixels.unsqueeze(0))
    rays = rays.reshape(VALID_SUPPORT_SAMPLES, 3)
    if not bool(valid.all()):
        raise ValueError(
            "Fisheye publication outline must unproject inside valid support"
        )
    if not bool((radial_fraction < 1.0).all()):
        raise ValueError(
            "Fisheye publication outline must stay inside valid-radius support"
        )
    if not bool((rays[:, 2] > 0.0).all()):
        raise ValueError(
            "Fisheye publication outline must remain in front of the camera"
        )
    return (rays * (float(depth_m) / rays[:, 2:3])).double().cpu().numpy()


def _calibrated_frustum_segments(
    pose12: np.ndarray, camera: CameraTW, *, depth_m: float
) -> list[np.ndarray]:
    rotation, translation = _pose_parts(pose12)
    outline_camera = _valid_support_outline_camera(camera, depth_m=depth_m)
    outline_world = (rotation @ outline_camera.T).T + translation
    perimeter = [
        outline_world[np.asarray((index, (index + 1) % len(outline_world)))]
        for index in range(len(outline_world))
    ]
    spokes = [
        np.vstack((translation, outline_world[index]))
        for index in range(0, len(outline_world), 2)
    ]
    return [*perimeter, *spokes]


def _panel_payload(
    projection: Projection,
    *,
    target_corners: np.ndarray,
    history_poses: np.ndarray,
    root_pose: np.ndarray,
    candidate_poses: np.ndarray,
    candidate_families: np.ndarray,
    camera: CameraTW,
    valid: np.ndarray,
    selected_shell: int,
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
        "root_frustum": [],
        "selected_path": projection.points(
            np.vstack([root_pose[9:12], candidate_centres[selected_shell]])
        ),
        "selected_frustum": _project_segments(
            projection,
            _calibrated_frustum_segments(
                candidate_poses[selected_shell], camera, depth_m=0.14
            ),
        ),
        "candidates": [
            {
                "shell": int(shell),
                "center": projection.points(candidate_centres[shell : shell + 1])[0],
                "valid": bool(valid[shell]),
                "selected": bool(shell == selected_shell),
                "family": str(candidate_families[shell]),
            }
            for shell in range(candidate_centres.shape[0])
        ],
    }
    payload["history_frusta"] = [
        _project_segments(
            projection,
            _calibrated_frustum_segments(history_poses[row], camera, depth_m=0.08),
        )
        for row in HISTORY_ROWS
    ]
    payload["valid_frusta"] = []
    payload["invalid_frusta"] = []
    return payload


def main() -> None:
    repo_root = Path(__file__).resolve().parents[5]
    data_root = Path(os.environ.get("ARIA_NBV_DATA_ROOT", repo_root / ".data"))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=data_root)
    parser.add_argument(
        "--rollout-store",
        type=Path,
        default=None,
    )
    parser.add_argument("--raw-shard", type=Path, default=None)
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
    if args.raw_shard is None:
        args.raw_shard = data_root / RAW_SHARD_RELATIVE
    if args.mesh is None:
        args.mesh = (
            data_root / "ase_meshes_processed/scene_81286_0.1_nocrop_dbbf5c71a22f.ply"
        )

    os.environ.setdefault("EGL_PLATFORM", "surfaceless")
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    oblique_path = output_dir / "candidate_scene_81286_000035_oblique.png"
    oblique_crop_path = output_dir / "candidate_scene_81286_000035_oblique_crop.png"
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
    position_ids = reader.array("candidates/position_id")[candidate_mask][
        shell_order
    ].astype(np.int64)
    candidate_families = np.asarray(
        [decode_position_id(position_id) for position_id in position_ids],
        dtype=np.str_,
    )
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
    camera, _, history_poses = _load_camera_and_rgb_history(
        args.raw_shard.expanduser().resolve()
    )

    mesh = _crop_mesh(args.mesh)
    renderer = _scene_renderer(mesh, width_px=1500, height_px=920)
    oblique = _render_oblique(renderer, oblique_path, oblique_crop_path)
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
            "frame": "ASE world; physical RGB history and canonical candidate-sampling cameras; metres",
            "construction": "physical calibrated RGB history and stored rollout geometry over a processed ASE ground-truth mesh cutaway",
            "evidential_role": "auditable finite-candidate contract example, not a performance result",
            "frustum_primitive": "CameraTW-valid eight-point fisheye support polygon with four cardinal spokes; no filled faces",
            "camera_source": f"{RAW_SHARD_RELATIVE.as_posix()}::{SNIPPET_ID}",
            "family_source": "stored candidates/position_id decoded by rollouts.read_model.decode_position_id",
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
                    "display_crop_px": OBLIQUE_CROP_PX,
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
            "forward_local": int((candidate_families == "forward_local").sum()),
            "target_bearing_local": int(
                (candidate_families == "target_bearing_local").sum()
            ),
            "lateral_target_bypass": int(
                (candidate_families == "lateral_target_bypass").sum()
            ),
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
            "background": oblique_crop_path.name,
            **_panel_payload(
                oblique,
                target_corners=target_corners,
                history_poses=history_poses,
                root_pose=rollout_pose,
                candidate_poses=candidate_poses,
                candidate_families=candidate_families,
                camera=camera,
                valid=valid,
                selected_shell=SELECTED_SHELL,
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
                candidate_families=candidate_families,
                camera=camera,
                valid=valid,
                selected_shell=SELECTED_SHELL,
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
    print(f"wrote {oblique_crop_path}")
    print(f"wrote {top_path}")


if __name__ == "__main__":
    main()
