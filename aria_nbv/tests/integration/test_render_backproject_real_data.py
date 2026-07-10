"""Real-data integration test for depth rendering + backprojection.

This guards against coordinate-convention regressions between:
    - CameraTW (OpenCV/RDF: +x right, +y down),
    - PoseTW (world←camera),
    - PyTorch3D rasterizer/unprojection utilities.
"""

from __future__ import annotations

import pytest
import torch

from aria_nbv.data_handling import AseEfmDatasetConfig, EfmSnippetView
from aria_nbv.rendering.pytorch3d_depth_renderer import Pytorch3DDepthRendererConfig
from aria_nbv.rendering.unproject import backproject_depths_p3d_batch


def _first_mesh_sample() -> EfmSnippetView:
    """Load a single real sample with an attached mesh, otherwise skip."""

    cfg = AseEfmDatasetConfig(
        load_meshes=True,
        require_mesh=False,
        batch_size=1,
        snippet_length_s=2.0,
        # Keep mesh small enough for CI/dev boxes.
        mesh_simplify_ratio=0.02,
        verbosity=0,
    )
    try:
        dataset = cfg.setup_target()
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"ASE dataset not available locally: {exc}")

    sample = None
    for idx, cand in enumerate(dataset):
        if cand.has_mesh and cand.mesh_verts is not None and cand.mesh_faces is not None:
            sample = cand
            break
        if idx >= 20:
            break

    if sample is None:
        pytest.skip("Could not find a sample with an attached mesh in the first 20 items.")

    return sample


def test_render_and_backproject_pixel_signs_real() -> None:
    """A pixel to the right of cx backprojects to -X in the camera frame (P3D NDC)."""

    sample = _first_mesh_sample()
    device = torch.device("cpu")

    # Use the first RGB frame for a deterministic calibration/pose pair.
    frame_idx = 0
    cam_frame = sample.camera_rgb.calib[frame_idx].to(device=device)
    cam_frame = cam_frame.scale_to_size((64, 64))

    t_world_rig = sample.trajectory.t_world_rig[frame_idx].to(device=device)
    t_cam_rig = sample.camera_rgb.calib.T_camera_rig[frame_idx].to(device=device)
    t_world_cam = t_world_rig @ t_cam_rig.inverse()
    pose_batch = t_world_cam if t_world_cam.tensor().ndim == 2 else t_world_cam.unsqueeze(0)

    renderer = Pytorch3DDepthRendererConfig(device="cpu", verbosity=0).setup_target()
    depths, pix_to_face, cameras = renderer.render(
        poses=pose_batch,
        mesh=(sample.mesh_verts.to(device=device), sample.mesh_faces.to(device=device)),
        camera=cam_frame,
        frame_index=None,
    )

    depth = depths[0]
    hits = pix_to_face[0] >= 0

    c = cam_frame.c.reshape(-1, 2)[0].float()
    cx, cy = float(c[0].item()), float(c[1].item())
    w = int(cam_frame.size.reshape(-1, 2)[0, 0].item())
    h = int(cam_frame.size.reshape(-1, 2)[0, 1].item())

    y = int(round(cy))
    y = max(0, min(h - 1, y))

    # Find one hit pixel right of cx and one left of cx along the same row.
    x0 = int(round(cx))
    x0 = max(0, min(w - 1, x0))

    x_right = next((x for x in range(min(x0 + 2, w - 1), w) if bool(hits[y, x].item())), None)
    x_left = next((x for x in range(max(x0 - 2, 0), -1, -1) if bool(hits[y, x].item())), None)
    if x_right is None or x_left is None:
        pytest.skip("Could not find hit pixels on both sides of the principal point.")

    def _backproject_single(x_px: int) -> torch.Tensor:
        depth_single = torch.full_like(depth, float("nan"))
        mask_single = torch.zeros_like(hits)
        depth_single[y, x_px] = depth[y, x_px]
        mask_single[y, x_px] = True
        padded, lengths = backproject_depths_p3d_batch(
            depths=depth_single.unsqueeze(0),
            mask_valid=mask_single.unsqueeze(0),
            cameras=cameras[0],
            stride=1,
        )
        pts_world = padded[0, : int(lengths[0].item())]
        assert pts_world.shape == (1, 3)
        return pts_world[0]

    pt_world_right = _backproject_single(x_right)
    pt_world_left = _backproject_single(x_left)

    # Convert back to camera frame (OpenCV/RDF) using the PoseTW we rendered with.
    t_cam_world = pose_batch.inverse()
    pt_cam_right = t_cam_world.transform(pt_world_right).reshape(-1)
    pt_cam_left = t_cam_world.transform(pt_world_left).reshape(-1)

    assert pt_cam_right[2].item() > 0
    assert pt_cam_left[2].item() > 0
    assert pt_cam_right[0].item() < 0, "Pixel right of cx should map to -X (P3D NDC convention)."
    assert pt_cam_left[0].item() > 0, "Pixel left of cx should map to +X (P3D NDC convention)."
