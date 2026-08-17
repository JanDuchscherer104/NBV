"""Dispatch-level laziness tests for stored-rollout UI projections."""

# ruff: noqa: S101, SLF001

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from aria_nbv.app.panels import _stored_rollouts_page as page
from aria_nbv.rollouts.zarr_store import write_rollout_zarr_store
from tests.rollout_fixtures import build_rollout_records


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
    monkeypatch.setattr(page, "_cached_store_bundle", lambda _path: (reader, object(), {}))
    monkeypatch.setattr(
        page,
        "candidate_audit_rows",
        lambda *_args, **_kwargs: pytest.fail(f"{projection} materialized candidate_audit_rows"),
    )
    monkeypatch.setattr(page, owner_name, _owner_stub(expected))

    result = page._cached_projection.__wrapped__("/fixture.zarr", projection, **kwargs)

    assert result == expected


def test_candidate_group_materializes_one_candidate_projection_and_reuses_its_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The explicit group branch may read candidates once and must reuse them."""

    reader = object()
    candidate_rows = [{"candidate_row_id": 7}, {"candidate_row_id": 11}]
    recursive_calls: list[tuple[str, int | None]] = []
    summary_calls: list[tuple[object, str, object]] = []
    dispatch = page._cached_projection.__wrapped__

    monkeypatch.setattr(page, "_cached_store_bundle", lambda _path: (reader, object(), {}))

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

    monkeypatch.setattr(page, "_cached_projection", recursive_projection)
    monkeypatch.setattr(page, "candidate_group_summary_rows", summarize)

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
    monkeypatch.setattr(page.st, "info", messages.append)
    monkeypatch.setattr(page, "_render_store_header_summary", lambda _path: pytest.fail("header was rendered"))

    page._render_validated_store_header("/tampered.zarr", validation_ok=False)

    assert messages == ["Coverage and physical-cost projections are withheld until store validation succeeds."]


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

    monkeypatch.setattr(page, "_cached_projection_cached", cached_projection)
    page._cached_projection(store.as_posix(), "header")
    page._cached_projection(store.as_posix(), "header")
    manifest.write_text('{"generation": "second"}', encoding="utf-8")
    page._cached_projection(store.as_posix(), "header")

    assert identities[0] == identities[1]
    assert identities[2] != identities[0]


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
    first_reader, first_validation, first_manifest = page._cached_store_bundle(path)
    first_steps = page._cached_projection(path, "steps")
    first_bundle = page._cached_evidence_bundle(path, "pilot")
    assert first_validation.ok
    assert first_reader.store_dir == selected.resolve()
    assert first_manifest == first_reader.manifest()
    assert len(first_steps) > 0

    replacement = tmp_path / "replacement-link.zarr"
    replacement.symlink_to(second.store_dir, target_is_directory=True)
    replacement.replace(selected)

    second_reader, second_validation, second_manifest = page._cached_store_bundle(path)
    second_steps = page._cached_projection(path, "steps")
    second_bundle = page._cached_evidence_bundle(path, "pilot")
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
        manifest = page._cached_store_bundle(rollout_store_dir.as_posix())[2]
        marker = json.dumps(manifest, sort_keys=True)
        topology_calls.append(marker)
        return {"manifest": marker}

    def failures(reader: object, *, config: object) -> list[dict[str, str]]:
        marker = page._cached_store_bundle(reader.store_dir.as_posix())[2]  # type: ignore[attr-defined]
        value = json.dumps(marker, sort_keys=True)
        failure_calls.append(value)
        return [{"manifest": value}]

    monkeypatch.setattr(page, "build_dataset_topology", topology)
    monkeypatch.setattr(page, "suspicious_rollout_rows", failures)
    path = selected.as_posix()
    topology_first = page._cached_topology(path, (), None)
    failure_first = page._cached_failures(path, 1, 0.5, 1.0)

    replacement = tmp_path / "replacement-link.zarr"
    replacement.symlink_to(second.store_dir, target_is_directory=True)
    replacement.replace(selected)

    topology_second = page._cached_topology(path, (), None)
    failure_second = page._cached_failures(path, 1, 0.5, 1.0)

    assert topology_first != topology_second
    assert failure_first != failure_second
    assert len(topology_calls) == 2
    assert len(failure_calls) == 2


def _owner_stub(result: object) -> Callable[..., object]:
    def owner(*_args: object, **_kwargs: object) -> object:
        return result

    return owner
