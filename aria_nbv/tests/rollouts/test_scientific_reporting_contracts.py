"""Fail-closed scientific reporting contracts."""

# ruff: noqa: S101

from __future__ import annotations

import hashlib
import inspect
from pathlib import Path

import pytest

pytest.importorskip("efm3d")

from aria_nbv.rollouts import reporting
from aria_nbv.rollouts.reporting import (
    build_thesis_report_frames,
    scientific_report_blockers,
    serialize_thesis_report_bundle,
)
from aria_nbv.rollouts.scientific_audit import (
    AuditCohortSummary,
    AuditProvenance,
    AuditSamplingUnit,
    AuditStratumDimension,
    MandatoryCohortStatus,
    NamedSha256,
    ScientificAuditArtifact,
    ScientificAuditPayload,
    ValidityPredicateContract,
    freeze_hash_priority_cohort,
    seal_scientific_audit,
    write_scientific_audit,
)
from aria_nbv.rollouts.zarr_store import write_rollout_zarr_store
from tests.rollout_fixtures import build_rollout_records
from tests.rollouts.test_scientific_audit import _complete_payload


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _store(tmp_path: Path):
    source_sha = _sha("reporting-source")
    split_sha = _sha("reporting-split")
    records = build_rollout_records(horizon=1, num_samples=6, seed=901)[:1]
    records[0].lineage.source.source_offline_store_manifest_hash = source_sha
    records[0].lineage.source.split_manifest_hash = split_sha
    result = write_rollout_zarr_store(tmp_path / "rollouts.zarr", records)
    return result, source_sha, split_sha


def _contract(kind: str) -> ValidityPredicateContract:
    return ValidityPredicateContract.derive(
        predicate_kind=kind,  # type: ignore[arg-type]
        owner=f"{kind}_validator",
        name=f"{kind}:v1",
        comparison_operator="<=",
        threshold=0.25,
        unit="m",
        frame="ARIA world",
        semantic_config_sha256=_sha(f"{kind}:config"),
    )


def _artifact(
    *,
    rollout_sha: str,
    source_sha: str,
    split_sha: str,
    complete_validity: bool = True,
    endpoint_comparator_offset: float = 0.0,
) -> ScientificAuditArtifact:
    payload = _complete_payload(endpoint_comparator_offset=endpoint_comparator_offset)
    endpoint = payload.endpoint_rows[0].model_copy(
        update={"source_store_sha256": source_sha, "split_manifest_sha256": split_sha}
    )
    provenance = AuditProvenance(
        rollout_store_sha256=rollout_sha,
        source_store_sha256=source_sha,
        split_manifest_sha256=split_sha,
        raw_assets=(NamedSha256(name="target_mesh", sha256=_sha("target-mesh")),),
        evaluator_id="independent-target-reconstruction-v1",
        implementation_revision="git:reporting-test",
        resolved_config_sha256=_sha("reporting-config"),
    )
    if not complete_validity:
        candidate = payload.model_copy(update={"provenance": provenance, "endpoint_rows": (endpoint,)})
        return seal_scientific_audit(ScientificAuditPayload.model_validate(candidate.model_dump(mode="python")))

    units = [AuditSamplingUnit(unit_id="endpoint-1", stratum_id="endpoint")]
    allocations = {"endpoint": 1}
    dimensions = {"endpoint": (AuditStratumDimension(name="scene_id", value="scene-1"),)}
    for kind in ("state", "path", "combined_actor"):
        stratum_id = f"validity-{kind}"
        units.append(AuditSamplingUnit(unit_id=stratum_id, stratum_id=stratum_id))
        allocations[stratum_id] = 1
        dimensions[stratum_id] = (
            AuditStratumDimension(name="scene_id", value="scene-1"),
            AuditStratumDimension(name="predicate_kind", value=kind),
        )
    cohort = freeze_hash_priority_cohort(tuple(units), allocations, seed="reporting-audit", dimensions=dimensions)
    base_validity = payload.validity_rows[0]
    validity_rows = []
    for kind in ("state", "path", "combined_actor"):
        stratum_id = f"validity-{kind}"
        stratum = next(item for item in cohort.strata if item.stratum_id == stratum_id)
        contract = _contract(kind)
        validity_rows.append(
            base_validity.model_copy(
                update={
                    "unit_id": stratum_id,
                    "stratum_id": stratum_id,
                    "persisted_contract": contract,
                    "independent_contract": contract,
                    "inclusion_probability": stratum.inclusion_probability,
                    "inverse_probability_weight": stratum.inverse_probability_weight,
                }
            )
        )
    summary = AuditCohortSummary(
        cohort_id=endpoint.cohort_id,
        endpoint_row_count=1,
        validity_row_count=3,
        mandatory_status=MandatoryCohortStatus.PASS,
        reason="All reporting gates pass.",
    )
    candidate = payload.model_copy(
        update={
            "provenance": provenance,
            "cohort": cohort,
            "endpoint_rows": (endpoint,),
            "validity_rows": tuple(validity_rows),
            "cohort_summaries": (summary,),
        }
    )
    return seal_scientific_audit(ScientificAuditPayload.model_validate(candidate.model_dump(mode="python")))


