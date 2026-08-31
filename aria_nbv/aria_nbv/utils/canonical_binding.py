"""Deterministic byte encoding for scientific request identities.

The encoder is intentionally small and closed.  It accepts only values used by
typed request DTOs and rejects ambient Python objects instead of deriving an
unstable identity from ``repr``.
"""

from __future__ import annotations

import struct
import sys
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import fields, is_dataclass
from enum import Enum, StrEnum
from hashlib import sha256

import torch
from efm3d.aria.camera import CameraTW
from efm3d.aria.pose import PoseTW


class BindingEncodingRevision(StrEnum):
    """Version of the canonical request-binding byte encoding."""

    CANONICAL_SHA256_V1 = "canonical_sha256_v1"


class CanonicalBindingError(ValueError):
    """Raised when a value cannot be represented by the canonical encoding."""


def canonical_binding_bytes(value: object) -> bytes:
    """Encode one supported value with type and shape information preserved."""

    return _encode(value)


def canonical_binding_sha256(value: object) -> str:
    """Return the SHA-256 digest of :func:`canonical_binding_bytes`."""

    return sha256(canonical_binding_bytes(value)).hexdigest()


def _framed(tag: bytes, payload: bytes) -> bytes:
    return tag + struct.pack(">Q", len(payload)) + payload


def _encode(value: object) -> bytes:  # noqa: C901 - one closed type dispatch is the interface.
    if value is None:
        return _framed(b"n", b"")
    if isinstance(value, bool):
        return _framed(b"b", b"1" if value else b"0")
    if isinstance(value, int):
        return _framed(b"i", str(value).encode("ascii"))
    if isinstance(value, float):
        if not torch.isfinite(torch.tensor(value, dtype=torch.float64)):
            raise CanonicalBindingError("Canonical bindings require finite floats.")
        return _framed(b"f", struct.pack(">d", value))
    if isinstance(value, str):
        return _framed(b"s", unicodedata.normalize("NFC", value).encode("utf-8"))
    if isinstance(value, Enum):
        return _framed(b"e", _encode(value.value))
    if isinstance(value, torch.device):
        return _framed(b"d", str(value).encode("ascii"))
    if isinstance(value, torch.dtype):
        return _framed(b"y", str(value).encode("ascii"))
    if isinstance(value, PoseTW):
        return _framed(b"p", _encode_tensor(value.tensor()))
    if isinstance(value, CameraTW):
        return _framed(b"c", _encode_tensor(value.tensor()))
    if isinstance(value, torch.Tensor):
        return _framed(b"t", _encode_tensor(value))
    if is_dataclass(value) and not isinstance(value, type):
        payload = b"".join(
            _framed(b"k", _encode(field.name) + _encode(getattr(value, field.name))) for field in fields(value)
        )
        return _framed(b"a", payload)
    if isinstance(value, Mapping):
        encoded_items = [(_encode(key), _encode(item)) for key, item in value.items()]
        encoded_items.sort(key=lambda item: item[0])
        if any(left[0] == right[0] for left, right in zip(encoded_items, encoded_items[1:], strict=False)):
            raise CanonicalBindingError("Mapping keys collide after canonical normalization.")
        return _framed(b"m", b"".join(_framed(b"k", key + item) for key, item in encoded_items))
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, memoryview)):
        return _framed(b"q", b"".join(_framed(b"v", _encode(item)) for item in value))
    if isinstance(value, (bytes, bytearray, memoryview)):
        return _framed(b"x", bytes(value))
    raise CanonicalBindingError(f"Unsupported canonical-binding value: {type(value).__qualname__}.")


def _encode_tensor(value: torch.Tensor) -> bytes:
    tensor = value.detach()
    if tensor.is_floating_point() and not bool(torch.isfinite(tensor).all().item()):
        raise CanonicalBindingError("Canonical bindings require finite tensors.")
    cpu = tensor.contiguous().cpu()
    header = _encode((str(cpu.dtype), tuple(cpu.shape)))
    try:
        array = cpu.numpy()
        if array.dtype.itemsize > 1 and (
            array.dtype.byteorder == ">" or (array.dtype.byteorder == "=" and sys.byteorder == "big")
        ):
            array = array.byteswap().view(array.dtype.newbyteorder("<"))
        else:
            array = array.view(array.dtype.newbyteorder("<"))
        payload = bytes(array.tobytes(order="C"))
    except TypeError as error:
        raise CanonicalBindingError(f"Unsupported tensor dtype for canonical binding: {cpu.dtype}.") from error
    return header + payload


__all__ = [
    "BindingEncodingRevision",
    "CanonicalBindingError",
    "canonical_binding_bytes",
    "canonical_binding_sha256",
]
