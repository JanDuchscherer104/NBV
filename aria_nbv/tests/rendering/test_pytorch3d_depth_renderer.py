import pytest
import torch
from efm3d.aria import CameraTW, PoseTW
from pytorch3d.structures import Meshes

from aria_nbv.rendering.pytorch3d_depth_renderer import (
    Pytorch3DDepthRenderer,
    Pytorch3DDepthRendererConfig,
    camera_tw_to_pytorch3d,
)


def _test_camera(size: int = 64, fx: float = 50.0) -> CameraTW:
    s = float(size)
    c = 0.5 * (s - 1)
    return CameraTW.from_parameters(
        width=torch.tensor([s]),
        height=torch.tensor([s]),
        fx=torch.tensor([fx]),
        fy=torch.tensor([fx]),
        cx=torch.tensor([c]),
        cy=torch.tensor([c]),
        dist_params=torch.zeros(0),
    )


def test_camera_tw_adapter_preserves_off_axis_intrinsics_and_pose() -> None:
    """The public adapter must retain non-square calibration and PoseTW frame semantics."""

    camera = CameraTW.from_parameters(
        width=torch.tensor([80.0]),
        height=torch.tensor([40.0]),
        fx=torch.tensor([70.0]),
        fy=torch.tensor([60.0]),
        cx=torch.tensor([21.5]),
        cy=torch.tensor([13.25]),
        dist_params=torch.zeros(0),
    )
    angle = torch.tensor(0.3)
    rotation = torch.tensor(
        [
            [torch.cos(angle), -torch.sin(angle), 0.0],
            [torch.sin(angle), torch.cos(angle), 0.0],
            [0.0, 0.0, 1.0],
        ]
    ).unsqueeze(0)
    pose = PoseTW.from_Rt(rotation, torch.tensor([[1.0, -0.5, 0.2]]))

    converted = camera_tw_to_pytorch3d(camera, pose, device=torch.device("cpu"))

    assert converted.in_ndc() is False
    assert torch.equal(converted.image_size, torch.tensor([[40.0, 80.0]]))
    assert torch.equal(converted.focal_length, torch.tensor([[70.0, 60.0]]))
    assert torch.equal(converted.principal_point, torch.tensor([[21.5, 13.25]]))
    points_world = torch.randn(1, 8, 3)
    expected = pose.inverse().transform(points_world)
    actual = converted.get_world_to_view_transform().transform_points(points_world)
    assert torch.allclose(actual, expected, atol=1e-5)


def test_depth_renderer_plane_constant_depth_cpu():
    # Simple square plane at z=2 facing the camera.
    verts = torch.tensor(
        [
            [-1.0, -1.0, 2.0],
            [1.0, -1.0, 2.0],
            [1.0, 1.0, 2.0],
            [-1.0, 1.0, 2.0],
        ],
        dtype=torch.float32,
    )
    faces = torch.tensor([[0, 1, 2], [0, 2, 3]], dtype=torch.int64)

    cam = _test_camera()
    pose_wc_single = PoseTW.from_Rt(torch.eye(3), torch.zeros(3))  # cam at origin, looking +Z.
    pose_wc = PoseTW(pose_wc_single._data.unsqueeze(0))  # batchify

    cfg = Pytorch3DDepthRendererConfig(device="cpu", is_debug=True, zfar=10.0)
    renderer = Pytorch3DDepthRenderer(cfg)

    depth, pix_to_face, _ = renderer.render(poses=pose_wc, mesh=(verts, faces), camera=cam)

    assert depth.shape == (1, 64, 64)
    valid = pix_to_face >= 0
    hit_ratio = valid.float().mean()
    assert hit_ratio > 0.5
    assert valid.any()
    assert torch.isclose(depth[valid].min(), torch.tensor(2.0), atol=1e-3)


