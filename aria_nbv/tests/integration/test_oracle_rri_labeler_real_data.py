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

import pytest  # isort: split

from aria_nbv.configs import PathConfig
from aria_nbv.data_handling import AseEfmDatasetConfig
from aria_nbv.pipelines import OracleRriLabelerConfig
from aria_nbv.pose_generation import CandidateViewGeneratorConfig
from aria_nbv.pose_generation.types import ViewDirectionMode
from aria_nbv.rendering import CandidateDepthRendererConfig, Pytorch3DDepthRendererConfig
from aria_nbv.rri_metrics.oracle_rri import OracleRRIConfig
from aria_nbv.utils import Verbosity


def _skip_if_missing_data() -> None:
    paths = PathConfig()
    atek_dir = paths.resolve_atek_data_dir("efm")
    if not atek_dir.exists():
        pytest.skip(f"ATEK data dir missing: {atek_dir}", allow_module_level=True)
    if not any(atek_dir.glob("**/*.tar")):
        pytest.skip(f"No ATEK shards found under {atek_dir}", allow_module_level=True)
    mesh_dir = paths.ase_meshes
    if not any(mesh_dir.glob("scene_ply_*.ply")):
        pytest.skip(f"No ASE meshes found under {mesh_dir}", allow_module_level=True)


_skip_if_missing_data()


@pytest.fixture(scope="session")
def efm_sample():
    cfg = AseEfmDatasetConfig(
        scene_ids=["81283"],
        batch_size=None,
        load_meshes=True,
        require_mesh=True,
        mesh_simplify_ratio=0.02,  # aggressive decimation for speed
        device="cpu",
        verbosity=Verbosity.QUIET,
        is_debug=True,
    )
    ds = cfg.setup_target()
    return next(iter(ds))


@pytest.mark.skipif(not PYTORCH3D_AVAILABLE, reason="PyTorch3D required for this pipeline")
def test_oracle_rri_labeler_runs_real_data(efm_sample):
    mesh = efm_sample.mesh
    assert mesh is not None

    # Keep the real data-flow but cap mesh complexity for test runtime.
    keep_faces = min(int(mesh.faces.shape[0]), 2_000)
    keep_idx = np.linspace(0, int(mesh.faces.shape[0]) - 1, num=keep_faces, dtype=int)
    mesh_small = mesh.submesh([keep_idx], append=True)
    verts_small = torch.as_tensor(mesh_small.vertices, dtype=torch.float32)
    faces_small = torch.as_tensor(mesh_small.faces, dtype=torch.int64)
    sample_small = type(efm_sample)(
        efm=efm_sample.efm,
        scene_id=efm_sample.scene_id,
        snippet_id=efm_sample.snippet_id,
        mesh=mesh_small,
        crop_bounds=efm_sample.crop_bounds,
        mesh_verts=verts_small,
        mesh_faces=faces_small,
    )

    generator_cfg = CandidateViewGeneratorConfig(
        num_samples=3,
        oversample_factor=1.0,
        max_resamples=0,
        # Deterministic + stable: keep the camera at the reference pose with the same rotation.
        min_radius=0.0,
        max_radius=0.0,
        view_direction_mode=ViewDirectionMode.FORWARD_RIG,
        # Disable pruning rules for speed + determinism in tests.
        min_distance_to_mesh=0.0,
        ensure_collision_free=False,
        ensure_free_space=False,
        device="cpu",
        verbosity=Verbosity.QUIET,
        is_debug=False,
    )

    depth_cfg = CandidateDepthRendererConfig(
        renderer=Pytorch3DDepthRendererConfig(
            device="cpu",
            verbosity=Verbosity.QUIET,
            dtype="float32",
        ),
        max_candidates_final=3,
        resolution_scale=0.1,
        verbosity=Verbosity.QUIET,
        is_debug=False,
    )

    oracle_cfg = OracleRRIConfig()

    cfg = OracleRriLabelerConfig(
        generator=generator_cfg,
        depth=depth_cfg,
        oracle=oracle_cfg,
        backprojection_stride=32,
        device="cpu",
    )
    labeler = cfg.setup_target()
    batch = labeler.run(sample_small)

    assert batch.depths.depths.shape[0] == batch.rri.rri.shape[0]
    assert batch.depths.candidate_indices.shape[0] == batch.rri.rri.shape[0]
    assert torch.isfinite(batch.rri.rri).all()
