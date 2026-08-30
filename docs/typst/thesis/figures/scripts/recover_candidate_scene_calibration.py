#!/usr/bin/env python3
"""Recover the calibrated pinned scene JSON when the original rollout store is absent.

The preserved baseline JSON owns the original Open3D projections, target OBB,
candidate centres, validity, selection, and sample-specific counts. Its camera
wires were generic pose glyphs. This script recovers only the root and selected
pose from those exact projections, replaces the visible camera glyphs with
all-valid Fisheye624 support cones from the raw ASE shard, and records residuals
and frame distinctions in the output JSON.

The normal exporter remains the primary path when the pinned rollout Zarr is
available. This recovery path exists so the committed calibrated figure remains
reproducible from tracked inputs plus the raw source shard.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from export_candidate_scene_geometry import (
    HISTORY_ROWS,
    RAW_SHARD_RELATIVE,
    SNIPPET_ID,
    _calibrated_frustum_segments,
    _crop_oblique_raster,
    _load_camera_and_rgb_history,
    _matrix_pose,
    _pose_matrix,
)

WIDTH_PX = 1500
HEIGHT_PX = 920
VIEW = np.asarray(
    [
        [0.74239320, 0.66996443, -5.9604645e-8, 11.514154],
        [-0.31147209, 0.34514481, 0.88535881, -0.23706396],
        [0.59315890, -0.65728432, 0.46490848, -14.282628],
        [0.0, 0.0, 0.0, 1.0],
    ],
    dtype=np.float64,
)
PROJECTION = np.asarray(
    [
        [1.9452449, 0.0, 0.0, 0.0],
        [0.0, 3.1715949, 0.0, 0.0],
        [0.0, 0.0, -1.0, -0.2],
        [0.0, 0.0, -1.0, 0.0],
    ],
    dtype=np.float64,
)
OPENGL_TO_CV = np.diag([1.0, -1.0, -1.0, 1.0])
CAMERA_MATRIX = np.asarray(
    [
        [PROJECTION[0, 0] * WIDTH_PX / 2.0, 0.0, WIDTH_PX / 2.0],
        [0.0, PROJECTION[1, 1] * HEIGHT_PX / 2.0, HEIGHT_PX / 2.0],
        [0.0, 0.0, 1.0],
    ],
    dtype=np.float64,
)
GENERIC_LOCAL = np.asarray(
    [
        [0.0, 0.0, 0.0],
        [-0.60, -0.45, 1.0],
        [0.60, -0.45, 1.0],
        [0.60, 0.45, 1.0],
        [-0.60, 0.45, 1.0],
    ],
    dtype=np.float64,
)
SAMPLING_BASIS = np.asarray(
    [
        [0.0, -1.0, 0.0, 0.0],
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ],
    dtype=np.float64,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _project(points_world: np.ndarray) -> list[list[float]]:
    points = np.asarray(points_world, dtype=np.float64).reshape(-1, 3)
    homogeneous = np.concatenate([points, np.ones((len(points), 1))], axis=1)
    clip = (PROJECTION @ VIEW @ homogeneous.T).T
    ndc = clip[:, :3] / clip[:, 3:4]
    panel = np.column_stack(((ndc[:, 0] + 1.0) / 2.0, (ndc[:, 1] + 1.0) / 2.0))
    return np.round(panel, 7).tolist()


def _project_segments(segments: list[np.ndarray]) -> list[list[list[float]]]:
    return [_project(segment) for segment in segments]


def _observed_vertices(segments: list[list[list[float]]]) -> np.ndarray:
    """Recover ordered centre/corners from the original eight generic segments."""

    if len(segments) != 8:
        raise ValueError(f"Expected eight generic wire segments, got {len(segments)}")
    return np.asarray(
        [
            segments[4][0],
            segments[4][1],
            segments[5][1],
            segments[6][1],
            segments[7][1],
        ],
        dtype=np.float64,
    )


def _recover_pose(
    segments: list[list[list[float]]], *, scale_m: float
) -> tuple[np.ndarray, dict[str, float]]:
    observed = _observed_vertices(segments)
    pixels = np.column_stack(
        (observed[:, 0] * WIDTH_PX, (1.0 - observed[:, 1]) * HEIGHT_PX)
    )
    local = GENERIC_LOCAL * scale_m
    ok, rotation_vec, translation = cv2.solvePnP(
        local,
        pixels,
        CAMERA_MATRIX,
        None,
        flags=cv2.SOLVEPNP_EPNP,
    )
    if not ok:
        raise RuntimeError("EPNP failed for preserved root/candidate wire")
    ok, rotation_vec, translation = cv2.solvePnP(
        local,
        pixels,
        CAMERA_MATRIX,
        None,
        rotation_vec,
        translation,
        True,
        flags=cv2.SOLVEPNP_ITERATIVE,
    )
    if not ok:
        raise RuntimeError("Iterative PnP refinement failed")

    rotation_cv, _ = cv2.Rodrigues(rotation_vec)
    camera_from_glyph = np.eye(4, dtype=np.float64)
    camera_from_glyph[:3, :3] = rotation_cv
    camera_from_glyph[:3, 3] = translation[:, 0]
    world_from_glyph = np.linalg.inv(OPENGL_TO_CV @ VIEW) @ camera_from_glyph

    recovered_world = (
        world_from_glyph @ np.concatenate((local, np.ones((len(local), 1))), axis=1).T
    ).T[:, :3]
    recovered_panel = np.asarray(_project(recovered_world))
    delta = recovered_panel - observed
    delta_px = np.column_stack((delta[:, 0] * WIDTH_PX, delta[:, 1] * HEIGHT_PX))
    residual = {
        "rms_px": float(np.sqrt(np.mean(delta_px**2))),
        "max_px": float(np.max(np.linalg.norm(delta_px, axis=1))),
    }
    if residual["max_px"] > 1e-4:
        raise ValueError(f"PnP recovery exceeds 1e-4 px: {residual}")
    return world_from_glyph, residual


def _rotation_distance_deg(first: np.ndarray, second: np.ndarray) -> float:
    cosine = np.clip((np.trace(first.T @ second) - 1.0) / 2.0, -1.0, 1.0)
    return float(math.degrees(math.acos(cosine)))


def _recover(
    baseline: dict[str, Any], *, raw_shard: Path, baseline_path: Path
) -> dict[str, Any]:
    output = copy.deepcopy(baseline)
    original_oblique = baseline["oblique"]
    oblique = output["oblique"]
    root_matrix, root_residual = _recover_pose(
        original_oblique["root_frustum"], scale_m=0.22
    )
    selected_matrix, selected_residual = _recover_pose(
        original_oblique["selected_frustum"], scale_m=0.29
    )

    camera, device_history, rgb_history = _load_camera_and_rgb_history(raw_shard)
    expected_sampling_root = _pose_matrix(device_history[-1]) @ SAMPLING_BASIS
    np.testing.assert_allclose(
        expected_sampling_root, root_matrix, atol=2e-5, rtol=2e-5
    )
    sampling_rotation_error = _rotation_distance_deg(
        expected_sampling_root[:3, :3], root_matrix[:3, :3]
    )
    if sampling_rotation_error >= 2e-4:
        raise ValueError("Recovered root rotation does not match the sampling frame")

    physical_rgb_root = _pose_matrix(rgb_history[-1])
    physical_sampling_translation = float(
        np.linalg.norm(physical_rgb_root[:3, 3] - root_matrix[:3, 3])
    )
    physical_sampling_rotation = _rotation_distance_deg(
        physical_rgb_root[:3, :3], root_matrix[:3, :3]
    )
    np.testing.assert_allclose(physical_sampling_translation, 0.013734805, atol=1e-5)
    np.testing.assert_allclose(physical_sampling_rotation, 92.544884, atol=2e-4)

    oblique["background"] = "candidate_scene_81286_000035_oblique_crop.png"
    oblique["history_path"] = _project(rgb_history[:, 9:12])
    oblique["history_frusta"] = [
        _project_segments(
            _calibrated_frustum_segments(rgb_history[row], camera, depth_m=0.08)
        )
        for row in HISTORY_ROWS
    ]
    oblique["root_center"] = _project(root_matrix[None, :3, 3])[0]
    oblique["root_frustum"] = []
    oblique["selected_path"] = _project(
        np.vstack((root_matrix[:3, 3], selected_matrix[:3, 3]))
    )
    oblique["selected_frustum"] = _project_segments(
        _calibrated_frustum_segments(
            _matrix_pose(selected_matrix), camera, depth_m=0.14
        )
    )
    oblique["valid_frusta"] = []
    oblique["invalid_frusta"] = []

    provenance = output["provenance"]
    provenance["frame"] = (
        "ASE world; physical RGB history and canonical candidate-sampling cameras; metres"
    )
    provenance["construction"] = (
        "physical calibrated RGB history plus PnP-recovered canonical "
        "sampling-camera candidate pose over processed ASE GT mesh"
    )
    provenance["frustum_primitive"] = (
        "ARIA RGB CameraTW all-valid calibration-domain support rays; straight "
        "polygon connections approximate the curved fisheye support boundary"
    )
    provenance["view_contracts"]["oblique"]["display_crop_px"] = [245, 150, 1255, 750]
    provenance["family_source"] = (
        "reconstructed pinned configuration blocks from preserved shell order "
        "(shells 0--23 forward-local, 24--47 target-bearing-local, and 48--59 "
        "lateral-target-bypass); the original rollout position_id table is unavailable, "
        "so row-level stored family provenance is not independently re-decoded"
    )
    provenance["calibrated_outline"] = {
        "owner": "efm3d.aria.CameraTW.unproject with its returned validity mask",
        "camera_model": "CameraModelType.FISHEYE624",
        "image_size_px": [240, 240],
        "valid_radius_px": float(camera.valid_radius.reshape(-1)[0]),
        "outline_samples": 8,
        "outline_margin_px": 0.25,
        "history_rows": list(HISTORY_ROWS),
        "depth_m": {"history": 0.08, "selected": 0.14},
        "boundary_note": (
            "The outline is sampled just inside the valid-radius ellipse, clipped "
            "inward to the raster, and asserted all-valid by CameraTW.unproject."
        ),
        "raw_pose_source": (
            f"{RAW_SHARD_RELATIVE.as_posix()}::{SNIPPET_ID}.mtd#ts_world_device.pth "
            "and RGB t_device_camera"
        ),
        "candidate_pose_recovery": {
            "method": (
                "OpenCV EPNP plus iterative refinement against the exact preserved "
                "Open3D view/projection and generic wire endpoints"
            ),
            "root_residual": root_residual,
            "selected_residual": selected_residual,
            "expected_sampling_vs_recovered_root": {
                "translation_m": float(
                    np.linalg.norm(expected_sampling_root[:3, 3] - root_matrix[:3, 3])
                ),
                "rotation_deg": sampling_rotation_error,
            },
            "physical_rgb_vs_sampling_root": {
                "translation_m": physical_sampling_translation,
                "rotation_deg": physical_sampling_rotation,
            },
        },
        "input_sha256": {
            "generic_baseline_json": _sha256(baseline_path),
            "oblique_raster": _sha256(
                baseline_path.parent / "candidate_scene_81286_000035_oblique.png"
            ),
            "oblique_crop": _sha256(
                baseline_path.parent / "candidate_scene_81286_000035_oblique_crop.png"
            ),
            "raw_shard": _sha256(raw_shard),
        },
    }
    return output


def main() -> None:
    repo_root = Path(__file__).resolve().parents[5]
    data_root = Path(os.environ.get("ARIA_NBV_DATA_ROOT", repo_root / ".data"))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--baseline",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "data/candidate_scene_81286_000035_generic_baseline.json",
    )
    parser.add_argument(
        "--raw-shard",
        type=Path,
        default=data_root / RAW_SHARD_RELATIVE,
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "data/candidate_scene_81286_000035.json",
    )
    parser.add_argument(
        "--oblique-raster",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "data/candidate_scene_81286_000035_oblique.png",
    )
    parser.add_argument(
        "--crop-output",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "data/candidate_scene_81286_000035_oblique_crop.png",
    )
    args = parser.parse_args()
    baseline_path = args.baseline.expanduser().resolve()
    raw_shard = args.raw_shard.expanduser().resolve()
    oblique_raster = args.oblique_raster.expanduser().resolve()
    crop_output = args.crop_output.expanduser().resolve()
    crop_output.parent.mkdir(parents=True, exist_ok=True)
    _crop_oblique_raster(oblique_raster, crop_output)
    baseline: dict[str, Any] = json.loads(baseline_path.read_text(encoding="utf-8"))
    output = _recover(baseline, raw_shard=raw_shard, baseline_path=baseline_path)
    args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
