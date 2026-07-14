"""Identifier, shard-resolution, and semidense-bound helpers for ASE/ATEK data.

This module provides the deterministic glue used by :class:`AseEfmDataset`:
raw-to-compact sample-key conversion, WebDataset shard lookup, scene/snippet
inference, and world-frame AABB extraction from consumed EFM point keys. It
does not adapt tensor schemas or load meshes itself.
"""

from __future__ import annotations

import re
import tarfile
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

import torch
from efm3d.aria.aria_constants import (
    ARIA_POINTS_VOL_MAX,
    ARIA_POINTS_VOL_MIN,
    ARIA_POINTS_WORLD,
)

from ..configs import PathConfig

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


def _infer_ids(
    efm_dict: Mapping[str, Any],
    sequence_name: str | None = None,
) -> tuple[str, str]:
    """Infer scene and snippet ids from keys/url."""
    scene_id = str(sequence_name or efm_dict.get("sequence_name", "unknown"))
    snippet_id = efm_dict.get("__key__") or efm_dict.get("__url__")
    if isinstance(snippet_id, str):
        snippet_id = compact_ase_atek_sample_id(Path(snippet_id).stem)
    else:
        snippet_id = "unknown"
    if scene_id == "unknown" and "__url__" in efm_dict:
        parent = Path(str(efm_dict["__url__"])).parent.name
        if parent.isdigit():
            scene_id = parent
    return scene_id, str(snippet_id)


def _unique_preserve_order(values: Iterable[str]) -> list[str]:
    """Return unique values while preserving their first-seen order."""
    return list(dict.fromkeys(values))


def _looks_like_sample_key(snippet_id: str) -> bool:
    """Return whether a snippet identifier looks like a per-sample key."""
    return (
        any(token in snippet_id for token in ("AtekDataSample", "DataSample"))
        or raw_ase_atek_sample_id(snippet_id) is not None
    )


def _looks_like_shard_id(snippet_id: str) -> bool:
    """Return whether a snippet identifier refers to a shard tar."""
    stem = Path(snippet_id).name
    return stem.startswith("shards-") or stem.endswith("_tar") or stem.endswith(".tar")


def _normalize_shard_stem(snippet_id: str) -> str:
    """Normalize shard identifiers into a tar-file stem."""
    stem = Path(snippet_id).stem
    if stem.endswith("_tar"):
        stem = stem[: -len("_tar")]
    return stem


def _matches_snippet_token(prefix: str, token: str) -> bool:
    """Return whether a shard member prefix matches the requested token."""
    prefixes = _ase_atek_identifier_variants(prefix)
    tokens = _ase_atek_identifier_variants(token)
    return any(
        candidate == requested or candidate.endswith(requested) for candidate in prefixes for requested in tokens
    )


def _tar_contains_snippet(tar_path: Path, snippet_token: str) -> bool:
    """Return whether a shard tar contains the requested snippet token."""
    with tarfile.open(tar_path, "r") as tar:
        for member in tar:
            prefix = member.name.split(".", 1)[0]
            if _matches_snippet_token(prefix, snippet_token):
                return True
    return False


def _resolve_tar_from_path(
    *,
    snippet_id: str,
    paths: PathConfig,
) -> Path | None:
    """Resolve an explicit shard path or relative shard reference."""
    candidate = Path(snippet_id)
    if candidate.is_absolute():
        if candidate.suffix != ".tar":
            candidate = candidate.with_suffix(".tar")
        return candidate if candidate.exists() else None
    if candidate.parent != Path():
        resolved = paths.resolve_under_root(candidate)
        if resolved.suffix != ".tar":
            resolved = resolved.with_suffix(".tar")
        return resolved if resolved.exists() else None
    return None


def _resolve_tar_for_shard(
    *,
    shard_id: str,
    scene_dirs: list[Path],
) -> list[Path]:
    """Resolve a shard identifier against the configured scene directories."""
    stem = _normalize_shard_stem(shard_id)
    matches: list[Path] = []
    for scene_dir in scene_dirs:
        candidate = scene_dir / f"{stem}.tar"
        if candidate.exists():
            matches.append(candidate)
    return matches


def _find_tar_for_sample(
    *,
    sample_key: str,
    scene_dirs: list[Path],
) -> Path | None:
    """Find the shard tar that contains the requested sample key."""
    for scene_dir in scene_dirs:
        for tar_path in sorted(scene_dir.glob("*.tar")):
            if _tar_contains_snippet(tar_path, sample_key):
                return tar_path
    return None


