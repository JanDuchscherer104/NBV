"""Batch input normalization for VIN-compatible Lightning scorers.

`aria_nbv.lightning.lit_module.VinLightningModule` trains candidate scorers
through a shared forward contract: actor-visible snippet evidence, candidate
poses, reference pose, PyTorch3D cameras, and optional cached EVL backbone
outputs. This sidecar owns the batch-to-forward-input conversion so future
myopic and finite-horizon Lightning paths can reuse the same device and
snippet/backbone validation without copying the full training step.
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
from ..data_handling.raw.views import is_efm_snippet_view_instance, is_vin_snippet_view_instance
from ..vin.types import EvlBackboneOutput


@dataclass(frozen=True, slots=True)
class CandidateScorerBatchInputs:
    """Device-normalized inputs for a candidate scorer forward pass.

    Attributes:
        efm: Actor-visible EFM or minimal VIN snippet evidence.
        candidate_poses_world_cam: Candidate poses as world←camera
            ``PoseTW["B N 12"]`` or ``PoseTW["N 12"]`` on the module device.
        reference_pose_world_rig: Reference rig pose as world←rig on the module
            device.
        p3d_cameras: PyTorch3D cameras aligned with candidate rows on the
            module device.
        backbone_out: Optional cached EVL backbone output on the module device.
    """

    efm: EfmSnippetView | VinSnippetView
    candidate_poses_world_cam: PoseTW
    reference_pose_world_rig: PoseTW
    p3d_cameras: PerspectiveCameras
    backbone_out: EvlBackboneOutput | None


def prepare_candidate_scorer_batch_inputs(
    batch: VinOracleBatch,
    *,
    device: torch.device,
) -> CandidateScorerBatchInputs:
    """Prepare scorer-forward inputs from one `VinOracleBatch`.

    Args:
        batch: Oracle-labelled VIN batch from the Lightning datamodule.
        device: Destination device used by the owning Lightning module.

    Returns:
        `CandidateScorerBatchInputs` ready to pass to the structural
        `aria_nbv.vin.candidate_scorer.CandidateScorer.forward` protocol.

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