def test_depth_renderer_bounds_mesh_replication_batch(monkeypatch: pytest.MonkeyPatch) -> None:
    verts = torch.tensor(
        [
            [-1.0, -1.0, 2.0],
            [1.0, -1.0, 2.0],
            [1.0, 1.0, 2.0],
            [-1.0, 1.0, 2.0],
        ],
        dtype=torch.float32,
    )
    faces = torch.tensor([[0, 1, 2], [0, 2, 3]], dtype=torch.int64)
    pose_single = PoseTW.from_Rt(torch.eye(3), torch.zeros(3))
    poses = PoseTW(pose_single.tensor().reshape(1, 12).repeat(5, 1))
    camera = _test_camera()
    reference = Pytorch3DDepthRenderer(Pytorch3DDepthRendererConfig(device="cpu", zfar=10.0, max_views_per_batch=5))
    reference_depth, reference_pix_to_face, reference_cameras = reference.render(
        poses=poses,
        mesh=(verts, faces),
        camera=camera,
    )
    extend_sizes: list[int] = []
    original_extend = Meshes.extend

    def _record_extend(meshes: Meshes, count: int) -> Meshes:
        extend_sizes.append(count)
        return original_extend(meshes, count)

    monkeypatch.setattr(Meshes, "extend", _record_extend)
    renderer = Pytorch3DDepthRenderer(Pytorch3DDepthRendererConfig(device="cpu", zfar=10.0, max_views_per_batch=2))

    depth, pix_to_face, cameras = renderer.render(poses=poses, mesh=(verts, faces), camera=camera)

    assert extend_sizes == [2, 2, 1]
    assert torch.equal(depth, reference_depth)
    assert torch.equal(pix_to_face, reference_pix_to_face)
    assert torch.equal(cameras.R, reference_cameras.R)
    assert torch.equal(cameras.T, reference_cameras.T)


def test_renderer_reuses_mesh_and_raster_settings_for_same_inputs() -> None:
    """Invariant PyTorch3D state is prepared once without changing rendering inputs."""

    verts = torch.tensor([[-1.0, -1.0, 2.0], [1.0, -1.0, 2.0], [0.0, 1.0, 2.0]])
    faces = torch.tensor([[0, 1, 2]], dtype=torch.int64)
    renderer = Pytorch3DDepthRenderer(Pytorch3DDepthRendererConfig(device="cpu", verbosity=0))

    first_mesh = renderer._prepared_mesh(verts, faces)
    second_mesh = renderer._prepared_mesh(verts, faces)
    first_settings = renderer._raster_settings(height=32, width=40)
    second_settings = renderer._raster_settings(height=32, width=40)

    assert first_mesh is second_mesh
    assert first_settings is second_settings


def test_renderer_rebuilds_mesh_after_source_mutation() -> None:
    verts = torch.tensor([[-1.0, -1.0, 2.0], [1.0, -1.0, 2.0], [0.0, 1.0, 2.0]])
    faces = torch.tensor([[0, 1, 2]], dtype=torch.int64)
    renderer = Pytorch3DDepthRenderer(Pytorch3DDepthRendererConfig(device="cpu", verbosity=0))

    first_mesh = renderer._prepared_mesh(verts, faces)
    verts.add_(1.0)
    second_mesh = renderer._prepared_mesh(verts, faces)

    assert second_mesh is not first_mesh


def test_renderer_inference_tensors_bypass_mesh_cache() -> None:
    renderer = Pytorch3DDepthRenderer(Pytorch3DDepthRendererConfig(device="cpu", verbosity=0))
    with torch.inference_mode():
        verts = torch.tensor([[-1.0, -1.0, 2.0], [1.0, -1.0, 2.0], [0.0, 1.0, 2.0]])
        faces = torch.tensor([[0, 1, 2]], dtype=torch.int64)
        first_mesh = renderer._prepared_mesh(verts, faces)
        second_mesh = renderer._prepared_mesh(verts, faces)

    assert first_mesh is not second_mesh
    assert renderer._mesh_cache == {}
