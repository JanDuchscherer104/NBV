"""Dispatch-level laziness tests for stored-rollout UI projections."""

# ruff: noqa: S101, SLF001

from __future__ import annotations

import ast
import inspect
import json
import os
from collections.abc import Callable
from pathlib import Path

import pandas as pd
import pytest
import zarr

from aria_nbv.app.panels._stored_rollouts import failure_triage, inspect_rerun, overview_topology, qh_admission, session
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

    result = session._cached_corpus_summary.__wrapped__(("/b.zarr", "/a.zarr"), ("b-id", "a-id"))

    assert result is expected
    assert calls == [(Path("/b.zarr"), Path("/a.zarr"))]


@pytest.mark.parametrize(
    ("projection", "owner_name", "kwargs"),
    [
        ("invariants", "store_invariant_rows", {}),
        ("cohorts", "comparable_policy_cohorts", {}),
        ("paired", "paired_policy_comparison_rows", {}),
        ("steps", "rollout_step_objective_rows", {}),
        ("temporal", "temporal_metric_summary_rows", {"metric": "selected_target_rri"}),
        ("candidate_flow", "candidate_flow_rows", {}),
        ("ranks", "selected_candidate_rank_rows", {}),
        ("targets", "target_audit_rows", {}),
        ("masks", "mask_combination_rows", {}),
        ("tree", "rollout_tree_summary_rows", {}),
        ("root_geometry", "root_relative_candidate_rows", {}),
        ("depth_summary", "selected_depth_summary_rows", {}),
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
    monkeypatch.setattr(session, "_cached_store_bundle", lambda _path: (reader, object(), {}))
    monkeypatch.setattr(
        session,
        "candidate_audit_rows",
        lambda *_args, **_kwargs: pytest.fail(f"{projection} materialized candidate_audit_rows"),
    )
    monkeypatch.setattr(session, owner_name, _owner_stub(expected))

    result = session._cached_projection.__wrapped__("/fixture.zarr", projection, **kwargs)

    assert result == expected


def test_candidate_group_materializes_one_candidate_projection_and_reuses_its_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The explicit group branch may read candidates once and must reuse them."""

    reader = object()
    candidate_rows = [{"candidate_row_id": 7}, {"candidate_row_id": 11}]
    recursive_calls: list[tuple[str, int | None]] = []
    summary_calls: list[tuple[object, str, object]] = []
    dispatch = session._cached_projection.__wrapped__

    monkeypatch.setattr(session, "_cached_store_bundle", lambda _path: (reader, object(), {}))

    def recursive_projection(
        _store_path: str,
        projection: str,
        *,
        limit: int | None = None,
        **_kwargs: object,
    ) -> list[dict[str, int]]:
        recursive_calls.append((projection, limit))
        assert projection == "candidates"
        return candidate_rows

    def summarize(
        source: object,
        *,
        group_by: str,
        audit_rows: object,
    ) -> list[dict[str, object]]:
        summary_calls.append((source, group_by, audit_rows))
        return [{"family": "fixture", "candidate_count": len(candidate_rows)}]

    monkeypatch.setattr(session, "_cached_projection", recursive_projection)
    monkeypatch.setattr(session, "candidate_group_summary_rows", summarize)

    result = dispatch(
        "/fixture.zarr",
        "candidate_group",
        group_by="mixture",
        limit=25,
    )

    assert recursive_calls == [("candidates", 25)]
    assert summary_calls == [(reader, "mixture", candidate_rows)]
    assert result == [{"family": "fixture", "candidate_count": 2}]


def test_invalid_store_withholds_scientific_header_projection(monkeypatch: pytest.MonkeyPatch) -> None:
    """Invalid or tampered stores keep diagnostics but never render coverage projections."""

    messages: list[str] = []
    monkeypatch.setattr(overview_topology.st, "info", messages.append)
    monkeypatch.setattr(
        overview_topology, "_render_store_header_summary", lambda _path: pytest.fail("header was rendered")
    )

    overview_topology._render_validated_store_header("/tampered.zarr", validation_ok=False)

    assert messages == ["Coverage and physical-cost projections are withheld until store validation succeeds."]


def test_failure_promotion_preserves_ids_and_selects_inspection_route(monkeypatch: pytest.MonkeyPatch) -> None:
    """Failure promotion changes only the Diagnose route while carrying stable ids."""

    state: dict[str, object] = {
        "stored_rollout_id": 3,
        "stored_step_id": 8,
    }
    monkeypatch.setattr(failure_triage.st, "session_state", state)

    failure_triage._carry_failure_to_inspect({"rollout_row_id": 12, "step_row_id": 19})

    assert state == {
        "stored_rollout_id": 12,
        "stored_step_id": 19,
        "stored_rollouts_section": "Diagnose a store",
        "stored_rollouts_diagnose_mode": "Inspect, export, and Rerun",
    }


@pytest.mark.parametrize(
    ("module", "reference"),
    [
        (failure_triage, "https://www.itl.nist.gov/div898/handbook/toolaids/pff/pmc.pdf"),
        (inspect_rerun, "https://pytorch3d.org/docs/renderer_getting_started"),
    ],
)
def test_diagnose_plot_guides_use_narrative_sections(module: object, reference: str) -> None:
    """Diagnostic plots retain focused narrative guidance and their source."""

    tree = ast.parse(inspect.getsource(module))
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "ScientificExplanation"
    ]
    assert calls
    for call in calls:
        fields = {keyword.arg for keyword in call.keywords}
        assert {"question", "answer", "sections", "evidence_role", "source_fields", "external_references"} <= fields
        assert {"intuition", "visual_encoding", "uncertainty", "definition"}.isdisjoint(fields)
        assert reference in ast.get_source_segment(inspect.getsource(module), call)


def test_projection_dispatch_binds_manifest_identity_for_same_path_replacement(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The validated page boundary forwards a stable, replacement-sensitive cache identity."""

    store = tmp_path / "replacement.zarr"
    store.mkdir()
    manifest = store / "manifest.json"
    manifest.write_text('{"generation": "first"}', encoding="utf-8")
    identities: list[str] = []

    def cached_projection(_path: str, _projection: str, *, store_identity: str, **_kwargs: object) -> object:
        identities.append(store_identity)
        return []

    monkeypatch.setattr(session, "_cached_projection_cached", cached_projection)
    session._cached_projection(store.as_posix(), "header")
    session._cached_projection(store.as_posix(), "header")
    manifest.write_text('{"generation": "second"}', encoding="utf-8")
    session._cached_projection(store.as_posix(), "header")

    assert identities[0] == identities[1]
    assert identities[2] != identities[0]


def test_root_geometry_projection_bumps_its_cache_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    """A changed root-geometry row shape must not reuse an old cache entry."""

    revisions: list[int] = []

    def cached_projection(_path: str, _projection: str, *, projection_revision: int, **_kwargs: object) -> object:
        revisions.append(projection_revision)
        return []

    monkeypatch.setattr(session, "_cached_projection_cached", cached_projection)
    session._cached_projection("/fixture.zarr", "header")
    session._cached_projection("/fixture.zarr", "root_geometry")

    assert revisions == [1, 2]


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

    def cached_projection(_path: str, _projection: str, *, store_identity: str, **_kwargs: object) -> object:
        identities.append(store_identity)
        return []

    monkeypatch.setattr(session, "_cached_projection_cached", cached_projection)
    original_read_bytes = Path.read_bytes
    monkeypatch.setattr(Path, "read_bytes", lambda _self: pytest.fail("cache identity must not read payload bytes"))
    session._cached_projection(result.store_dir.as_posix(), "header")
    monkeypatch.setattr(Path, "read_bytes", original_read_bytes)
    root = zarr.open_group(result.store_dir, mode="a")
    candidate_ids = root["candidates/candidate_row_id"]
    candidate_ids[0] = int(candidate_ids[0]) + 1
    os.utime(manifest, ns=(manifest_stat.st_atime_ns, manifest_stat.st_mtime_ns))
    monkeypatch.setattr(Path, "read_bytes", lambda _self: pytest.fail("cache identity must not read payload bytes"))
    session._cached_projection(result.store_dir.as_posix(), "header")

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
    monkeypatch.setattr(qh_admission, "_cached_store_bundle", lambda _path: (object(), object(), {}))
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
    qh_admission._render_q_h_evidence("/fixture.zarr")

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
    first_steps = session._cached_projection(path, "steps")
    first_bundle = session._cached_evidence_bundle(path, "pilot")
    assert first_validation.ok
    assert first_reader.store_dir == selected.resolve()
    assert first_manifest == first_reader.manifest()
    assert len(first_steps) > 0

    replacement = tmp_path / "replacement-link.zarr"
    replacement.symlink_to(second.store_dir, target_is_directory=True)
    replacement.replace(selected)

    second_reader, second_validation, second_manifest = session._cached_store_bundle(path)
    second_steps = session._cached_projection(path, "steps")
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


def test_store_header_renders_compact_cost_metrics(monkeypatch: pytest.MonkeyPatch) -> None:
    """Physical-cost scalars stay readable cards rather than a one-row byte table."""

    header = {
        "scenes": 1,
        "targets": 2,
        "source_rows": 3,
        "physical_store_bytes": 2 * 1024**2,
        "physical_bytes_per_rollout": 19_002.25,
        "physical_bytes_per_candidate": 395.8859,
        "return_semantics": "cumulative_target_root_gain",
        "discount_gamma": 1.0,
        "reference_scene_count": None,
        "reference_source_row_count": None,
    }
    metrics: list[tuple[str, str]] = []

    class Column:
        def metric(self, label: str, value: str) -> None:
            metrics.append((label, value))

    monkeypatch.setattr(overview_topology, "_cached_projection", lambda *_args: header)
    monkeypatch.setattr(overview_topology.st, "markdown", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(overview_topology.st, "caption", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(overview_topology.st, "columns", lambda count: [Column() for _ in range(count)])
    monkeypatch.setattr(overview_topology, "_download_json", lambda *_args, **_kwargs: None)

    overview_topology._render_store_header_summary("/fixture.zarr")

    assert ("Store size", "2.0 MiB") in metrics
    assert ("Bytes / rollout", "18.6 KiB") in metrics
    assert ("Bytes / candidate", "395.9 B") in metrics
    assert ("Return semantics", "cumulative_target_root_gain") in metrics
    assert ("Discount gamma", "1") in metrics


def _owner_stub(result: object) -> Callable[..., object]:
    def owner(*_args: object, **_kwargs: object) -> object:
        return result

    return owner
