"""Stable seed derivation shared by rollout and candidate runtimes."""

from __future__ import annotations

import hashlib
import json
import math
from typing import TypeAlias

SeedPart: TypeAlias = str | int | float | bool | None | tuple["SeedPart", ...]


def _validate_part(value: SeedPart, *, path: str) -> None:
    if value is None or isinstance(value, (str, int, bool)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise TypeError(f"{path} must contain finite floats")
        return
    if isinstance(value, tuple):
        for index, item in enumerate(value):
            _validate_part(item, path=f"{path}[{index}]")
        return
    raise TypeError(f"unsupported seed part at {path}: {type(value).__name__}")


def derive_stable_seed(*parts: SeedPart) -> int:
    """Derive one reproducible unsigned 32-bit seed from a lineage path."""

    for index, part in enumerate(parts):
        _validate_part(part, path=f"parts[{index}]")
    payload = json.dumps(parts, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:4], "big")


__all__ = ["SeedPart", "derive_stable_seed"]
