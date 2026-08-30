"""Cache and read-model boundary for stored-rollout panels."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from functools import wraps
from pathlib import Path
from typing import Any, Literal, cast

import numpy as np
import streamlit as st

from ....configs import PathConfig
from ....dataset_topology import build_dataset_topology
from ....rollouts import RolloutZarrStoreReader
from ....rollouts.candidate_benchmark import (
    CandidateBenchmark,
    CandidateFamilyPreflight,
    benchmark_binding_from_reader,
    benchmarks_from_reader,
    candidate_family_preflight_from_reader,
    read_bundle_bytes,
    reduce_candidate_records,
    serialize_bundle_bytes,
)
from ....rollouts.inspection import (
    RolloutSuspiciousQueryConfig,
    build_effective_streamlit_trust,
    build_manifest_facts,
    build_promotion_evidence,
    build_schema_validation,
    candidate_audit_rows,
    candidate_flow_rows,
    candidate_population_evidence,
    comparable_policy_cohorts,
    discounted_rollout_return_rows,
    discover_rollout_store_paths,
    mask_combination_rows,
    oracle_headroom_evidence,
    paired_policy_comparison_rows,
    proposal_support_geometry,
    q_h_evidence_rows,
    reconstruction_endpoint_summary_rows,
    reconstruction_metric_summary_rows,
    rollout_header_summary,
    rollout_step_objective_rows,
    rollout_store_inventory_rows,
    rollout_trajectory_geometry,
    rollout_tree_summary_rows,
    selected_candidate_rank_rows,
    selected_depth_preview,
    selected_depth_summary_rows,
    store_invariant_rows,
    suspicious_rollout_rows,
    target_audit_rows,
    temporal_metric_summary_rows,
)
from ....rollouts.reporting import (
    RolloutCorpusSummary,
    build_rollout_corpus_summary,
    build_thesis_report_frames,
    serialize_thesis_report_bundle,
)

CORPUS_SUMMARY_STATE_KEY = "stored_rollouts_corpus_summary"
CANDIDATE_BENCHMARK_STATE_KEY = "candidate_benchmark_build_result"


@dataclass(frozen=True, slots=True)
class CandidateBenchmarkBuildResult:
    """Identity-bound result of one explicit candidate benchmark build.

    Attributes:
        store_identity: Replacement-sensitive selected-store identity.
        state_key: Optional factual state restriction applied to both products.
        candidate_limit: Positive display-only row limit.
        records: Bounded immutable records used to construct interactive figures.
        bundle_bytes: Complete deterministic benchmark export for ``state_key``;
            this population is never truncated by ``candidate_limit``.
    """

    store_identity: str
    state_key: str | None
    candidate_limit: int
    records: tuple[CandidateBenchmark, ...]
    bundle_bytes: bytes
    family_preflight: CandidateFamilyPreflight | None = None


@st.cache_resource(show_spinner=False)
def _cached_store_bundle_cached(
    store_path: str, *, store_identity: str = ""
) -> tuple[RolloutZarrStoreReader, Any, dict[str, Any]]:
    """Open and validate one replacement-sensitive rollout store identity."""

    reader = RolloutZarrStoreReader(Path(store_path))
    manifest_payload = build_manifest_facts(reader).payload
    schema = build_schema_validation(reader)
    promotion = build_promotion_evidence(reader, manifest_payload=manifest_payload)
    trust = build_effective_streamlit_trust(schema, promotion)
    return reader, trust, manifest_payload


@wraps(cast(Callable[..., Any], getattr(_cached_store_bundle_cached, "__wrapped__", _cached_store_bundle_cached)))
def _cached_store_bundle(store_path: str) -> tuple[RolloutZarrStoreReader, Any, dict[str, Any]]:
    """Open one store through a cache key that changes when its manifest is replaced."""

    identity = _store_projection_identity(store_path)
    reader, validation, manifest = _cached_store_bundle_cached(store_path, store_identity=identity)
    _assert_current_identity(store_path, identity)
    if reader.store_dir.resolve() != Path(store_path).expanduser().resolve():
        raise RuntimeError("stored-rollout reader resolved to a different canonical path")
    return reader, validation, manifest


@st.cache_data(show_spinner="Scanning rollout stores…", max_entries=8)
def _cached_inventory(cache_root: str) -> list[dict[str, Any]]:
    """Project the immutable rollout-store inventory once per cache root."""

    return rollout_store_inventory_rows(
        discover_rollout_store_paths(Path(cache_root)),
        validate=False,
    )


@st.cache_data(show_spinner="Loading rollout evidence…", max_entries=128)
def _cached_candidate_population_cached(store_path: str, store_identity: str, sample_size: int = 500) -> dict[str, Any]:
    """Build the complete candidate bundle once per immutable store identity."""

    reader, _, _ = _cached_store_bundle_cached(store_path, store_identity=store_identity)
    return candidate_population_evidence(reader, sample_size=sample_size)


@st.cache_data(show_spinner="Building bounded candidate benchmark display…", max_entries=32)
def _cached_candidate_benchmark_records_cached(
    store_path: str,
    state_key: str | None,
    candidate_limit: int,
    *,
    store_identity: str = "",
) -> tuple[dict[str, Any], ...]:
    """Cache serializable display records by identity, state, and row limit."""

    reader, _, _ = _cached_store_bundle_cached(store_path, store_identity=store_identity)
    records = benchmarks_from_reader(reader, state_key=state_key, candidate_limit=candidate_limit)
    return tuple(record.to_record() for record in records)


@st.cache_data(show_spinner="Building complete candidate benchmark export…", max_entries=32)
def _cached_candidate_benchmark_export_cached(
    store_path: str,
    state_key: str | None,
    *,
    store_identity: str = "",
) -> bytes:
    """Cache a complete export by validated identity and optional state only."""

    reader, _, manifest = _cached_store_bundle_cached(store_path, store_identity=store_identity)
    binding = benchmark_binding_from_reader(reader, manifest)
    records = benchmarks_from_reader(reader, state_key=state_key, candidate_limit=None)
    payload = serialize_bundle_bytes(records, provenance=binding)
    read_bundle_bytes(payload, expected_binding=binding)
    return payload


@st.cache_data(show_spinner="Evaluating complete candidate-family support…", max_entries=32)
def _cached_candidate_family_preflight_cached(
    store_path: str,
    *,
    store_identity: str = "",
) -> CandidateFamilyPreflight:
    """Cache the complete canonical family gate by immutable store identity."""

    reader, _, _ = _cached_store_bundle_cached(store_path, store_identity=store_identity)
    return candidate_family_preflight_from_reader(reader, require_known_applicability=True)


def _store_projection_identity(store_path: str) -> str:
    """Return a replacement-sensitive identity without reading Zarr payloads."""

    path = Path(store_path)
    try:
        digest = hashlib.sha256()
        for relative_name in ("_SUCCESS.json", "_owner.json", "manifest.json"):
            child = path / relative_name
            if not child.is_file():
                continue
            relative = relative_name.encode()
            stat = child.stat()
            digest.update(len(relative).to_bytes(8, "big"))
            digest.update(relative)
            digest.update(stat.st_size.to_bytes(8, "big"))
            digest.update(stat.st_mtime_ns.to_bytes(8, "big"))
            digest.update(stat.st_ctime_ns.to_bytes(8, "big"))
            digest.update(stat.st_ino.to_bytes(8, "big"))
        success = _read_json_mapping(path / "_SUCCESS.json")
        seal = success.get("rollout_store_content_sha256") if success is not None else None
        identity = f"store:{seal or 'unpromoted'}:{digest.hexdigest()}"
    except OSError:
        try:
            stat = path.stat()
            identity = f"store:{stat.st_size}:{stat.st_mtime_ns}"
        except OSError:
            identity = "missing"
    return identity


def _assert_current_identity(store_path: str, expected_identity: str) -> None:
    """Fail closed when a selected store changed during a projection."""

    current = _store_projection_identity(store_path)
    if current != expected_identity:
        raise RuntimeError("selected rollout store changed during inspection; reopen it before reading")


class StoredRolloutSession:
    """Fixed-generation handle for one selected rollout store.

    The selected directory entry is the identity boundary: callers may keep a
    handle across Streamlit reruns, but every named projection verifies that
    entry before reading.  This prevents a page-held reader from silently
    mixing evidence after an atomic store replacement.
    """

    def __init__(
        self,
        canonical_path: Path,
        store_identity: str,
        reader: Any,
        validation: Any,
        manifest_payload: dict[str, Any],
        inventory_row: dict[str, Any] | None = None,
        selected_path: Path | None = None,
    ) -> None:
        self.canonical_path = Path(canonical_path)
        self.store_identity = store_identity
        self._reader = reader
        self.validation = validation
        self.manifest_payload = manifest_payload
        self.inventory_row = inventory_row
        self._selected_path = selected_path or self.canonical_path

    @property
    def reader(self) -> Any:
        """Return the opened reader only while the selected generation is current."""

        self._assert_current_identity()
        return self._reader

    def _assert_current_identity(self) -> str:
        current = _store_projection_identity(self._selected_path.as_posix())
        if current != self.store_identity:
            raise RuntimeError(
                "selected rollout store changed after this session opened; reopen the store before projecting evidence"
            )
        return self.store_identity

    def _projection_path(self) -> str:
        """Check the selected entry and return the fixed canonical cache path."""

        self._assert_current_identity()
        return self.canonical_path.as_posix()

    def candidate_population(self, sample_size: int = 500) -> dict[str, Any]:
        store_path = self._projection_path()
        result = _cached_candidate_population_cached(store_path, self.store_identity, sample_size)
        self._assert_current_identity()
        return result

    def candidate_benchmark_records(
        self, *, state_key: str | None = None, candidate_limit: int | None = 500
    ) -> tuple[CandidateBenchmark, ...]:
        """Build immutable benchmark facts through the canonical inspection reader."""

        if candidate_limit is None:
            result = benchmarks_from_reader(self.reader, state_key=state_key, candidate_limit=None)
            self._assert_current_identity()
            return result
        rows = _cached_candidate_benchmark_records_cached(
            self._projection_path(),
            state_key,
            candidate_limit,
            store_identity=self.store_identity,
        )
        result = reduce_candidate_records(list(rows))
        self._assert_current_identity()
        return result

    def candidate_benchmark_export(self, *, state_key: str | None = None) -> bytes:
        """Export one deterministic benchmark bundle from validated facts."""

        payload = _cached_candidate_benchmark_export_cached(
            self._projection_path(),
            state_key,
            store_identity=self.store_identity,
        )
        self._assert_current_identity()
        return payload

    def build_candidate_benchmark(
        self,
        *,
        state_key: str | None = None,
        candidate_limit: int = 500,
    ) -> CandidateBenchmarkBuildResult:
        """Build bounded display facts and a complete export under one identity."""

        if candidate_limit <= 0:
            raise ValueError("candidate_limit must be positive")
        identity = self._assert_current_identity()
        records = self.candidate_benchmark_records(state_key=state_key, candidate_limit=candidate_limit)
        bundle_bytes = self.candidate_benchmark_export(state_key=state_key)
        self._assert_current_identity()
        family_preflight = _cached_candidate_family_preflight_cached(
            self._projection_path(),
            store_identity=identity,
        )
        self._assert_current_identity()
        return CandidateBenchmarkBuildResult(
            identity,
            state_key,
            candidate_limit,
            records,
            bundle_bytes,
            family_preflight,
        )

    def invariants(self) -> Any:
        return _cached_invariants(self._projection_path(), store_identity=self.store_identity)

    def header(self) -> Any:
        return _cached_header(self._projection_path(), store_identity=self.store_identity)

    def cohorts(self) -> Any:
        return _cached_cohorts(self._projection_path(), store_identity=self.store_identity)

    def paired(self) -> Any:
        return _cached_paired(self._projection_path(), store_identity=self.store_identity)

    def steps(self, rollout_row_id: int | None = None) -> Any:
        return _cached_steps(self._projection_path(), rollout_row_id=rollout_row_id, store_identity=self.store_identity)

    def reconstruction_metrics(self) -> Any:
        return _cached_reconstruction_metrics(self._projection_path(), store_identity=self.store_identity)

    def reconstruction_endpoints(self) -> Any:
        return _cached_reconstruction_endpoints(self._projection_path(), store_identity=self.store_identity)

    def discounted_returns(self) -> Any:
        return _cached_discounted_returns(self._projection_path(), store_identity=self.store_identity)

    def headroom(self) -> Any:
        return _cached_headroom(self._projection_path(), store_identity=self.store_identity)

    def temporal(self, metric: str, group_fields: tuple[str, ...] = ()) -> Any:
        return _cached_temporal(self._projection_path(), metric, group_fields, store_identity=self.store_identity)

    def candidate_flow(
        self,
        policies: tuple[str, ...] | None = None,
        step_indices: tuple[int, ...] | None = None,
    ) -> Any:
        return _cached_candidate_flow(
            self._projection_path(), policies, step_indices, store_identity=self.store_identity
        )

    def ranks(
        self,
        policies: tuple[str, ...] | None = None,
        step_indices: tuple[int, ...] | None = None,
    ) -> Any:
        return _cached_ranks(self._projection_path(), policies, step_indices, store_identity=self.store_identity)

    def targets(self) -> Any:
        return _cached_targets(self._projection_path(), store_identity=self.store_identity)

    def masks(self) -> Any:
        return _cached_masks(self._projection_path(), store_identity=self.store_identity)

    def candidates(
        self,
        rollout_row_id: int | None = None,
        step_row_id: int | None = None,
        limit: int | None = None,
    ) -> Any:
        return _cached_candidates(
            self._projection_path(), rollout_row_id, step_row_id, limit, store_identity=self.store_identity
        )

    def q_h(self, deep_count: bool = False) -> Any:
        return _cached_q_h(self._projection_path(), deep_count, store_identity=self.store_identity)

    def q_h_progressive(
        self,
        *,
        chunk_size: int,
        state_row_limit: int | None,
        progress_callback: Callable[[int, int], bool] | None,
    ) -> Any:
        """Read progressive Q_H evidence while guarding the fixed generation."""

        self._assert_current_identity()
        result = q_h_evidence_rows(
            self._reader,
            deep_count=True,
            chunk_size=chunk_size,
            state_row_limit=state_row_limit,
            progress_callback=progress_callback,
            validation_result=self.validation,
        )
        self._assert_current_identity()
        return result

    def selected_depth_preview(self, step_row_id: int) -> Any:
        """Preview one selected-depth artifact while guarding the fixed generation."""

        self._assert_current_identity()
        result = selected_depth_preview(self._reader, step_row_id=step_row_id)
        self._assert_current_identity()
        return result

    def rollout_ids(self) -> list[int]:
        """Return persisted rollout ids from this fixed-generation reader."""

        self._assert_current_identity()
        result = np.asarray(self._reader.array("rollouts/rollout_row_id"), dtype=np.int64).reshape(-1).tolist()
        self._assert_current_identity()
        return [int(value) for value in result]

    def tree(self) -> Any:
        return _cached_tree(self._projection_path(), store_identity=self.store_identity)

    def root_geometry(self, limit: int | None = None) -> Any:
        return _cached_root_geometry(self._projection_path(), limit, store_identity=self.store_identity)

    def proposal_geometry(self, limit: int | None = None) -> Any:
        """Return bounded candidate points plus their normalized pose frames."""

        return _cached_proposal_geometry(self._projection_path(), limit, store_identity=self.store_identity)

    def trajectory_geometry(self) -> Any:
        """Return factual root and selected-pose trajectory geometry."""

        return _cached_trajectory_geometry(self._projection_path(), store_identity=self.store_identity)

    def depth_summary(self, rollout_row_id: int | None = None, limit: int | None = None) -> Any:
        return _cached_depth_summary(self._projection_path(), rollout_row_id, limit, store_identity=self.store_identity)

    def failures(
        self, min_valid_candidates: int, dominant_invalid_fraction: float, max_step_distance_m: float
    ) -> list[dict[str, Any]]:
        return _cached_failures(
            self._projection_path(),
            min_valid_candidates,
            dominant_invalid_fraction,
            max_step_distance_m,
            store_identity=self.store_identity,
        )

    def topology(
        self,
        vin_store_dirs: tuple[str, ...],
        paths: PathConfig,
        selected_source_row_id: int | None = None,
    ) -> Any:
        return _cached_topology(
            self._projection_path(),
            vin_store_dirs,
            paths,
            selected_source_row_id,
            store_identity=self.store_identity,
        )

    def evidence_bundle(self, evidence_status: str) -> bytes:
        identity = self._assert_current_identity()
        bundle = _cached_evidence_bundle(self._projection_path(), evidence_status, store_identity=self.store_identity)
        _assert_current_identity(self._selected_path.as_posix(), identity)
        return bundle


def open_stored_rollout_session(path: str | Path, inventory_row: dict[str, Any] | None = None) -> StoredRolloutSession:
    """Open a metadata-bound session and reject a replacement during opening."""

    selected_path = Path(path).expanduser().absolute()
    canonical_path = selected_path.resolve()
    identity = _store_projection_identity(selected_path.as_posix())
    reader, validation, manifest_payload = _cached_store_bundle_cached(
        canonical_path.as_posix(), store_identity=identity
    )
    try:
        identity_unchanged = _store_projection_identity(selected_path.as_posix()) == identity
        target_unchanged = selected_path.resolve() == canonical_path
    except OSError as error:
        raise RuntimeError("selected rollout store changed while opening; reopen the store") from error
    if not identity_unchanged or not target_unchanged:
        raise RuntimeError("selected rollout store changed while opening; reopen the store")
    reader_store_dir = getattr(reader, "store_dir", canonical_path)
    if Path(reader_store_dir).resolve() != canonical_path:
        raise RuntimeError("selected rollout reader resolved to a different canonical path")
    return StoredRolloutSession(
        canonical_path,
        identity,
        reader,
        validation,
        manifest_payload,
        inventory_row,
        selected_path,
    )


def _identity_cache(function: Callable[..., Any]) -> Callable[..., Any]:
    """Cache one named projection against fixed metadata identity."""

    @st.cache_data(show_spinner="Loading rollout evidence…", max_entries=128)
    def cached(
        store_path: str,
        args: tuple[Any, ...],
        kwargs: tuple[tuple[str, Any], ...],
        identity: str,
        owner: str,
    ) -> Any:
        del identity, owner
        return function(store_path, *args, **dict(kwargs))

    # Streamlit derives the cache key from the wrapped callable's qualified
    # name.  Every nested ``cached`` function otherwise shares the same name,
    # allowing unrelated projections (for example header and steps) to reuse
    # one another's result.  Keep the small decorator seam, but give each
    # named owner a stable cache identity.
    cached_dynamic: Any = cached
    cached_dynamic.__name__ = f"{function.__name__}_cached"
    cached_dynamic.__qualname__ = f"{function.__qualname__}_cached"

    @wraps(function)
    def wrapper(store_path: str, *args: Any, **kwargs: Any) -> Any:
        supplied_identity = kwargs.pop("store_identity", None)
        identity = supplied_identity or _store_projection_identity(store_path)
        _assert_current_identity(store_path, identity)
        result = cached(
            store_path,
            args,
            tuple(sorted(kwargs.items())),
            identity,
            function.__qualname__,
        )
        _assert_current_identity(store_path, identity)
        return result

    wrapper_dynamic: Any = wrapper
    wrapper_dynamic.clear = cached_dynamic.clear
    return cast(Callable[..., Any], wrapper_dynamic)


@_identity_cache
def _cached_invariants(store_path: str) -> Any:
    reader, _, manifest = _cached_store_bundle(store_path)
    return store_invariant_rows(reader, manifest_payload=manifest)


@_identity_cache
def _cached_header(store_path: str) -> Any:
    reader, _, manifest = _cached_store_bundle(store_path)
    return rollout_header_summary(reader, manifest_payload=manifest)


@_identity_cache
def _cached_cohorts(store_path: str) -> Any:
    reader, _, _ = _cached_store_bundle(store_path)
    return comparable_policy_cohorts(reader)


@_identity_cache
def _cached_paired(store_path: str) -> Any:
    reader, _, _ = _cached_store_bundle(store_path)
    return paired_policy_comparison_rows(reader)


@_identity_cache
def _cached_steps(store_path: str, rollout_row_id: int | None = None) -> Any:
    reader, _, _ = _cached_store_bundle(store_path)
    return rollout_step_objective_rows(reader, rollout_row_id=rollout_row_id)


@_identity_cache
def _cached_reconstruction_metrics(store_path: str) -> Any:
    reader, _, _ = _cached_store_bundle(store_path)
    return reconstruction_metric_summary_rows(reader)


@_identity_cache
def _cached_reconstruction_endpoints(store_path: str) -> Any:
    reader, _, _ = _cached_store_bundle(store_path)
    return reconstruction_endpoint_summary_rows(reader)


@_identity_cache
def _cached_discounted_returns(store_path: str) -> Any:
    reader, _, manifest = _cached_store_bundle(store_path)
    attrs = manifest.get("root_attrs", {})
    attrs = attrs if isinstance(attrs, dict) else {}
    return discounted_rollout_return_rows(
        reader, return_semantics=attrs.get("return_semantics"), discount_gamma=attrs.get("discount_gamma")
    )


@_identity_cache
def _cached_headroom(store_path: str) -> Any:
    reader, _, _ = _cached_store_bundle(store_path)
    return oracle_headroom_evidence(reader)


@_identity_cache
def _cached_candidate_flow(
    store_path: str, policies: tuple[str, ...] | None = None, step_indices: tuple[int, ...] | None = None
) -> Any:
    reader, _, _ = _cached_store_bundle(store_path)
    return candidate_flow_rows(reader, policies=policies, step_indices=step_indices)


@_identity_cache
def _cached_ranks(
    store_path: str, policies: tuple[str, ...] | None = None, step_indices: tuple[int, ...] | None = None
) -> Any:
    reader, _, _ = _cached_store_bundle(store_path)
    return selected_candidate_rank_rows(reader, policies=policies, step_indices=step_indices)


@_identity_cache
def _cached_temporal(store_path: str, metric: str, group_fields: tuple[str, ...] = ()) -> Any:
    reader, _, _ = _cached_store_bundle(store_path)
    return temporal_metric_summary_rows(reader, metric=metric, group_fields=group_fields)


@_identity_cache
def _cached_targets(store_path: str) -> Any:
    reader, _, _ = _cached_store_bundle(store_path)
    return target_audit_rows(reader)


@_identity_cache
def _cached_masks(store_path: str) -> Any:
    reader, _, _ = _cached_store_bundle(store_path)
    return mask_combination_rows(reader)


@_identity_cache
def _cached_candidates(
    store_path: str, rollout_row_id: int | None = None, step_row_id: int | None = None, limit: int | None = None
) -> list[dict[str, Any]]:
    reader, _, _ = _cached_store_bundle(store_path)
    rows: list[dict[str, Any]] = []
    candidate_audit_rows(
        reader, rollout_row_id=rollout_row_id, step_row_id=step_row_id, limit=limit, row_callback=rows.append
    )
    return rows


@_identity_cache
def _cached_q_h(store_path: str, deep_count: bool = False) -> Any:
    reader, validation, _ = _cached_store_bundle(store_path)
    return q_h_evidence_rows(reader, deep_count=deep_count, validation_result=validation)


@_identity_cache
def _cached_tree(store_path: str) -> Any:
    reader, _, _ = _cached_store_bundle(store_path)
    return rollout_tree_summary_rows(reader)


@_identity_cache
def _cached_root_geometry(store_path: str, limit: int | None = None) -> Any:
    reader, _, _ = _cached_store_bundle(store_path)
    rows = [asdict(point) for point in proposal_support_geometry(reader).points]
    return rows if limit is None else rows[:limit]


@_identity_cache
def _cached_proposal_geometry(store_path: str, limit: int | None = None) -> Any:
    reader, _, _ = _cached_store_bundle(store_path)
    projection = proposal_support_geometry(reader, max_candidates=50_000 if limit is None else limit)
    return {
        "points": [asdict(point) for point in projection.points],
        "frames": [asdict(frame) for frame in projection.frames],
        "issues": [asdict(issue) for issue in projection.issues],
        "truncated": projection.truncated,
    }


@_identity_cache
def _cached_trajectory_geometry(store_path: str) -> Any:
    reader, _, _ = _cached_store_bundle(store_path)
    projection = rollout_trajectory_geometry(reader)
    return {
        "points": [asdict(point) for point in projection.points],
        "frames": [asdict(frame) for frame in projection.frames],
        "issues": [asdict(issue) for issue in projection.issues],
        "truncated": projection.truncated,
    }


@_identity_cache
def _cached_depth_summary(store_path: str, rollout_row_id: int | None = None, limit: int | None = None) -> Any:
    reader, _, _ = _cached_store_bundle(store_path)
    return selected_depth_summary_rows(reader, rollout_row_id=rollout_row_id, limit=limit)


def _read_json_mapping(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


@st.cache_resource(show_spinner="Resolving dataset topology…", max_entries=16)
def _cached_topology_cached(
    store_path: str,
    vin_store_dirs: tuple[str, ...],
    paths: PathConfig,
    selected_source_row_id: int | None = None,
    *,
    store_identity: str = "",
) -> Any:
    """Resolve one replacement-sensitive cross-store topology and reuse its Rich tree."""

    return build_dataset_topology(
        rollout_store_dir=Path(store_path),
        vin_store_dirs=[Path(value) for value in vin_store_dirs],
        path_config=paths,
        selected_source_row_id=selected_source_row_id,
    )


@wraps(cast(Callable[..., Any], getattr(_cached_topology_cached, "__wrapped__", _cached_topology_cached)))
def _cached_topology(
    store_path: str,
    vin_store_dirs: tuple[str, ...],
    paths: PathConfig,
    selected_source_row_id: int | None = None,
    *,
    store_identity: str | None = None,
) -> Any:
    """Resolve topology through a cache key bound to the selected store identity."""

    identity = store_identity or _store_projection_identity(store_path)
    _assert_current_identity(store_path, identity)
    result = _cached_topology_cached(
        store_path,
        vin_store_dirs,
        paths,
        selected_source_row_id,
        store_identity=identity,
    )
    _assert_current_identity(store_path, identity)
    return result


@st.cache_data(show_spinner="Evaluating failure predicates…", max_entries=32)
def _cached_failures_cached(
    store_path: str,
    min_valid_candidates: int,
    dominant_invalid_fraction: float,
    max_step_distance_m: float,
    *,
    store_identity: str = "",
) -> list[dict[str, Any]]:
    """Cache failure triage for one replacement-sensitive store and threshold tuple."""

    reader, _, _ = _cached_store_bundle(store_path)
    config = RolloutSuspiciousQueryConfig(
        min_valid_candidates=min_valid_candidates,
        dominant_invalid_fraction=dominant_invalid_fraction,
        max_step_distance_m=max_step_distance_m,
    )
    return suspicious_rollout_rows(reader, config=config)


@wraps(cast(Callable[..., Any], getattr(_cached_failures_cached, "__wrapped__", _cached_failures_cached)))
def _cached_failures(
    store_path: str,
    min_valid_candidates: int,
    dominant_invalid_fraction: float,
    max_step_distance_m: float,
    *,
    store_identity: str | None = None,
) -> list[dict[str, Any]]:
    """Evaluate failure triage through a cache key bound to the selected store identity."""

    identity = store_identity or _store_projection_identity(store_path)
    _assert_current_identity(store_path, identity)
    result = _cached_failures_cached(
        store_path,
        min_valid_candidates,
        dominant_invalid_fraction,
        max_step_distance_m,
        store_identity=identity,
    )
    _assert_current_identity(store_path, identity)
    return result


@st.cache_data(show_spinner="Building deterministic evidence bundle…", max_entries=16)
def _cached_evidence_bundle_cached(store_path: str, evidence_status: str, *, store_identity: str = "") -> bytes:
    """Build one deterministic bundle for a replacement-sensitive store identity."""

    if evidence_status not in {"pilot", "confirmatory"}:
        raise ValueError(f"Unsupported evidence status: {evidence_status!r}")
    status = cast(Literal["pilot", "confirmatory"], evidence_status)
    frames = build_thesis_report_frames([Path(store_path)], evidence_status=status)
    return serialize_thesis_report_bundle(frames)


@wraps(
    cast(
        Callable[..., Any],
        getattr(_cached_evidence_bundle_cached, "__wrapped__", _cached_evidence_bundle_cached),
    )
)
def _cached_evidence_bundle(store_path: str, evidence_status: str, *, store_identity: str | None = None) -> bytes:
    """Build a report bundle through the replacement-sensitive store cache key."""

    identity = store_identity or _store_projection_identity(store_path)
    _assert_current_identity(store_path, identity)
    result = _cached_evidence_bundle_cached(
        store_path,
        evidence_status,
        store_identity=identity,
    )
    _assert_current_identity(store_path, identity)
    return result


def _clear_stored_rollout_caches() -> None:
    """Clear only the inspector caches after stores are created or replaced."""

    _cached_inventory.clear()
    for projection in (
        _cached_invariants,
        _cached_header,
        _cached_cohorts,
        _cached_paired,
        _cached_steps,
        _cached_reconstruction_metrics,
        _cached_reconstruction_endpoints,
        _cached_discounted_returns,
        _cached_headroom,
        _cached_candidate_flow,
        _cached_ranks,
        _cached_temporal,
        _cached_targets,
        _cached_masks,
        _cached_candidates,
        _cached_candidate_population_cached,
        _cached_candidate_benchmark_records_cached,
        _cached_candidate_benchmark_export_cached,
        _cached_candidate_family_preflight_cached,
        _cached_q_h,
        _cached_tree,
        _cached_root_geometry,
        _cached_depth_summary,
        _cached_proposal_geometry,
        _cached_trajectory_geometry,
    ):
        clear: Any = getattr(projection, "clear", None)
        if callable(clear):
            clear()
    _cached_topology_cached.clear()
    _cached_failures_cached.clear()
    _cached_evidence_bundle_cached.clear()
    _cached_store_bundle_cached.clear()
    _cached_corpus_summary.clear()
    st.session_state.pop(CORPUS_SUMMARY_STATE_KEY, None)
    st.session_state.pop(CANDIDATE_BENCHMARK_STATE_KEY, None)


def clear_rollout_page_caches() -> None:
    """Clear only stored-rollout caches and page-local retained state."""

    _clear_stored_rollout_caches()


@st.cache_data(show_spinner="Aggregating validated rollout stores…", max_entries=8)
def _cached_corpus_summary(
    store_paths: tuple[str, ...],
    store_identities: tuple[str, ...],
) -> RolloutCorpusSummary:
    """Build an explicit corpus summary bound to ordered store identities."""

    if len(store_paths) != len(store_identities):
        raise ValueError("corpus store paths and identities must have equal length")
    for path, identity in zip(store_paths, store_identities, strict=True):
        _assert_current_identity(path, identity)
    result = build_rollout_corpus_summary(Path(path) for path in store_paths)
    for path, identity in zip(store_paths, store_identities, strict=True):
        _assert_current_identity(path, identity)
    return result
