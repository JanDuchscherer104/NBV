"""Minimal score contract consumed by finite-candidate replay."""

from __future__ import annotations

from dataclasses import dataclass

import torch

from ...pose_generation.types import CandidateSamplingResult


@dataclass(frozen=True, slots=True)
class CandidateScores:
    """Scores aligned to the hard-valid rows of one candidate table."""

    values: torch.Tensor
    """Compact score vector in stable valid-candidate order."""

    action_mask: torch.Tensor
    """Full-shell hard action mask; invalid rows are never selectable."""

    candidate_shell_indices: torch.Tensor
    """Full-shell row ids corresponding one-to-one with ``values``."""

    name: str
    """Stable semantic name of the score used for action selection."""

    @classmethod
    def from_valid_values(
        cls,
        values: torch.Tensor,
        *,
        name: str,
        candidates: CandidateSamplingResult,
        device: torch.device,
        dtype: torch.dtype,
    ) -> "CandidateScores":
        """Normalize compact scores and bind them to one hard-masked table."""

        action_mask = torch.as_tensor(candidates.mask_valid, device=device, dtype=torch.bool).reshape(-1)
        shell_indices = torch.nonzero(action_mask, as_tuple=False).reshape(-1)
        scores = torch.as_tensor(values, device=device, dtype=dtype).reshape(-1)
        if scores.shape[0] != shell_indices.shape[0]:
            raise ValueError(
                f"Candidate score vector must contain {shell_indices.shape[0]} hard-valid rows, got {scores.shape[0]}.",
            )
        return cls(
            values=scores,
            action_mask=action_mask,
            candidate_shell_indices=shell_indices,
            name=str(name),
        )

    def validate_for(
        self,
        candidates: CandidateSamplingResult,
        *,
        device: torch.device,
        dtype: torch.dtype,
    ) -> "CandidateScores":
        """Verify the hard mask and candidate-order link against ``candidates``."""

        expected_mask = torch.as_tensor(candidates.mask_valid, device=device, dtype=torch.bool).reshape(-1)
        expected_indices = torch.nonzero(expected_mask, as_tuple=False).reshape(-1)
        action_mask = torch.as_tensor(self.action_mask, device=device, dtype=torch.bool).reshape(-1)
        shell_indices = torch.as_tensor(self.candidate_shell_indices, device=device, dtype=torch.long).reshape(-1)
        values = torch.as_tensor(self.values, device=device, dtype=dtype).reshape(-1)
        if not torch.equal(action_mask, expected_mask):
            raise ValueError("CandidateScores.action_mask must equal the candidate table hard-valid mask.")
        if not torch.equal(shell_indices, expected_indices):
            raise ValueError("CandidateScores.candidate_shell_indices must preserve hard-valid candidate order.")
        if values.shape[0] != shell_indices.shape[0]:
            raise ValueError("CandidateScores.values must align one-to-one with candidate_shell_indices.")
        return CandidateScores(
            values=values,
            action_mask=action_mask,
            candidate_shell_indices=shell_indices,
            name=str(self.name),
        )


__all__ = ["CandidateScores"]
