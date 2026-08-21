"""Dispatch-level laziness tests for stored-rollout UI projections."""

# ruff: noqa: S101, SLF001

from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

import pytest
import zarr

from aria_nbv.app.panels import _stored_rollout_session as session
from aria_nbv.app.panels import _stored_rollouts_page as page
from aria_nbv.configs import PathConfig
from aria_nbv.oracle.pipelines.shards import plan_rollout_shards, run_rollout_shard
from aria_nbv.rollouts.zarr_store import RolloutZarrStoreReader, write_rollout_zarr_store
from tests.rollout_fixtures import build_rollout_records
from tests.rollouts.test_dataset_writer import _fake_record, _FakeRolloutConfig


@pytest.mark.parametrize(
    ("projection", "owner_name", "kwargs"),
    [
        ("invariants", "_cached_invariants_cached", {}),
        ("cohorts", "_cached_cohorts_cached", {}),
        ("paired", "_cached_paired_cached", {}),
        ("steps", "_cached_steps_cached", {}),
        ("temporal", "_cached_temporal_cached", {"metric": "selected_target_rri"}),
        ("candidate_flow", "_cached_candidate_flow_cached", {}),
        ("ranks", "_cached_ranks_cached", {}),
        ("targets", "_cached_targets_cached", {}),
        ("masks", "_cached_masks_cached", {}),
        ("tree", "_cached_tree_cached", {}),
        ("root_geometry", "_cached_root_geometry_cached", {}),
        ("depth_summary", "_cached_depth_summary_cached", {}),
    ],
)
def test_lightweight_dispatch_does_not_materialize_candidate_audit(
    monkeypatch: pytest.MonkeyPatch,
    projection: str,
    owner_name: str,
    kwargs: dict[str, object],
) -> None:
    """Unopened normalized-candidate branches must have exactly zero reads."""

    reader = object()
    expected = [{"projection": projection}]
    monkeypatch.setattr(session, "_cached_store_bundle_cached", lambda _path, **_kwargs: (reader, object(), {}))
    monkeypatch.setattr(
        session,
        "candidate_audit_rows",
        lambda *_args, **_kwargs: pytest.fail(f"{projection} materialized candidate_audit_rows"),
    )
    monkeypatch.setattr(session, owner_name, _owner_stub(expected))

    result = getattr(session, owner_name)("/fixture.zarr", store_identity="fixture", **kwargs)

    assert result == expected


