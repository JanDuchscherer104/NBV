"""Regression tests for depth→point-cloud backprojection conventions.

These tests ensure that the PyTorch3D depth renderer + unprojection utilities
agree with the OpenCV-style pinhole convention used by ``CameraTW``:

    - camera +X points right in the image,
    - camera +Y points down in the image,
    - camera +Z points forward.

Historically, mismatched conventions (camera vs screen axes) caused backprojected
points to appear on the wrong side of the camera frustum in 3D plots.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import torch

# Make vendored efm3d importable
sys.path.append(str(Path(__file__).resolve().parents[3] / "external" / "efm3d"))

from efm3d.aria import CameraTW, PoseTW  # noqa: E402

from aria_nbv.rendering.pytorch3d_depth_renderer import Pytorch3DDepthRendererConfig  # noqa: E402
from aria_nbv.rendering.unproject import (  # noqa: E402
    _pixel_grid,
    backproject_depths_camera_tw_batch,
    backproject_depths_p3d_batch,
)


def test_unprojection_reuses_pixel_grid_for_same_shape() -> None:
    """Pixel-coordinate preparation is deterministic and cached by shape/stride/device."""

    _pixel_grid.cache_clear()
    first = _pixel_grid(8, 10, 2, torch.device("cpu"))
    second = _pixel_grid(8, 10, 2, torch.device("cpu"))

    assert first[0] is second[0]
    assert first[1] is second[1]


def test_p3d_world_to_view_matches_pose_inverse_transform() -> None:
    """Renderer must pass extrinsics to PyTorch3D using the correct convention.

    Historically, passing :attr:`PoseTW.R` directly as ``PerspectiveCameras.R``
    caused a transpose mismatch (PoseTW uses column-vector convention while
    PyTorch3D's transforms use row vectors).
    """

    width, height = 64, 64
    fx, fy = 60.0, 60.0
    cx, cy = width / 2.0, height / 2.0

    cam = CameraTW.from_surreal(
        width=torch.tensor([float(width)], dtype=torch.float32),
        height=torch.tensor([float(height)], dtype=torch.float32),
        type_str="Pinhole",
        params=torch.tensor([[fx, fy, cx, cy]], dtype=torch.float32),
        gain=torch.zeros(1),
        exposure_s=torch.zeros(1),
        valid_radius=torch.tensor([float(max(width, height))], dtype=torch.float32),
        T_camera_rig=PoseTW.from_matrix3x4(torch.eye(3, 4).unsqueeze(0)),
    )

    # Non-trivial pose (world <- cam): rotate about +Z and translate.
    angle = torch.tensor(0.3, dtype=torch.float32)
    c, s = torch.cos(angle), torch.sin(angle)
    r_world_cam = torch.tensor(
        [[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]],
        dtype=torch.float32,
    ).unsqueeze(0)
    t_world_cam = torch.tensor([[1.0, -0.5, 0.2]], dtype=torch.float32)
    pose_world_cam = PoseTW.from_Rt(r_world_cam, t_world_cam)

    renderer = Pytorch3DDepthRendererConfig(device="cpu", verbosity=0).setup_target()
    verts = torch.tensor([[-1.0, -1.0, 3.0], [1.0, -1.0, 3.0], [1.0, 1.0, 3.0]], dtype=torch.float32)
    faces = torch.tensor([[0, 1, 2]], dtype=torch.int64)
    _, _, cameras = renderer.render(poses=pose_world_cam, mesh=(verts, faces), camera=cam)

    # Compare world->camera mapping between PoseTW and PyTorch3D.
    pts_world = torch.randn(1, 10, 3, dtype=torch.float32)
    pts_cam_pose = pose_world_cam.inverse().transform(pts_world)
    pts_cam_p3d = cameras.get_world_to_view_transform().transform_points(pts_world)
    assert torch.allclose(pts_cam_p3d, pts_cam_pose, atol=1e-5)


@pytest.mark.parametrize("dx_px", [10, -10])
def test_backproject_depth_matches_pinhole_signs(dx_px: int) -> None:
    """Backprojection follows current UUT camera convention (LUF, half-pixel center)."""

    width, height = 64, 64
    fx, fy = 60.0, 60.0
    cx, cy = width / 2.0, height / 2.0
    z = 4.0

    cam = CameraTW.from_surreal(
        width=torch.tensor([float(width)], dtype=torch.float32),
        height=torch.tensor([float(height)], dtype=torch.float32),
        type_str="Pinhole",
        params=torch.tensor([[fx, fy, cx, cy]], dtype=torch.float32),
        gain=torch.zeros(1),
        exposure_s=torch.zeros(1),
        valid_radius=torch.tensor([float(max(width, height))], dtype=torch.float32),
        T_camera_rig=PoseTW.from_matrix3x4(torch.eye(3, 4).unsqueeze(0)),
    )
    pose_world_cam = PoseTW.from_matrix3x4(torch.eye(3, 4).unsqueeze(0))

    # Build a PyTorch3D camera via the renderer path (this is what the pipeline uses).
    renderer = Pytorch3DDepthRendererConfig(device="cpu", verbosity=0).setup_target()
    verts = torch.tensor(
        [[-1.0, -1.0, z], [1.0, -1.0, z], [1.0, 1.0, z], [-1.0, 1.0, z]],
        dtype=torch.float32,
    )
    faces = torch.tensor([[0, 2, 1], [0, 3, 2]], dtype=torch.int64)
    _, pix_to_face, cameras = renderer.render(poses=pose_world_cam, mesh=(verts, faces), camera=cam)

    # Only one pixel is valid → backprojection returns a single 3D point.
    x_px = int(cx + dx_px)
    y_px = int(cy)
    depth = torch.full((height, width), float("nan"), dtype=torch.float32)
    valid = torch.zeros((height, width), dtype=torch.bool)
    depth[y_px, x_px] = z
    valid[y_px, x_px] = True

    # Mask used by the pipeline is pix_to_face>=0 plus znear/zfar, but for this
    # synthetic plane + explicit valid mask we only need the single pixel.
    assert pix_to_face.shape[-2:] == (height, width)

    padded, lengths = backproject_depths_p3d_batch(
        depths=depth.unsqueeze(0),
        mask_valid=valid.unsqueeze(0),
        cameras=cameras[0],
        stride=1,
    )
    pts = padded[0, : int(lengths[0].item())]
    assert pts.shape == (1, 3)

    expected_sign = -1.0 if dx_px > 0 else 1.0
    assert torch.sign(pts[0, 0]).item() == expected_sign
    assert torch.isclose(pts[0, 2], torch.tensor(z, dtype=pts.dtype, device=pts.device), atol=1e-5)


def test_backproject_batch_matches_single_pixel() -> None:
    """Batch backprojection should preserve the same coordinate convention as the single version."""

    width, height = 64, 64
    fx, fy = 60.0, 60.0
    cx, cy = width / 2.0, height / 2.0
    z = 4.0

    cam = CameraTW.from_surreal(
        width=torch.tensor([float(width)], dtype=torch.float32),
        height=torch.tensor([float(height)], dtype=torch.float32),
        type_str="Pinhole",
        params=torch.tensor([[fx, fy, cx, cy]], dtype=torch.float32),
        gain=torch.zeros(1),
        exposure_s=torch.zeros(1),
        valid_radius=torch.tensor([float(max(width, height))], dtype=torch.float32),
        T_camera_rig=PoseTW.from_matrix3x4(torch.eye(3, 4).unsqueeze(0)),
    )
    pose_world_cam = PoseTW.from_matrix3x4(torch.eye(3, 4).unsqueeze(0))

    renderer = Pytorch3DDepthRendererConfig(device="cpu", verbosity=0).setup_target()
    verts = torch.tensor(
        [[-1.0, -1.0, z], [1.0, -1.0, z], [1.0, 1.0, z], [-1.0, 1.0, z]],
        dtype=torch.float32,
    )
    faces = torch.tensor([[0, 2, 1], [0, 3, 2]], dtype=torch.int64)
    _, pix_to_face, cameras = renderer.render(poses=pose_world_cam, mesh=(verts, faces), camera=cam)

    x_px = int(cx + 10)
    y_px = int(cy)
    depths = torch.full((1, height, width), float("nan"), dtype=torch.float32)
    mask = torch.zeros((1, height, width), dtype=torch.bool)
    depths[0, y_px, x_px] = z
    mask[0, y_px, x_px] = True

    padded, lengths = backproject_depths_p3d_batch(depths=depths, mask_valid=mask, cameras=cameras, stride=1)
    assert lengths.tolist() == [1]
    assert padded.shape == (1, 1, 3)

    # Pixel is at cx+10 (right of centre) → X world-coord should be negative (P3D NDC sign).
    assert torch.sign(padded[0, 0, 0]).item() == -1.0


def test_camera_tw_backprojection_matches_derived_pytorch3d_camera() -> None:
    """Typed stored calibration must use the same half-pixel/sign path as rendered cameras."""

    camera = CameraTW.from_parameters(
        width=torch.tensor([5.0]),
        height=torch.tensor([3.0]),
        fx=torch.tensor([7.0]),
        fy=torch.tensor([8.0]),
        cx=torch.tensor([1.25]),
        cy=torch.tensor([0.75]),
        dist_params=torch.zeros(0),
    )
    pose = PoseTW.from_Rt(torch.eye(3).unsqueeze(0), torch.tensor([[1.0, -0.5, 0.2]]))
    depth = torch.zeros((1, 3, 5), dtype=torch.float32)
    valid = torch.zeros_like(depth, dtype=torch.bool)
    depth[0, 1, 3] = 2.0
    valid[0, 1, 3] = True
    renderer = Pytorch3DDepthRendererConfig(device="cpu", verbosity=0).setup_target()
    vertices = torch.tensor([[-1.0, -1.0, 3.0], [1.0, -1.0, 3.0], [0.0, 1.0, 3.0]])
    faces = torch.tensor([[0, 1, 2]], dtype=torch.int64)
    _rendered, _faces, p3d_camera = renderer.render(pose, (vertices, faces), camera)

    expected = backproject_depths_p3d_batch(depth, valid, p3d_camera)
    actual = backproject_depths_camera_tw_batch(depth, valid, camera, pose)

    assert torch.equal(actual[1], expected[1])
    assert torch.allclose(actual[0], expected[0], atol=1e-6)
