"""Stable seed derivation shared by rollout and candidate runtimes."""

from __future__ import annotations

import hashlib
import json


def derive_stable_seed(*parts: object) -> int:
    """Derive one reproducible unsigned 32-bit seed from a lineage path."""

    payload = json.dumps(parts, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:4], "big")


__all__ = ["derive_stable_seed"]
