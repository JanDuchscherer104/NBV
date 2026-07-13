"""Canonical conversions between raw and compact ASE-ATEK identifiers."""

from __future__ import annotations

import re
from typing import Any

_RAW_ASE_ATEK_SAMPLE_RE = re.compile(r"AriaSyntheticEnvironment_(?P<scene>[^_]+)_AtekDataSample_(?P<sample>[^_:/.\s]+)")
_COMPACT_ASE_ATEK_SAMPLE_RE = re.compile(r"ASE_(?P<scene>[^_]+)_Atek_(?P<sample>[^_:/.\s]+)")


def compact_ase_atek_sample_id(raw: str) -> str:
    """Return the compact public identifier for one ASE-ATEK sample key."""

    def _replace(match: re.Match[str]) -> str:
        return f"ASE_{match.group('scene')}_Atek_{match.group('sample')}"

    return _RAW_ASE_ATEK_SAMPLE_RE.sub(_replace, str(raw))


def raw_ase_atek_sample_id(compact: str) -> str | None:
    """Return the raw ATEK key for a compact ASE-ATEK identifier."""

    match = _COMPACT_ASE_ATEK_SAMPLE_RE.fullmatch(str(compact))
    if match is None:
        return None
    return f"AriaSyntheticEnvironment_{match.group('scene')}_AtekDataSample_{match.group('sample')}"


def compact_ase_atek_identifiers(value: Any) -> Any:
    """Recursively compact ASE-ATEK identifiers inside JSON-like objects."""

    if isinstance(value, str):
        return compact_ase_atek_sample_id(value)
    if isinstance(value, list):
        return [compact_ase_atek_identifiers(item) for item in value]
    if isinstance(value, tuple):
        return tuple(compact_ase_atek_identifiers(item) for item in value)
    if isinstance(value, dict):
        return {compact_ase_atek_identifiers(key): compact_ase_atek_identifiers(item) for key, item in value.items()}
    return value


def _ase_atek_identifier_variants(identifier: str) -> set[str]:
    """Return raw and compact variants for matching one ASE-ATEK identifier."""

    value = str(identifier)
    variants = {value, compact_ase_atek_sample_id(value)}
    raw = raw_ase_atek_sample_id(value)
    if raw is not None:
        variants.add(raw)
    return {variant for variant in variants if variant}


__all__ = [
    "compact_ase_atek_identifiers",
    "compact_ase_atek_sample_id",
    "raw_ase_atek_sample_id",
]
