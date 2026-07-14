"""Deterministic candidate color mapping for Rerun inspector views.

The helpers in this module return plain ``uint8`` RGBA arrays that can be
passed directly to Rerun component constructors.  They intentionally avoid a
Matplotlib dependency so diagnostic colors stay stable across environments.
Validity masks retain their hard action semantics; oracle RRI and rank are
diagnostic overlays and never determine whether a candidate is selectable.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

import numpy as np
import torch
from numpy.typing import NDArray

ColorMode = Literal["oracle_rri", "rank", "validity"]

ArrayLike1D = Sequence[float] | Sequence[int] | np.ndarray | torch.Tensor
BoolArrayLike1D = Sequence[bool] | np.ndarray | torch.Tensor
RGBAArray = NDArray[np.uint8]

VALID_RGBA = np.array([34, 197, 94, 255], dtype=np.uint8)
"""``ndarray["4", uint8]`` color used for valid candidates."""

INVALID_RGBA = np.array([148, 163, 184, 96], dtype=np.uint8)
"""Muted ``ndarray["4", uint8]`` color used for invalid candidates."""

UNKNOWN_RGBA = np.array([100, 116, 139, 160], dtype=np.uint8)
"""Fallback ``ndarray["4", uint8]`` color for non-finite diagnostics."""

TARGET_OBB_RGBA = np.array([255, 55, 95, 255], dtype=np.uint8)
"""Distinct ``ndarray["4", uint8]`` color for a resolved target OBB."""

_RRI_STOPS = np.array(
    [
        [68, 1, 84],
        [59, 82, 139],
        [33, 145, 140],
        [94, 201, 98],
        [253, 231, 37],
    ],
    dtype=np.float32,
)

_RANK_PALETTE = np.array(
    [
        [37, 99, 235],
        [16, 185, 129],
        [245, 158, 11],
        [239, 68, 68],
        [139, 92, 246],
        [20, 184, 166],
        [236, 72, 153],
        [107, 114, 128],
    ],
    dtype=np.uint8,
)

_STEP_PALETTE = np.array(
    [
        [56, 189, 248],
        [251, 191, 36],
        [168, 85, 247],
        [34, 197, 94],
        [244, 114, 182],
        [249, 115, 22],
        [20, 184, 166],
        [239, 68, 68],
    ],
    dtype=np.uint8,
)

_GT_OBB_PALETTE = np.array(
    [
        [245, 158, 11],
        [250, 204, 21],
        [234, 179, 8],
        [251, 146, 60],
        [252, 211, 77],
        [217, 119, 6],
        [253, 186, 116],
        [202, 138, 4],
    ],
    dtype=np.uint8,
)

_DETECTED_OBB_PALETTE = np.array(
    [
        [59, 130, 246],
        [14, 165, 233],
        [6, 182, 212],
        [99, 102, 241],
        [45, 212, 191],
        [37, 99, 235],
        [34, 211, 238],
        [129, 140, 248],
    ],
    dtype=np.uint8,
)


def oracle_rri_to_rgba(
    oracle_rri: ArrayLike1D,
    *,
    validity: BoolArrayLike1D | None = None,
    vmin: float | None = None,
    vmax: float | None = None,
    alpha: int = 255,
) -> RGBAArray:
    """Map oracle RRI values to deterministic RGBA colors.

    Args:
        oracle_rri: ``Tensor["N", float32]`` oracle/evaluation values. Higher
            finite values map to brighter colors.
        validity: Optional ``Tensor["N", bool]`` hard validity mask. Invalid candidates override
            the RRI color with `INVALID_RGBA`.
        vmin: Optional lower normalization bound.  Defaults to the minimum
            finite RRI in ``oracle_rri``.
        vmax: Optional upper normalization bound.  Defaults to the maximum
            finite RRI in ``oracle_rri``.
        alpha: Alpha channel for finite, valid RRI colors.

    Returns:
        ``ndarray["N 4", uint8]`` aligned with the input candidate axis.
    """

    values = _as_1d_array(oracle_rri, name="oracle_rri", dtype=np.float32)
    alpha_u8 = _validate_uint8_scalar(alpha, name="alpha")
    colors = np.tile(UNKNOWN_RGBA, (values.shape[0], 1))

    finite = np.isfinite(values)
    if finite.any():
        lo = float(np.nanmin(values[finite])) if vmin is None else float(vmin)
        hi = float(np.nanmax(values[finite])) if vmax is None else float(vmax)
        if not np.isfinite(lo) or not np.isfinite(hi):
            raise ValueError(f"RRI normalization bounds must be finite, got vmin={lo}, vmax={hi}")

        norm = np.full(values.shape, 0.5, dtype=np.float32)
        if hi > lo:
            norm[finite] = np.clip((values[finite] - lo) / (hi - lo), 0.0, 1.0)

        colors[finite, :3] = _interpolate_rgb(_RRI_STOPS, norm[finite])
        colors[finite, 3] = alpha_u8

    return _apply_validity_override(colors, validity)


def rank_to_rgba(
    ranks: ArrayLike1D,
    *,
    validity: BoolArrayLike1D | None = None,
    alpha: int = 255,
) -> RGBAArray:
    """Map integer candidate ranks to a stable categorical RGBA palette.

    Args:
        ranks: ``Tensor["N", int64]`` candidate ranks where rank ``0`` receives the first palette
            color.
        validity: Optional ``Tensor["N", bool]`` hard validity mask. Invalid candidates override
            the rank color with `INVALID_RGBA`.
        alpha: Alpha channel for valid rank colors.

    Returns:
        ``ndarray["N 4", uint8]`` aligned with the rank axis.
    """

    values = _as_1d_array(ranks, name="ranks", dtype=np.int64)
    alpha_u8 = _validate_uint8_scalar(alpha, name="alpha")
    colors = np.empty((values.shape[0], 4), dtype=np.uint8)
    palette_idx = np.mod(values, _RANK_PALETTE.shape[0])
    colors[:, :3] = _RANK_PALETTE[palette_idx]
    colors[:, 3] = alpha_u8
    return _apply_validity_override(colors, validity)


def validity_to_rgba(validity: BoolArrayLike1D) -> RGBAArray:
    """Map candidate validity directly to valid/invalid RGBA colors.

    Args:
        validity: ``Tensor["N", bool]`` hard candidate-validity mask.

    Returns:
        ``ndarray["N 4", uint8]`` using only valid/invalid palette entries.
    """

    mask = _as_bool_array(validity, count=None)
    colors = np.tile(INVALID_RGBA, (mask.shape[0], 1))
    colors[mask] = VALID_RGBA
    return colors


def step_to_rgba(step_indices: ArrayLike1D, *, alpha: int = 255) -> RGBAArray:
    """Map ``Tensor["N", int64]`` rollout depths to ``ndarray["N 4", uint8]``."""

    values = _as_1d_array(step_indices, name="step_indices", dtype=np.int64)
    alpha_u8 = _validate_uint8_scalar(alpha, name="alpha")
    colors = np.empty((values.shape[0], 4), dtype=np.uint8)
    colors[:, :3] = _STEP_PALETTE[np.mod(values, _STEP_PALETTE.shape[0])]
    colors[:, 3] = alpha_u8
    return colors


def obb_semantic_rgba(
    sem_ids: ArrayLike1D,
    *,
    family: Literal["gt", "detected"],
    target_mask: BoolArrayLike1D | None = None,
    alpha: int = 235,
) -> RGBAArray:
    """Color OBB rows while keeping GT and detected evidence visually distinct.

    Args:
        sem_ids: ``Tensor["K", int64]`` semantic ids aligned with OBB rows.
        family: ``"gt"`` for oracle/evaluation boxes or ``"detected"`` for
            actor-visible predicted/tracked boxes.
        target_mask: Optional ``Tensor["K", bool]`` rows to highlight.
        alpha: Default alpha channel in ``[0, 255]``.

    Returns:
        ``ndarray["K 4", uint8]`` semantic colors.
    """

    values = _as_1d_array(sem_ids, name="sem_ids", dtype=np.int64)
    alpha_u8 = _validate_uint8_scalar(alpha, name="alpha")
    palette = _GT_OBB_PALETTE if family == "gt" else _DETECTED_OBB_PALETTE
    colors = np.empty((values.shape[0], 4), dtype=np.uint8)
    colors[:, :3] = palette[np.mod(values, palette.shape[0])]
    colors[:, 3] = alpha_u8
    if target_mask is not None:
        mask = _as_bool_array(target_mask, count=colors.shape[0])
        colors[mask] = TARGET_OBB_RGBA
    return colors


def candidate_rgba(
    mode: ColorMode,
    *,
    oracle_rri: ArrayLike1D | None = None,
    ranks: ArrayLike1D | None = None,
    validity: BoolArrayLike1D | None = None,
    alpha: int = 255,
) -> RGBAArray:
    """Return candidate colors for the requested scalar or categorical mode.

    Args:
        mode: Color mapping mode, one of ``"oracle_rri"``, ``"rank"``, or
            ``"validity"``.
        oracle_rri: ``Tensor["N", float32]`` oracle values required for
            ``mode="oracle_rri"``.
        ranks: ``Tensor["N", int64]`` values required for ``mode="rank"``.
        validity: ``Tensor["N", bool]`` hard mask used directly or as override.
        alpha: Alpha channel for valid non-validity color modes.

    Returns:
        ``ndarray["N 4", uint8]`` aligned with the supplied candidate axis.
    """

    if mode == "oracle_rri":
        if oracle_rri is None:
            raise ValueError("oracle_rri is required when mode='oracle_rri'")
        return oracle_rri_to_rgba(oracle_rri, validity=validity, alpha=alpha)
    if mode == "rank":
        if ranks is None:
            raise ValueError("ranks is required when mode='rank'")
        return rank_to_rgba(ranks, validity=validity, alpha=alpha)
    if validity is None:
        raise ValueError("validity is required when mode='validity'")
    return validity_to_rgba(validity)


def _as_1d_array(values: ArrayLike1D, *, name: str, dtype: np.dtype | type[np.generic]) -> np.ndarray:
    """Convert a tensor or array-like input to a one-dimensional NumPy array."""

    if isinstance(values, torch.Tensor):
        arr = values.detach().cpu().numpy()
    else:
        arr = np.asarray(values)
    arr = arr.reshape(-1)
    return arr.astype(dtype, copy=False)


def _as_bool_array(values: BoolArrayLike1D, *, count: int | None) -> np.ndarray:
    """Convert a tensor or array-like mask to one-dimensional boolean values."""

    if isinstance(values, torch.Tensor):
        arr = values.detach().cpu().numpy()
    else:
        arr = np.asarray(values)
    mask = arr.reshape(-1).astype(bool, copy=False)
    if count is not None and mask.shape[0] != count:
        raise ValueError(f"validity length {mask.shape[0]} must match color count {count}")
    return mask


def _apply_validity_override(colors: RGBAArray, validity: BoolArrayLike1D | None) -> RGBAArray:
    """Apply invalid-candidate coloring to a copied RGBA array."""

    out = colors.copy()
    if validity is None:
        return out
    mask = _as_bool_array(validity, count=out.shape[0])
    out[~mask] = INVALID_RGBA
    return out


def _interpolate_rgb(stops: np.ndarray, normalized: np.ndarray) -> NDArray[np.uint8]:
    """Interpolate RGB palette stops for normalized values in ``[0, 1]``."""

    positions = np.linspace(0.0, 1.0, num=stops.shape[0], dtype=np.float32)
    rgb = np.empty((normalized.shape[0], 3), dtype=np.float32)
    for channel in range(3):
        rgb[:, channel] = np.interp(normalized, positions, stops[:, channel])
    return np.rint(rgb).astype(np.uint8)


def _validate_uint8_scalar(value: int, *, name: str) -> np.uint8:
    """Validate and convert an integer-like value to ``uint8``."""

    value_int = int(value)
    if value_int < 0 or value_int > 255:
        raise ValueError(f"{name} must be in [0, 255], got {value}")
    return np.uint8(value_int)


__all__ = [
    "ColorMode",
    "RGBAArray",
    "VALID_RGBA",
    "INVALID_RGBA",
    "TARGET_OBB_RGBA",
    "UNKNOWN_RGBA",
    "candidate_rgba",
    "obb_semantic_rgba",
    "oracle_rri_to_rgba",
    "rank_to_rgba",
    "step_to_rgba",
    "validity_to_rgba",
]
