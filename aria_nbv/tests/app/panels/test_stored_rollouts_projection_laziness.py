"""Dispatch-level laziness tests for stored-rollout UI projections."""

# ruff: noqa: S101, SLF001

from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path

import pandas as pd
import pytest
import zarr

from aria_nbv.app.panels._stored_rollouts import overview_topology, qh_admission, session
from aria_nbv.configs import PathConfig
from aria_nbv.oracle.pipelines.shards import plan_rollout_shards, run_rollout_shard
from aria_nbv.rollouts.zarr_store import write_rollout_zarr_store
from tests.rollout_fixtures import build_rollout_records
from tests.rollouts.test_dataset_writer import _fake_record, _FakeRolloutConfig


def test_contract_overview_label_is_compact_and_keeps_exact_identity() -> None:
    """Overview labels show the profile once while preserving the full contract ID."""

    label = overview_topology._contract_overview_label(
        {
            "profile": "rich-60",
            "contract": "rich-60 · candidate abcdef123456",
            "contract_id": "0123456789abcdef",
        }
    )

    assert label == "rich-60 · candidate abcdef123456 · contract_id=0123456789abcdef"
    assert label.count("rich-60") == 1


def test_corpus_overview_defers_per_store_qh_rows_to_drill_down(monkeypatch: pytest.MonkeyPatch) -> None:
    """Overview stays aggregate-only while drill-down retains store-qualified evidence."""

    metrics: dict[str, object] = {}
    frames: list[object] = []

    class Column:
        def metric(self, label: str, value: object) -> None:
            metrics[label] = value

    summary = session.RolloutCorpusSummary(
        verdict="Ready",
        selected_paths=(Path("/fixture.zarr"),),
        included_stores=({"path": "/fixture.zarr", "store_id": "fixture", "profile": "pilot"},),
        excluded_stores=(),
        totals={
            "selected_store_count": 1,
            "included_store_count": 1,
            "excluded_store_count": 0,
            "q_h_chain_count": 3,
            "q_h_state_count": 6,
            "q_h_trainable_count": 17,
            "storage_bytes": 1024,
        },
        candidate_support=pd.DataFrame(),
        endpoints=pd.DataFrame(),
        failure_counts=pd.DataFrame(),
        q_h_stores=pd.DataFrame([{"store_id": "fixture", "state_count": 6}]),
    )
    monkeypatch.setattr(overview_topology.st, "subheader", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(overview_topology.st, "columns", lambda count: [Column() for _ in range(count)])
    monkeypatch.setattr(overview_topology.st, "caption", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(overview_topology.st, "dataframe", lambda frame, **_kwargs: frames.append(frame))

    overview_topology._render_corpus_overview(summary, selected_count=1)

    assert metrics["Selected stores (operational)"] == 1
    assert metrics["Included stores (operational)"] == 1
    assert metrics["Excluded stores (operational)"] == 0
    assert frames == []

    overview_topology._render_corpus_details(summary)

    assert len(frames) == 2


def test_corpus_summary_cache_delegates_only_after_explicit_dispatch_and_preserves_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The UI cache key binds ordered paths and identities before calling reporting."""

    calls: list[tuple[Path, ...]] = []
    expected = object()

    def build(paths):
        calls.append(tuple(paths))
        return expected

    monkeypatch.setattr(session, "build_rollout_corpus_summary", build)
    monkeypatch.setattr(session, "_assert_current_identity", lambda *_args: None)

    result = session._cached_corpus_summary.__wrapped__(("/b.zarr", "/a.zarr"), ("b-id", "a-id"))

    assert result is expected
    assert calls == [(Path("/b.zarr"), Path("/a.zarr"))]


def test_named_session_operations_have_no_generic_projection_dispatcher() -> None:
    """Presentation owners use named operations instead of a string dispatcher."""

    source = Path(session.__file__).read_text(encoding="utf-8")
    assert "def _cached_projection" not in source
    assert "rglob(" not in source
    assert hasattr(session, "_cached_steps")
    assert hasattr(session, "_cached_candidates")


def test_refresh_rollout_caches_clears_each_page_family(monkeypatch: pytest.MonkeyPatch) -> None:
    """The shared refresh action invalidates Training Dataset lazily as well."""

    calls: list[str] = []
    monkeypatch.setattr(session, "_clear_stored_rollout_caches", lambda: calls.append("rollouts"))
    monkeypatch.setattr(
        "aria_nbv.app.panels.training_dataset._clear_training_dataset_caches",
        lambda: calls.append("training"),
    )

    session.clear_rollout_page_caches()

    assert calls == ["rollouts", "training"]


def test_invalid_store_withholds_scientific_header_projection(monkeypatch: pytest.MonkeyPatch) -> None:
    """Invalid or tampered stores keep diagnostics but never render coverage projections."""

    messages: list[str] = []
    monkeypatch.setattr(overview_topology.st, "info", messages.append)
    monkeypatch.setattr(
        overview_topology, "_render_store_header_summary", lambda _handle: pytest.fail("header was rendered")
    )

    overview_topology._render_validated_store_header(object(), validation_ok=False)

    assert messages == ["Coverage and physical-cost projections are withheld until store validation succeeds."]


def test_store_bundle_composes_one_manifest_schema_and_promotion_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The fixed-generation cache returns immutable typed trust without mutating validation."""

    result = write_rollout_zarr_store(
        tmp_path / "typed-trust.zarr", build_rollout_records(horizon=1, num_samples=6, seed=907)[:1]
    )
    calls = {"manifest": 0, "schema": 0, "promotion": 0, "trust": 0}
    original_manifest = session.build_manifest_facts
    original_schema = session.build_schema_validation
    original_promotion = session.build_promotion_evidence
    original_trust = session.build_effective_streamlit_trust

    def manifest(*args, **kwargs):
        calls["manifest"] += 1
        return original_manifest(*args, **kwargs)

    def schema(*args, **kwargs):
        calls["schema"] += 1
        return original_schema(*args, **kwargs)

    def promotion(*args, **kwargs):
        calls["promotion"] += 1
        return original_promotion(*args, **kwargs)

    def trust(*args, **kwargs):
        calls["trust"] += 1
        return original_trust(*args, **kwargs)

    monkeypatch.setattr(session, "build_manifest_facts", manifest)
    monkeypatch.setattr(session, "build_schema_validation", schema)
    monkeypatch.setattr(session, "build_promotion_evidence", promotion)
    monkeypatch.setattr(session, "build_effective_streamlit_trust", trust)
    _, effective, manifest_payload = session._cached_store_bundle_cached.__wrapped__(
        result.store_dir.as_posix(), store_identity="typed-trust"
    )

    assert calls == {"manifest": 1, "schema": 1, "promotion": 1, "trust": 1}
    assert effective.ok
    assert isinstance(effective.errors, tuple)
    assert manifest_payload["root_attrs"]["schema_version"]


def test_named_cache_identity_changes_for_same_path_replacement(tmp_path: Path) -> None:
    """The validated page boundary forwards a stable, replacement-sensitive cache identity."""

    store = tmp_path / "replacement.zarr"
    store.mkdir()
    manifest = store / "manifest.json"
    manifest.write_text('{"generation": "first"}', encoding="utf-8")
    first = session._store_projection_identity(store.as_posix())
    second = session._store_projection_identity(store.as_posix())
    manifest.write_text('{"generation": "second"}', encoding="utf-8")
    third = session._store_projection_identity(store.as_posix())

    assert first == second
    assert third != first


def test_store_cache_identity_does_not_read_payload_bytes(tmp_path: Path) -> None:
    result = write_rollout_zarr_store(
        tmp_path / "array-mutation.zarr",
        build_rollout_records(horizon=1, num_samples=6, seed=901)[:1],
    )
    original_read_bytes = Path.read_bytes
    Path.read_bytes = lambda _self: pytest.fail("cache identity must not read payload bytes")
    try:
        session._store_projection_identity(result.store_dir.as_posix())
    finally:
        Path.read_bytes = original_read_bytes


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
    _, first_validation, _ = session._cached_store_bundle(store_path)
    assert first_validation.ok

    root = zarr.open_group(result.final_dir, mode="a")
    clearance = root["candidate_diagnostics/path_min_clearance_m"]
    clearance[0] = float(clearance[0]) + 0.125
    for path, mtime_ns in mtimes.items():
        os.utime(path, ns=(path.stat().st_atime_ns, mtime_ns))

    second_identity = session._store_projection_identity(store_path)
    _, second_validation, _ = session._cached_store_bundle(store_path)

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
    monkeypatch.setattr(qh_admission.st, "session_state", session_state)
    monkeypatch.setattr(qh_admission.st, "markdown", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(qh_admission.st, "toggle", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        qh_admission.st,
        "number_input",
        lambda label, **_kwargs: 2 if "chunk" in label else 0,
    )
    monkeypatch.setattr(qh_admission.st, "checkbox", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(qh_admission.st, "progress", lambda *_args, **_kwargs: progress)
    monkeypatch.setattr(qh_admission.st, "empty", lambda: status)
    monkeypatch.setattr(qh_admission.st, "dataframe", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(qh_admission, "_download_frame", lambda *_args, **_kwargs: None)

    class Handle:
        canonical_path = Path("/fixture.zarr")
        reader = object()
        validation = object()

        def q_h(self, **_kwargs):
            return []

    handle = Handle()
    callback_results: list[bool] = []

    def q_h(**kwargs):
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

    handle.q_h_progressive = q_h  # type: ignore[method-assign]
    qh_admission._render_q_h_evidence(handle)

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
    first_reader, first_validation, first_manifest = session._cached_store_bundle(path)
    first_steps = session._cached_steps(path)
    first_bundle = session._cached_evidence_bundle(path, "pilot")
    assert first_validation.ok
    assert first_reader.store_dir == selected.resolve()
    assert first_manifest == first_reader.manifest()
    assert len(first_steps) > 0

    replacement = tmp_path / "replacement-link.zarr"
    replacement.symlink_to(second.store_dir, target_is_directory=True)
    replacement.replace(selected)

    second_reader, second_validation, second_manifest = session._cached_store_bundle(path)
    second_steps = session._cached_steps(path)
    second_bundle = session._cached_evidence_bundle(path, "pilot")
    assert second_validation.ok
    assert second_reader.store_dir == selected.resolve()
    assert second_manifest == second_reader.manifest()
    assert len(second_steps) > len(first_steps)
    assert second_manifest != first_manifest
    assert second_bundle != first_bundle


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
        manifest = session._cached_store_bundle(rollout_store_dir.as_posix())[2]
        marker = json.dumps(manifest, sort_keys=True)
        topology_calls.append(marker)
        return {"manifest": marker}

    def failures(reader: object, *, config: object) -> list[dict[str, str]]:
        marker = session._cached_store_bundle(reader.store_dir.as_posix())[2]  # type: ignore[attr-defined]
        value = json.dumps(marker, sort_keys=True)
        failure_calls.append(value)
        return [{"manifest": value}]

    monkeypatch.setattr(session, "build_dataset_topology", topology)
    monkeypatch.setattr(session, "suspicious_rollout_rows", failures)
    path = selected.as_posix()
    topology_first = session._cached_topology(path, (), None)
    failure_first = session._cached_failures(path, 1, 0.5, 1.0)

    replacement = tmp_path / "replacement-link.zarr"
    replacement.symlink_to(second.store_dir, target_is_directory=True)
    replacement.replace(selected)

    topology_second = session._cached_topology(path, (), None)
    failure_second = session._cached_failures(path, 1, 0.5, 1.0)

    assert topology_first != topology_second
    assert failure_first != failure_second
    assert len(topology_calls) == 2
    assert len(failure_calls) == 2


def test_fixed_session_rejects_mid_handle_swap(tmp_path: Path) -> None:
    """A page-held session cannot project a replacement generation."""

    first = write_rollout_zarr_store(
        tmp_path / "session-first.zarr", build_rollout_records(horizon=1, num_samples=6, seed=201)[:1]
    )
    second = write_rollout_zarr_store(
        tmp_path / "session-second.zarr", build_rollout_records(horizon=1, num_samples=6, seed=202)[:2]
    )
    selected = tmp_path / "session-selected.zarr"
    selected.symlink_to(first.store_dir, target_is_directory=True)
    handle = session.open_stored_rollout_session(selected)
    assert handle.header()["rollouts"] == 1

    replacement = tmp_path / "session-replacement.zarr"
    replacement.symlink_to(second.store_dir, target_is_directory=True)
    replacement.replace(selected)

    with pytest.raises(RuntimeError, match="changed"):
        handle.header()


def test_session_open_rejects_mid_open_generation_swap(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Opening fails if the selected entry changes while the reader is built."""

    first = tmp_path / "generation-a.zarr"
    second = tmp_path / "generation-b.zarr"
    first.mkdir()
    second.mkdir()
    selected = tmp_path / "selected.zarr"
    selected.symlink_to(first, target_is_directory=True)

    def swap_during_bundle(path: str, *, store_identity: str):
        replacement = tmp_path / "replacement.zarr"
        replacement.symlink_to(second, target_is_directory=True)
        replacement.replace(selected)
        return object(), object(), {"generation": path, "identity": store_identity}

    monkeypatch.setattr(session, "_cached_store_bundle_cached", swap_during_bundle)
    with pytest.raises(RuntimeError, match="changed while opening"):
        session.open_stored_rollout_session(selected)


def test_lightweight_dispatch_does_not_materialize_candidate_audit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Opening the named session boundary never opens the heavyweight candidate audit."""

    monkeypatch.setattr(session, "candidate_audit_rows", lambda *_a, **_k: pytest.fail("candidate audit opened"))
    monkeypatch.setattr(session, "_store_projection_identity", lambda _path: "fixture")
    monkeypatch.setattr(
        session,
        "_cached_store_bundle_cached",
        lambda *_a, **_k: (object(), object(), {"manifest": "fixture"}),
    )
    opened = session.open_stored_rollout_session(Path("/fixture.zarr"))
    assert opened.store_identity == "fixture"


def test_manifest_read_failure_blocks_session_without_synthetic_manifest(monkeypatch: pytest.MonkeyPatch) -> None:
    """A manifest read failure cannot become a trusted synthetic empty payload."""

    class Reader:
        def manifest(self):
            raise RuntimeError("manifest read failed")

    monkeypatch.setattr(session, "RolloutZarrStoreReader", lambda _path: Reader())
    with pytest.raises(RuntimeError, match="manifest read failed"):
        session._cached_store_bundle_cached.__wrapped__("/unpromoted.zarr", store_identity="fixture")


def test_open_session_binds_real_projections_until_next_open(tmp_path: Path) -> None:
    """An old handle fails closed after replacement while a new handle reads the new generation."""

    first = write_rollout_zarr_store(
        tmp_path / "first.zarr", build_rollout_records(horizon=1, num_samples=6, seed=111)[:1]
    )
    second = write_rollout_zarr_store(
        tmp_path / "second.zarr", build_rollout_records(horizon=1, num_samples=6, seed=112)[:2]
    )
    selected = tmp_path / "selected.zarr"
    selected.symlink_to(first.store_dir, target_is_directory=True)
    old = session.open_stored_rollout_session(selected)
    old_steps = old.steps()
    replacement = tmp_path / "replacement.zarr"
    replacement.symlink_to(second.store_dir, target_is_directory=True)
    replacement.replace(selected)
    with pytest.raises(RuntimeError, match="store changed"):
        old.steps()
    new = session.open_stored_rollout_session(selected)
    assert len(new.steps()) > len(old_steps)


def test_open_session_rejects_mid_open_generation_swap(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Opening cannot return a reader from one generation after the selected path swaps."""

    selected = tmp_path / "selected.zarr"
    selected.mkdir()
    identities = iter(("first", "second"))
    monkeypatch.setattr(session, "_store_projection_identity", lambda _path: next(identities))
    monkeypatch.setattr(session, "_cached_store_bundle_cached", lambda *_a, **_k: _swap_selected(tmp_path, selected))
    with pytest.raises(RuntimeError, match="changed while opening"):
        session.open_stored_rollout_session(selected)


def _swap_selected(tmp_path: Path, selected: Path):
    replacement = tmp_path / "replacement.zarr"
    replacement.mkdir()
    replacement.replace(selected)
    return object(), object(), {}


def test_open_session_symlink_aliases_share_canonical_identity_and_cache_owner(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Symlink aliases use one canonical path and identity key."""

    target = tmp_path / "target.zarr"
    target.mkdir()
    aliases = [tmp_path / "a.zarr", tmp_path / "b.zarr"]
    for alias in aliases:
        alias.symlink_to(target, target_is_directory=True)
    calls = []
    monkeypatch.setattr(
        session, "_cached_store_bundle_cached", lambda path, **kw: calls.append((path, kw)) or (object(), object(), {})
    )
    first = session.open_stored_rollout_session(aliases[0])
    second = session.open_stored_rollout_session(aliases[1])
    assert first.canonical_path == second.canonical_path == target.resolve()
    assert first.store_identity == second.store_identity
    assert all(path == target.resolve().as_posix() for path, _ in calls)


def test_projection_dispatch_binds_manifest_identity_for_same_path_replacement(tmp_path: Path) -> None:
    """Named projections receive a replacement-sensitive identity key."""

    store = tmp_path / "replacement.zarr"
    store.mkdir()
    manifest = store / "manifest.json"
    manifest.write_text('{"generation": "first"}', encoding="utf-8")
    first = session._store_projection_identity(store)
    manifest.write_text('{"generation": "second"}', encoding="utf-8")
    second = session._store_projection_identity(store)
    assert first != second


def test_store_cache_identity_does_not_enumerate_payload_chunks(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Identity inspection remains marker-only and never walks payload chunks."""

    store = tmp_path / "marker.zarr"
    store.mkdir()
    (store / "manifest.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(Path, "rglob", lambda *_a, **_k: pytest.fail("payload chunks enumerated"))
    assert session._store_projection_identity(store)


def test_store_cache_identity_ignores_payload_mutation_until_replacement(tmp_path: Path) -> None:
    """Payload edits alone do not change the lightweight cache identity."""

    result = write_rollout_zarr_store(
        tmp_path / "mutation.zarr", build_rollout_records(horizon=1, num_samples=6, seed=901)[:1]
    )
    first = session._store_projection_identity(result.store_dir)
    root = zarr.open_group(result.store_dir, mode="a")
    root["candidates/candidate_row_id"][0] = int(root["candidates/candidate_row_id"][0]) + 1
    assert session._store_projection_identity(result.store_dir) == first


def test_stored_rollout_lightweight_header_reads_manifest_validation_promotion_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Header demand composes manifest, validation, and promotion once."""

    result = write_rollout_zarr_store(
        tmp_path / "header.zarr", build_rollout_records(horizon=1, num_samples=6, seed=103)[:1]
    )
    calls = {"manifest": 0, "validation": 0, "promotion": 0}
    original_manifest = session.build_manifest_facts
    original_schema = session.build_schema_validation
    original_promotion = session.build_promotion_evidence

    monkeypatch.setattr(
        session,
        "build_manifest_facts",
        lambda *args, **kwargs: (
            calls.__setitem__("manifest", calls["manifest"] + 1) or original_manifest(*args, **kwargs)
        ),
    )
    monkeypatch.setattr(
        session,
        "build_schema_validation",
        lambda *args, **kwargs: (
            calls.__setitem__("validation", calls["validation"] + 1) or original_schema(*args, **kwargs)
        ),
    )
    monkeypatch.setattr(
        session,
        "build_promotion_evidence",
        lambda *args, **kwargs: (
            calls.__setitem__("promotion", calls["promotion"] + 1) or original_promotion(*args, **kwargs)
        ),
    )
    _, validation, manifest = session._cached_store_bundle_cached.__wrapped__(
        result.store_dir.as_posix(), store_identity="fixture"
    )
    assert validation.ok
    assert manifest
    assert calls["manifest"] == 1


def test_stored_rollout_session_cache_decorator_matrix_is_explicit() -> None:
    """The current session retains explicit cache owners and no generic dispatcher."""

    source = Path(session.__file__).read_text(encoding="utf-8")
    assert "def _cached_projection" not in source
    assert "def candidate_group(" not in source
    assert "@st.cache_resource(show_spinner=False)" in source
    assert "Evaluating failure predicates" in source


def test_stored_rollout_session_candidate_population_uses_captured_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    """Candidate population uses the opened handle identity rather than recomputing a path key."""

    calls = []
    monkeypatch.setattr(
        session,
        "_cached_candidate_population_cached",
        lambda path, identity, sample_size=500: calls.append((path, identity, sample_size)) or {"sample": []},
    )
    handle = session.StoredRolloutSession(Path("/selected.zarr"), "first", object(), object(), {}, None)
    monkeypatch.setattr(handle, "_assert_current_identity", lambda: "first")
    assert handle.candidate_population(17) == {"sample": []}
    assert calls == [("/selected.zarr", "first", 17)]


def test_stored_rollout_session_candidate_population_fails_closed_on_mid_read_replacement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A replacement during the cached population read is detected afterward."""

    identities = iter(("first", "second"))
    monkeypatch.setattr(session, "_store_projection_identity", lambda _path: next(identities))
    monkeypatch.setattr(
        session,
        "_cached_candidate_population_cached",
        lambda _path, _identity, _sample_size: {"sample": ["read"]},
    )
    handle = session.StoredRolloutSession(Path("/selected.zarr"), "first", object(), object(), {}, None)

    with pytest.raises(RuntimeError, match="changed after this session opened"):
        handle.candidate_population()


def test_cached_proposal_geometry_preserves_zero_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    """An explicit zero bound is distinct from the uncapped default."""

    captured: list[int | None] = []

    monkeypatch.setattr(session, "_cached_store_bundle", lambda _path: (object(), object(), {}))
    monkeypatch.setattr(
        session,
        "proposal_support_geometry",
        lambda _reader, *, max_candidates: (
            captured.append(max_candidates)
            or type("Projection", (), {"points": (), "frames": (), "issues": (), "truncated": True})()
        ),
    )

    session._cached_proposal_geometry.__wrapped__("/selected.zarr", 0)

    assert captured == [0]


def test_stored_rollout_session_clear_invalidates_every_matrix_owner_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cache clearing visits every current owner exactly once."""

    names = (
        "_cached_inventory",
        "_cached_store_bundle_cached",
        "_cached_invariants",
        "_cached_header",
        "_cached_cohorts",
        "_cached_paired",
        "_cached_steps",
        "_cached_reconstruction_metrics",
        "_cached_reconstruction_endpoints",
        "_cached_discounted_returns",
        "_cached_headroom",
        "_cached_candidate_flow",
        "_cached_ranks",
        "_cached_temporal",
        "_cached_targets",
        "_cached_masks",
        "_cached_candidates",
        "_cached_candidate_population_cached",
        "_cached_q_h",
        "_cached_tree",
        "_cached_root_geometry",
        "_cached_depth_summary",
        "_cached_proposal_geometry",
        "_cached_trajectory_geometry",
        "_cached_topology_cached",
        "_cached_failures_cached",
        "_cached_evidence_bundle_cached",
        "_cached_corpus_summary",
    )
    cleared = []
    for name in names:
        monkeypatch.setattr(
            session, name, type("Owner", (), {"clear": lambda _self, name=name: cleared.append(name)})()
        )
    session._clear_stored_rollout_caches()
    assert set(cleared) == set(names)
    assert len(cleared) == len(set(cleared))


def test_stored_rollout_session_clear_forces_candidate_population_recomputation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Refreshing the direct candidate-population owner cannot reuse its prior result."""

    class Owner:
        def __init__(self) -> None:
            self.calls = 0
            self.clears = 0

        def __call__(self, _path: str, _identity: str, _sample_size: int) -> dict[str, int]:
            self.calls += 1
            return {"calls": self.calls}

        def clear(self) -> None:
            self.clears += 1

    owner = Owner()
    monkeypatch.setattr(session, "_cached_candidate_population_cached", owner)
    handle = session.StoredRolloutSession(Path("/selected.zarr"), "first", object(), object(), {}, None)
    monkeypatch.setattr(handle, "_assert_current_identity", lambda: "first")

    assert handle.candidate_population() == {"calls": 1}
    session._clear_stored_rollout_caches()
    assert handle.candidate_population() == {"calls": 2}
    assert owner.clears == 1


def test_stored_rollout_session_discounted_returns_reads_generated_store(tmp_path: Path) -> None:
    """Discounted-return projection reads the generated store through the session."""

    result = write_rollout_zarr_store(
        tmp_path / "returns.zarr", build_rollout_records(horizon=2, num_samples=6, seed=1201)[:1]
    )
    opened = session.open_stored_rollout_session(result.store_dir)
    returns = opened.discounted_returns()
    assert returns["available"] is True
    assert returns["rows"]


def test_stored_rollout_session_failure_projection_stays_bound_to_old_handle(monkeypatch: pytest.MonkeyPatch) -> None:
    """Failure projection carries the captured identity into its cache owner."""

    calls = []
    monkeypatch.setattr(
        session, "_cached_failures", lambda *args, **kwargs: calls.append(kwargs["store_identity"]) or []
    )
    handle = session.StoredRolloutSession(Path("/selected.zarr"), "first", object(), object(), {}, None)
    monkeypatch.setattr(handle, "_assert_current_identity", lambda: "first")
    assert handle.failures(1, 0.5, 1.0) == []
    assert calls == ["first"]


def test_stored_rollout_session_has_no_legacy_candidate_group_owner() -> None:
    """Candidate grouping remains owned by the candidate population projection."""

    source = Path(session.__file__).read_text(encoding="utf-8")
    assert "def candidate_group(" not in source
    assert "def _cached_candidate_group" not in source


def test_stored_rollout_session_inventory_row_is_presentation_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Inventory metadata does not influence the session identity or core reader."""

    store = tmp_path / "inventory.zarr"
    store.mkdir()
    monkeypatch.setattr(session, "_store_projection_identity", lambda _path: "identity")
    monkeypatch.setattr(session, "_cached_store_bundle_cached", lambda *_a, **_k: ("reader", object(), {}))
    first = session.open_stored_rollout_session(store, inventory_row={"count": 1})
    second = session.open_stored_rollout_session(store, inventory_row={"count": 99})
    assert first.store_identity == second.store_identity == "identity"
    assert first.reader == second.reader == "reader"


def test_stored_rollout_session_next_open_observes_replacement(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A later open captures the replacement identity."""

    store = tmp_path / "selected.zarr"
    store.mkdir()
    identities = iter(("first", "first", "second", "second"))
    monkeypatch.setattr(session, "_store_projection_identity", lambda _path: next(identities))
    monkeypatch.setattr(
        session, "_cached_store_bundle_cached", lambda _path, **kwargs: (kwargs["store_identity"], object(), {})
    )
    first = session.open_stored_rollout_session(store)
    second = session.open_stored_rollout_session(store)
    assert first.store_identity == "first"
    assert second.store_identity == "second"


def test_stored_rollout_session_open_computes_identity_once_and_binds_core_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Session opening binds one identity to one canonical core cache key."""

    store = tmp_path / "selected.zarr"
    store.mkdir()
    calls = []
    monkeypatch.setattr(session, "_store_projection_identity", lambda path: calls.append(path) or "identity")
    core = object()
    monkeypatch.setattr(session, "_cached_store_bundle_cached", lambda path, **kwargs: (core, object(), {}))
    opened = session.open_stored_rollout_session(store)
    assert calls == [store.resolve().as_posix(), store.resolve().as_posix()]
    assert opened.reader is core


def test_stored_rollout_session_open_does_not_materialize_heavy_projection_owners(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Opening a session does not invoke candidate, Q_H, or statistics owners."""

    store = tmp_path / "selected.zarr"
    store.mkdir()
    heavy = []
    for name in ("candidate_audit_rows", "candidate_population_evidence", "q_h_evidence_rows"):
        monkeypatch.setattr(session, name, lambda *args, name=name, **kwargs: heavy.append(name))
    monkeypatch.setattr(session, "_cached_store_bundle_cached", lambda *_a, **_k: (object(), object(), {}))
    session.open_stored_rollout_session(store)
    assert heavy == []


def test_stored_rollout_session_rejects_mid_handle_swap(monkeypatch: pytest.MonkeyPatch) -> None:
    """Named session operations fail closed when the selected identity changes."""

    identities = iter(("first", "second"))
    monkeypatch.setattr(session, "_store_projection_identity", lambda _path: next(identities))
    handle = session.StoredRolloutSession(Path("/selected.zarr"), "first", object(), object(), {}, None)
    with pytest.raises(RuntimeError, match="store changed"):
        handle.header()


def test_stored_rollout_session_topology_preserves_structured_cache_arguments(monkeypatch: pytest.MonkeyPatch) -> None:
    """Topology retains structured VIN directories, PathConfig, source row, and identity."""

    calls = []
    monkeypatch.setattr(session, "_cached_topology", lambda *args, **kwargs: calls.append((args, kwargs)) or object())
    handle = session.StoredRolloutSession(Path("/selected.zarr"), "identity", object(), object(), {}, None)
    monkeypatch.setattr(handle, "_assert_current_identity", lambda: "identity")
    paths = PathConfig()
    handle.topology(("/vin-a", "/vin-b"), paths, 7)
    assert calls and calls[0][0][1:4] == (("/vin-a", "/vin-b"), paths, 7)


def test_stored_rollout_session_progressive_qh_rejects_mid_domain_call_swap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Progressive Q_H evidence cannot return rows from a replaced generation."""

    identities = iter(("first", "second"))
    monkeypatch.setattr(session, "_store_projection_identity", lambda _path: next(identities))
    monkeypatch.setattr(session, "q_h_evidence_rows", lambda *_args, **_kwargs: [{"generation": "first"}])
    handle = session.StoredRolloutSession(Path("/selected.zarr"), "first", object(), object(), {}, None)
    with pytest.raises(RuntimeError, match="store changed"):
        handle.q_h_progressive(chunk_size=1, state_row_limit=None, progress_callback=None)


def test_stored_rollout_session_selected_depth_rejects_mid_domain_call_swap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Selected-depth preview cannot return a stale artifact after replacement."""

    identities = iter(("first", "second"))
    monkeypatch.setattr(session, "_store_projection_identity", lambda _path: next(identities))
    monkeypatch.setattr(session, "selected_depth_preview", lambda *_args, **_kwargs: {"generation": "first"})
    handle = session.StoredRolloutSession(Path("/selected.zarr"), "first", object(), object(), {}, None)
    with pytest.raises(RuntimeError, match="store changed"):
        handle.selected_depth_preview(step_row_id=1)


def _owner_stub(result: object) -> Callable[..., object]:
    def owner(*_args: object, **_kwargs: object) -> object:
        return result

    return owner
