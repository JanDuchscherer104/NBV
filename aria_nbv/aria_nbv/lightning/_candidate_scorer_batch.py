"""Batch input normalization for VIN-compatible Lightning scorers.

:class:`aria_nbv.lightning.VinLightningModule` trains candidate scorers
through a shared forward contract: actor-visible snippet evidence, candidate
poses, reference pose, PyTorch3D cameras, and optional cached EVL backbone
outputs. This sidecar owns the batch-to-forward-input conversion so future
myopic and finite-horizon Lightning paths can reuse the same device and
snippet/backbone validation without copying the full training step.

Oracle RRI values, point-mesh diagnostics, GT OBBs, and target-evaluation
geometry stay on :class:`aria_nbv.data_handling.VinOracleBatch`; this module
deliberately does not expose them to the scorer forward pass.
"""

from __future__ import annotations

from dataclasses import dataclass

import torch
from efm3d.aria.pose import PoseTW
from pytorch3d.renderer.cameras import PerspectiveCameras  # type: ignore[import-untyped]

from ..data_handling import (
    EfmSnippetView,
    VinOracleBatch,
    VinSnippetView,
)
from ..data_handling.ase_efm.views import is_efm_snippet_view_instance
from ..data_handling.vin_store.views import is_vin_snippet_view_instance
from ..vin.types import EvlBackboneOutput


@dataclass(frozen=True, slots=True)
class CandidateScorerBatchInputs:
    """Device-normalized inputs for a candidate scorer forward pass.

    Attributes:
        efm: Actor-visible EFM or minimal VIN snippet evidence.
        candidate_poses_world_cam: Compact/right-padded candidate table as
            world-from-camera poses on the module device.
        reference_pose_world_rig: World-from-rig reference pose on the module
            device.
        p3d_cameras: PyTorch3D cameras aligned with candidate rows on the
            module device.
        backbone_out: Optional cached actor-visible EVL output on the module
            device.
    """

    efm: EfmSnippetView | VinSnippetView
    """Actor-visible :class:`EfmSnippetView` or :class:`VinSnippetView`.

    Semidense points are expressed in world-frame metres. A minimal VIN view
    requires `backbone_out` because it does not carry all inputs needed to run
    EVL inside the scorer.
    """

    candidate_poses_world_cam: PoseTW
    """World-from-camera ``PoseTW["N_q 12"]`` or ``PoseTW["B N_q 12"]``.

    ``N_q`` is the compact candidate count for one sample or the right-padded
    collation width for a batch. It is not the rollout full-shell width
    ``N_shell``; padded rows are excluded by
    :meth:`VinOracleBatch.candidate_valid_mask` before loss or selection.
    """

    reference_pose_world_rig: PoseTW
    """World-from-rig ``PoseTW["12"]`` or ``PoseTW["B 12"]`` reference pose."""

    p3d_cameras: PerspectiveCameras
    """Candidate-aligned PyTorch3D cameras on the scorer device.

    Batched camera parameters use a flattened ``B*N_q`` camera axis while
    preserving the same row order as `candidate_poses_world_cam`.
    """

    backbone_out: EvlBackboneOutput | None
    """Optional cached actor-visible EVL fields, moved to the scorer device."""


def prepare_candidate_scorer_batch_inputs(
    batch: VinOracleBatch,
    *,
    device: torch.device,
) -> CandidateScorerBatchInputs:
    """Prepare actor-visible scorer inputs from one oracle-labelled batch.

    Args:
        batch: :class:`VinOracleBatch` containing compact/right-padded
            candidates plus oracle-only training labels.
        device: Destination device used by the owning Lightning module.

    Returns:
        :class:`CandidateScorerBatchInputs` ready for the structural candidate
        scorer forward protocol. Oracle labels and GT evaluation assets are
        intentionally absent.

    Raises:
        RuntimeError: If the batch lacks actor-visible snippet evidence or if a
            minimal `VinSnippetView` batch lacks cached backbone outputs.
    """

    efm_snippet_view = batch.efm_snippet_view
    if is_efm_snippet_view_instance(efm_snippet_view) or is_vin_snippet_view_instance(efm_snippet_view):
        efm = efm_snippet_view
    else:
        raise RuntimeError(
            "VIN batch missing semidense snippet view; VinModelV3 requires VinSnippetView or EfmSnippetView.",
        )

    backbone_out = batch.backbone_out
    if backbone_out is None and not is_efm_snippet_view_instance(efm_snippet_view):
        raise RuntimeError(
            "VIN batch missing both efm snippet view and cached backbone outputs.",
        )
    if backbone_out is not None:
        backbone_out = backbone_out.to(device)

    p3d_cameras = batch.p3d_cameras.to(device)
    if p3d_cameras.device != device:
        p3d_cameras = p3d_cameras.to(device)

    return CandidateScorerBatchInputs(
        efm=efm,
        candidate_poses_world_cam=batch.candidate_poses_world_cam.to(device=device),
        reference_pose_world_rig=batch.reference_pose_world_rig.to(device=device),
        p3d_cameras=p3d_cameras,
        backbone_out=backbone_out,
    )


__all__ = [
    "CandidateScorerBatchInputs",
    "prepare_candidate_scorer_batch_inputs",
]
