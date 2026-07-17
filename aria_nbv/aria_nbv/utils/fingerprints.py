"""Stable short fingerprints for configs and persisted lineage payloads.

This module provides dedicated hashes for :class:`BaseConfig`, msgspec
payloads, and JSON-compatible dictionaries, preserving each surface's canonical
serialization convention. It owns deterministic digest/truncation mechanics,
not schema migration, semantic equivalence, authentication, or signatures.

Each helper preserves its existing serialization convention; these hashes are
identity aids, not cryptographic authenticity or content-signing guarantees.
"""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, Any

import msgspec

if TYPE_CHECKING:
    from .base_config import BaseConfig


def stable_config_hash(config: "BaseConfig", *, length: int = 16) -> str:
    """Hash a `BaseConfig` JSON-able dump with the existing lineage semantics."""

    payload = repr(config.model_dump_jsonable()).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:length]


def stable_msgspec_hash(payload: object, *, length: int = 16) -> str:
    """Hash a msgspec-serializable lineage payload."""

    return hashlib.sha256(msgspec.json.encode(payload)).hexdigest()[:length]


def stable_json_signature(payload: dict[str, Any]) -> str:
    """Return the existing SHA-1 signature for JSON-serializable offline metadata."""

    serial = json.dumps(payload, sort_keys=True, ensure_ascii=True)
    return hashlib.sha1(serial.encode("utf-8")).hexdigest()


__all__ = ["stable_config_hash", "stable_json_signature", "stable_msgspec_hash"]
