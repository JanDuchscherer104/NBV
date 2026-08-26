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
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any

import pandas as pd

SCHEMA_ID = "aria-nbv-candidate-benchmark-v1"
MANIFEST_NAME = "manifest.json"
DATA_NAME = "candidates.parquet"
BINDING_KEYS = (
    "source_sha256", "scene_split_sha256", "store_content_sha256", "config_sha256",
    "candidate_config_sha256", "oracle_config_sha256", "family_config_sha256",
    "schema_id", "implementation_revision", "evidence_class", "completion",
)


def _canonical(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _canonical(value[k]) for k in sorted(value, key=str)}
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    if hasattr(value, "item"):
        return _canonical(value.item())
    return value


def canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
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
    """One aligned candidate row retained for bounded interactive support plots."""

    candidate_id: int
    xyz: tuple[float, float, float]
    family: str
    position: str
    actor_valid: bool
    selected: bool
    state_key: str
    candidate_config: str | None = None
    rollout_config: str | None = None
    branch_schedule: str | None = None
    unavailable_reason: str | None = None

    def __post_init__(self) -> None:
        if not self.family or not self.position or not self.state_key:
            raise ValueError("candidate point family, position, and state_key are required")
        if not isinstance(self.actor_valid, bool) or not isinstance(self.selected, bool):
            raise ValueError("candidate point statuses must be bool")
        if len(self.xyz) != 3 or not all(math.isfinite(float(value)) for value in self.xyz):
            raise ValueError("candidate point xyz must be a finite 3-vector")


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
        for point in self.coordinates:
            if len(point) != 3 or not all(math.isfinite(float(value)) for value in point):
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
                coordinates=tuple(tuple(float(value) for value in point) for point in record.get("coordinates", ())),
                lineage=_mapping_field(record.get("lineage", {})),
                points=tuple(
                    CandidatePoint(**{**point, "xyz": tuple(float(value) for value in point["xyz"])})
                    for point in record.get("points", ())
                ),
            )
        key = (dto.scene_key, dto.state_key)
        if key in keys:
            raise ValueError(f"duplicate benchmark state key: {key}")
        keys.add(key)
        result.append(dto)
    return tuple(sorted(result, key=lambda item: (item.scene_key, item.state_key)))


def benchmarks_from_reader(reader: Any, *, state_key: str | None = None, candidate_limit: int = 500) -> tuple[CandidateBenchmark, ...]:
    """Build state-keyed facts from the canonical inspection candidate rows."""

    from .inspection import candidate_audit_rows

    grouped: dict[tuple[str, str], dict[str, list[Mapping[str, Any]]]] = {}
    if candidate_limit <= 0:
        raise ValueError("candidate_limit must be positive")
    if state_key is None:
        audit_rows = candidate_audit_rows(reader, limit=candidate_limit)
    else:
        match = re.fullmatch(r"rollout:(\d+)/step:(\d+)", state_key)
        if match is None:
            return ()
        audit_rows = candidate_audit_rows(
            reader,
            rollout_row_id=int(match.group(1)),
            step_row_id=int(match.group(2)),
            limit=candidate_limit,
        )
    for row in audit_rows:
        key = (str(row["scene"]), f"rollout:{row['rollout_row_id']}/step:{row['step_row_id']}")
        grouped.setdefault(key, {}).setdefault(str(row["position"]), []).append(row)
    result = []
    for (scene, state), family_rows in sorted(grouped.items()):
        families = []
        candidate_ids: list[int] = []
        coordinates: list[tuple[float, float, float]] = []
        lineage: dict[str, str] = {}
        points: list[CandidatePoint] = []
        for family, rows in sorted(family_rows.items()):
            applicable = None
            valid = sum(bool(row.get("actor_action")) for row in rows)
            selected = sum(bool(row.get("selected")) for row in rows)
            families.append(CandidateFamilyCounts(family, applicable, len(rows), valid, selected, len(rows), "unavailable_in_legacy_store"))
            for row in rows:
                candidate_ids.append(int(row["candidate_row_id"]))
                scale = (sum(float(row.get(f"root_to_target_{axis}_m") or 0.0) ** 2 for axis in ("x", "y", "z")) ** 0.5)
                scale = scale if scale > 0.0 else 1.0
                coordinates.append(tuple(float(row[f"root_relative_{axis}_m"]) / scale for axis in ("x", "y", "z")))
                points.append(CandidatePoint(int(row["candidate_row_id"]), coordinates[-1], family, str(row["position"]), bool(row.get("actor_action")), bool(row.get("selected")), state, str(row.get("candidate_config")), str(row.get("rollout_config")), str(row.get("branch_schedule"))))
        result.append(
            CandidateBenchmark(
                scene_key=scene,
                state_key=state,
                families=tuple(families),
                geometry={"candidate_count": float(len(candidate_ids))},
                candidate_ids=tuple(candidate_ids),
                coordinates=tuple(coordinates),
                lineage=lineage,
                points=tuple(points),
            )
        )
    return tuple(result)