def test_candidate_group_materializes_one_candidate_projection_and_reuses_its_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The explicit group branch may read candidates once and must reuse them."""

    reader = object()
    candidate_rows = [{"candidate_row_id": 7}, {"candidate_row_id": 11}]
    recursive_calls: list[tuple[str, int | None]] = []
    summary_calls: list[tuple[object, str, object]] = []
    monkeypatch.setattr(session, "_cached_store_bundle_cached", lambda _path, **_kwargs: (reader, object(), {}))

    def candidate_projection(_store_path: str, *, limit: int | None = None, **_kwargs: object) -> list[dict[str, int]]:
        recursive_calls.append(("candidates", limit))
        return candidate_rows

    def summarize(
        source: object,
        *,
        group_by: str,
        audit_rows: object,
    ) -> list[dict[str, object]]:
        summary_calls.append((source, group_by, audit_rows))
        return [{"family": "fixture", "candidate_count": len(candidate_rows)}]

    monkeypatch.setattr(session, "_cached_candidates_cached", candidate_projection)
    monkeypatch.setattr(session, "candidate_group_summary_rows", summarize)

    result = session._cached_candidate_group_cached.__wrapped__(
        "/fixture.zarr", group_by="mixture", limit=25, store_identity="fixture"
    )

    assert recursive_calls == [("candidates", 25)]
    assert summary_calls == [(reader, "mixture", candidate_rows)]
    assert result == [{"family": "fixture", "candidate_count": 2}]


def test_invalid_store_withholds_scientific_header_projection(monkeypatch: pytest.MonkeyPatch) -> None:
    """Invalid or tampered stores keep diagnostics but never render coverage projections."""

    messages: list[str] = []
    monkeypatch.setattr(page.st, "info", messages.append)
    monkeypatch.setattr(page, "_render_store_header_summary", lambda _path: pytest.fail("header was rendered"))

    page._render_validated_store_header("/tampered.zarr", validation_ok=False)

    assert messages == ["Coverage and physical-cost projections are withheld until store validation succeeds."]


def test_manifest_read_failure_blocks_session_without_synthetic_manifest(monkeypatch: pytest.MonkeyPatch) -> None:
    """A manifest failure remains visible and cannot become a trusted empty payload."""

    class Reader:
        def manifest(self) -> dict[str, object]:
            raise RuntimeError("manifest read failed")

    monkeypatch.setattr(session, "RolloutZarrStoreReader", lambda _path: Reader())
    monkeypatch.setattr(session, "build_schema_validation", lambda _reader: object())

    with pytest.raises(RuntimeError, match="manifest read failed"):
        session._cached_store_bundle_cached.__wrapped__("/unpromoted.zarr", store_identity="fixture")


def test_projection_dispatch_binds_manifest_identity_for_same_path_replacement(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The validated page boundary forwards a stable, replacement-sensitive cache identity."""

    store = tmp_path / "replacement.zarr"
    store.mkdir()
    manifest = store / "manifest.json"
    manifest.write_text('{"generation": "first"}', encoding="utf-8")
    identities: list[str] = []

    def cached_header(_path: str, *, store_identity: str, **_kwargs: object) -> object:
        identities.append(store_identity)
        return []

    monkeypatch.setattr(session, "_cached_header_cached", cached_header)
    session._cached_header_cached(store.as_posix(), store_identity=session._store_projection_identity(store))
    session._cached_header_cached(store.as_posix(), store_identity=session._store_projection_identity(store))
    manifest.write_text('{"generation": "second"}', encoding="utf-8")
    session._cached_header_cached(store.as_posix(), store_identity=session._store_projection_identity(store))

    assert identities[0] == identities[1]
    assert identities[2] != identities[0]


