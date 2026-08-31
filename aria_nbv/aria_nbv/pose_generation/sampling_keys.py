"""Versioned random-key facts for finite candidate generation."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal


class CandidateSubstreamRevision(StrEnum):
    """Candidate-local seed behavior retained across interface migrations."""

    SHIPPED_V1 = "shipped_mixture_seed_paths_v1"


@dataclass(frozen=True, slots=True)
class CandidateSamplingKey:
    """Root key and interpretation used for one candidate-generation request."""

    revision: CandidateSubstreamRevision
    """Versioned interpretation of the root seed."""

    source: Literal["rollout_proposal", "direct_base"]
    """Legacy seed path whose exact behavior must be retained."""

    root_seed: int | None
    """Non-negative root seed, or ``None`` to retain global RNG behavior."""

    def __post_init__(self) -> None:
        if not isinstance(self.revision, CandidateSubstreamRevision):
            raise ValueError("Candidate sampling revision must be a declared CandidateSubstreamRevision.")
        if self.source not in {"rollout_proposal", "direct_base"}:
            raise ValueError("Candidate sampling source must be rollout_proposal or direct_base.")
        if self.root_seed is not None and (
            isinstance(self.root_seed, bool) or not isinstance(self.root_seed, int) or self.root_seed < 0
        ):
            raise ValueError("Candidate root_seed must be a non-negative integer or None.")


def derive_shipped_component_seed(node_seed: int, component_identity: str) -> int:
    """Preserve the shipped SHA-256 component-local seed derivation exactly."""

    payload = json.dumps(
        ("component", int(node_seed), str(component_identity)),
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:4], "big")


__all__ = ["CandidateSamplingKey", "CandidateSubstreamRevision", "derive_shipped_component_seed"]