def test_pilot_without_audit_is_deterministic_and_never_relabels_proxy_facts(tmp_path: Path) -> None:
    result, _, _ = _store(tmp_path)

    first = build_thesis_report_frames([result.store_dir], evidence_status="pilot")
    second = build_thesis_report_frames([result.store_dir], evidence_status="pilot")

    assert serialize_thesis_report_bundle(first) == serialize_thesis_report_bundle(second)
    assert first["audit_blockers"]["code"].tolist() == ["scientific_audit_absent"]
    assert set(first["facts"]["status"]) == {"pilot"}
    assert set(first["scientific_fact_registry"]["status"]) == {"unavailable"}
    assert set(first["scientific_fact_registry"]["evidence_tier"]) == {"blocked"}


def test_pilot_records_malformed_tampered_and_wrong_store_audits_as_blockers(tmp_path: Path) -> None:
    result, source_sha, split_sha = _store(tmp_path)
    malformed = tmp_path / "malformed.json"
    malformed.write_text('{"status":NaN}', encoding="utf-8")
    malformed_frames = build_thesis_report_frames(
        [result.store_dir], evidence_status="pilot", scientific_audit=malformed
    )
    assert malformed_frames["audit_blockers"].iloc[0]["code"].startswith("scientific_audit_invalid")

    wrong = _artifact(rollout_sha=_sha("wrong-store"), source_sha=source_sha, split_sha=split_sha)
    wrong_frames = build_thesis_report_frames([result.store_dir], evidence_status="pilot", scientific_audit=wrong)
    assert "wrong_rollout_store" in set(wrong_frames["audit_blockers"]["code"])
    assert set(wrong_frames["scientific_fact_registry"]["status"]) == {"unavailable"}

    tampered = wrong.model_copy(update={"bundle_sha256": _sha("tampered")})
    tampered_frames = build_thesis_report_frames([result.store_dir], evidence_status="pilot", scientific_audit=tampered)
    assert tampered_frames["audit_blockers"].iloc[0]["code"].startswith("scientific_audit_invalid")


def test_confirmatory_requires_exact_pass_audit_and_exports_ordered_provenance(tmp_path: Path) -> None:
    result, source_sha, split_sha = _store(tmp_path)
    artifact = _artifact(
        rollout_sha=result.manifest_sha256,
        source_sha=source_sha,
        split_sha=split_sha,
    )

    frames = build_thesis_report_frames([result.store_dir], evidence_status="confirmatory", scientific_audit=artifact)
    provenance = frames["audit_provenance"].iloc[0]
    assert provenance["bundle_sha256"] == artifact.bundle_sha256
    assert provenance["cohort_sha256"] == artifact.cohort.cohort_sha256
    assert provenance["source_store_sha256"] == source_sha
    assert provenance["split_manifest_sha256"] == split_sha
    assert provenance["endpoint_row_count"] == 1
    assert provenance["validity_row_count"] == 3
    assert provenance["evidence_tier"] == "confirmatory"
    assert frames["audit_blockers"].empty
    registry = frames["scientific_fact_registry"]
    assert registry["evidence_id"].tolist() == sorted(registry["evidence_id"].tolist())
    assert len(registry) == len(reporting._SCIENTIFIC_FACT_REGISTRY)
    assert not registry.duplicated(["store_id", "evidence_id"]).any()
    registry_by_id = registry.set_index("evidence_id")
    assert registry_by_id.loc["E1", "status"] == "available"
    assert registry_by_id.loc["E2", "status"] == "unavailable"
    assert registry_by_id.loc["E2", "reason"] == "raw_qh_not_estimable"
    assert registry_by_id.loc["E3", "status"] == "unavailable"
    assert registry_by_id.loc["E4", "status"] == "unavailable"
    assert registry_by_id.loc["E7", "reason"] == "scene_cluster_ci_gate_not_met"
    assert registry_by_id.loc["V7", "status"] == "available"
    assert registry_by_id.loc["V8", "status"] == "available"
    assert set(frames["facts"]["status"]) == {"pilot"}
    assert serialize_thesis_report_bundle(frames) == serialize_thesis_report_bundle(
        build_thesis_report_frames([result.store_dir], evidence_status="confirmatory", scientific_audit=artifact)
    )


