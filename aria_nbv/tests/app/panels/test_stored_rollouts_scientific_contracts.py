"""Isolation and immutability contracts for stored-rollout scientific reads."""

# ruff: noqa: S101, SLF001

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import zarr

pytest.importorskip("efm3d")

from aria_nbv.app.panels._stored_rollouts import (
    candidate_generation,
    inspect_rerun,
    oracle_headroom,
    reconstruction_return,
    validity_support,
)
from aria_nbv.app.panels._stored_rollouts import (
    session as stored_session,
)
from aria_nbv.rollouts import reporting
from aria_nbv.rollouts.reporting import build_thesis_report_frames, scientific_report_blockers
from tests.rollouts.test_scientific_reporting_contracts import _artifact, _store


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _zarr_structure(group: zarr.Group, prefix: str = "") -> tuple[tuple[object, ...], ...]:
    entries: list[tuple[object, ...]] = [("group", prefix, dict(group.attrs))]
    for name, array in sorted(group.arrays(), key=lambda item: item[0]):
        entries.append(
            (
                "array",
                f"{prefix}/{name}".lstrip("/"),
                tuple(array.shape),
                str(array.dtype),
                tuple(array.chunks),
                dict(array.attrs),
            )
        )
    for name, child in sorted(group.groups(), key=lambda item: item[0]):
        entries.extend(_zarr_structure(child, f"{prefix}/{name}".lstrip("/")))
    return tuple(entries)


def _store_snapshot(store_dir: Path) -> dict[str, object]:
    root = zarr.open_group(store_dir, mode="r")
    manifest = stored_session._reader(store_dir.as_posix()).manifest()
    files = tuple(
        (path.relative_to(store_dir).as_posix(), _sha256(path))
        for path in sorted(store_dir.rglob("*"))
        if path.is_file()
    )
    return {
        "root_attrs": dict(root.attrs),
        "manifest": json.loads(json.dumps(manifest, sort_keys=True, default=str)),
        "tree": _zarr_structure(root),
        "file_sha256": files,
    }


def test_sidecar_only_scientific_reads_leave_real_rollout_store_byte_and_schema_identical(tmp_path: Path) -> None:
    result, source_sha, split_sha = _store(tmp_path)
    artifact = _artifact(rollout_sha=result.manifest_sha256, source_sha=source_sha, split_sha=split_sha)
    audit_path = tmp_path / "scientific-audit.json"
    audit_path.write_bytes(artifact.model_dump_json().encode())
    before = _store_snapshot(result.store_dir)
    stored_session.clear_stored_rollout_caches()

    pilot = build_thesis_report_frames([result.store_dir], evidence_status="pilot")
    blocked = scientific_report_blockers(result.store_dir, None)
    confirmatory = build_thesis_report_frames(
        [result.store_dir], evidence_status="confirmatory", scientific_audit=artifact
    )
    session = stored_session.open_stored_rollout_session(result.store_dir, inventory_row=None, audit_path=audit_path)
    state = session.audit_state()
    endpoints = session.audited_endpoints()
    effects = session.audited_policy_effects()
    bundle = session.evidence_bundle(evidence_status="pilot")

    after = _store_snapshot(result.store_dir)

    assert pilot["audit_blockers"].iloc[0]["code"] == "scientific_audit_absent"
    assert blocked == ("scientific_audit_absent",)
    assert confirmatory["audit_blockers"].empty
    assert state.evidence_tier == "confirmatory"
    assert len(endpoints) == 1
    assert effects["available"] is True
    assert bundle
    assert after == before


def test_evidence_bundle_cache_key_changes_for_audit_content_and_live_store_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stored_session._cached_evidence_bundle.clear()
    calls: list[tuple[object, ...]] = []
    live_store_sha256 = ["a" * 64]

    def frames(*args: object, **kwargs: object) -> dict[str, object]:
        calls.append((*args, kwargs["scientific_audit"], kwargs["evidence_status"]))
        return {"stores": object()}

    monkeypatch.setattr(stored_session, "build_thesis_report_frames", frames)
    monkeypatch.setattr(stored_session, "serialize_thesis_report_bundle", lambda _frames: b"bundle")
    monkeypatch.setattr(
        stored_session,
        "_reader",
        lambda _store_path: SimpleNamespace(root=SimpleNamespace(attrs={"manifest_sha256": live_store_sha256[0]})),
    )
    audit = tmp_path / "audit.json"

    assert (
        stored_session._cached_evidence_bundle("store.zarr", "a" * 64, audit.as_posix(), "first", "pilot") == b"bundle"
    )
    assert (
        stored_session._cached_evidence_bundle("store.zarr", "a" * 64, audit.as_posix(), "first", "pilot") == b"bundle"
    )
    assert (
        stored_session._cached_evidence_bundle("store.zarr", "a" * 64, audit.as_posix(), "second", "pilot") == b"bundle"
    )
    live_store_sha256[0] = "b" * 64
    assert (
        stored_session._cached_evidence_bundle("store.zarr", "b" * 64, audit.as_posix(), "second", "pilot") == b"bundle"
    )

    assert len(calls) == 3
    stored_session._cached_evidence_bundle.clear()


def test_section_modules_cannot_instantiate_zarr_or_execute_the_independent_audit_pipeline() -> None:
    sections = (candidate_generation, reconstruction_return, oracle_headroom, validity_support, inspect_rerun)
    forbidden = (
        "RolloutZarrStoreReader",
        "zarr.open",
        "rollout_audit",
        "oracle.pipelines",
        "load_scientific_audit",
    )

    for module in sections:
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert not any(token in source for token in forbidden)

    assert "oracle.pipelines" not in Path(reporting.__file__).read_text(encoding="utf-8")


def test_candidate_scientific_view_visibly_labels_its_deterministic_sample_as_display_only() -> None:
    source = Path(candidate_generation.__file__).read_text(encoding="utf-8")

    assert "Deterministic display sample design" in source
    assert "display-only" in source
