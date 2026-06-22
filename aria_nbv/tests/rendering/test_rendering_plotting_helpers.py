import torch
from efm3d.aria.pose import PoseTW

from aria_nbv.rendering.plotting import (
    DepthBoxOverlay,
    depth_grid_with_box_overlays,
    depth_histogram,
    project_world_points_to_image,
)


def test_depth_histogram_returns_traces():
    depths = torch.tensor(
        [
            [[1.0, 2.0], [3.0, 4.0]],
            [[0.5, 0.5], [0.5, 0.5]],
        ]
    )
    fig = depth_histogram(depths, bins=5, zfar=5.0)
    assert len(fig.data) == depths.shape[0]


def test_project_world_points_to_image_uses_pose_inverse_and_pinhole_intrinsics():
    pose = PoseTW.from_matrix3x4(torch.eye(3, 4).unsqueeze(0))
    points = torch.tensor(
        [
            [0.0, 0.0, 2.0],
            [1.0, -0.5, 2.0],
        ],
        dtype=torch.float32,
    )

    projected = project_world_points_to_image(
        points,
        pose,
        focal_px=(100.0, 100.0),
        principal_point_px=(50.0, 60.0),
    )

    assert projected[0].tolist() == [50.0, 60.0]
    assert projected[1].tolist() == [100.0, 35.0]


def test_depth_grid_with_box_overlays_adds_projected_wireframe_trace():
    depths = torch.ones((1, 4, 4), dtype=torch.float32)
    corners = torch.tensor(
        [
            [1.0, 1.0],
            [2.0, 1.0],
            [2.0, 2.0],
            [1.0, 2.0],
            [1.0, 1.0],
            [2.0, 1.0],
            [2.0, 2.0],
            [1.0, 2.0],
        ],
        dtype=torch.float32,
    ).numpy()

    fig = depth_grid_with_box_overlays(
        depths,
        overlays=[[DepthBoxOverlay(corners_px=corners, name="target", color="#ff0000")]],
        titles=["selected"],
    )

    assert len(fig.data) == 2
    assert fig.data[1].name == "target"
