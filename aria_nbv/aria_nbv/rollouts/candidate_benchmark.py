"""Immutable, presentation-free candidate benchmark evidence.

The benchmark is deliberately a small interchange contract.  Producers may
reduce their candidate audit in any way, but consumers read the resulting
content-addressed bundle rather than reinterpreting rollout metadata.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import tempfile
import zipfile
from collections.abc import Collection, Iterable, Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, cast

import numpy as np
import pandas as pd

SCHEMA_ID = "aria-nbv-candidate-benchmark-v1"
MANIFEST_NAME = "manifest.json"
DATA_NAME = "candidates.parquet"
MULTI_STORE_BINDING_ALGORITHM = "sha256-canonical-json-v1"
BINDING_KEYS = (
    "source_sha256",
    "scene_split_sha256",
    "store_content_sha256",
    "config_sha256",
    "candidate_config_sha256",
    "oracle_config_sha256",
    "family_config_sha256",
    "schema_id",
    "implementation_revision",
    "evidence_class",
    "completion",
)


def _canonical(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _canonical(value[k]) for k in sorted(value, key=str)}
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    if hasattr(value, "item"):
        return _canonical(value.item())
    return value


def canonical_json_bytes(value: Any) -> bytes:
    """Return stable UTF-8 JSON bytes for hashing and export."""

    return json.dumps(_canonical(value), ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()


def _json_field(value: Mapping[str, Any]) -> str:
    return canonical_json_bytes(value).decode("utf-8")


def _mapping_field(value: Any) -> Mapping[str, Any]:
    if isinstance(value, str):
        parsed = json.loads(value)
        if not isinstance(parsed, dict):
            raise ValueError("benchmark mapping field must contain a JSON object")
        return parsed
    if not isinstance(value, Mapping):
        raise ValueError("benchmark mapping field must contain a mapping")
    return value


def _freeze(value: Any) -> Any:
    """Recursively freeze manifest values returned to consumers."""
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def sha256_bytes(value: bytes) -> str:
    """Return a SHA-256 hex digest."""

    return hashlib.sha256(value).hexdigest()


def aggregate_store_content_sha256(store_seals: Mapping[str, str]) -> str:
    """Bind an ordered set of promoted store identities and content seals."""

    if not store_seals:
        raise ValueError("multi-store benchmark binding requires at least one store seal")
    stores = []
    for store_id, seal in sorted(store_seals.items()):
        if not store_id:
            raise ValueError("multi-store benchmark binding requires non-empty store identities")
        if not re.fullmatch(r"[0-9a-f]{64}", seal) or set(seal) == {"0"}:
            raise ValueError(f"store {store_id!r} has no nonzero SHA-256 content seal")
        stores.append({"store_id": store_id, "rollout_store_content_sha256": seal})
    return sha256_bytes(
        canonical_json_bytes(
            {
                "algorithm": MULTI_STORE_BINDING_ALGORITHM,
                "stores": stores,
            }
        )
    )


@dataclass(frozen=True, slots=True)
class CandidateFamilyCounts:
    """Counts for one family, preserving applicability and denominators."""

    family: str
    applicable: bool | None
    attempted: int = 0
    valid: int = 0
    selected: int = 0
    denominator: int = 0
    reason: str | None = None

    def __post_init__(self) -> None:
        for name in ("attempted", "valid", "selected", "denominator"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be non-negative")
        if self.valid > self.attempted or self.selected > self.valid:
            raise ValueError("family counts must satisfy selected <= valid <= attempted")
        if self.applicable is not None and not isinstance(self.applicable, bool):
            raise ValueError("family applicability must be bool or None")
        if self.denominator < self.attempted:
            raise ValueError("family denominator must be at least attempted")


@dataclass(frozen=True, slots=True)
class CandidatePoint:
    """One persisted candidate row in the target-aligned proposal-support frame."""

    candidate_id: int
    """Stable candidate-row identity in the rollout store."""

    xyz: tuple[float, float, float]
    """Candidate centre in the normalized proposal-support frame."""

    family: str
    """Configured proposal-family identifier."""

    position: str
    """Persisted position strategy used to generate the candidate."""

    actor_valid: bool
    """Whether the candidate passes the authoritative physical action mask."""

    selected: bool
    """Whether the rollout policy selected this candidate at the factual state."""

    state_key: str
    """Stable ``rollout:<id>/step:<id>`` factual-state identity."""

    candidate_config: str | None = None
    """Persisted candidate-generation configuration lineage, when available."""

    rollout_config: str | None = None
    """Persisted rollout configuration lineage, when available."""

    branch_schedule: str | None = None
    """Persisted branch schedule lineage, when available."""

    unavailable_reason: str | None = None
    """Explicit reason when a legacy store cannot supply a requested diagnostic."""

    target_relative_xyz: tuple[float, float, float] | None = None
    """Target-to-candidate displacement in the same normalized support frame as ``xyz``."""

    view_direction_xyz: tuple[float, float, float] | None = None
    """Unit camera-forward direction expressed in the same proposal-support axes."""

    view_jitter_yaw_deg: float | None = None
    """Persisted local yaw residual in degrees."""

    view_jitter_pitch_deg: float | None = None
    """Persisted local pitch residual in degrees."""

    view_jitter_is_bounded: bool | None = None
    """Per-candidate declaration distinguishing bounded box from uncapped spherical support."""

    view_jitter_azimuth_limit_deg: float | None = None
    """Configured non-negative yaw cap in degrees for a bounded row."""

    view_jitter_elevation_limit_deg: float | None = None
    """Configured non-negative pitch cap in degrees for a bounded row."""

    def __post_init__(self) -> None:
        if not self.family or not self.position or not self.state_key:
            raise ValueError("candidate point family, position, and state_key are required")
        if not isinstance(self.actor_valid, bool) or not isinstance(self.selected, bool):
            raise ValueError("candidate point statuses must be bool")
        if len(self.xyz) != 3 or not all(math.isfinite(float(value)) for value in self.xyz):
            raise ValueError("candidate point xyz must be a finite 3-vector")
        if self.target_relative_xyz is not None and (
            len(self.target_relative_xyz) != 3
            or not all(math.isfinite(float(value)) for value in self.target_relative_xyz)
        ):
            raise ValueError("target_relative_xyz must be a finite 3-vector when present")
        if self.view_direction_xyz is not None and (
            len(self.view_direction_xyz) != 3
            or not all(math.isfinite(float(value)) for value in self.view_direction_xyz)
            or not math.isclose(sum(float(value) ** 2 for value in self.view_direction_xyz), 1.0, abs_tol=1e-4)
        ):
            raise ValueError("view_direction_xyz must be a finite unit 3-vector when present")
        if self.view_jitter_is_bounded is not None and not isinstance(self.view_jitter_is_bounded, bool):
            raise ValueError("view_jitter_is_bounded must be bool or None")
        for name in (
            "view_jitter_yaw_deg",
            "view_jitter_pitch_deg",
            "view_jitter_azimuth_limit_deg",
            "view_jitter_elevation_limit_deg",
        ):
            value = getattr(self, name)
            if value is not None and not math.isfinite(float(value)):
                raise ValueError(f"{name} must be finite when present")
        for name in ("view_jitter_azimuth_limit_deg", "view_jitter_elevation_limit_deg"):
            value = getattr(self, name)
            if value is not None and float(value) < 0.0:
                raise ValueError(f"{name} must be non-negative when present")


@dataclass(frozen=True, slots=True)
class CandidateBenchmark:
    """Frozen benchmark facts for one immutable candidate-generation state."""

    state_key: str
    scene_key: str
    families: tuple[CandidateFamilyCounts, ...]
    geometry: Mapping[str, float] = field(default_factory=dict)
    diversity: Mapping[str, float] = field(default_factory=dict)
    timings_ms: Mapping[str, float] = field(default_factory=dict)
    resources: Mapping[str, float] = field(default_factory=dict)
    provenance: Mapping[str, str] = field(default_factory=dict)
    candidate_ids: tuple[int, ...] = ()
    coordinates: tuple[tuple[float, float, float], ...] = ()
    lineage: Mapping[str, str] = field(default_factory=dict)
    points: tuple[CandidatePoint, ...] = ()

    def __post_init__(self) -> None:
        if not self.state_key or not self.scene_key:
            raise ValueError("state_key and scene_key are required")
        if len({family.family for family in self.families}) != len(self.families):
            raise ValueError("family names must be unique")
        if len(self.candidate_ids) != len(self.coordinates):
            raise ValueError("candidate ids and coordinates must be aligned")
        if len(set(self.candidate_ids)) != len(self.candidate_ids):
            raise ValueError("candidate ids must be unique")
        for coordinate_value in self.coordinates:
            if len(coordinate_value) != 3 or not all(math.isfinite(float(value)) for value in coordinate_value):
                raise ValueError("candidate coordinates must be finite 3-vectors")
        if len(self.points) != len(self.candidate_ids):
            raise ValueError("candidate points and ids must be aligned")
        for candidate_id, coordinate, point in zip(self.candidate_ids, self.coordinates, self.points, strict=True):
            if point.candidate_id != candidate_id or point.state_key != self.state_key or point.xyz != coordinate:
                raise ValueError("candidate points must align exactly with candidate ids and coordinates")
        for mapping_name in ("geometry", "diversity", "timings_ms", "resources", "provenance", "lineage"):
            value = getattr(self, mapping_name)
            object.__setattr__(self, mapping_name, MappingProxyType(dict(value)))

    def to_record(self) -> dict[str, Any]:
        """Flatten facts into one deterministic row for Parquet."""

        return {
            "scene_key": self.scene_key,
            "state_key": self.state_key,
            "families": [asdict(family) for family in self.families],
            "geometry": _json_field(self.geometry),
            "diversity": _json_field(self.diversity),
            "timings_ms": _json_field(self.timings_ms),
            "resources": _json_field(self.resources),
            "provenance": _json_field(self.provenance),
            "candidate_ids": list(self.candidate_ids),
            "coordinates": [list(point) for point in self.coordinates],
            "lineage": _json_field(self.lineage),
            "points": [asdict(point) for point in self.points],
        }


@dataclass(frozen=True, slots=True)
class CandidateBenchmarkBundle:
    """Validated immutable bundle returned by :func:`read_bundle`."""

    manifest: Mapping[str, Any]
    records: tuple[CandidateBenchmark, ...]
    path: Path


def reduce_candidate_records(records: list[Mapping[str, Any]]) -> tuple[CandidateBenchmark, ...]:
    """Normalize reducer input into immutable benchmark DTOs."""

    result = []
    keys: set[tuple[str, str]] = set()
    for record in records:
        families = tuple(CandidateFamilyCounts(**family) for family in record.get("families", ()))
        dto = CandidateBenchmark(
            state_key=str(record["state_key"]),
            scene_key=str(record["scene_key"]),
            families=families,
            geometry=_mapping_field(record.get("geometry", {})),
            diversity=_mapping_field(record.get("diversity", {})),
            timings_ms=_mapping_field(record.get("timings_ms", {})),
            resources=_mapping_field(record.get("resources", {})),
            provenance=_mapping_field(record.get("provenance", {})),
            candidate_ids=tuple(int(value) for value in record.get("candidate_ids", ())),
            coordinates=tuple(_coordinate3(point) for point in record.get("coordinates", ())),
            lineage=_mapping_field(record.get("lineage", {})),
            points=tuple(
                CandidatePoint(
                    **{
                        **point,
                        "xyz": tuple(float(value) for value in point["xyz"]),
                        "target_relative_xyz": (
                            None
                            if point.get("target_relative_xyz") is None
                            else tuple(float(value) for value in point["target_relative_xyz"])
                        ),
                        "view_direction_xyz": (
                            None
                            if point.get("view_direction_xyz") is None
                            else tuple(float(value) for value in point["view_direction_xyz"])
                        ),
                    }
                )
                for point in record.get("points", ())
            ),
        )
        key = (dto.scene_key, dto.state_key)
        if key in keys:
            raise ValueError(f"duplicate benchmark state key: {key}")
        keys.add(key)
        result.append(dto)
    return tuple(sorted(result, key=lambda item: (item.scene_key, item.state_key)))


def benchmarks_from_reader(
    reader: Any, *, state_key: str | None = None, candidate_limit: int | None = 500
) -> tuple[CandidateBenchmark, ...]:
    """Build state-keyed facts from the canonical inspection candidate rows."""

    from .inspection import candidate_audit_rows, proposal_support_geometry

    grouped: dict[tuple[str, str], dict[str, list[Mapping[str, Any]]]] = {}
    if candidate_limit is not None and candidate_limit <= 0:
        raise ValueError("candidate_limit must be positive")
    requested_rollout_ids = None
    requested_state: tuple[int, int] | None = None
    if state_key is not None:
        match = re.fullmatch(r"rollout:(\d+)/step:(\d+)", state_key)
        if match is None:
            return ()
        requested_state = (int(match.group(1)), int(match.group(2)))
        requested_rollout_ids = (requested_state[0],)
    projection = None
    if hasattr(reader, "root"):
        projection = proposal_support_geometry(
            reader,
            rollout_row_ids=requested_rollout_ids,
            step_row_ids=None if requested_state is None else (requested_state[1],),
            max_candidates=candidate_limit,
        )
    geometry_points = {point.candidate_row_id: point for point in projection.points} if projection else {}
    geometry_frames = {frame.frame_id: frame for frame in projection.frames} if projection else {}
    if state_key is None:
        audit_rows = candidate_audit_rows(reader, limit=candidate_limit)
    else:
        assert requested_state is not None
        audit_rows = candidate_audit_rows(
            reader,
            rollout_row_id=requested_state[0],
            step_row_id=requested_state[1],
            limit=candidate_limit,
        )
    for row in audit_rows:
        if projection is not None and int(row["candidate_row_id"]) not in geometry_points:
            continue
        key = (str(row["scene"]), f"rollout:{row['rollout_row_id']}/step:{row['step_row_id']}")
        grouped.setdefault(key, {}).setdefault(str(row["position"]), []).append(row)
    result = []
    for (scene, state), family_rows in sorted(grouped.items()):
        families = []
        candidate_ids: list[int] = []
        coordinates: list[tuple[float, float, float]] = []
        frame_ids: set[str] = set()
        lineage: dict[str, str] = {}
        points: list[CandidatePoint] = []
        for family, rows in sorted(family_rows.items()):
            applicable = None
            valid = sum(bool(row.get("actor_action")) for row in rows)
            selected = sum(bool(row.get("selected")) for row in rows)
            families.append(
                CandidateFamilyCounts(
                    family, applicable, len(rows), valid, selected, len(rows), "unavailable_in_legacy_store"
                )
            )
            for family_row in rows:
                candidate_id = int(family_row["candidate_row_id"])
                projected = geometry_points.get(candidate_id)
                if projection is not None and projected is None:
                    continue
                coordinate = (
                    (float(projected.x), float(projected.y), float(projected.z))
                    if projected is not None
                    else _legacy_coordinate(family_row)
                )
                candidate_ids.append(candidate_id)
                coordinates.append(coordinate)
                target_relative = None
                if projected is not None:
                    frame_ids.add(projected.frame_id)
                    frame = geometry_frames.get(projected.frame_id)
                    if frame is not None:
                        target_relative = (
                            coordinate[0] - frame.target_x,
                            coordinate[1] - frame.target_y,
                            coordinate[2] - frame.target_z,
                        )
                points.append(
                    CandidatePoint(
                        candidate_id,
                        coordinates[-1],
                        family,
                        str(family_row["position"]),
                        bool(family_row.get("actor_action")),
                        bool(family_row.get("selected")),
                        state,
                        str(family_row.get("candidate_config")),
                        str(family_row.get("rollout_config")),
                        str(family_row.get("branch_schedule")),
                        target_relative_xyz=target_relative,
                        view_direction_xyz=(
                            None
                            if projected is None or getattr(projected, "camera_forward_x", None) is None
                            else (
                                cast(float, projected.camera_forward_x),
                                cast(float, projected.camera_forward_y),
                                cast(float, projected.camera_forward_z),
                            )
                        ),
                        view_jitter_yaw_deg=_finite_value(family_row.get("view_jitter_yaw_deg")),
                        view_jitter_pitch_deg=_finite_value(family_row.get("view_jitter_pitch_deg")),
                        view_jitter_is_bounded=(
                            bool(family_row["view_jitter_is_bounded"])
                            if family_row.get("view_jitter_is_bounded") is not None
                            else None
                        ),
                        view_jitter_azimuth_limit_deg=_finite_value(family_row.get("view_jitter_azimuth_limit_deg")),
                        view_jitter_elevation_limit_deg=_finite_value(
                            family_row.get("view_jitter_elevation_limit_deg")
                        ),
                    )
                )
        geometry = {"candidate_count": float(len(candidate_ids))}
        if projection is not None:
            state_frames = [geometry_frames[frame_id] for frame_id in sorted(frame_ids)]
            if state_frames:
                targets = {(frame.target_x, frame.target_y, frame.target_z) for frame in state_frames}
                if len(targets) != 1:
                    raise ValueError(f"candidate benchmark state {state!r} spans multiple proposal-support frames")
                target_x, target_y, target_z = targets.pop()
                geometry.update({"target_x": target_x, "target_y": target_y, "target_z": target_z})
        result.append(
            CandidateBenchmark(
                scene_key=scene,
                state_key=state,
                families=tuple(families),
                geometry=geometry,
                candidate_ids=tuple(candidate_ids),
                coordinates=tuple(coordinates),
                lineage=lineage,
                points=tuple(points),
            )
        )
    return tuple(result)


def _legacy_coordinate(row: Mapping[str, Any]) -> tuple[float, float, float]:
    """Normalize an audit-only row for backward-compatible bundles."""

    scale = sum(float(row.get(f"root_to_target_{axis}_m") or 0.0) ** 2 for axis in ("x", "y", "z")) ** 0.5
    scale = scale if scale > 0.0 else 1.0
    return (
        float(row["root_relative_x_m"]) / scale,
        float(row["root_relative_y_m"]) / scale,
        float(row["root_relative_z_m"]) / scale,
    )


def _coordinate3(values: Iterable[Any]) -> tuple[float, float, float]:
    """Normalize one serialized coordinate while enforcing its length."""

    coordinate = tuple(float(value) for value in values)
    if len(coordinate) != 3:
        raise ValueError("candidate coordinates must be finite 3-vectors")
    return coordinate


def _finite_value(value: Any) -> float | None:
    """Return a finite scalar, preserving unavailable legacy values as ``None``."""

    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def circular_minimum_covering_span_deg(angles_deg: Iterable[float]) -> float | None:
    """Return the shortest circular arc covering angles in degrees.

    The branch cut is handled on the circle, so ``-179`` and ``179`` span
    two degrees rather than 358 degrees.
    """

    values = np.asarray(list(angles_deg), dtype=float).reshape(-1)
    values = values[np.isfinite(values)]
    if values.size == 0:
        return None
    wrapped = np.sort(np.mod(values, 360.0))
    gaps = np.diff(np.concatenate((wrapped, wrapped[:1] + 360.0)))
    return float(360.0 - np.max(gaps))


def target_side_count_balance(
    points: Iterable[CandidatePoint],
    *,
    target_conditioned_positions: Collection[str] = ("target_bearing_local", "target_orbit"),
) -> float | None:
    """Return attempted target-family side-count balance for one factual state.

    The lateral coordinate is read from ``target_relative_xyz``. Rows without a
    common-frame target displacement are excluded rather than reconstructed
    from incompatible audit coordinates.
    """

    positive, negative, _ = _target_side_counts(
        points,
        target_conditioned_positions=target_conditioned_positions,
    )
    if positive + negative == 0:
        return None
    return 1.0 - abs(positive - negative) / float(positive + negative)


def _target_side_counts(
    points: Iterable[CandidatePoint],
    *,
    target_conditioned_positions: Collection[str],
) -> tuple[int, int, int]:
    """Count positive, negative, and neutral target-relative lateral rows."""

    positive = 0
    negative = 0
    neutral = 0
    for point in points:
        if str(getattr(point, "position", "")) not in target_conditioned_positions:
            continue
        values = getattr(point, "target_relative_xyz", None)
        if values is None:
            continue
        value = float(values[1])
        if not math.isfinite(value):
            continue
        if value > 1e-9:
            positive += 1
        elif value < -1e-9:
            negative += 1
        else:
            neutral += 1
    return positive, negative, neutral


def target_relative_orbit_span_deg(
    points: Iterable[CandidatePoint],
    *,
    target_conditioned_positions: Collection[str] = ("target_bearing_local", "target_orbit"),
) -> float | None:
    """Return the minimum circular azimuth span around the target, in degrees."""

    angles = []
    for point in points:
        values = getattr(point, "target_relative_xyz", None)
        if values is None:
            continue
        if str(getattr(point, "position", "")) not in target_conditioned_positions:
            continue
        dx = float(values[0])
        dy = float(values[1])
        if math.isfinite(dx) and math.isfinite(dy) and math.hypot(dx, dy) > 1e-9:
            angles.append(math.degrees(math.atan2(dy, -dx)))
    return circular_minimum_covering_span_deg(angles)


def candidate_support_metrics(
    points: Iterable[CandidatePoint],
    *,
    configured_families: Collection[str] | None = None,
    projected_target_centers: int | None = None,
    total_target_centers: int | None = None,
) -> dict[str, float | int | None]:
    """Compute frame-safe candidate-support facts for one factual state.

    Args:
        points: Attempted rows expressed in one target-aligned support frame.
        configured_families: Complete configured family identifiers, including
            families with no emitted or valid row.
        projected_target_centers: Evaluated rows whose target centre projects
            inside the calibrated image domain.
        total_target_centers: Rows on which target-centre projection was
            evaluated.

    Returns:
        State-level support counts and fractions. ``None`` denotes unavailable
        evidence; projection is calibrated framing rather than visibility.

    Notes:
        Geometry from unrelated root and decision frames is intentionally not
        combined. Normal callers obtain coordinates from
        :func:`aria_nbv.rollouts.inspection.proposal_support_geometry`.
    """

    if projected_target_centers is not None and projected_target_centers < 0:
        raise ValueError("projected_target_centers must be non-negative")
    if total_target_centers is not None and total_target_centers < 0:
        raise ValueError("total_target_centers must be non-negative")
    if (
        projected_target_centers is not None
        and total_target_centers is not None
        and projected_target_centers > total_target_centers
    ):
        raise ValueError("projected_target_centers cannot exceed total_target_centers")
    point_list = tuple(points)
    side_positive, side_negative, side_neutral = _target_side_counts(
        point_list,
        target_conditioned_positions=("target_bearing_local", "target_orbit"),
    )
    actor_values = [getattr(point, "actor_valid", getattr(point, "actor_action", None)) for point in point_list]
    actor_known = [value for value in actor_values if isinstance(value, bool)]
    actor_valid = sum(actor_known)
    metrics: dict[str, float | int | None] = {
        "actor_valid_fraction": (actor_valid / len(actor_known)) if actor_known else None,
        "per_state_valid_support": actor_valid if actor_known else None,
        "target_side_count_balance": target_side_count_balance(point_list),
        "target_side_positive_count": side_positive,
        "target_side_negative_count": side_negative,
        "target_side_neutral_count": side_neutral,
        "target_side_balance_undefined": int(side_positive + side_negative == 0),
        "target_relative_orbit_span_deg": target_relative_orbit_span_deg(point_list),
        "target_center_projection_fraction": (
            projected_target_centers / total_target_centers
            if projected_target_centers is not None and total_target_centers
            else None
        ),
    }
    if configured_families is None:
        metrics["zero_valid_family_state_rate"] = None
    else:
        families = tuple(configured_families)
        if not families:
            metrics["zero_valid_family_state_rate"] = None
        else:
            zero = sum(
                1
                for family in families
                if not any(
                    getattr(point, "family", None) == family and bool(getattr(point, "actor_valid", False))
                    for point in point_list
                )
            )
            metrics["zero_valid_family_state_rate"] = zero / len(families)
    jitter = [
        point
        for point in point_list
        if getattr(point, "view_jitter_yaw_deg", None) is not None
        and getattr(point, "view_jitter_pitch_deg", None) is not None
    ]
    nonzero = [
        point
        for point in jitter
        if abs(float(point.view_jitter_yaw_deg or 0.0)) > 1e-9 or abs(float(point.view_jitter_pitch_deg or 0.0)) > 1e-9
    ]
    bounded = [point for point in jitter if getattr(point, "view_jitter_is_bounded", None) is True]
    compliant = [
        point
        for point in bounded
        if point.view_jitter_azimuth_limit_deg is not None
        and point.view_jitter_elevation_limit_deg is not None
        and abs(float(point.view_jitter_yaw_deg or 0.0)) <= float(point.view_jitter_azimuth_limit_deg) + 1e-6
        and abs(float(point.view_jitter_pitch_deg or 0.0)) <= float(point.view_jitter_elevation_limit_deg) + 1e-6
    ]
    metrics.update(
        {
            "nonzero_jitter_fraction": len(nonzero) / len(jitter) if jitter else None,
            "bounded_jitter_declaration_fraction": len(bounded) / len(jitter) if jitter else None,
            "bounded_jitter_cap_compliance_fraction": len(compliant) / len(bounded) if bounded else None,
            "uncapped_spherical_count": sum(
                getattr(point, "view_jitter_is_bounded", None) is False for point in jitter
            ),
        }
    )
    return metrics


def write_bundle(
    path: Path | str,
    records: list[Mapping[str, Any]] | tuple[CandidateBenchmark, ...],
    *,
    provenance: Mapping[str, str] | None = None,
) -> Path:
    """Atomically write a deterministic JSON/Parquet evidence bundle."""

    destination = Path(path).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if records and isinstance(records[0], Mapping):
        dtos = reduce_candidate_records(records)
    else:
        dtos = tuple(cast(tuple[CandidateBenchmark, ...], records))
    rows = [item.to_record() for item in dtos]
    frame = pd.DataFrame(
        rows,
        columns=[
            "scene_key",
            "state_key",
            "families",
            "geometry",
            "diversity",
            "timings_ms",
            "resources",
            "provenance",
            "candidate_ids",
            "coordinates",
            "lineage",
            "points",
        ],
    )
    with tempfile.TemporaryDirectory(dir=destination.parent) as temp:
        temp_path = Path(temp) / destination.name
        temp_path.mkdir()
        parquet_path = temp_path / DATA_NAME
        try:
            frame.to_parquet(parquet_path, index=False)
        except (ImportError, ValueError) as exc:
            raise RuntimeError("candidate benchmark export requires a Parquet engine (pyarrow or fastparquet)") from exc
        data_hash = sha256_bytes(parquet_path.read_bytes())
        provenance_payload = dict(provenance or {})
        missing_binding = [key for key in BINDING_KEYS if key not in provenance_payload]
        if missing_binding:
            raise ValueError(f"missing immutable benchmark binding fields: {', '.join(missing_binding)}")
        provenance_payload.update(
            {
                "schema_id": SCHEMA_ID,
                "implementation_revision": "1",
                "evidence_class": "candidate_benchmark",
                "completion": "complete",
            }
        )
        manifest = {
            "schema_id": SCHEMA_ID,
            "evidence_class": "candidate_benchmark",
            "completion": "complete",
            "revision": 1,
            "record_count": len(rows),
            "data_sha256": data_hash,
            "provenance": _canonical(provenance_payload),
        }
        (temp_path / MANIFEST_NAME).write_bytes(canonical_json_bytes(manifest))
        try:
            destination.mkdir()
        except FileExistsError as exc:
            raise FileExistsError(f"immutable benchmark bundle already exists: {destination}") from exc
        for name in (MANIFEST_NAME, DATA_NAME):
            os.link(temp_path / name, destination / name)
    return destination


def _existing_sha256(mapping: Mapping[str, Any], *names: str) -> str | None:
    """Return the first real SHA-256 identity exposed by a manifest mapping."""

    for name in names:
        value = mapping.get(name)
        if isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) and set(value) != {"0"}:
            return value
    return None


def benchmark_binding_from_manifest(manifest_payload: Mapping[str, Any]) -> dict[str, str]:
    """Derive a non-sentinel immutable binding from the canonical store manifest."""

    manifest = manifest_payload.get("manifest", manifest_payload)
    if not isinstance(manifest, Mapping):
        raise ValueError("canonical rollout manifest is missing")
    generation = manifest.get("generation", {})
    generation = generation if isinstance(generation, Mapping) else {}
    writer = generation.get("writer_config", {})
    writer = writer if isinstance(writer, Mapping) else {}
    coverage = manifest.get("source_coverage", {})
    coverage = coverage if isinstance(coverage, Mapping) else {}
    root_attrs = manifest_payload.get("root_attrs", {})
    root_attrs = root_attrs if isinstance(root_attrs, Mapping) else {}
    source = _existing_sha256(manifest, "source_sha256", "source_manifest_sha256") or sha256_bytes(
        canonical_json_bytes(coverage)
    )
    split = _existing_sha256(manifest, "scene_split_sha256", "split_manifest_sha256") or _existing_sha256(
        root_attrs, "split_manifest_hash"
    )
    split = split or sha256_bytes(
        canonical_json_bytes(
            {"split": root_attrs.get("split_manifest_hash"), "scenes": coverage.get("scene_counts", {})}
        )
    )
    store = _existing_sha256(manifest_payload, "store_content_sha256", "content_sha256") or _existing_sha256(
        manifest, "store_content_sha256", "content_sha256"
    )
    if store is None:
        raise ValueError("rollout manifest has no content hash; derive benchmark binding from the store reader")
    config = _existing_sha256(generation, "config_sha256", "writer_config_sha256") or sha256_bytes(
        canonical_json_bytes(writer)
    )
    mixture = writer.get("candidate_mixture", {}) if isinstance(writer, Mapping) else {}
    scorer = writer.get("target_scorer", {}) if isinstance(writer, Mapping) else {}
    family = mixture.get("components", []) if isinstance(mixture, Mapping) else []
    return {
        "source_sha256": source,
        "scene_split_sha256": split,
        "store_content_sha256": store,
        "config_sha256": config,
        "candidate_config_sha256": sha256_bytes(canonical_json_bytes(mixture)),
        "oracle_config_sha256": sha256_bytes(canonical_json_bytes(scorer)),
        "family_config_sha256": sha256_bytes(canonical_json_bytes(family)),
        "schema_id": SCHEMA_ID,
        "implementation_revision": "1",
        "evidence_class": "candidate_benchmark",
        "completion": "complete",
    }


def benchmark_binding_from_reader(reader: Any, manifest_payload: Mapping[str, Any] | None = None) -> dict[str, str]:
    """Derive bindings from a validated reader and its promoted store seal."""

    payload = dict(manifest_payload or reader.manifest())
    store_dir = getattr(reader, "store_dir", None)
    if store_dir is None:
        raise ValueError("candidate benchmark binding requires a reader with a store_dir")
    root = Path(store_dir).expanduser().resolve()
    seals = []
    for name in ("_SUCCESS.json", "_owner.json"):
        seal = root / name
        if seal.is_file():
            try:
                parsed = json.loads(seal.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise ValueError(f"invalid promoted store seal: {name}") from exc
            value = parsed.get("rollout_store_content_sha256") if isinstance(parsed, Mapping) else None
            if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value) or set(value) == {"0"}:
                raise ValueError(f"promoted store seal {name} has no nonzero content hash")
            seals.append(value)
    if seals:
        if len(seals) != 2 or seals[0] != seals[1]:
            raise ValueError("promoted store seals disagree on rollout_store_content_sha256")
        payload["store_content_sha256"] = seals[0]
    elif (root / "_SUCCESS.json").exists() or (root / "_owner.json").exists():
        raise ValueError("promoted store requires both valid content seals")
    elif root.is_dir():
        digest = hashlib.sha256()
        for path in sorted(
            (item for item in root.rglob("*") if item.is_file()), key=lambda item: item.relative_to(root).as_posix()
        ):
            relative = path.relative_to(root).as_posix().encode("utf-8")
            content = path.read_bytes()
            digest.update(len(relative).to_bytes(8, "big"))
            digest.update(relative)
            digest.update(len(content).to_bytes(8, "big"))
            digest.update(content)
        payload["store_content_sha256"] = digest.hexdigest()
    return benchmark_binding_from_manifest(payload)


def serialize_bundle_bytes(records: tuple[CandidateBenchmark, ...], *, provenance: Mapping[str, str]) -> bytes:
    """Produce deterministic bundle bytes through the same canonical writer."""

    with tempfile.TemporaryDirectory() as directory:
        bundle = write_bundle(Path(directory) / "candidate-benchmark", records, provenance=provenance)
        import io

        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
            for name in (MANIFEST_NAME, DATA_NAME):
                info = zipfile.ZipInfo(name)
                info.date_time = (1980, 1, 1, 0, 0, 0)
                archive.writestr(info, (bundle / name).read_bytes())
        return output.getvalue()


def read_bundle_bytes(payload: bytes, *, expected_binding: Mapping[str, str]) -> CandidateBenchmarkBundle:
    """Validate a canonical exported ZIP through :func:`read_bundle`."""

    with tempfile.TemporaryDirectory() as directory:
        archive_path = Path(directory) / "bundle.zip"
        archive_path.write_bytes(payload)
        with zipfile.ZipFile(archive_path) as archive:
            names = sorted(archive.namelist())
            if names != [DATA_NAME, MANIFEST_NAME]:
                raise ValueError("invalid candidate benchmark archive members")
            root = Path(directory) / "bundle"
            root.mkdir()
            archive.extractall(root)
        return read_bundle(root, expected_binding=expected_binding)


def read_bundle(path: Path | str, *, expected_binding: Mapping[str, str]) -> CandidateBenchmarkBundle:
    """Read and validate exactly one complete, current, hash-bound bundle."""

    root = Path(path).expanduser().resolve()
    if not root.is_dir() or root.name.startswith("fixture"):
        raise ValueError("fixture or missing candidate benchmark bundle")
    manifest_path, parquet_path = root / MANIFEST_NAME, root / DATA_NAME
    if not manifest_path.is_file() or not parquet_path.is_file():
        raise ValueError("partial candidate benchmark bundle")
    if {entry.name for entry in root.iterdir()} != {MANIFEST_NAME, DATA_NAME}:
        raise ValueError("schema-mismatched candidate benchmark bundle: unexpected files")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("invalid candidate benchmark manifest") from exc
    required = {"schema_id", "evidence_class", "completion", "revision", "record_count", "data_sha256", "provenance"}
    if set(manifest) != required:
        raise ValueError("schema-mismatched candidate benchmark bundle")
    if (
        manifest.get("schema_id") != SCHEMA_ID
        or manifest.get("evidence_class") != "candidate_benchmark"
        or manifest.get("completion") != "complete"
        or manifest.get("revision") != 1
        or not isinstance(manifest.get("record_count"), int)
        or manifest.get("record_count") < 0
        or not isinstance(manifest.get("data_sha256"), str)
        or not isinstance(manifest.get("provenance"), dict)
    ):
        raise ValueError("schema-mismatched candidate benchmark bundle")
    if set(expected_binding) != set(BINDING_KEYS):
        raise ValueError("expected_binding must contain every immutable benchmark binding field")
    if any(
        key.endswith("_sha256")
        and (
            not re.fullmatch(r"[0-9a-f]{64}", str(manifest["provenance"].get(key, "")))
            or set(str(manifest["provenance"].get(key, ""))) == {"0"}
        )
        for key in BINDING_KEYS
    ):
        raise ValueError("invalid benchmark SHA-256 binding")
    if any(manifest["provenance"].get(key) != value for key, value in expected_binding.items()):
        raise ValueError("stale candidate benchmark bundle: provenance binding mismatch")
    if any(key not in manifest["provenance"] for key in BINDING_KEYS):
        raise ValueError("stale candidate benchmark bundle: incomplete provenance binding")
    actual_hash = sha256_bytes(parquet_path.read_bytes())
    if manifest.get("data_sha256") != actual_hash:
        raise ValueError("hash-mismatched candidate benchmark bundle")
    try:
        frame = pd.read_parquet(parquet_path)
    except Exception as exc:
        raise ValueError("invalid candidate benchmark Parquet payload") from exc
    expected_columns = {
        "scene_key",
        "state_key",
        "families",
        "geometry",
        "diversity",
        "timings_ms",
        "resources",
        "provenance",
        "candidate_ids",
        "coordinates",
        "lineage",
        "points",
    }
    if set(frame.columns) != expected_columns:
        raise ValueError("schema-mismatched candidate benchmark columns")
    if len(frame) != manifest.get("record_count"):
        raise ValueError("stale candidate benchmark bundle")
    raw_records = frame.to_dict(orient="records")
    try:
        records = reduce_candidate_records(cast(list[Mapping[str, Any]], raw_records))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("schema-mismatched candidate benchmark rows") from exc
    return CandidateBenchmarkBundle(_freeze(manifest), records, root)


__all__ = [
    "SCHEMA_ID",
    "BINDING_KEYS",
    "CandidateBenchmark",
    "CandidateBenchmarkBundle",
    "CandidateFamilyCounts",
    "CandidatePoint",
    "candidate_support_metrics",
    "canonical_json_bytes",
    "circular_minimum_covering_span_deg",
    "read_bundle",
    "benchmarks_from_reader",
    "read_bundle_bytes",
    "reduce_candidate_records",
    "serialize_bundle_bytes",
    "sha256_bytes",
    "target_relative_orbit_span_deg",
    "target_side_count_balance",
    "write_bundle",
    "benchmark_binding_from_manifest",
]