@pytest.mark.parametrize("case", ["absent", "fail", "wrong_store", "wrong_source", "incomplete_validity"])
def test_confirmatory_rejects_every_nonadmissible_audit(tmp_path: Path, case: str) -> None:
    result, source_sha, split_sha = _store(tmp_path)
    reference: ScientificAuditArtifact | None
    if case == "absent":
        reference = None
    elif case == "fail":
        reference = _artifact(
            rollout_sha=result.manifest_sha256,
            source_sha=source_sha,
            split_sha=split_sha,
            endpoint_comparator_offset=0.1,
        )
    elif case == "wrong_store":
        reference = _artifact(rollout_sha=_sha("wrong"), source_sha=source_sha, split_sha=split_sha)
    elif case == "wrong_source":
        reference = _artifact(
            rollout_sha=result.manifest_sha256,
            source_sha=_sha("wrong-source"),
            split_sha=split_sha,
        )
    else:
        reference = _artifact(
            rollout_sha=result.manifest_sha256,
            source_sha=source_sha,
            split_sha=split_sha,
            complete_validity=False,
        )

    with pytest.raises(ValueError, match="Confirmatory"):
        build_thesis_report_frames([result.store_dir], evidence_status="confirmatory", scientific_audit=reference)


def test_confirmatory_path_rejects_duplicate_nonfinite_and_hash_mismatch(tmp_path: Path) -> None:
    result, source_sha, split_sha = _store(tmp_path)
    artifact = _artifact(
        rollout_sha=result.manifest_sha256,
        source_sha=source_sha,
        split_sha=split_sha,
    )
    valid_path = tmp_path / "audit.json"
    write_scientific_audit(
        valid_path, ScientificAuditPayload.model_validate(artifact.model_dump(exclude={"bundle_sha256"}))
    )
    valid_text = valid_path.read_text(encoding="utf-8")
    variants = {
        "duplicate": valid_text.replace('{"artifact_role"', '{"status":"pass","artifact_role"', 1),
        "nonfinite": valid_text.replace('"observed_distinct_scenes":1', '"observed_distinct_scenes":NaN', 1),
        "hash": valid_text.replace(artifact.bundle_sha256, _sha("wrong-hash"), 1),
    }
    for name, content in variants.items():
        path = tmp_path / f"{name}.json"
        path.write_text(content, encoding="utf-8")
        with pytest.raises(ValueError, match="Confirmatory"):
            build_thesis_report_frames([result.store_dir], evidence_status="confirmatory", scientific_audit=path)


def test_reporting_never_imports_or_executes_the_audit_pipeline() -> None:
    source = inspect.getsource(reporting)
    assert "oracle.pipelines" not in source
    assert "rollout_audit" not in source


def test_reporting_readiness_exactly_matches_full_and_incomplete_validity_gates(tmp_path: Path) -> None:
    result, source_sha, split_sha = _store(tmp_path)
    full = _artifact(
        rollout_sha=result.manifest_sha256,
        source_sha=source_sha,
        split_sha=split_sha,
    )
    incomplete = _artifact(
        rollout_sha=result.manifest_sha256,
        source_sha=source_sha,
        split_sha=split_sha,
        complete_validity=False,
    )

    assert scientific_report_blockers(result.store_dir, full) == ()
    blockers = scientific_report_blockers(result.store_dir, incomplete)
    assert any("required_validity_contract_incomplete" in blocker for blocker in blockers)
