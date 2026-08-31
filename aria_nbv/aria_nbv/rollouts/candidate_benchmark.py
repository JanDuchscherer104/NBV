"""Immutable, presentation-free candidate benchmark evidence.

The benchmark is deliberately a small interchange contract.  Producers may
reduce their candidate audit in any way, but consumers read the resulting
content-addressed bundle rather than reinterpreting rollout metadata.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import os
import re
import tempfile
import zipfile
from collections.abc import Collection, Iterable, Mapping
from dataclasses import asdict, dataclass, field, fields
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Literal, cast

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from ..pose_generation.types import CandidateSamplingResult

SCHEMA_ID = "aria-nbv-candidate-benchmark-v1"
CANDIDATE_SUPPORT_METRICS_REVISION = 1
FAMILY_PREFLIGHT_SCHEMA_ID = "aria-nbv-candidate-family-preflight-v2"
FAMILY_PHASE_A_SCHEMA_ID = "aria-nbv-candidate-family-phase-a-evidence-v2"
FAMILY_SUPPORT_FLOOR_REVISION = "family-support-floor-v1"
FLAT_GAIN_REVISION = "state-conditional-flat-gain-range-v2"
FLAT_GAIN_AGGREGATION = "minimum-per-state-range"
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


def _family_payload(value: "CandidateFamilyCounts", *, parquet: bool = False) -> dict[str, Any]:
    """Serialize one frozen cell without deepcopying its mapping proxy."""

    return {
        "family": value.family,
        "applicable": value.applicable,
        "attempted": value.attempted,
        "valid": value.valid,
        "selected": value.selected,
        "denominator": value.denominator,
        "reason": value.reason,
        "invalid_reason_bitsets": list(value.invalid_reason_bitsets),
        "first_failure": value.first_failure,
        "margins": _json_field(value.margins) if parquet else dict(value.margins),
        "refill_rounds": value.refill_rounds,
        "fallback_used": value.fallback_used,
        "support_failure": value.support_failure,
    }


def _optional_text(value: Any) -> str | None:
    """Preserve missing lineage while normalizing present values to text."""

    return None if value is None else str(value)


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
    """One factual state/family cell without fabricating missing provenance.

    ``applicable=None`` denotes an unknown legacy state, not false. Diagnostic
    fields summarize only values persisted for the cell; absent margins,
    refill state, fallback state, or support failure remain ``None``.
    """

    family: str
    applicable: bool | None
    attempted: int = 0
    valid: int = 0
    selected: int = 0
    denominator: int = 0
    reason: str | None = None
    invalid_reason_bitsets: tuple[int, ...] = ()
    first_failure: str | None = None
    margins: Mapping[str, float] = field(default_factory=dict)
    refill_rounds: int | None = None
    fallback_used: bool | None = None
    support_failure: str | None = None

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
        if any(reason < 0 for reason in self.invalid_reason_bitsets):
            raise ValueError("invalid-reason bitsets must be non-negative")
        if self.refill_rounds is not None and self.refill_rounds < 0:
            raise ValueError("refill_rounds must be non-negative when present")
        object.__setattr__(self, "margins", MappingProxyType(dict(self.margins)))

    def to_payload(self) -> dict[str, Any]:
        """Return a compact serializable projection without copying the proxy."""

        return _family_payload(self)


class CandidateSupportFailure(StrEnum):
    """Machine-readable failure reasons kept distinct by the preflight gate."""

    LOW_ROOT_SUPPORT = "low_root_support"
    FAMILY_COLLAPSE = "family_collapse"
    LOW_TARGET_FAMILY_SUPPORT = "low_target_family_support"
    UNKNOWN_FAMILY_APPLICABILITY = "unknown_family_applicability"
    RECORDED_SUPPORT_FAILURE = "recorded_support_failure"
    FLAT_GAIN = "flat_gain"
    MISSING_POPULATION_COVERAGE = "missing_population_coverage"
    MISSING_PRODUCTION_PROVENANCE = "missing_production_provenance"


@dataclass(frozen=True, slots=True)
class CandidateFamilyPreflightConfig:
    """Versioned family-support and label-variation policy.

    The resolved root threshold is ``max(12, ceil(0.25 * query_width))``.
    Family floors are independent: every applicable family must contribute at
    least one selected row in each factual state, while applicable
    non-forward target-aware families must contribute at least three selected
    rows in total. ``flat_gain_tolerance`` is applied to the exact finite,
    oracle-labelled target-root-gain range; it never infers reward from
    geometry.
    """

    query_width: int
    configured_families: tuple[str, ...]
    target_aware_families: tuple[str, ...] = ("target_bearing_local", "lateral_target_bypass")
    forward_family: str = "forward_local"
    min_selected_per_applicable_family: int = 1
    min_selected_target_aware_total: int = 3
    flat_gain_tolerance: float = 1.0e-4
    flat_gain_aggregation: str = FLAT_GAIN_AGGREGATION
    require_known_applicability: bool = True
    expected_population_size: int | None = None
    audit_strata_count: int = 10
    family_floor_revision: str = FAMILY_SUPPORT_FLOOR_REVISION
    flat_gain_revision: str = FLAT_GAIN_REVISION

    def __post_init__(self) -> None:
        if self.query_width <= 0:
            raise ValueError("query_width must be positive")
        if not self.configured_families or len(set(self.configured_families)) != len(self.configured_families):
            raise ValueError("configured_families must be non-empty and unique")
        if self.min_selected_per_applicable_family < 0 or self.min_selected_target_aware_total < 0:
            raise ValueError("family support floors must be non-negative")
        if not math.isfinite(self.flat_gain_tolerance) or self.flat_gain_tolerance < 0:
            raise ValueError("flat_gain_tolerance must be finite and non-negative")
        if self.flat_gain_aggregation != FLAT_GAIN_AGGREGATION:
            raise ValueError(f"flat_gain_aggregation must be {FLAT_GAIN_AGGREGATION!r}")
        if self.expected_population_size is not None and self.expected_population_size <= 0:
            raise ValueError("expected_population_size must be positive when present")
        if self.audit_strata_count <= 0:
            raise ValueError("audit_strata_count must be positive")
        if self.family_floor_revision != FAMILY_SUPPORT_FLOOR_REVISION:
            raise ValueError(f"family_floor_revision must be {FAMILY_SUPPORT_FLOOR_REVISION!r}")
        if self.flat_gain_revision != FLAT_GAIN_REVISION:
            raise ValueError(f"flat_gain_revision must be {FLAT_GAIN_REVISION!r}")

    @property
    def resolved_min_valid(self) -> int:
        """Return the persisted root-support threshold for this query width."""

        return max(12, math.ceil(0.25 * self.query_width))

    @property
    def config_sha256(self) -> str:
        """Bind every gate decision to the exact versioned policy."""

        return sha256_bytes(canonical_json_bytes(asdict(self)))

    def to_payload(self) -> dict[str, Any]:
        """Serialize the complete reader-resolvable family policy."""

        return cast(dict[str, Any], _canonical(asdict(self)))

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "CandidateFamilyPreflightConfig":
        """Decode one complete persisted family policy without defaults."""

        required = {item.name for item in fields(cls)}
        missing = sorted(required - set(payload))
        if missing:
            raise ValueError(f"candidate-family policy is missing persisted fields: {missing}")
        return cls(
            query_width=int(payload["query_width"]),
            configured_families=tuple(str(value) for value in payload["configured_families"]),
            target_aware_families=tuple(str(value) for value in payload["target_aware_families"]),
            forward_family=str(payload["forward_family"]),
            min_selected_per_applicable_family=int(payload["min_selected_per_applicable_family"]),
            min_selected_target_aware_total=int(payload["min_selected_target_aware_total"]),
            flat_gain_tolerance=float(payload["flat_gain_tolerance"]),
            flat_gain_aggregation=str(payload["flat_gain_aggregation"]),
            require_known_applicability=bool(payload["require_known_applicability"]),
            expected_population_size=(
                None if payload["expected_population_size"] is None else int(payload["expected_population_size"])
            ),
            audit_strata_count=int(payload["audit_strata_count"]),
            family_floor_revision=str(payload["family_floor_revision"]),
            flat_gain_revision=str(payload["flat_gain_revision"]),
        )


def candidate_family_preflight_config_from_writer(
    writer_config: Any,
    *,
    expected_population_size: int | None = None,
) -> CandidateFamilyPreflightConfig:
    """Resolve the complete family policy from one typed rollout writer config."""

    mixture = getattr(writer_config, "candidate_mixture", None)
    components = getattr(mixture, "components", None)
    query_width = getattr(mixture, "total_count", None)
    if not components or not isinstance(query_width, int) or query_width <= 0:
        raise ValueError("rollout writer lacks complete candidate-mixture provenance")
    configured: list[str] = []
    target_aware: list[str] = []
    forward_family: str | None = None
    target_positions = {"target_bearing_local", "lateral_target_bypass", "target_orbit"}
    for component in components:
        name = str(getattr(component, "name", ""))
        position = getattr(component, "position_mode", None)
        position_value = str(getattr(position, "value", position or ""))
        if not name or not position_value:
            raise ValueError("rollout writer candidate components require names and position roles")
        names = [name]
        paired = getattr(component, "paired_view_mode", None)
        if paired is not None:
            paired_value = str(getattr(paired, "value", paired))
            names.append(f"{name}__paired_{paired_value}")
        configured.extend(names)
        if position_value in target_positions:
            target_aware.extend(names)
        if position_value == "forward_local":
            if forward_family is not None and forward_family != name:
                raise ValueError("rollout writer has ambiguous forward-family provenance")
            forward_family = name
    return CandidateFamilyPreflightConfig(
        query_width=query_width,
        configured_families=tuple(configured),
        target_aware_families=tuple(target_aware),
        forward_family=forward_family or "forward_local",
        require_known_applicability=True,
        expected_population_size=expected_population_size,
    )


@dataclass(frozen=True, slots=True)
class FlatGainOutcome:
    """State-conditional label variation with exact label/state denominators."""

    available: bool
    passed: bool | None
    denominator: int
    eligible_state_denominator: int
    tolerance: float
    observed_range: float | None
    revision: str
    aggregation: str
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class CandidatePopulationCoverage:
    """Population counts used by the canonical family preflight decision."""

    expected: int | None
    selected_source_rows: int
    represented_rows: int
    target_states: int
    unique_scenes: int

    def __post_init__(self) -> None:
        values = (
            self.selected_source_rows,
            self.represented_rows,
            self.target_states,
            self.unique_scenes,
        )
        if any(value < 0 for value in values):
            raise ValueError("candidate population coverage counts must be non-negative")
        if self.expected is not None and self.expected <= 0:
            raise ValueError("candidate population expected count must be positive")

    @property
    def complete(self) -> bool:
        """Return whether evidence contains a non-empty complete population."""

        if self.expected is None:
            return self.represented_rows > 0 and self.unique_scenes > 0
        return all(
            value == self.expected
            for value in (
                self.selected_source_rows,
                self.represented_rows,
                self.target_states,
                self.unique_scenes,
            )
        )


@dataclass(frozen=True, slots=True)
class CandidatePreflightBlocker:
    """One deterministic go/no-go blocker, optionally scoped to state/family."""

    code: CandidateSupportFailure
    detail: str
    state_key: str | None = None
    family: str | None = None


@dataclass(frozen=True, slots=True)
class CandidateFamilyPreflight:
    """Canonical presentation-free Phase-A family-support decision."""

    go: bool
    schema_id: str
    config_sha256: str
    config: CandidateFamilyPreflightConfig
    query_width: int
    resolved_min_valid: int
    cells: tuple[tuple[str, CandidateFamilyCounts], ...]
    blockers: tuple[CandidatePreflightBlocker, ...]
    flat_gain: FlatGainOutcome
    coverage: CandidatePopulationCoverage
    audit_strata: Mapping[str, tuple[str, ...]]

    def __post_init__(self) -> None:
        object.__setattr__(self, "audit_strata", MappingProxyType(dict(self.audit_strata)))

    def to_payload(self) -> dict[str, Any]:
        """Serialize the single canonical decision for CLI, campaign, and UI."""

        return {
            "schema_id": self.schema_id,
            "go": self.go,
            "config_sha256": self.config_sha256,
            "config": self.config.to_payload(),
            "query_width": self.query_width,
            "resolved_min_valid": self.resolved_min_valid,
            "cells": [{"state_key": state_key, **_canonical(_family_payload(cell))} for state_key, cell in self.cells],
            "blockers": [{**asdict(blocker), "code": blocker.code.value} for blocker in self.blockers],
            "flat_gain": asdict(self.flat_gain),
            "coverage": asdict(self.coverage),
            "audit_strata": {name: list(scenes) for name, scenes in self.audit_strata.items()},
        }


@dataclass(frozen=True, slots=True)
class CandidateFamilyPhaseAEvidence:
    """Immutable Phase-A proposal-support audit and canonical gate result.

    This is a no-render, no-reward-label Phase-A proposal-support audit with
    privileged GT target instruction and mesh validity. It therefore uses
    oracle-owned target geometry for instruction and physical validity without
    claiming to be oracle-free.

    ``source_manifest_sha256`` binds the reviewed manifest file bytes, while
    ``source_store_manifest_hash`` preserves the VIN store's native canonical
    manifest identity. Current stores use the repository's 16-hex stable
    msgspec hash; older compatible evidence may carry a 64-hex identity. These
    two provenance domains are intentionally not re-hashed into one another.
    """

    source_manifest_sha256: str
    source_store_manifest_hash: str
    source_cache_version: str
    split_manifest_hash: str
    source_store_dir: str
    writer_config_sha256: str
    implementation_revision: str
    generation_revision: Mapping[str, str]
    runtime_identity: Mapping[str, str]
    source_row_count: int
    scene_count: int
    target_state_count: int
    excluded_source_rows: Mapping[str, str]
    records: tuple["CandidateBenchmark", ...]
    preflight: CandidateFamilyPreflight

    def __post_init__(self) -> None:
        for name in ("source_manifest_sha256", "writer_config_sha256"):
            if not re.fullmatch(r"[0-9a-f]{64}", getattr(self, name)):
                raise ValueError(f"{name} must be a SHA-256 identity")
        if not re.fullmatch(r"(?:[0-9a-f]{16}|[0-9a-f]{64})", self.source_store_manifest_hash):
            raise ValueError("source_store_manifest_hash must preserve the canonical store-manifest identity")
        if not self.source_cache_version or not self.split_manifest_hash or not self.source_store_dir:
            raise ValueError("Phase-A evidence requires complete source-store lineage")
        if self.generation_revision.get("clean_commit") != self.implementation_revision:
            raise ValueError("Phase-A implementation revision must equal the clean generation commit")
        required_revision = {
            "contract_revision",
            "clean_commit",
            "head_tree",
            "uv_lock_sha256",
            "content_bundle_hash",
            "revision_hash",
        }
        if required_revision - set(self.generation_revision):
            raise ValueError("Phase-A evidence requires complete generation revision identity")
        required_runtime = {"python", "torch", "cuda", "pytorch3d", "gpu_name", "gpu_capability"}
        if required_runtime - set(self.runtime_identity):
            raise ValueError("Phase-A evidence requires complete CUDA runtime identity")
        if self.source_row_count < 1 or self.scene_count < 1 or self.target_state_count < 0:
            raise ValueError("Phase-A evidence counts are invalid")
        if self.preflight.flat_gain.available or self.preflight.flat_gain.denominator != 0:
            raise ValueError("Phase-A evidence must not contain oracle reward labels")
        coverage = self.preflight.coverage
        if (
            coverage.selected_source_rows != self.source_row_count
            or coverage.represented_rows != len(self.records)
            or coverage.target_states != self.target_state_count
            or coverage.unique_scenes != self.scene_count
        ):
            raise ValueError("Phase-A evidence counts disagree with canonical population coverage")
        object.__setattr__(self, "excluded_source_rows", MappingProxyType(dict(self.excluded_source_rows)))
        object.__setattr__(self, "generation_revision", MappingProxyType(dict(self.generation_revision)))
        object.__setattr__(self, "runtime_identity", MappingProxyType(dict(self.runtime_identity)))

    def to_payload(self) -> dict[str, Any]:
        """Serialize records and the one reducer result with a content hash."""

        payload = {
            "schema_id": FAMILY_PHASE_A_SCHEMA_ID,
            "source_manifest_sha256": self.source_manifest_sha256,
            "source_store_manifest_hash": self.source_store_manifest_hash,
            "source_cache_version": self.source_cache_version,
            "split_manifest_hash": self.split_manifest_hash,
            "source_store_dir": self.source_store_dir,
            "writer_config_sha256": self.writer_config_sha256,
            "implementation_revision": self.implementation_revision,
            "generation_revision": dict(self.generation_revision),
            "runtime_identity": dict(self.runtime_identity),
            "source_row_count": self.source_row_count,
            "scene_count": self.scene_count,
            "target_state_count": self.target_state_count,
            "excluded_source_rows": dict(self.excluded_source_rows),
            "oracle_labels_included": False,
            "records": [record.to_record() for record in self.records],
            "preflight": self.preflight.to_payload(),
            "broad_generation_admitted": False,
            "broad_generation_blocker": "broad_generation_blocked_pending_wp18",
        }
        return {**payload, "artifact_sha256": sha256_bytes(canonical_json_bytes(payload))}


@dataclass(frozen=True, slots=True)
class CandidateFamilyPhaseAExpectation:
    """Externally owned identities required to admit one Phase-A artifact."""

    source_manifest_sha256: str
    source_store_manifest_hash: str
    source_cache_version: str
    split_manifest_hash: str
    source_store_dir: str
    writer_config_sha256: str
    generation_revision_hash: str


def candidate_family_preflight_from_payload(payload: Mapping[str, Any]) -> CandidateFamilyPreflight:
    """Reconstruct the immutable reducer result from a primitive payload."""

    if payload.get("schema_id") != FAMILY_PREFLIGHT_SCHEMA_ID:
        raise ValueError("unsupported candidate-family preflight schema")
    config_payload = payload.get("config")
    if not isinstance(config_payload, Mapping):
        raise ValueError("candidate-family preflight requires the complete reducer policy")
    config = CandidateFamilyPreflightConfig.from_payload(config_payload)
    cells = tuple(
        (
            str(item["state_key"]),
            CandidateFamilyCounts(
                family=str(item["family"]),
                applicable=(None if item.get("applicable") is None else bool(item["applicable"])),
                attempted=int(item.get("attempted", 0)),
                valid=int(item.get("valid", 0)),
                selected=int(item.get("selected", 0)),
                denominator=int(item.get("denominator", 0)),
                reason=_optional_text(item.get("reason")),
                invalid_reason_bitsets=tuple(int(value) for value in item.get("invalid_reason_bitsets", ())),
                first_failure=_optional_text(item.get("first_failure")),
                margins=_mapping_field(item.get("margins", {})),
                refill_rounds=(None if item.get("refill_rounds") is None else int(item["refill_rounds"])),
                fallback_used=(None if item.get("fallback_used") is None else bool(item["fallback_used"])),
                support_failure=_optional_text(item.get("support_failure")),
            ),
        )
        for item in payload.get("cells", ())
    )
    blockers = tuple(
        CandidatePreflightBlocker(
            code=CandidateSupportFailure(str(item["code"])),
            detail=str(item["detail"]),
            state_key=_optional_text(item.get("state_key")),
            family=_optional_text(item.get("family")),
        )
        for item in payload.get("blockers", ())
    )
    flat_payload = payload.get("flat_gain")
    coverage_payload = payload.get("coverage")
    if not isinstance(flat_payload, Mapping) or not isinstance(coverage_payload, Mapping):
        raise ValueError("candidate-family preflight requires flat-gain and population evidence")
    flat_gain = FlatGainOutcome(
        available=bool(flat_payload["available"]),
        passed=None if flat_payload.get("passed") is None else bool(flat_payload["passed"]),
        denominator=int(flat_payload["denominator"]),
        eligible_state_denominator=int(flat_payload["eligible_state_denominator"]),
        tolerance=float(flat_payload["tolerance"]),
        observed_range=(None if flat_payload.get("observed_range") is None else float(flat_payload["observed_range"])),
        revision=str(flat_payload["revision"]),
        aggregation=str(flat_payload["aggregation"]),
        reason=_optional_text(flat_payload.get("reason")),
    )
    coverage = CandidatePopulationCoverage(
        expected=(None if coverage_payload.get("expected") is None else int(coverage_payload["expected"])),
        selected_source_rows=int(coverage_payload["selected_source_rows"]),
        represented_rows=int(coverage_payload["represented_rows"]),
        target_states=int(coverage_payload["target_states"]),
        unique_scenes=int(coverage_payload["unique_scenes"]),
    )
    result = CandidateFamilyPreflight(
        go=bool(payload["go"]),
        schema_id=FAMILY_PREFLIGHT_SCHEMA_ID,
        config_sha256=str(payload["config_sha256"]),
        config=config,
        query_width=int(payload["query_width"]),
        resolved_min_valid=int(payload["resolved_min_valid"]),
        cells=cells,
        blockers=blockers,
        flat_gain=flat_gain,
        coverage=coverage,
        audit_strata=MappingProxyType(
            {
                str(name): tuple(str(scene) for scene in scenes)
                for name, scenes in cast(Mapping[str, Iterable[Any]], payload.get("audit_strata", {})).items()
            }
        ),
    )
    if result.go != (not result.blockers):
        raise ValueError("candidate-family preflight go flag disagrees with blockers")
    if (
        result.config_sha256 != config.config_sha256
        or result.query_width != config.query_width
        or result.resolved_min_valid != config.resolved_min_valid
    ):
        raise ValueError("candidate-family preflight policy identity disagrees with its decision")
    return result


def read_candidate_family_phase_a(
    path: Path | str,
    *,
    expected: CandidateFamilyPhaseAExpectation,
) -> CandidateFamilyPhaseAEvidence:
    """Validate content, source, config, and revision identities before use."""

    payload = json.loads(Path(path).expanduser().resolve().read_bytes())
    if not isinstance(payload, dict) or payload.get("schema_id") != FAMILY_PHASE_A_SCHEMA_ID:
        raise ValueError("unsupported candidate-family Phase-A evidence schema")
    claimed_hash = str(payload.pop("artifact_sha256", ""))
    if claimed_hash != sha256_bytes(canonical_json_bytes(payload)):
        raise ValueError("candidate-family Phase-A artifact content hash mismatch")
    expected_values = asdict(expected)
    actual_values = {
        "source_manifest_sha256": payload.get("source_manifest_sha256"),
        "source_store_manifest_hash": payload.get("source_store_manifest_hash"),
        "source_cache_version": payload.get("source_cache_version"),
        "split_manifest_hash": payload.get("split_manifest_hash"),
        "source_store_dir": payload.get("source_store_dir"),
        "writer_config_sha256": payload.get("writer_config_sha256"),
        "generation_revision_hash": (
            payload.get("generation_revision", {}).get("revision_hash")
            if isinstance(payload.get("generation_revision"), Mapping)
            else None
        ),
    }
    if actual_values != expected_values:
        raise ValueError("candidate-family Phase-A source/config/revision identity mismatch")
    records_payload = payload.get("records")
    if not isinstance(records_payload, list):
        raise ValueError("candidate-family Phase-A records must be a list")
    preflight_payload = payload.get("preflight")
    if not isinstance(preflight_payload, Mapping):
        raise ValueError("candidate-family Phase-A preflight payload is missing")
    records = reduce_candidate_records(records_payload)
    records_by_key = {(record.scene_key, record.state_key): record for record in records}
    persisted_keys = tuple((str(record["scene_key"]), str(record["state_key"])) for record in records_payload)
    if len(records_by_key) != len(persisted_keys) or any(key not in records_by_key for key in persisted_keys):
        raise ValueError("candidate-family Phase-A record identities do not round-trip")
    evidence = CandidateFamilyPhaseAEvidence(
        source_manifest_sha256=str(payload["source_manifest_sha256"]),
        source_store_manifest_hash=str(payload["source_store_manifest_hash"]),
        source_cache_version=str(payload["source_cache_version"]),
        split_manifest_hash=str(payload["split_manifest_hash"]),
        source_store_dir=str(payload["source_store_dir"]),
        writer_config_sha256=str(payload["writer_config_sha256"]),
        implementation_revision=str(payload["implementation_revision"]),
        generation_revision=cast(Mapping[str, str], payload["generation_revision"]),
        runtime_identity=cast(Mapping[str, str], payload["runtime_identity"]),
        source_row_count=int(payload["source_row_count"]),
        scene_count=int(payload["scene_count"]),
        target_state_count=int(payload["target_state_count"]),
        excluded_source_rows=cast(Mapping[str, str], payload.get("excluded_source_rows", {})),
        records=tuple(records_by_key[key] for key in persisted_keys),
        preflight=candidate_family_preflight_from_payload(preflight_payload),
    )
    recomputed = reduce_candidate_family_preflight(
        evidence.records,
        evidence.preflight.config,
        coverage=evidence.preflight.coverage,
    )
    if recomputed.to_payload() != evidence.preflight.to_payload():
        raise ValueError("candidate-family Phase-A reducer evidence disagrees with its records and policy")
    if evidence.to_payload()["artifact_sha256"] != claimed_hash:
        raise ValueError("candidate-family Phase-A artifact does not round-trip canonically")
    return evidence


def write_candidate_family_phase_a(path: Path | str, evidence: CandidateFamilyPhaseAEvidence) -> Path:
    """Atomically write one compact, canonical Phase-A JSON artifact."""

    target = Path(path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = canonical_json_bytes(evidence.to_payload()) + b"\n"
    with tempfile.NamedTemporaryFile(dir=target.parent, prefix=f".{target.name}.", delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, target)
    return target


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

    oracle_label: bool = False
    """Whether direct continuous target-root gain is a valid oracle label."""

    target_root_gain: float | None = None
    """Direct continuous target-root gain when ``oracle_label`` is true."""

    def __post_init__(self) -> None:
        if not self.family or not self.position or not self.state_key:
            raise ValueError("candidate point family, position, and state_key are required")
        if not isinstance(self.actor_valid, bool) or not isinstance(self.selected, bool):
            raise ValueError("candidate point statuses must be bool")
        if not isinstance(self.oracle_label, bool):
            raise ValueError("oracle_label must be bool")
        if self.target_root_gain is not None and not math.isfinite(self.target_root_gain):
            raise ValueError("target_root_gain must be finite when present")
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
            "families": [_family_payload(family, parquet=True) for family in self.families],
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
class CandidateFamilySelection:
    """One factual state/family shell selection shared by UI and plots."""

    state_key: str
    family: str

    def __post_init__(self) -> None:
        if not self.state_key or not self.family:
            raise ValueError("candidate-family selection requires state and family")


def select_candidate_family_shell(
    records: Iterable[CandidateBenchmark],
    selection: CandidateFamilySelection,
) -> tuple[CandidateBenchmark, ...]:
    """Project one selected cell into the existing 2-D/3-D shell interface."""

    selected_records: list[CandidateBenchmark] = []
    for record in records:
        if record.state_key != selection.state_key:
            continue
        points = tuple(point for point in record.points if point.family == selection.family)
        family = tuple(cell for cell in record.families if cell.family == selection.family)
        if not family:
            continue
        selected_records.append(
            CandidateBenchmark(
                state_key=record.state_key,
                scene_key=record.scene_key,
                families=family,
                geometry=record.geometry,
                diversity=record.diversity,
                timings_ms=record.timings_ms,
                resources=record.resources,
                provenance=record.provenance,
                candidate_ids=tuple(point.candidate_id for point in points),
                coordinates=tuple(point.xyz for point in points),
                lineage=record.lineage,
                points=points,
            )
        )
    return tuple(selected_records)


def benchmark_from_sampling_result(
    result: "CandidateSamplingResult",
    *,
    scene_key: str,
    state_key: str,
    family_positions: Mapping[str, str],
    target_center_world: Iterable[float],
    provenance: Mapping[str, str] | None = None,
) -> CandidateBenchmark:
    """Reduce one generated full shell without scoring or rendering it.

    The sampling result is the authoritative attempted-row table. Its compact
    valid mask defines final-shell ``selected`` counts for the family gate;
    there is no policy-selected transition in this Phase-A path. Rule reason
    bitsets and continuous margins are copied only when the generator produced
    them, so missing diagnostics remain unavailable rather than inferred.

    Args:
        result: Full-shell candidate-generation result with component lineage.
        scene_key: Stable source-scene identity.
        state_key: Stable source-sample and target identity.
        family_positions: Config-owned component-to-position-mode mapping.
        target_center_world: Target centre used by the candidate generator.
        provenance: Optional immutable source/config identities.

    Returns:
        Presentation-free benchmark record consumable by the canonical family
        preflight reducer, serializer, plots, campaign gate, and Streamlit.

    Raises:
        ValueError: If full-shell family lineage or tensor alignment is absent.
    """

    import torch

    from .trace import INVALID_REASON_CODES, _candidate_invalid_reasons

    mask_valid = result.mask_valid.detach().to(device="cpu", dtype=torch.bool).reshape(-1)
    shell_count = int(mask_valid.numel())
    if result.component_name is None or len(result.component_name) != shell_count:
        raise ValueError("Phase-A candidate evidence requires full-shell component_name lineage.")
    if result.shell_offsets_ref is None or result.shell_offsets_ref.reshape(-1, 3).shape[0] != shell_count:
        raise ValueError("Phase-A candidate evidence requires aligned full-shell reference offsets.")

    reason_bitset, primary_reason = _candidate_invalid_reasons(result)
    reason_bitset = reason_bitset.detach().to(device="cpu").reshape(-1)
    primary_reason = primary_reason.detach().to(device="cpu").reshape(-1)
    reason_names = {int(code): name for name, code in INVALID_REASON_CODES.items()}
    offsets_ref = result.shell_offsets_ref.detach().to(device="cpu", dtype=torch.float32).reshape(-1, 3)
    target_world = torch.as_tensor(tuple(target_center_world), dtype=torch.float32).reshape(1, 3)
    target_ref = result.reference_pose.inverse().transform(target_world.to(result.reference_pose.t.device))
    target_ref = target_ref.detach().to(device="cpu", dtype=torch.float32).reshape(3)
    normalization = max(float(torch.linalg.norm(target_ref).item()), 1.0e-6)
    coordinates_tensor = offsets_ref / normalization
    target_relative_tensor = (offsets_ref - target_ref.reshape(1, 3)) / normalization

    shell_rotations = result.shell_poses.R.detach().to(device="cpu", dtype=torch.float32).reshape(-1, 3, 3)
    reference_rotation = result.reference_pose.R.detach().to(device="cpu", dtype=torch.float32).reshape(3, 3)
    forward_world = shell_rotations[:, :, 2]
    forward_ref = forward_world @ reference_rotation
    forward_ref = forward_ref / torch.linalg.norm(forward_ref, dim=1, keepdim=True).clamp_min(1.0e-8)

    family_indices: dict[str, list[int]] = {}
    for index, family in enumerate(result.component_name):
        family_indices.setdefault(str(family), []).append(index)
    missing = sorted(set(family_indices) - set(family_positions))
    if missing:
        raise ValueError(f"Phase-A candidate evidence has unconfigured component lineage: {missing!r}.")

    margin_sources = {
        "free_space_margin_m": "free_space_margin_m",
        "mesh_distance_m": "min_distance_to_mesh",
        "path_min_clearance_m": "path_min_clearance_m",
        "target_pixel_margin_px": "target_pixel_margin_px",
    }
    families: list[CandidateFamilyCounts] = []
    for family in family_positions:
        indices = family_indices.get(family, [])
        index_tensor = torch.as_tensor(indices, dtype=torch.int64)
        valid_count = int(mask_valid[index_tensor].sum().item()) if indices else 0
        invalid_indices = [index for index in indices if not bool(mask_valid[index])]
        failures: dict[str, int] = {}
        for index in invalid_indices:
            reason = reason_names.get(int(primary_reason[index].item()), f"reason_{int(primary_reason[index].item())}")
            failures[reason] = failures.get(reason, 0) + 1
        first_failure = min(failures, key=lambda name: (-failures[name], name)) if failures else None
        margins: dict[str, float] = {}
        for public_name, extra_name in margin_sources.items():
            value = result.extras.get(extra_name)
            if not isinstance(value, torch.Tensor) or value.reshape(-1).numel() != shell_count or not indices:
                continue
            selected = value.detach().to(device="cpu", dtype=torch.float32).reshape(-1)[index_tensor]
            finite = selected[torch.isfinite(selected)]
            if finite.numel():
                margins[public_name] = float(finite.min().item())
        families.append(
            CandidateFamilyCounts(
                family=family,
                applicable=True,
                attempted=len(indices),
                valid=valid_count,
                selected=valid_count,
                denominator=len(indices),
                invalid_reason_bitsets=tuple(sorted({int(reason_bitset[index].item()) for index in invalid_indices})),
                first_failure=first_failure,
                margins=margins,
            )
        )

    coordinates = tuple(_coordinate3(row) for row in coordinates_tensor.tolist())
    points = tuple(
        CandidatePoint(
            candidate_id=index,
            xyz=coordinates[index],
            family=str(result.component_name[index]),
            position=family_positions[str(result.component_name[index])],
            actor_valid=bool(mask_valid[index]),
            selected=False,
            state_key=state_key,
            target_relative_xyz=_coordinate3(target_relative_tensor[index].tolist()),
            view_direction_xyz=_coordinate3(forward_ref[index].tolist()),
        )
        for index in range(shell_count)
    )
    return CandidateBenchmark(
        state_key=state_key,
        scene_key=scene_key,
        families=tuple(families),
        geometry={"candidate_count": float(shell_count), "root_target_distance_m": normalization},
        provenance=dict(provenance or {}),
        candidate_ids=tuple(range(shell_count)),
        coordinates=coordinates,
        lineage={"family_identity": "component_name", "selection_semantics": "final_valid_action_shell"},
        points=points,
    )


@dataclass(frozen=True, slots=True)
class CandidateBenchmarkSource:
    """Durable identity of a validated benchmark representation.

    Attributes:
        kind: ``directory`` for a persisted bundle or ``archive-bytes`` for an
            in-memory ZIP payload.
        sha256: Content identity of the exact source representation.
        path: Canonical persisted directory for ``directory`` sources; absent
            for archive bytes, which have no durable filesystem location.
    """

    kind: Literal["directory", "archive-bytes"]
    sha256: str
    path: Path | None = None

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[0-9a-f]{64}", self.sha256):
            raise ValueError("candidate benchmark source requires a SHA-256 identity")
        if self.kind == "directory" and self.path is None:
            raise ValueError("directory benchmark source requires a path")
        if self.kind == "archive-bytes" and self.path is not None:
            raise ValueError("archive-byte benchmark source cannot claim a filesystem path")


@dataclass(frozen=True, slots=True)
class CandidateBenchmarkBundle:
    """Validated immutable benchmark facts and their durable source identity."""

    manifest: Mapping[str, Any]
    records: tuple[CandidateBenchmark, ...]
    source: CandidateBenchmarkSource


def reduce_candidate_records(records: list[Mapping[str, Any]]) -> tuple[CandidateBenchmark, ...]:
    """Normalize reducer input into immutable benchmark DTOs."""

    result = []
    keys: set[tuple[str, str]] = set()
    for record in records:
        families = tuple(
            CandidateFamilyCounts(
                **{
                    **family,
                    "invalid_reason_bitsets": tuple(int(value) for value in family.get("invalid_reason_bitsets", ())),
                    "margins": _mapping_field(family.get("margins", {})),
                }
            )
            for family in record.get("families", ())
        )
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
    """Build state-keyed facts from canonical candidate rows and geometry.

    Candidate audit rows own attempted, valid, and selected counts. Proposal
    geometry is an optional visualization join: projection failures retain the
    affected state and counts with an explicit lineage reason. For one requested
    state, the complete shell is projected before the display row limit is
    applied, so a limit smaller than the shell cannot fabricate empty support.
    """

    from .inspection import candidate_audit_rows, proposal_support_geometry

    grouped: dict[tuple[str, str], dict[str, list[Mapping[str, Any]]]] = {}
    configured_families = _configured_family_names(reader)
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
            max_candidates=None if requested_state is not None else candidate_limit,
        )
    geometry_points = {point.candidate_row_id: point for point in projection.points} if projection else {}
    geometry_frames = {frame.frame_id: frame for frame in projection.frames} if projection else {}
    geometry_issues = tuple(getattr(projection, "issues", ())) if projection else ()
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
        key = (str(row["scene"]), f"rollout:{row['rollout_row_id']}/step:{row['step_row_id']}")
        grouped.setdefault(key, {}).setdefault(str(row["mixture"]), []).append(row)
    result = []
    for (scene, state), family_rows in sorted(grouped.items()):
        families = []
        candidate_ids: list[int] = []
        coordinates: list[tuple[float, float, float]] = []
        frame_ids: set[str] = set()
        lineage: dict[str, str] = {"family_identity": "mixture_component"}
        points: list[CandidatePoint] = []
        state_rows = [row for rows in family_rows.values() for row in rows]
        missing_geometry = projection is not None and any(
            int(row["candidate_row_id"]) not in geometry_points for row in state_rows
        )
        if missing_geometry:
            rollout_row_id = int(state_rows[0]["rollout_row_id"])
            step_row_id = int(state_rows[0]["step_row_id"])
            issue_codes = sorted(
                {
                    str(issue.code)
                    for issue in geometry_issues
                    if issue.rollout_row_id == rollout_row_id
                    and (issue.step_row_id is None or issue.step_row_id == step_row_id)
                }
            )
            lineage["proposal_support_unavailable_reason"] = ",".join(
                issue_codes or ("candidate_geometry_unavailable",)
            )
        state_family_names = sorted(set(family_rows) | set(configured_families))
        for family in state_family_names:
            rows = family_rows.get(family, [])
            applicable = True if family in configured_families else None
            valid = sum(bool(row.get("actor_action")) for row in rows)
            selected = sum(int(row.get("compact_valid_index", -1)) >= 0 for row in rows)
            invalid_rows = [row for row in rows if not bool(row.get("actor_action"))]
            first_failures: dict[str, int] = {}
            for invalid_row in invalid_rows:
                reason = str(invalid_row.get("invalid_reason") or "unknown")
                first_failures[reason] = first_failures.get(reason, 0) + 1
            first_failure = (
                min(first_failures, key=lambda reason: (-first_failures[reason], reason)) if first_failures else None
            )
            margins: dict[str, float] = {}
            for name in (
                "free_space_margin_m",
                "mesh_distance_m",
                "path_min_clearance_m",
                "target_pixel_margin_px",
            ):
                values = _finite_values(rows, name)
                if values:
                    margins[name] = min(values)
            families.append(
                CandidateFamilyCounts(
                    family=family,
                    applicable=applicable,
                    attempted=len(rows),
                    valid=valid,
                    selected=selected,
                    denominator=len(rows),
                    reason=None if applicable is not None else "unavailable_in_legacy_store",
                    invalid_reason_bitsets=tuple(
                        sorted({int(row.get("invalid_reason_bitset") or 0) for row in invalid_rows})
                    ),
                    first_failure=first_failure,
                    margins=margins,
                    refill_rounds=_consistent_optional_int(rows, "refill_rounds"),
                    fallback_used=_consistent_optional_bool(rows, "fallback_used"),
                    support_failure=_consistent_optional_text(rows, "support_failure"),
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
                        candidate_id=candidate_id,
                        xyz=coordinates[-1],
                        family=family,
                        position=str(family_row["position"]),
                        actor_valid=bool(family_row.get("actor_action")),
                        selected=bool(family_row.get("selected")),
                        state_key=state,
                        oracle_label=bool(family_row.get("oracle_label")),
                        target_root_gain=_finite_value(family_row.get("target_root_gain")),
                        candidate_config=_optional_text(family_row.get("candidate_config")),
                        rollout_config=_optional_text(family_row.get("rollout_config")),
                        branch_schedule=_optional_text(family_row.get("branch_schedule")),
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


def _configured_family_names(reader: Any) -> tuple[str, ...]:
    """Read configured family identity without guessing legacy provenance."""

    try:
        manifest = reader.manifest().get("manifest", {})
    except (AttributeError, TypeError):
        return ()
    generation = manifest.get("generation", {}) if isinstance(manifest, Mapping) else {}
    writer = generation.get("writer_config", {}) if isinstance(generation, Mapping) else {}
    mixture = writer.get("candidate_mixture", {}) if isinstance(writer, Mapping) else {}
    components = mixture.get("components", ()) if isinstance(mixture, Mapping) else ()
    names = []
    for component in components if isinstance(components, Collection) else ():
        if isinstance(component, Mapping):
            name = component.get("name") or component.get("family") or component.get("position")
        elif isinstance(component, (list, tuple)) and component:
            name = component[0]
        else:
            name = None
        if name is not None:
            names.append(str(name))
    return tuple(dict.fromkeys(names))


def _consistent_optional_int(rows: Iterable[Mapping[str, Any]], name: str) -> int | None:
    values = {int(row[name]) for row in rows if row.get(name) is not None}
    return next(iter(values)) if len(values) == 1 else None


def _consistent_optional_bool(rows: Iterable[Mapping[str, Any]], name: str) -> bool | None:
    values = {bool(row[name]) for row in rows if row.get(name) is not None}
    return next(iter(values)) if len(values) == 1 else None


def _consistent_optional_text(rows: Iterable[Mapping[str, Any]], name: str) -> str | None:
    values = {str(row[name]) for row in rows if row.get(name) is not None}
    return next(iter(values)) if len(values) == 1 else None


def _finite_values(rows: Iterable[Mapping[str, Any]], name: str) -> list[float]:
    """Return only persisted finite diagnostic scalars for one cell."""

    values = []
    for row in rows:
        value = _finite_value(row.get(name))
        if value is not None:
            values.append(value)
    return values


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


def reduce_candidate_family_preflight(
    records: Iterable[CandidateBenchmark],
    config: CandidateFamilyPreflightConfig,
    *,
    coverage: CandidatePopulationCoverage | None = None,
) -> CandidateFamilyPreflight:
    """Evaluate root support, family floors, and direct label variation once.

    Root support is evaluated per factual state against the resolved threshold.
    Here ``selected`` means retained in the final valid action shell
    (``compact_valid_index >= 0``), not the one policy-chosen transition row.
    Family floors therefore apply to each state/family cell. Forward rows remain
    excluded from the per-state target-aware total. Unknown applicability is retained and
    blocks only when the supplied policy requires deployable provenance.
    """

    records = tuple(sorted(records, key=lambda record: (record.scene_key, record.state_key)))
    cells: list[tuple[str, CandidateFamilyCounts]] = []
    blockers: list[CandidatePreflightBlocker] = []
    derived_coverage = CandidatePopulationCoverage(
        expected=config.expected_population_size,
        selected_source_rows=len(records),
        represented_rows=len(records),
        target_states=len(records),
        unique_scenes=len({record.scene_key for record in records}),
    )
    coverage = coverage or derived_coverage
    if coverage.expected != config.expected_population_size:
        raise ValueError("candidate population coverage expectation disagrees with preflight policy")
    if not coverage.complete:
        blockers.append(
            CandidatePreflightBlocker(
                CandidateSupportFailure.MISSING_POPULATION_COVERAGE,
                f"expected={coverage.expected}; selected_source_rows={coverage.selected_source_rows}; represented_rows={coverage.represented_rows}; "
                f"target_states={coverage.target_states}; unique_scenes={coverage.unique_scenes}",
            )
        )
    for record in records:
        family_by_name = {family.family: family for family in record.families}
        target_selected = 0
        any_target_applicable = False
        for family_name in config.configured_families:
            cell = family_by_name.get(
                family_name,
                CandidateFamilyCounts(
                    family=family_name,
                    applicable=None,
                    reason="family_missing_from_state_provenance",
                ),
            )
            cells.append((record.state_key, cell))
            if cell.support_failure is not None and cell.applicable is not False:
                blockers.append(
                    CandidatePreflightBlocker(
                        CandidateSupportFailure.RECORDED_SUPPORT_FAILURE,
                        cell.support_failure,
                        record.state_key,
                        family_name,
                    )
                )
            if config.require_known_applicability and cell.applicable is None:
                blockers.append(
                    CandidatePreflightBlocker(
                        CandidateSupportFailure.UNKNOWN_FAMILY_APPLICABILITY,
                        "applicability is missing from the audited state",
                        record.state_key,
                        family_name,
                    )
                )
            if cell.applicable is True and cell.selected < config.min_selected_per_applicable_family:
                blockers.append(
                    CandidatePreflightBlocker(
                        CandidateSupportFailure.FAMILY_COLLAPSE,
                        f"selected={cell.selected} < family_floor={config.min_selected_per_applicable_family}",
                        record.state_key,
                        family_name,
                    )
                )
            if family_name in set(config.target_aware_families) - {config.forward_family}:
                if cell.applicable is True:
                    any_target_applicable = True
                    target_selected += cell.selected
        valid_total = sum(family.valid for family in record.families if family.applicable is not False)
        if valid_total < config.resolved_min_valid:
            blockers.append(
                CandidatePreflightBlocker(
                    CandidateSupportFailure.LOW_ROOT_SUPPORT,
                    f"valid={valid_total} < min_valid={config.resolved_min_valid}",
                    state_key=record.state_key,
                )
            )
        if any_target_applicable and target_selected < config.min_selected_target_aware_total:
            blockers.append(
                CandidatePreflightBlocker(
                    CandidateSupportFailure.LOW_TARGET_FAMILY_SUPPORT,
                    f"selected={target_selected} < target_family_floor={config.min_selected_target_aware_total}",
                    state_key=record.state_key,
                )
            )

    labels_by_state = {
        record.state_key: tuple(
            point.target_root_gain
            for point in record.points
            if point.oracle_label and point.target_root_gain is not None
        )
        for record in records
    }
    eligible_state_ranges = {
        state_key: max(values) - min(values) for state_key, values in labels_by_state.items() if len(values) >= 2
    }
    label_denominator = sum(len(values) for values in labels_by_state.values())
    if eligible_state_ranges:
        observed_range = min(eligible_state_ranges.values())
        failing_states = {
            state_key: value
            for state_key, value in eligible_state_ranges.items()
            if value <= config.flat_gain_tolerance
        }
        flat_gain = FlatGainOutcome(
            available=True,
            passed=not failing_states,
            denominator=label_denominator,
            eligible_state_denominator=len(eligible_state_ranges),
            tolerance=config.flat_gain_tolerance,
            observed_range=observed_range,
            revision=config.flat_gain_revision,
            aggregation=config.flat_gain_aggregation,
        )
        for state_key, state_range in sorted(failing_states.items()):
            blockers.append(
                CandidatePreflightBlocker(
                    CandidateSupportFailure.FLAT_GAIN,
                    f"state_label_range={state_range:.12g} <= tolerance={config.flat_gain_tolerance:.12g}",
                    state_key=state_key,
                )
            )
    else:
        flat_gain = FlatGainOutcome(
            available=False,
            passed=None,
            denominator=label_denominator,
            eligible_state_denominator=0,
            tolerance=config.flat_gain_tolerance,
            observed_range=None,
            revision=config.flat_gain_revision,
            aggregation=config.flat_gain_aggregation,
            reason="no_state_with_multiple_valid_target_labels",
        )

    scenes = sorted({record.scene_key for record in records})
    audit_strata: dict[str, tuple[str, ...]] = {}
    stratum_count = min(config.audit_strata_count, len(scenes))
    for index in range(stratum_count):
        audit_strata[f"audit-stratum-{index:02d}"] = tuple(scenes[index::stratum_count])
    ordered_blockers = tuple(
        sorted(blockers, key=lambda item: (item.code.value, item.state_key or "", item.family or "", item.detail))
    )
    return CandidateFamilyPreflight(
        go=not ordered_blockers,
        schema_id=FAMILY_PREFLIGHT_SCHEMA_ID,
        config_sha256=config.config_sha256,
        config=config,
        query_width=config.query_width,
        resolved_min_valid=config.resolved_min_valid,
        cells=tuple(cells),
        blockers=ordered_blockers,
        flat_gain=flat_gain,
        coverage=coverage,
        audit_strata=audit_strata,
    )


def candidate_family_preflight_from_reader(
    reader: Any,
    *,
    require_known_applicability: bool,
    flat_gain_tolerance: float = 1.0e-4,
) -> CandidateFamilyPreflight:
    """Build the complete store gate through the canonical benchmark reducer."""

    records = benchmarks_from_reader(reader, candidate_limit=None)
    config = _candidate_family_policy_from_reader(reader)
    if config is None:
        fallback = CandidateFamilyPreflightConfig(
            query_width=1,
            configured_families=("unknown",),
            flat_gain_tolerance=flat_gain_tolerance,
            require_known_applicability=require_known_applicability,
        )
        result = reduce_candidate_family_preflight(records, fallback)
        blocker = CandidatePreflightBlocker(
            CandidateSupportFailure.MISSING_PRODUCTION_PROVENANCE,
            "rollout manifest lacks the complete candidate_family_preflight policy",
        )
        blockers = tuple(
            sorted(
                (*result.blockers, blocker),
                key=lambda item: (item.code.value, item.state_key or "", item.family or "", item.detail),
            )
        )
        return CandidateFamilyPreflight(
            go=False,
            schema_id=result.schema_id,
            config_sha256=result.config_sha256,
            config=result.config,
            query_width=result.query_width,
            resolved_min_valid=result.resolved_min_valid,
            cells=result.cells,
            blockers=blockers,
            flat_gain=result.flat_gain,
            coverage=result.coverage,
            audit_strata=result.audit_strata,
        )
    if config.require_known_applicability != require_known_applicability:
        raise ValueError("reader-backed preflight applicability policy disagrees with the requested profile")
    if not math.isclose(config.flat_gain_tolerance, flat_gain_tolerance, rel_tol=0.0, abs_tol=0.0):
        raise ValueError("reader-backed preflight flat-gain tolerance disagrees with persisted policy")
    return reduce_candidate_family_preflight(records, config)


def _candidate_family_policy_from_reader(reader: Any) -> CandidateFamilyPreflightConfig | None:
    """Resolve only a complete, manifest-owned production policy."""

    try:
        manifest = reader.manifest().get("manifest", {})
    except (AttributeError, TypeError):
        return None
    generation = manifest.get("generation", {}) if isinstance(manifest, Mapping) else {}
    payload = generation.get("candidate_family_preflight") if isinstance(generation, Mapping) else None
    if not isinstance(payload, Mapping):
        return None
    return CandidateFamilyPreflightConfig.from_payload(payload)


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
        "metrics_revision": CANDIDATE_SUPPORT_METRICS_REVISION,
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
        "target_center_projected_count": projected_target_centers,
        "target_center_evaluated_count": total_target_centers,
    }
    if configured_families is None:
        metrics["zero_valid_family_state_rate"] = None
        metrics["zero_valid_family_count"] = None
    else:
        families = tuple(configured_families)
        if not families:
            metrics["zero_valid_family_state_rate"] = None
            metrics["zero_valid_family_count"] = None
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
            metrics["zero_valid_family_count"] = zero
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
            "view_jitter_evaluated_count": len(jitter),
            "view_jitter_bounded_count": len(bounded),
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
    """Validate canonical ZIP bytes without fabricating a temporary path."""

    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            names = sorted(archive.namelist())
            if names != [DATA_NAME, MANIFEST_NAME]:
                raise ValueError("invalid candidate benchmark archive members")
            manifest_bytes = archive.read(MANIFEST_NAME)
            parquet_bytes = archive.read(DATA_NAME)
    except zipfile.BadZipFile as exc:
        raise ValueError("invalid candidate benchmark archive") from exc
    return _read_bundle_payload(
        manifest_bytes,
        parquet_bytes,
        expected_binding=expected_binding,
        source=CandidateBenchmarkSource("archive-bytes", sha256_bytes(payload)),
    )


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
    manifest_bytes = manifest_path.read_bytes()
    parquet_bytes = parquet_path.read_bytes()
    return _read_bundle_payload(
        manifest_bytes,
        parquet_bytes,
        expected_binding=expected_binding,
        source=CandidateBenchmarkSource(
            "directory",
            sha256_bytes(
                canonical_json_bytes(
                    {
                        MANIFEST_NAME: sha256_bytes(manifest_bytes),
                        DATA_NAME: sha256_bytes(parquet_bytes),
                    }
                )
            ),
            root,
        ),
    )


def _read_bundle_payload(
    manifest_bytes: bytes,
    parquet_bytes: bytes,
    *,
    expected_binding: Mapping[str, str],
    source: CandidateBenchmarkSource,
) -> CandidateBenchmarkBundle:
    """Validate exact manifest and Parquet bytes from either supported source."""

    try:
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
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
    actual_hash = sha256_bytes(parquet_bytes)
    if manifest.get("data_sha256") != actual_hash:
        raise ValueError("hash-mismatched candidate benchmark bundle")
    try:
        frame = pd.read_parquet(io.BytesIO(parquet_bytes))
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
    return CandidateBenchmarkBundle(_freeze(manifest), records, source)


__all__ = [
    "SCHEMA_ID",
    "CANDIDATE_SUPPORT_METRICS_REVISION",
    "BINDING_KEYS",
    "CandidateBenchmark",
    "CandidateBenchmarkBundle",
    "CandidateBenchmarkSource",
    "CandidateFamilyPhaseAExpectation",
    "CandidateFamilyPhaseAEvidence",
    "CandidateFamilyPreflight",
    "CandidateFamilyPreflightConfig",
    "CandidateFamilyCounts",
    "CandidateFamilySelection",
    "CandidatePopulationCoverage",
    "CandidatePreflightBlocker",
    "CandidatePoint",
    "CandidateSupportFailure",
    "FlatGainOutcome",
    "candidate_support_metrics",
    "benchmark_from_sampling_result",
    "candidate_family_preflight_config_from_writer",
    "candidate_family_preflight_from_payload",
    "candidate_family_preflight_from_reader",
    "canonical_json_bytes",
    "circular_minimum_covering_span_deg",
    "read_bundle",
    "read_candidate_family_phase_a",
    "benchmarks_from_reader",
    "read_bundle_bytes",
    "reduce_candidate_records",
    "reduce_candidate_family_preflight",
    "select_candidate_family_shell",
    "serialize_bundle_bytes",
    "sha256_bytes",
    "target_relative_orbit_span_deg",
    "target_side_count_balance",
    "write_bundle",
    "write_candidate_family_phase_a",
    "benchmark_binding_from_manifest",
]
