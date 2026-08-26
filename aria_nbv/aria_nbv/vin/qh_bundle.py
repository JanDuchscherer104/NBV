"""Persistence-neutral identity for one immutable Q_H inference bundle."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models.target_finite_horizon import TargetFiniteHorizonScorer

QH_INFERENCE_BUNDLE_SCHEMA_VERSION = "qh-inference-bundle-v1"


@dataclass(frozen=True, slots=True)
class QhInferenceBundleRef:
    """Content-bound location of one immutable Q_H inference bundle."""

    bundle_path: Path
    """Absolute directory containing the verified manifest and payloads."""

    schema_version: str
    """Closed bundle schema expected by the loader."""

    manifest_sha256: str
    """SHA-256 of the canonical manifest payload excluding its own digest field."""


@dataclass(frozen=True, slots=True)
class QhInferenceRuntime:
    """Verified scorer plus the immutable identities required by inference callers."""

    scorer: "TargetFiniteHorizonScorer"
    """Evaluation-mode scorer loaded from the verified scorer-state artifact."""

    bundle_manifest_sha256: str
    """Digest of the verified bundle manifest."""

    scorer_state_sha256: str
    """Digest of the verified scorer-state artifact."""

    scorer_config_hash: str
    """Digest binding the scorer configuration to its serialized state."""

    implementation_sha256: str
    """Digest of the complete importable ``aria_nbv`` package tree."""

    actor_state_contract_hash: str
    """Digest of the actor-visible input contract."""

    learning_contract_hash: str
    """Digest of replay and fitted-Q learning semantics."""

    target_protocol: str
    """Target-input protocol admitted by the learning contract."""

    candidate_config_hashes: tuple[str, ...]
    """Candidate-generation identities admitted by the learning contract."""

    action_mask_semantics: str
    """Meaning of actor action masks for this runtime."""

    representation_semantics: str
    """Meaning of the actor representation consumed by the scorer."""

    trained_horizons: tuple[int, ...]
    """Sorted scalar horizons with positive manifest-bound training support."""


__all__ = ["QH_INFERENCE_BUNDLE_SCHEMA_VERSION", "QhInferenceBundleRef", "QhInferenceRuntime"]
