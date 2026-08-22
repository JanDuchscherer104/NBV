"""Persistence-neutral identity for one immutable Q_H inference bundle."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

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


__all__ = ["QH_INFERENCE_BUNDLE_SCHEMA_VERSION", "QhInferenceBundleRef"]
