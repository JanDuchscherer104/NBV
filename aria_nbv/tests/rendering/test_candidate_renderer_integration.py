import sys
from pathlib import Path

import numpy as np
import torch

# Make vendored efm3d importable
sys.path.append(str(Path(__file__).resolve().parents[2] / "external" / "efm3d"))

try:
    import pytorch3d.renderer as _pytorch3d_renderer  # noqa: F401
except Exception:  # pragma: no cover - availability guard
    PYTORCH3D_AVAILABLE = False
else:  # pragma: no cover - availability guard
    PYTORCH3D_AVAILABLE = True

from efm3d.aria import CameraTW, PoseTW  # noqa: E402
from efm3d.aria.aria_constants import ARIA_CALIB, ARIA_IMG  # noqa: E402

from aria_nbv.configs import PathConfig  # noqa: E402
from aria_nbv.data_handling import AseEfmDatasetConfig  # noqa: E402
from aria_nbv.data_handling.raw.views import EfmSnippetView  # noqa: E402
from aria_nbv.pose_generation.types import CandidateSamplingResult  # noqa: E402
from aria_nbv.rendering import (  # noqa: E402
    CandidateDepthRendererConfig,
    Pytorch3DDepthRendererConfig,
)


def _skip_if_missing_data():
    paths = PathConfig()
    atek_dir = paths.resolve_atek_data_dir("efm")
    if not atek_dir.exists():
        pytest.skip(f"ATEK data dir missing: {atek_dir}", allow_module_level=True)
    if not any(atek_dir.glob("**/*.tar")):
        pytest.skip(f"No ATEK shards found under {atek_dir}", allow_module_level=True)
    mesh_dir = paths.ase_meshes
    if not any(mesh_dir.glob("scene_ply_*.ply")):
        pytest.skip(f"No ASE meshes found under {mesh_dir}", allow_module_level=True)


import pytest  # isort: split  # noqa: E402,E401

_skip_if_missing_data()


@pytest.fixture(scope="session")
def path_cfg():
    return PathConfig()


@pytest.fixture(scope="session")
def efm_config(path_cfg):
    return AseEfmDatasetConfig(
        paths=path_cfg,
        scene_ids=["81283"],
        batch_size=None,
        verbosity=0,
        load_meshes=True,
        require_mesh=True,
        mesh_simplify_ratio=0.02,  # aggressive decimation for test speed
    )


@pytest.fixture(scope="session")
def efm_sample(efm_config):
    ds = efm_config.setup_target()
    return next(iter(ds))


def _single_candidate(sample):
    # Use the SLAM-left intrinsics of the last frame; set ref←cam to identity so world pose = reference_pose.
    base_cam = sample.camera_slam_left.calib
    calib_last = base_cam[-1] if base_cam.tensor().ndim > 1 else base_cam
    t_ref_cam = PoseTW.from_matrix3x4(torch.eye(3, 4).unsqueeze(0))
    size = calib_last.size.reshape(-1, 2)[0]
    focals = calib_last.f.reshape(-1, 2)[0]
    centers = calib_last.c.reshape(-1, 2)[0]
    dist = calib_last.dist.reshape(1, -1)
    cam = CameraTW.from_parameters(
        width=torch.tensor([[float(size[0].item())]]),
        height=torch.tensor([[float(size[1].item())]]),
        fx=torch.tensor([[float(focals[0].item())]]),
        fy=torch.tensor([[float(focals[1].item())]]),
        cx=torch.tensor([[float(centers[0].item())]]),
        cy=torch.tensor([[float(centers[1].item())]]),
        gain=torch.zeros((1, 1)),
        exposure_s=torch.zeros((1, 1)),
        valid_radiusx=torch.tensor([[float(max(size[0].item(), size[1].item()))]]),
        valid_radiusy=torch.tensor([[float(max(size[0].item(), size[1].item()))]]),
        T_camera_rig=t_ref_cam,
        dist_params=dist,
    )
    return CandidateSamplingResult(
        views=cam,
        reference_pose=sample.trajectory.t_world_rig[-1],
        mask_valid=torch.ones(1, dtype=torch.bool),
        masks={},
        shell_poses=t_ref_cam,
    )


@pytest.mark.skipif(not PYTORCH3D_AVAILABLE, reason="PyTorch3D required for this backend")
def test_integration_pytorch3d_backend(efm_sample):
    candidates = _single_candidate(efm_sample)
    cfg = CandidateDepthRendererConfig(
        max_candidates_final=1,
        renderer=Pytorch3DDepthRendererConfig(device="cpu", verbosity=0),
    )
    renderer = cfg.setup_target()
    batch = renderer.render(sample=efm_sample, candidates=candidates)
    depths = batch.depths
    hit_ratio = float((depths < renderer.renderer.config.zfar).float().mean().item())
    assert depths.shape[0] == 1
    assert hit_ratio > 0.1  # should see some geometry in real scene


def test_integration_cpu_backend(efm_sample):
    # Downscale camera for speed on CPU ray tracer.
    cam = efm_sample.camera_slam_left
    scaled_calib = cam.calib.scale_to_size((64, 64))
    num_frames, num_channels, _, _ = cam.images.shape
    scaled_images = torch.zeros(
        (num_frames, num_channels, 64, 64),
        device=cam.images.device,
        dtype=cam.images.dtype,
    )
    efm = dict(efm_sample.efm)
    efm[ARIA_IMG[1]] = scaled_images
    efm[ARIA_CALIB[1]] = scaled_calib
    sample_small = EfmSnippetView(
        efm=efm,
        scene_id=efm_sample.scene_id,
        snippet_id=efm_sample.snippet_id,
        mesh=efm_sample.mesh,
        mesh_verts=efm_sample.mesh_verts,
        mesh_faces=efm_sample.mesh_faces,
    )

    # Heavily decimate mesh for speed while keeping real-scene geometry.
    mesh = efm_sample.mesh
    assert mesh is not None
    keep = np.linspace(0, len(mesh.faces) - 1, num=min(len(mesh.faces), 5_000), dtype=int)
    mesh_small = mesh.submesh([keep], append=True)
    sample_cpu = EfmSnippetView(
        efm=sample_small.efm,
        scene_id=sample_small.scene_id,
        snippet_id=sample_small.snippet_id,
        mesh=mesh_small,
        mesh_verts=torch.from_numpy(mesh_small.vertices).to(dtype=torch.float32),
        mesh_faces=torch.from_numpy(mesh_small.faces).to(dtype=torch.int64),
    )

    candidates = _single_candidate(sample_cpu)
    cfg = CandidateDepthRendererConfig(
        max_candidates_final=1,
        renderer=Pytorch3DDepthRendererConfig(device="cpu", verbosity=0),
    )
    renderer = cfg.setup_target()
    batch = renderer.render(sample=sample_cpu, candidates=candidates)
    depths = batch.depths
    hit_ratio = float((depths < renderer.renderer.config.zfar).float().mean().item())
    assert depths.shape[0] == 1
    assert hit_ratio > 0.1
