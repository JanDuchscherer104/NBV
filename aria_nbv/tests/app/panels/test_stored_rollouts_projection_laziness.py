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
from aria_nbv.oracle.pipelines.shards import plan_rollout_shards, run_rollout_shard
from aria_nbv.rollouts.zarr_store import write_rollout_zarr_store
from tests.rollout_fixtures import build_rollout_records
from tests.rollouts.test_dataset_writer import _fake_record, _FakeRolloutConfig


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

    assert metrics == {
        "Included stores": 1,
        "Excluded stores": 0,
        "Q_H chains": "3",
        "Q_H states": "6",
        "Trainable candidates": "17",
        "Storage": "1.0 KiB",
    }
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

    monkeypatch.setattr(qh_admission, "q_h_evidence_rows", q_h)
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


def _owner_stub(result: object) -> Callable[..., object]:
    def owner(*_args: object, **_kwargs: object) -> object:
        return result

    return owner