def write_bundle(
    path: Path | str,
    records: list[Mapping[str, Any]] | tuple[CandidateBenchmark, ...],
    *,
    provenance: Mapping[str, str] = (),
) -> Path:
    """Atomically write a deterministic JSON/Parquet evidence bundle."""

    destination = Path(path).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    dtos = reduce_candidate_records(records) if records and isinstance(records[0], Mapping) else tuple(records)  # type: ignore[arg-type]
    rows = [item.to_record() for item in dtos]
    frame = pd.DataFrame(
        rows,
        columns=[
            "scene_key", "state_key", "families", "geometry", "diversity",
            "timings_ms", "resources", "provenance", "candidate_ids", "coordinates", "lineage", "points",
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
        provenance_payload = dict(provenance)
        missing_binding = [key for key in BINDING_KEYS if key not in provenance_payload]
        if missing_binding:
            raise ValueError(f"missing immutable benchmark binding fields: {', '.join(missing_binding)}")
        provenance_payload.update({"schema_id": SCHEMA_ID, "implementation_revision": "1", "evidence_class": "candidate_benchmark", "completion": "complete"})
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
    counts = manifest.get("counts", {})
    counts = counts if isinstance(counts, Mapping) else {}
    source = _existing_sha256(manifest, "source_sha256", "source_manifest_sha256") or sha256_bytes(canonical_json_bytes(coverage))
    split = _existing_sha256(manifest, "scene_split_sha256", "split_manifest_sha256") or _existing_sha256(root_attrs, "split_manifest_hash")
    split = split or sha256_bytes(canonical_json_bytes({"split": root_attrs.get("split_manifest_hash"), "scenes": coverage.get("scene_counts", {})}))
    store = _existing_sha256(manifest, "store_content_sha256", "content_sha256") or sha256_bytes(canonical_json_bytes({"root_attrs": root_attrs, "counts": counts}))
    config = _existing_sha256(generation, "config_sha256", "writer_config_sha256") or sha256_bytes(canonical_json_bytes(writer))
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
        "schema_id": SCHEMA_ID, "implementation_revision": "1",
        "evidence_class": "candidate_benchmark", "completion": "complete",
    }


def serialize_bundle_bytes(
    records: tuple[CandidateBenchmark, ...], *, provenance: Mapping[str, str]
) -> bytes:
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
        key.endswith("_sha256") and (
            not re.fullmatch(r"[0-9a-f]{64}", str(manifest["provenance"].get(key, "")))
            or set(str(manifest["provenance"].get(key, ""))) == {"0"}
        )
        for key in BINDING_KEYS
    ):
        raise ValueError("invalid benchmark SHA-256 binding")
    if any(
        manifest["provenance"].get(key) != value for key, value in expected_binding.items()
    ):
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
        "scene_key", "state_key", "families", "geometry", "diversity",
        "timings_ms", "resources", "provenance", "candidate_ids", "coordinates", "lineage", "points",
    }
    if set(frame.columns) != expected_columns:
        raise ValueError("schema-mismatched candidate benchmark columns")
    if len(frame) != manifest.get("record_count"):
        raise ValueError("stale candidate benchmark bundle")
    raw_records = frame.to_dict(orient="records")
    try:
        records = reduce_candidate_records(raw_records)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("schema-mismatched candidate benchmark rows") from exc
    return CandidateBenchmarkBundle(_freeze(manifest), records, root)


__all__ = [
    "SCHEMA_ID", "BINDING_KEYS", "CandidateBenchmark", "CandidateBenchmarkBundle",
    "CandidateFamilyCounts", "canonical_json_bytes", "read_bundle",
    "benchmarks_from_reader", "read_bundle_bytes", "reduce_candidate_records", "serialize_bundle_bytes", "sha256_bytes", "write_bundle",
    "benchmark_binding_from_manifest",
]
