"""Oracle candidate labels and scorer results.

Oracle scorers produce compact valid-candidate labels. Replay receives only a
separate `CandidateScores` projection assembled at a pipeline boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

import torch

if TYPE_CHECKING:
    from ..pose_generation.types import CandidateSamplingResult


@dataclass(frozen=True, slots=True)
class OracleCandidateLabels:
    """Compact Oracle labels aligned with stable valid candidate rows.

    ``V`` is the hard-valid subset of a candidate shell. These labels are
    privileged supervision and audit outputs; actor inputs receive only the
    separately projected candidate context.
    """

    scores: torch.Tensor
    """Selection-objective values as ``Tensor["V", float32]``."""

    score_label: str
    """Stable semantic name for `scores`."""

    metrics: dict[str, torch.Tensor]
    """Oracle metrics, each ``Tensor["V", float32]`` in compact-valid order."""

    candidate_shell_indices: torch.Tensor
    """Full-shell row ids as ``Tensor["V", int64]`` for compact label rows."""

    provenance: str
    """Scorer family that produced the labels, such as `target_rri`."""

    def selected(self, valid_index: int) -> dict[str, float]:
        """Return scalar labels for one selected compact candidate row."""

        return {name: float(values[valid_index].item()) for name, values in self.metrics.items()}

    def validate(
        self,
        candidates: CandidateSamplingResult,
        *,
        device: torch.device,
        dtype: torch.dtype,
    ) -> "OracleCandidateLabels":
        """Normalize tensors and verify compact rows against the candidate table."""

        action_mask = torch.as_tensor(candidates.mask_valid, device=device, dtype=torch.bool).reshape(-1)
        expected = torch.nonzero(action_mask, as_tuple=False).reshape(-1)
        shell_indices = torch.as_tensor(self.candidate_shell_indices, device=device, dtype=torch.long).reshape(-1)
        if not torch.equal(shell_indices, expected):
            raise ValueError("OracleCandidateLabels must preserve hard-valid candidate order.")
        scores = torch.as_tensor(self.scores, device=device, dtype=dtype).reshape(-1)
        if scores.shape[0] != expected.shape[0]:
            raise ValueError("OracleCandidateLabels.scores must align with valid candidates.")
        metrics: dict[str, torch.Tensor] = {}
        for name, values in self.metrics.items():
            metric = torch.as_tensor(values, device=device, dtype=dtype).reshape(-1)
            if metric.shape[0] != expected.shape[0]:
                raise ValueError(f"Oracle metric '{name}' must align with valid candidates.")
            metrics[name] = metric
        return replace(self, scores=scores, metrics=metrics, candidate_shell_indices=shell_indices)


@dataclass(slots=True)
class RetainedOracleEvidence:
    """Heavy Oracle evidence retained temporarily or for explicit audits.

    Candidate-leading tensors use the compact hard-valid axis ``V``. Point
    coordinates are world-frame metres and padded axes are paired with length
    vectors so padding never becomes geometric evidence.
    """

    candidate_point_clouds_world: torch.Tensor | None = None
    """Padded clouds as ``Tensor["V P 3", float32]`` in world metres."""

    candidate_point_cloud_lengths: torch.Tensor | None = None
    """Valid point counts as ``Tensor["V", int64]`` for padded clouds."""

    target_eval_current_points_world: torch.Tensor | None = None
    """Current target crop as ``Tensor["P_t 3", float32]`` in world metres."""

    target_eval_candidate_points_world: torch.Tensor | None = None
    """Candidate target crops as ``Tensor["V P_q 3", float32]`` in world metres."""

    target_eval_candidate_point_lengths: torch.Tensor | None = None
    """Valid target-crop counts as ``Tensor["V", int64]``."""

    target_eval_crop_policy: str | None = None
    """Versioned target-crop policy used for retained evidence."""

    target_eval_voxel_size_m: float | None = None
    """Voxel size used to fuse target evaluation evidence, in metres."""

    target_eval_max_points: int | None = None
    """Configured target-evidence point budget."""

    selected_depth_m: torch.Tensor | None = None
    """Selected depth as ``Tensor["H_d W_d", float32]`` in metres."""

    selected_depth_valid_mask: torch.Tensor | None = None
    """Finite-hit mask as ``Tensor["H_d W_d", bool]`` for `selected_depth_m`."""

    selected_depth_focal_px: tuple[float, float] | None = None
    """Selected-depth focal lengths `(fx, fy)` in pixels."""

    selected_depth_principal_point_px: tuple[float, float] | None = None
    """Selected-depth principal point `(cx, cy)` in pixels."""

    selected_depth_image_size_hw: tuple[int, int] | None = None
    """Selected-depth image size `(height, width)`."""

    def selected_point_cloud(self, valid_index: int) -> torch.Tensor | None:
        """Return the unpadded point cloud for one compact candidate row."""

        if self.candidate_point_clouds_world is None:
            return None
        row_index = 0 if self.candidate_point_clouds_world.shape[0] == 1 else valid_index
        cloud = self.candidate_point_clouds_world[row_index]
        if self.candidate_point_cloud_lengths is None:
            return cloud
        return cloud[: int(self.candidate_point_cloud_lengths[row_index].item())]

    def compact_for_selection(self, valid_index: int, *, retain_target_crops: bool) -> "RetainedOracleEvidence":
        """Drop non-selected render evidence while preserving configured audits."""

        selected = self.selected_point_cloud(valid_index)
        return RetainedOracleEvidence(
            candidate_point_clouds_world=None if selected is None else selected.unsqueeze(0),
            candidate_point_cloud_lengths=(
                None
                if selected is None
                else torch.tensor([selected.shape[0]], device=selected.device, dtype=torch.long)
            ),
            target_eval_current_points_world=(self.target_eval_current_points_world if retain_target_crops else None),
            target_eval_candidate_points_world=(
                self.target_eval_candidate_points_world if retain_target_crops else None
            ),
            target_eval_candidate_point_lengths=(
                self.target_eval_candidate_point_lengths if retain_target_crops else None
            ),
            target_eval_crop_policy=self.target_eval_crop_policy if retain_target_crops else None,
            target_eval_voxel_size_m=self.target_eval_voxel_size_m if retain_target_crops else None,
            target_eval_max_points=self.target_eval_max_points if retain_target_crops else None,
        )

    def validate(
        self,
        *,
        num_valid: int,
        device: torch.device,
        dtype: torch.dtype,
    ) -> "RetainedOracleEvidence":
        """Normalize candidate evidence and verify compact-row alignment."""

        clouds, lengths = _validated_point_cloud_rows(
            self.candidate_point_clouds_world,
            self.candidate_point_cloud_lengths,
            num_valid=num_valid,
            device=device,
            dtype=dtype,
            name="candidate_point_clouds_world",
        )
        target_clouds, target_lengths = _validated_point_cloud_rows(
            self.target_eval_candidate_points_world,
            self.target_eval_candidate_point_lengths,
            num_valid=num_valid,
            device=device,
            dtype=dtype,
            name="target_eval_candidate_points_world",
        )
        current = self.target_eval_current_points_world
        if current is not None:
            current = torch.as_tensor(current, device=device, dtype=dtype).reshape(-1, 3)
        return replace(
            self,
            candidate_point_clouds_world=clouds,
            candidate_point_cloud_lengths=lengths,
            target_eval_current_points_world=current,
            target_eval_candidate_points_world=target_clouds,
            target_eval_candidate_point_lengths=target_lengths,
        )


@dataclass(frozen=True, slots=True)
class OracleCandidateEvaluation:
    """One scorer result split into compact labels and retained evidence.

    Both payloads align to the same hard-valid axis ``V``; validation rejects
    any shell-index or leading-axis mismatch before replay consumes scores.
    """

    labels: OracleCandidateLabels
    """Compact supervision labels and full-shell row mapping."""

    evidence: RetainedOracleEvidence
    """Optional heavy geometry retained outside actor-visible state."""

    def validate(
        self,
        candidates: CandidateSamplingResult,
        *,
        device: torch.device,
        dtype: torch.dtype,
    ) -> "OracleCandidateEvaluation":
        """Return a normalized scorer result aligned with `candidates`."""

        labels = self.labels.validate(candidates, device=device, dtype=dtype)
        evidence = self.evidence.validate(num_valid=labels.scores.shape[0], device=device, dtype=dtype)
        return replace(self, labels=labels, evidence=evidence)


def _validated_point_cloud_rows(
    points: torch.Tensor | None,
    lengths: torch.Tensor | None,
    *,
    num_valid: int,
    device: torch.device,
    dtype: torch.dtype,
    name: str,
) -> tuple[torch.Tensor | None, torch.Tensor | None]:
    if points is None:
        if lengths is not None:
            raise ValueError(f"{name} lengths require point-cloud rows.")
        return None, None
    rows = torch.as_tensor(points, device=device, dtype=dtype)
    if rows.ndim != 3 or rows.shape[0] != num_valid or rows.shape[2] != 3:
        raise ValueError(f"{name} must have shape (num_valid, P, 3).")
    if lengths is None:
        row_lengths = torch.full((num_valid,), rows.shape[1], device=device, dtype=torch.long)
    else:
        row_lengths = torch.as_tensor(lengths, device=device, dtype=torch.long).reshape(-1)
        if row_lengths.shape[0] != num_valid:
            raise ValueError(f"{name} lengths must align with valid candidates.")
    return rows, row_lengths


__all__ = ["OracleCandidateEvaluation", "OracleCandidateLabels", "RetainedOracleEvidence"]
