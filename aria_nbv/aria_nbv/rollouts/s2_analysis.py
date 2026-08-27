"""Acquire and fingerprint target-frame spherical evidence from rollout stores.

This module is the presentation-free seam for S2 diagnostics. It owns the
validated analysis configuration, rollout-store opening, complete-population
reduction, and canonical evidence digest. Plot construction belongs to
:mod:`aria_nbv.rollouts.s2_plotting`; Streamlit and immutable reporting consume
the same acquired evidence without reopening or reimplementing the reducer.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
from pydantic import Field

from ..utils import BaseConfig
from .inspection import build_manifest_facts, s2_target_direction_histogram
from .zarr_store import RolloutZarrStoreReader


class S2AnalysisConfig(BaseConfig):
    """Configure complete target-frame S2 reduction and bounded overlays."""

    azimuth_bins: int = Field(default=36, ge=8, le=144)
    """Number of uniform target-frame azimuth cells."""

    elevation_bins: int = Field(default=18, ge=4, le=72)
    """Number of uniform target-frame ``z`` cells, yielding equal solid angle."""

    projection_limit: int = Field(default=2_000, ge=1)
    """Maximum deterministic incidence points retained per channel and store."""


@dataclass(frozen=True, slots=True)
class S2StoreEvidence:
    """One immutable rollout store's analyzed spherical evidence.

    The payload is the dataclass projection returned by the canonical rollout
    reducer. ``payload_sha256`` covers its normalized arrays, scalar support,
    provenance, and exclusions; callers may therefore bind figures and tables
    to the exact analyzed evidence rather than only to a filesystem path.
    """

    slot: int
    """One-based deterministic store slot within a report acquisition."""

    store_id: str
    """Persisted rollout manifest SHA-256 identifying the immutable store."""

    path: Path
    """Resolved rollout Zarr directory used for this acquisition."""

    config: S2AnalysisConfig
    """Validated reducer configuration frozen with the evidence."""

    payload: dict[str, Any]
    """Serialized :class:`~aria_nbv.rollouts.inspection.S2DirectionHistogram`."""

    payload_sha256: str
    """SHA-256 of :func:`canonical_s2_payload` for ``payload``."""


def acquire_s2_store_evidence(
    path: Path,
    *,
    slot: int,
    config: S2AnalysisConfig,
) -> S2StoreEvidence:
    """Open one immutable store and execute the canonical S2 reducer once.

    Args:
        path: Rollout Zarr directory. The strict reader and manifest projection
            validate persisted structure before analysis.
        slot: One-based stable report slot assigned by the caller's sorted
            source population.
        config: Complete-count binning and display-reservoir configuration.

    Returns:
        Acquired evidence with resolved source identity, serialized reducer
        output, and a canonical payload digest.
    """

    resolved = path.expanduser().resolve()
    reader = RolloutZarrStoreReader(resolved)
    manifest_payload = build_manifest_facts(reader).payload
    store_id = str(manifest_payload["root_attrs"]["manifest_sha256"])
    payload = asdict(
        s2_target_direction_histogram(
            reader,
            azimuth_bins=config.azimuth_bins,
            elevation_bins=config.elevation_bins,
            projection_limit=config.projection_limit,
        )
    )
    payload_sha256 = hashlib.sha256(canonical_s2_payload(payload)).hexdigest()
    return S2StoreEvidence(
        slot=slot,
        store_id=store_id,
        path=resolved,
        config=config,
        payload=payload,
        payload_sha256=payload_sha256,
    )


def canonical_s2_payload(payload: dict[str, Any]) -> bytes:
    """Serialize one reducer result for immutable source identity."""

    def normalize(value: Any) -> Any:
        if isinstance(value, dict):
            return {str(key): normalize(item) for key, item in sorted(value.items())}
        if isinstance(value, list | tuple):
            return [normalize(item) for item in value]
        if isinstance(value, np.ndarray):
            return normalize(value.tolist())
        if isinstance(value, np.generic):
            return value.item()
        return value

    return json.dumps(
        normalize(payload),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


__all__ = [
    "S2AnalysisConfig",
    "S2StoreEvidence",
    "acquire_s2_store_evidence",
    "canonical_s2_payload",
]