def test_store_cache_identity_changes_for_array_mutation_with_same_manifest_stat(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    result = write_rollout_zarr_store(
        tmp_path / "array-mutation.zarr",
        build_rollout_records(horizon=1, num_samples=6, seed=901)[:1],
    )
    manifest = result.store_dir / "manifest.json"
    manifest_stat = manifest.stat()
    identities: list[str] = []

    def cached_header(_path: str, *, store_identity: str, **_kwargs: object) -> object:
        identities.append(store_identity)
        return []

    monkeypatch.setattr(session, "_cached_header_cached", cached_header)
    original_read_bytes = Path.read_bytes
    monkeypatch.setattr(Path, "read_bytes", lambda _self: pytest.fail("cache identity must not read payload bytes"))
    session._cached_header_cached(
        result.store_dir.as_posix(), store_identity=session._store_projection_identity(result.store_dir)
    )
    monkeypatch.setattr(Path, "read_bytes", original_read_bytes)
    root = zarr.open_group(result.store_dir, mode="a")
    candidate_ids = root["candidates/candidate_row_id"]
    candidate_ids[0] = int(candidate_ids[0]) + 1
    os.utime(manifest, ns=(manifest_stat.st_atime_ns, manifest_stat.st_mtime_ns))
    monkeypatch.setattr(Path, "read_bytes", lambda _self: pytest.fail("cache identity must not read payload bytes"))
    session._cached_header_cached(
        result.store_dir.as_posix(), store_identity=session._store_projection_identity(result.store_dir)
    )

    assert identities[1] != identities[0]


def test_promoted_store_rejects_content_newer_than_completion_evidence(tmp_path: Path) -> None:
    result = write_rollout_zarr_store(
        tmp_path / "promoted.zarr",
        build_rollout_records(horizon=1, num_samples=6, seed=905)[:1],
    )
    seal = "a" * 64
    (result.store_dir / "_owner.json").write_text(json.dumps({"rollout_store_content_sha256": seal}), encoding="utf-8")
    (result.store_dir / "_SUCCESS.json").write_text(
        json.dumps({"rollout_store_content_sha256": seal}), encoding="utf-8"
    )
    (result.store_dir / "post-promotion.txt").write_text("tampered", encoding="utf-8")

    _, validation, _ = session._cached_store_bundle_cached.__wrapped__(
        result.store_dir.as_posix(), store_identity="changed"
    )

    assert not validation.ok
    assert "promoted rollout" in "; ".join(validation.errors)


def test_promoted_store_cache_and_report_reject_same_size_restored_mtime_tamper(tmp_path: Path) -> None:
    config = _FakeRolloutConfig([_fake_record(0)], store_dir=tmp_path)
    entry = plan_rollout_shards(config, rows_per_shard=1)[0]
    result = run_rollout_shard(
        config,
        shard_entry=entry,
        output_tmp=tmp_path / "unit.tmp",
        output_final=tmp_path / "unit",
    )
    store_path = result.final_dir.as_posix()
    mtimes = {path: path.stat().st_mtime_ns for path in result.final_dir.rglob("*") if path.is_file()}
    first_identity = session._store_projection_identity(store_path)
    _, first_validation, _ = session._cached_store_bundle_cached(store_path, store_identity=first_identity)
    assert first_validation.ok

    root = zarr.open_group(result.final_dir, mode="a")
    clearance = root["candidate_diagnostics/path_min_clearance_m"]
    clearance[0] = float(clearance[0]) + 0.125
    for path, mtime_ns in mtimes.items():
        os.utime(path, ns=(path.stat().st_atime_ns, mtime_ns))

    second_identity = session._store_projection_identity(store_path)
    _, second_validation, _ = session._cached_store_bundle_cached(store_path, store_identity=second_identity)

    assert second_identity != first_identity
    assert not second_validation.ok
    assert "canonical store content" in "; ".join(second_validation.errors)
    with pytest.raises(ValueError, match="promotion validation"):
        session.build_thesis_report_frames([result.final_dir], evidence_status="pilot")


def test_q_h_render_wires_progress_and_chunk_boundary_cancellation(monkeypatch: pytest.MonkeyPatch) -> None:
    class Progress:
        def __init__(self) -> None:
            self.calls: list[tuple[float, str]] = []

        def progress(self, fraction: float, *, text: str) -> None:
            self.calls.append((fraction, text))

    class Status:
        def __init__(self) -> None:
            self.captions: list[str] = []

        def caption(self, value: str) -> None:
            self.captions.append(value)

    progress = Progress()
    status = Status()
    session_state: dict[str, object] = {}
    monkeypatch.setattr(page.st, "session_state", session_state)
    monkeypatch.setattr(page.st, "markdown", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(page.st, "toggle", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        page.st,
        "number_input",
        lambda label, **_kwargs: 2 if "chunk" in label else 0,
    )
    monkeypatch.setattr(page.st, "checkbox", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(page.st, "progress", lambda *_args, **_kwargs: progress)
    monkeypatch.setattr(page.st, "empty", lambda: status)
    monkeypatch.setattr(page.st, "dataframe", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(page, "_download_frame", lambda *_args, **_kwargs: None)
    stored_session = session.StoredRolloutSession(
        Path("/fixture.zarr"), "fixture", object(), SimpleNamespace(ok=True), {}, None
    )
    callback_results: list[bool] = []

    def q_h(_reader, **kwargs):
        callback = kwargs["progress_callback"]
        callback_results.append(callback(2, 4))
        return [
            {
                "available": True,
                "deep_count": True,
                "count_reason": "cancelled during bounded current-store mask projection",
                "truncated": True,
            }
        ]

    monkeypatch.setattr(session, "q_h_evidence_rows", q_h)
    page._render_q_h_evidence(stored_session)

    assert callback_results == [False]
    assert progress.calls == [(0.5, "Q_H count: 2/4 state rows")]
    assert status.captions[-1] == "Q_H count stopped at a chunk boundary."


def test_all_store_backed_caches_follow_atomic_same_path_replacement(tmp_path: Path) -> None:
    """Readers, projections, and requested report bundles must not retain replaced-store evidence."""

    first = write_rollout_zarr_store(
        tmp_path / "first.zarr",
        build_rollout_records(horizon=2, num_samples=6, seed=101)[:1],
    )
    second = write_rollout_zarr_store(
        tmp_path / "second.zarr",
        build_rollout_records(horizon=2, num_samples=6, seed=102)[:2],
    )
    selected = tmp_path / "selected.zarr"
    selected.symlink_to(first.store_dir, target_is_directory=True)

    path = selected.as_posix()
    first_identity = session._store_projection_identity(path)
    first_reader, first_validation, first_manifest = session._cached_store_bundle_cached(
        path, store_identity=first_identity
    )
    first_steps = session._cached_steps_cached(path, store_identity=session._store_projection_identity(path))
    first_bundle = session._cached_evidence_bundle_cached(path, "pilot", store_identity=first_identity)
    assert first_validation.ok
    assert first_reader.store_dir == selected.resolve()
    assert first_manifest == first_reader.manifest()
    assert len(first_steps) > 0

    replacement = tmp_path / "replacement-link.zarr"
    replacement.symlink_to(second.store_dir, target_is_directory=True)
    replacement.replace(selected)

    second_identity = session._store_projection_identity(path)
    second_reader, second_validation, second_manifest = session._cached_store_bundle_cached(
        path, store_identity=second_identity
    )
    second_steps = session._cached_steps_cached(path, store_identity=second_identity)
    second_bundle = session._cached_evidence_bundle_cached(path, "pilot", store_identity=second_identity)
    assert second_validation.ok
    assert second_reader.store_dir == selected.resolve()
    assert second_manifest == second_reader.manifest()
    assert len(second_steps) > len(first_steps)
    assert second_manifest != first_manifest
    assert second_bundle != first_bundle


def test_open_session_binds_real_projections_until_next_open(tmp_path: Path) -> None:
    """An opened handle stays on its generation while a later open sees the swap."""

    first = write_rollout_zarr_store(
        tmp_path / "session-first.zarr",
        build_rollout_records(horizon=2, num_samples=6, seed=101)[:1],
    )
    second = write_rollout_zarr_store(
        tmp_path / "session-second.zarr",
        build_rollout_records(horizon=2, num_samples=6, seed=102)[:2],
    )
    selected = tmp_path / "session-selected.zarr"
    selected.symlink_to(first.store_dir, target_is_directory=True)
    session.clear_stored_rollout_caches()

    old = session.open_stored_rollout_session(selected)
    old_header = old.header()
    old_steps = old.steps()
    old_population = old.candidate_population()
    old_failures = old.failures(100, 0.0, 1.0)

    replacement = tmp_path / "session-replacement-link.zarr"
    replacement.symlink_to(second.store_dir, target_is_directory=True)
    replacement.replace(selected)

    assert old.header() == old_header
    assert old.steps() == old_steps
    assert old.candidate_population() == old_population
    assert old.failures(100, 0.0, 1.0) == old_failures

    new = session.open_stored_rollout_session(selected)
    assert new.store_identity != old.store_identity
    assert new.header()["rollouts"] > old_header["rollouts"]
    assert len(new.steps()) > len(old_steps)
    assert new.candidate_population()["population_count"] > old_population["population_count"]
    assert len(new.failures(100, 0.0, 1.0)) > len(old_failures)


def test_topology_and_failure_cache_owners_recompute_after_atomic_swap(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Topology and failure owners recompute replacement data, not just their dispatch keys."""

    first = write_rollout_zarr_store(
        tmp_path / "topology-first.zarr",
        build_rollout_records(horizon=2, num_samples=6, seed=111)[:1],
    )
    second = write_rollout_zarr_store(
        tmp_path / "topology-second.zarr",
        build_rollout_records(horizon=2, num_samples=6, seed=112)[:2],
    )
    selected = tmp_path / "selected.zarr"
    selected.symlink_to(first.store_dir, target_is_directory=True)
    topology_calls: list[str] = []
    failure_calls: list[str] = []

    def topology(*, rollout_store_dir: Path, **_kwargs: object) -> dict[str, str]:
        path = rollout_store_dir.as_posix()
        manifest = session._cached_store_bundle_cached(path, store_identity=session._store_projection_identity(path))[2]
        marker = json.dumps(manifest, sort_keys=True)
        topology_calls.append(marker)
        return {"manifest": marker}

    def failures(reader: object, *, config: object) -> list[dict[str, str]]:
        path = reader.store_dir.as_posix()  # type: ignore[attr-defined]
        marker = session._cached_store_bundle_cached(path, store_identity=session._store_projection_identity(path))[2]
        value = json.dumps(marker, sort_keys=True)
        failure_calls.append(value)
        return [{"manifest": value}]

    monkeypatch.setattr(session, "build_dataset_topology", topology)
    monkeypatch.setattr(session, "suspicious_rollout_rows", failures)
    path = selected.as_posix()
    first_identity = session._store_projection_identity(path)
    topology_first = session._cached_topology_cached(path, (), None, store_identity=first_identity)
    failure_first = session._cached_failures_cached(path, 1, 0.5, 1.0, store_identity=first_identity)

    replacement = tmp_path / "replacement-link.zarr"
    replacement.symlink_to(second.store_dir, target_is_directory=True)
    replacement.replace(selected)

    second_identity = session._store_projection_identity(path)
    topology_second = session._cached_topology_cached(path, (), None, store_identity=second_identity)
    failure_second = session._cached_failures_cached(path, 1, 0.5, 1.0, store_identity=second_identity)

    assert topology_first != topology_second
    assert failure_first != failure_second
    assert len(topology_calls) == 2
    assert len(failure_calls) == 2


def test_stored_rollout_session_open_computes_identity_once_and_binds_core_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Opening one session performs one identity walk and binds that key to its core."""

    store = tmp_path / "selected.zarr"
    store.mkdir()
    identity_calls: list[str] = []
    bundle_calls: list[tuple[str, str]] = []
    core = object()

    def identity(path: str) -> str:
        identity_calls.append(path)
        return "identity-1"

    def bundle(path: str, *, store_identity: str) -> tuple[object, object, dict[str, object]]:
        bundle_calls.append((path, store_identity))
        return core, object(), {}

    monkeypatch.setattr(session, "_store_projection_identity", identity)
    monkeypatch.setattr(session, "_cached_store_bundle_cached", bundle)

    opened = session.open_stored_rollout_session(store)

    assert identity_calls == [store.resolve().as_posix()]
    assert bundle_calls == [(store.resolve().as_posix(), "identity-1")]
    assert opened.canonical_path == store.resolve()
    assert opened.store_identity == "identity-1"
    assert opened.reader is core


def test_stored_rollout_session_inventory_row_is_presentation_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Changing inventory metadata does not alter identity or bound core inputs."""

    store = tmp_path / "selected.zarr"
    store.mkdir()
    bundle_calls: list[tuple[str, str]] = []
    monkeypatch.setattr(session, "_store_projection_identity", lambda _path: "identity-1")
    monkeypatch.setattr(
        session,
        "_cached_store_bundle_cached",
        lambda path, *, store_identity: bundle_calls.append((path, store_identity)) or (object(), object(), {}),
    )

    first = session.open_stored_rollout_session(store, inventory_row={"candidate_count": 1})
    second = session.open_stored_rollout_session(store, inventory_row={"candidate_count": 99})

    assert first.store_identity == second.store_identity == "identity-1"
    assert bundle_calls == [
        (store.resolve().as_posix(), "identity-1"),
        (store.resolve().as_posix(), "identity-1"),
    ]


def test_stored_rollout_session_clear_invalidates_every_matrix_owner_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """Owner-level invalidation clears inventory and candidate population as well as projections."""

    names = (
        "_cached_inventory",
        "_cached_store_bundle_cached",
        "_cached_invariants_cached",
        "_cached_header_cached",
        "_cached_cohorts_cached",
        "_cached_paired_cached",
        "_cached_steps_cached",
        "_cached_reconstruction_metrics_cached",
        "_cached_reconstruction_endpoints_cached",
        "_cached_discounted_returns_cached",
        "_cached_headroom_cached",
        "_cached_temporal_cached",
        "_cached_candidate_flow_cached",
        "_cached_ranks_cached",
        "_cached_targets_cached",
        "_cached_masks_cached",
        "_cached_candidates_cached",
        "_cached_candidate_group_cached",
        "_cached_q_h_cached",
        "_cached_tree_cached",
        "_cached_root_geometry_cached",
        "_cached_depth_summary_cached",
        "_cached_candidate_population_cached",
        "_cached_topology_cached",
        "_cached_failures_cached",
        "_cached_evidence_bundle_cached",
    )
    cleared: list[str] = []
    for name in names:
        monkeypatch.setattr(session, name, SimpleNamespace(clear=lambda name=name: cleared.append(name)))

    session.clear_stored_rollout_caches()

    assert cleared == list(names)


def test_stored_rollout_session_topology_preserves_structured_cache_arguments(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Topology retains PathConfig, VIN-directory tuple, and selected source row as arguments."""

    calls: list[tuple[object, tuple[str, ...], PathConfig, int | None, str]] = []
    config = PathConfig(root=tmp_path)
    monkeypatch.setattr(session, "_store_projection_identity", lambda _path: "identity-1")

    def cached_topology(
        path: str,
        vin_dirs: tuple[str, ...],
        paths: PathConfig,
        selected_source_row_id: int | None = None,
        *,
        store_identity: str,
    ) -> object:
        calls.append((path, vin_dirs, paths, selected_source_row_id, store_identity))
        return object()

    monkeypatch.setattr(session, "_cached_topology_cached", cached_topology)
    session._cached_topology_cached("/selected.zarr", ("/vin-a", "/vin-b"), config, 7, store_identity="identity-1")

    assert calls == [("/selected.zarr", ("/vin-a", "/vin-b"), config, 7, "identity-1")]


def test_stored_rollout_session_open_does_not_materialize_heavy_projection_owners(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Opening a session is metadata/core-only and does not read candidate or deep-Q_H evidence."""

    store = tmp_path / "selected.zarr"
    store.mkdir()
    heavy_calls: list[str] = []
    monkeypatch.setattr(session, "_store_projection_identity", lambda _path: "identity-1")
    monkeypatch.setattr(
        session,
        "_cached_store_bundle_cached",
        lambda *_args, **_kwargs: (object(), object(), {}),
    )
    for name in ("candidate_audit_rows", "candidate_population_evidence", "q_h_evidence_rows", "rollout_statistics"):
        if hasattr(session, name):
            monkeypatch.setattr(session, name, lambda *args, name=name, **kwargs: heavy_calls.append(name))

    session.open_stored_rollout_session(store)

    assert heavy_calls == []


def test_stored_rollout_lightweight_header_reads_manifest_validation_promotion_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The lightweight Streamlit trust/header path excludes compact statistics."""

    result = write_rollout_zarr_store(
        tmp_path / "facet-demand.zarr", build_rollout_records(horizon=1, num_samples=6, seed=103)[:1]
    )
    session.clear_stored_rollout_caches()
    calls = {"manifest": 0, "validation": 0, "promotion": 0}
    original_manifest = RolloutZarrStoreReader.manifest
    original_validate = RolloutZarrStoreReader.validate
    original_promotion = session.promoted_store_validation_error

    def manifest(reader):
        calls["manifest"] += 1
        return original_manifest(reader)

    def validate(reader):
        calls["validation"] += 1
        return original_validate(reader)

    def promotion(reader, *, manifest_payload=None):
        calls["promotion"] += 1
        return original_promotion(reader, manifest_payload=manifest_payload)

    monkeypatch.setattr(RolloutZarrStoreReader, "manifest", manifest)
    monkeypatch.setattr(RolloutZarrStoreReader, "validate", validate)
    monkeypatch.setattr(session, "promoted_store_validation_error", promotion)

    opened = session.open_stored_rollout_session(result.store_dir)
    header = opened.header()

    assert calls == {"manifest": 1, "validation": 1, "promotion": 1}
    assert header["rollouts"] == result.num_rollouts


def test_stored_rollout_session_candidate_population_uses_captured_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A bound session keeps candidate evidence on its opened store identity."""

    calls: list[tuple[str, str, int]] = []
    monkeypatch.setattr(
        session,
        "_cached_candidate_population_cached",
        lambda path, identity, sample_size=500: calls.append((path, identity, sample_size)) or {"sample": []},
    )
    handle = session.StoredRolloutSession(Path("/selected.zarr"), "first", object(), object(), {}, None)

    assert handle.candidate_population(17) == {"sample": []}
    assert calls == [("/selected.zarr", "first", 17)]


def test_stored_rollout_session_failure_projection_stays_bound_to_old_handle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Failure evidence uses the opened identity even when the path is later replaced."""

    calls: list[str] = []
    monkeypatch.setattr(
        session,
        "_cached_failures_cached",
        lambda path, _min, _fraction, _distance, *, store_identity: calls.append(store_identity) or [],
    )
    handle = session.StoredRolloutSession(Path("/selected.zarr"), "first", object(), object(), {}, None)

    assert handle.failures(1, 0.5, 1.0) == []
    assert calls == ["first"]


def test_stored_rollout_session_next_open_observes_replacement(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A later open captures the replacement identity rather than the old handle key."""

    store = tmp_path / "selected.zarr"
    store.mkdir()
    identities = iter(("first", "second"))
    monkeypatch.setattr(session, "_store_projection_identity", lambda _path: next(identities))
    monkeypatch.setattr(
        session,
        "_cached_store_bundle_cached",
        lambda path, *, store_identity: (store_identity, object(), {}),
    )

    first = session.open_stored_rollout_session(store)
    second = session.open_stored_rollout_session(store)

    assert first.store_identity == "first"
    assert second.store_identity == "second"


def test_stored_rollout_session_cache_decorator_matrix_is_explicit() -> None:
    """The session source keeps the exact cache kinds and bounds from the migration matrix."""

    source = Path(session.__file__).read_text(encoding="utf-8")
    assert "@st.cache_resource(show_spinner=False)" in source
    assert '@st.cache_resource(show_spinner="Resolving dataset topology…", max_entries=16)' in source
    assert '@st.cache_data(show_spinner="Scanning rollout stores…", max_entries=8)' in source
    assert source.count('@st.cache_data(show_spinner="Loading rollout evidence…", max_entries=128)') >= 2
    assert '@st.cache_data(show_spinner="Evaluating failure predicates…", max_entries=32)' in source
    assert '@st.cache_data(show_spinner="Building deterministic evidence bundle…", max_entries=16)' in source
    assert "_cached_projection" not in source
    assert "_named_projection" not in source
    assert "projection: str" not in source
    assert "Unknown cached rollout projection" not in source


def _owner_stub(result: object) -> Callable[..., object]:
    def owner(*_args: object, **_kwargs: object) -> object:
        return result

    return owner
