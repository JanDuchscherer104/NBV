"""Dispatch-level laziness tests for stored-rollout UI projections."""

# ruff: noqa: S101, SLF001

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from aria_nbv.app.panels import _stored_rollouts_page as page


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


def test_store_manifest_identity_changes_for_same_path_replacement(tmp_path: Path) -> None:
    """Replacing a manifest at one path produces a distinct heavy-projection cache identity."""

    store = tmp_path / "replacement.zarr"
    store.mkdir()
    manifest = store / "manifest.json"
    manifest.write_text('{"generation": "first"}', encoding="utf-8")
    first = page._store_projection_identity(store.as_posix())
    manifest.write_text('{"generation": "second"}', encoding="utf-8")

    assert page._store_projection_identity(store.as_posix()) != first


def _owner_stub(result: object) -> Callable[..., object]:
    def owner(*_args: object, **_kwargs: object) -> object:
        return result

    return owner