def _split_snippet_ids(snippet_ids: Iterable[str]) -> tuple[list[str], list[str]]:
    """Split mixed snippet identifiers into shard ids and sample keys."""
    shard_ids: list[str] = []
    sample_keys: list[str] = []
    for snippet_id in snippet_ids:
        if _looks_like_shard_id(snippet_id):
            shard_ids.append(snippet_id)
        else:
            sample_keys.append(snippet_id)
    return shard_ids, sample_keys


def _tensor3(value: Any) -> torch.Tensor | None:
    """Return ``value`` when it is a tensor with exactly three elements."""
    if isinstance(value, torch.Tensor) and value.numel() == 3:
        return value
    return None


def infer_semidense_bounds(
    efm_dict: Mapping[str, Any],
) -> tuple[torch.Tensor, torch.Tensor] | None:
    """Infer snippet world-space AABB from semidense metadata or points.

    Preference order:
    1) ``ARIA_POINTS_VOL_MIN`` / ``ARIA_POINTS_VOL_MAX`` (or legacy keys ``points/vol_min``, ``points/vol_max``)
    2) Axis-aligned bounds of finite semidense points (ignoring padded/NaN entries)

    Returns:
        Pair of ``Tensor["3", float32]`` world-frame bounds in metres on CPU,
        or ``None`` when neither EFM volume metadata nor finite MPS semidense
        points define an extent.
    """
    vol_min = _tensor3(efm_dict.get(ARIA_POINTS_VOL_MIN))
    if vol_min is None:
        vol_min = _tensor3(efm_dict.get("points/vol_min"))

    vol_max = _tensor3(efm_dict.get(ARIA_POINTS_VOL_MAX))
    if vol_max is None:
        vol_max = _tensor3(efm_dict.get("points/vol_max"))
    vol_bounds: tuple[torch.Tensor, torch.Tensor] | None = None
    if vol_min is not None and vol_max is not None and torch.isfinite(vol_min).all() and torch.isfinite(vol_max).all():
        vol_bounds = (vol_min.detach().cpu(), vol_max.detach().cpu())

    points = efm_dict.get(ARIA_POINTS_WORLD)
    point_bounds: tuple[torch.Tensor, torch.Tensor] | None = None
    if isinstance(points, torch.Tensor) and points.shape[-1] == 3:
        lengths = efm_dict.get("msdpd#points_world_lengths") or efm_dict.get(
            "points/lengths",
        )
        if isinstance(lengths, torch.Tensor):
            lengths = lengths.to(dtype=torch.long)

        mask_valid = torch.isfinite(points).all(dim=-1)
        if isinstance(lengths, torch.Tensor) and lengths.shape[0] == points.shape[0]:
            idx = torch.arange(points.shape[1], device=points.device).unsqueeze(
                0,
            ) < lengths.unsqueeze(-1)
            mask_valid &= idx

        if mask_valid.any():
            valid_points = points[mask_valid]
            min_vec = valid_points.min(dim=0).values.detach().cpu()
            max_vec = valid_points.max(dim=0).values.detach().cpu()
            if torch.isfinite(min_vec).all() and torch.isfinite(max_vec).all():
                point_bounds = (min_vec, max_vec)

    if vol_bounds is None and point_bounds is None:
        base_bounds = None
    elif vol_bounds is None:
        base_bounds = point_bounds
    elif point_bounds is None:
        base_bounds = vol_bounds
    else:
        vol_extent = (vol_bounds[1] - vol_bounds[0]).clamp_min(1e-6)
        point_extent = (point_bounds[1] - point_bounds[0]).clamp_min(1e-6)
        vol_volume = torch.prod(vol_extent)
        point_volume = torch.prod(point_extent)
        base_bounds = point_bounds if point_volume < vol_volume else vol_bounds

    return base_bounds


__all__ = [
    "_find_tar_for_sample",
    "_infer_ids",
    "_looks_like_sample_key",
    "_looks_like_shard_id",
    "_matches_snippet_token",
    "_normalize_shard_stem",
    "_resolve_tar_for_shard",
    "_resolve_tar_from_path",
    "_split_snippet_ids",
    "_tar_contains_snippet",
    "_tensor3",
    "_unique_preserve_order",
    "compact_ase_atek_identifiers",
    "compact_ase_atek_sample_id",
    "infer_semidense_bounds",
    "raw_ase_atek_sample_id",
]
