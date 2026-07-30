import pytest

pytest.importorskip("power_spherical")

import torch
from efm3d.aria.aria_constants import (
    ARIA_CALIB,
    ARIA_FRAME_ID,
    ARIA_IMG,
    ARIA_IMG_TIME_NS,
    ARIA_POSE_T_WORLD_RIG,
    ARIA_POSE_TIME_NS,
)
from efm3d.aria.camera import CameraTW
from efm3d.aria.pose import PoseTW

from aria_nbv.data_handling.ase_efm.views import EfmSnippetView
from aria_nbv.pose_generation.candidate_generation import CandidateViewGenerator, CandidateViewGeneratorConfig

pytest.importorskip("power_spherical")


def _dummy_camera() -> CameraTW:
    params = torch.tensor([[200.0, 200.0, 160.0, 120.0]], dtype=torch.float32)
    valid_radius = torch.tensor([9999.0], dtype=torch.float32)
    return CameraTW.from_surreal(
        width=torch.tensor([320.0]),
        height=torch.tensor([240.0]),
        type_str="Pinhole",
        params=params,
        valid_radius=valid_radius,
        T_camera_rig=PoseTW.from_matrix3x4(torch.eye(3, 4).unsqueeze(0)),
    )


def _sample_with_mesh(verts: torch.Tensor, faces: torch.Tensor) -> EfmSnippetView:
    cam = _dummy_camera()
    pose = PoseTW.from_matrix3x4(torch.eye(3, 4).unsqueeze(0))
    efm = {
        ARIA_IMG[0]: torch.zeros((1, 3, 4, 4), dtype=torch.float32),
        ARIA_CALIB[0]: cam,
        ARIA_IMG_TIME_NS[0]: torch.tensor([0], dtype=torch.int64),
        ARIA_FRAME_ID[0]: torch.tensor([0], dtype=torch.int64),
        ARIA_POSE_T_WORLD_RIG: pose,
        ARIA_POSE_TIME_NS: torch.tensor([0], dtype=torch.int64),
        "pose/gravity_in_world": torch.tensor([0.0, 0.0, -9.81]),
    }
    bounds_min = torch.tensor([-1.0, -1.0, -1.0])
    bounds_max = torch.tensor([1.0, 1.0, 1.0])
    return EfmSnippetView(
        efm=efm,
        scene_id="scene",
        snippet_id="snippet",
        mesh=None,
        crop_bounds=(bounds_min, bounds_max),
        mesh_verts=verts,
        mesh_faces=faces,
    )


def test_generate_from_typed_sample_uses_existing_mesh_tensors(monkeypatch):
    verts = torch.tensor([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], dtype=torch.float32)
    faces = torch.tensor([[0, 1, 2]], dtype=torch.int64)
    sample = _sample_with_mesh(verts, faces)

    _ = monkeypatch

    cfg = CandidateViewGeneratorConfig(
        num_samples=4,
        oversample_factor=1.0,
        max_resamples=1,
        ensure_collision_free=False,
        ensure_free_space=False,
        min_distance_to_mesh=0.0,
        device="cpu",
    )
    gen = CandidateViewGenerator(cfg)

    result = gen.generate_from_typed_sample(sample)

    assert result.views.tensor().shape[0] == cfg.num_samples
