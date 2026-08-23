"""Deterministic rollout reporting tests."""

# ruff: noqa: S101

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest
import zarr
from pandas.testing import assert_frame_equal
from typer.testing import CliRunner

pytest.importorskip("efm3d")

from aria_nbv.rollouts.info_cli import app as rollouts_info_app
from aria_nbv.rollouts.inspection import (
    candidate_group_summary_rows,
    rollout_statistics,
    rollout_step_objective_rows,
    rollout_tree_summary_rows,
    runtime_storage_statistics,
    selected_depth_summary_rows,
    suspicious_rollout_rows,
    target_audit_rows,
    validity_waterfall_rows,
)
from aria_nbv.rollouts.manifest import RolloutStoreInvocation, RolloutStoreManifestContext
from aria_nbv.rollouts.reporting import (
    ANALYSIS_FACT_SIDECAR_VERSION,
    THESIS_REPORT_TABLE_COLUMNS,
    build_thesis_report_frames,
    deserialize_thesis_report_bundle,
    serialize_thesis_report_bundle,
    validate_thesis_report_provenance,
    write_thesis_report_bundle,
)
from aria_nbv.rollouts.zarr_store import RolloutZarrStoreReader, RolloutZarrWriteResult, write_rollout_zarr_store
from tests.rollout_fixtures import build_rollout_records


def test_report_groups_materialize_candidate_audit_once_per_store(tmp_path, monkeypatch) -> None:
    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr", build_rollout_records(horizon=2, num_samples=6, seed=71)
    )
    import aria_nbv.rollouts.reporting as reporting

    original = reporting.candidate_audit_rows
    calls = 0

    def spy(reader):
        nonlocal calls
        calls += 1
        return original(reader)

    monkeypatch.setattr(reporting, "candidate_audit_rows", spy)
    frames = build_thesis_report_frames([result.store_dir], evidence_status="pilot")
    assert calls == 1
    assert len(frames["candidate_groups"]) > 0


def test_rollout_statistics_match_cli_stats_payload(tmp_path, capsys) -> None:
    """The report seam and CLI should expose the same compact statistics."""

    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr",
        build_rollout_records(horizon=2, num_samples=6, seed=71),
    )
    capsys.readouterr()
    reader = RolloutZarrStoreReader(result.store_dir)

    cli_result = CliRunner().invoke(
        rollouts_info_app,
        ["--store", str(result.store_dir), "--stats", "--json"],
    )

    assert cli_result.exit_code == 0
    assert json.loads(cli_result.output)["stats"] == rollout_statistics(
        reader,
        manifest_payload=reader.manifest(),
    )


def test_serialized_facts_and_storage_match_cli_payload(tmp_path, capsys) -> None:
    """Selected thesis facts and runtime storage should retain CLI semantics end to end."""

    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr",
        build_rollout_records(horizon=2, num_samples=6, seed=76),
    )
    capsys.readouterr()
    cli_result = CliRunner().invoke(
        rollouts_info_app,
        ["--store", str(result.store_dir), "--preflight", "--json"],
    )
    assert cli_result.exit_code == 0
    cli_payload = json.loads(cli_result.output)

    frames = build_thesis_report_frames([result.store_dir], evidence_status="pilot")
    bundle = json.loads(serialize_thesis_report_bundle(frames))
    statistics = {row["key"]: _typed_row_value(row) for row in bundle["tables"]["statistics"]["rows"]}
    facts = {row["key"]: row for row in bundle["tables"]["facts"]["rows"]}

    assert statistics["candidate_validity.valid"] == cli_payload["stats"]["candidate_validity"]["valid"]
    assert statistics["selected.path_length_m.mean"] == pytest.approx(
        cli_payload["stats"]["selected"]["path_length_m"]["mean"]
    )
    assert facts["candidate_validity.fraction"]["value"] == pytest.approx(
        cli_payload["stats"]["candidate_validity"]["fraction"]
    )
    assert facts["candidate_validity.fraction"]["n"] == cli_payload["stats"]["candidate_validity"]["total"]
    assert facts["candidate_validity.fraction"]["unit"] == "fraction"
    assert facts["candidate_validity.fraction"]["aggregation"] == "fraction"
    assert facts["candidate_validity.fraction"]["status"] == "pilot"
    assert (
        runtime_storage_statistics(
            result.store_dir,
            candidate_count=result.num_candidates,
        )
        == cli_payload["preflight"]["storage"]
    )
    assert bundle["tables"]["runtime_storage"]["rows"][0] == {
        "store_id": frames["stores"].iloc[0]["store_id"],
        **cli_payload["preflight"]["storage"],
        "status": "pilot",
        "source": "inspection.runtime_storage_statistics",
    }


def test_serialized_report_deserializes_through_domain_owner(tmp_path) -> None:
    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr", build_rollout_records(horizon=1, num_samples=6, seed=77)[:1]
    )
    frames = build_thesis_report_frames([result.store_dir], evidence_status="pilot")
    payload = serialize_thesis_report_bundle(frames)
    assert json.loads(payload)["source_revision"] is None
    rebuilt = deserialize_thesis_report_bundle(payload)
    for name in THESIS_REPORT_TABLE_COLUMNS:
        assert tuple(rebuilt[name].columns) == THESIS_REPORT_TABLE_COLUMNS[name]
    assert serialize_thesis_report_bundle(rebuilt) == payload


@pytest.mark.parametrize(
    "mutation",
    [
        lambda payload: payload.update(fixture_notice="synthetic"),
        lambda payload: payload.pop("source_revision"),
        lambda payload: payload["tables"]["facts"]["rows"][0].update(extra=True),
        lambda payload: payload["tables"]["stores"]["rows"][0].update(store_id=["wrong-type"]),
    ],
)
def test_serialized_report_rejects_envelope_row_and_scalar_drift(tmp_path, mutation) -> None:
    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr", build_rollout_records(horizon=1, num_samples=6, seed=78)[:1]
    )
    payload = json.loads(
        serialize_thesis_report_bundle(build_thesis_report_frames([result.store_dir], evidence_status="pilot"))
    )
    mutation(payload)
    with pytest.raises(ValueError):
        deserialize_thesis_report_bundle(payload)


def test_report_bundle_round_trips_unavailable_discounted_return(tmp_path) -> None:
    result = write_rollout_zarr_store(
        tmp_path / "discounted-unavailable.zarr",
        build_rollout_records(horizon=1, num_samples=6, seed=902)[:1],
    )
    root = zarr.open_group(result.store_dir, mode="a")
    root.attrs["return_semantics"] = "unsupported"
    root["q_h"].attrs["return_semantics"] = "unsupported"

    frames = build_thesis_report_frames([result.store_dir], evidence_status="pilot")
    payload = json.loads(serialize_thesis_report_bundle(frames))
    rows = payload["tables"]["discounted_return"]["rows"]
    assert len(rows) == 1
    assert rows[0]["available"] is False
    assert rows[0]["contract_status"] == "unavailable"
    assert rows[0]["reason"] == "unsupported return_semantics='unsupported'"


@pytest.mark.parametrize("gamma", [None, np.nan, -0.1, 1.1])
def test_report_bundle_fails_closed_for_invalid_discount_gamma(tmp_path, monkeypatch, gamma) -> None:
    result = write_rollout_zarr_store(
        tmp_path / "discounted-invalid-gamma.zarr",
        build_rollout_records(horizon=1, num_samples=6, seed=904)[:1],
    )
    accepted_validation = RolloutZarrStoreReader(result.store_dir).validate()
    root = zarr.open_group(result.store_dir, mode="a")
    root.attrs["discount_gamma"] = gamma
    root["q_h"].attrs["discount_gamma"] = gamma
    monkeypatch.setattr(RolloutZarrStoreReader, "validate", lambda _self: accepted_validation)

    frames = build_thesis_report_frames([result.store_dir], evidence_status="pilot")
    row = frames["discounted_return"].iloc[0]

    assert not bool(row["available"])
    assert row["contract_status"] == "unavailable"
    assert "discount_gamma" in str(row["reason"])


def test_report_headroom_summary_preserves_proxy_provenance(tmp_path) -> None:
    result = write_rollout_zarr_store(
        tmp_path / "headroom-provenance.zarr",
        build_rollout_records(horizon=1, num_samples=6, seed=903)[:1],
    )

    frames = build_thesis_report_frames([result.store_dir], evidence_status="pilot")

    summary = frames["oracle_headroom_summary"]
    assert set(summary["evidence_class"]) == {"diagnostic_proxy"}
    assert set(summary["metric_source"]) == {"final_cumulative_target_root_gain"}
    assert set(summary["endpoint_kind"]) == {"persisted_chain_terminal_step"}
    assert not summary["independent_endpoint_evaluation"].any()
    for table in ("reconstruction_metrics", "reconstruction_endpoints", "reconstruction_endpoint_summary"):
        reconstruction = frames[table]
        assert set(reconstruction["evidence_class"]) == {"diagnostic_proxy"}
        assert set(reconstruction["metric_source"]) == {"rollout_step_objective_rows"}
        assert set(reconstruction["endpoint_kind"]) == {"persisted_chain_terminal_step"}
        assert not reconstruction["independent_endpoint_evaluation"].any()


def test_streamlit_inspection_rows_map_identically_into_bundle_frames(tmp_path) -> None:
    """Report tables should be exact projections of the row builders used by Streamlit."""

    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr",
        build_rollout_records(horizon=2, num_samples=6, seed=77)[:1],
    )
    reader = RolloutZarrStoreReader(result.store_dir)
    frames = build_thesis_report_frames([result.store_dir], evidence_status="pilot")
    store_id = str(frames["stores"].iloc[0]["store_id"])
    expected_rows = {
        "targets": target_audit_rows(reader),
        "validity": validity_waterfall_rows(reader),
        "steps": rollout_step_objective_rows(reader),
        "rollout_tree": rollout_tree_summary_rows(reader),
        "selected_depth": selected_depth_summary_rows(reader, limit=None),
    }
    for name, rows in expected_rows.items():
        expected = _sorted_expected_frame(name, [{"store_id": store_id, **row} for row in rows])
        assert_frame_equal(frames[name], expected, check_dtype=False)

    group_rows = []
    for group_by in ("position", "strategy", "mixture", "invalid_reason", "policy"):
        for row in candidate_group_summary_rows(reader, group_by=group_by):
            row = dict(row)
            group = row.pop(group_by)
            group_rows.append({"store_id": store_id, "group_by": group_by, "group": group, **row})
    assert_frame_equal(
        frames["candidate_groups"],
        _sorted_expected_frame("candidate_groups", group_rows),
        check_dtype=False,
    )


def test_failures_projection_matches_shared_suspicious_rows(tmp_path) -> None:
    """Failure rows should retain the shared inspection predicates and evidence status."""

    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr",
        build_rollout_records(horizon=1, num_samples=6, seed=78)[:1],
    )
    root = zarr.open_group(result.store_dir, mode="a")
    selected = np.asarray(root["candidates/selected_mask"], dtype=np.bool_).reshape(-1)
    selected_row = int(np.flatnonzero(selected)[0])
    root["candidate_diagnostics/motion_step_length_m"][selected_row] = np.asarray(99.0, dtype=np.float32)
    reader = RolloutZarrStoreReader(result.store_dir)

    frames = build_thesis_report_frames([result.store_dir], evidence_status="pilot")
    store_id = str(frames["stores"].iloc[0]["store_id"])
    expected = _sorted_expected_frame(
        "failures",
        [
            {
                "store_id": store_id,
                **row,
                "status": "pilot",
                "source": "inspection.suspicious_rollout_rows",
            }
            for row in suspicious_rollout_rows(reader)
        ],
    )

    assert not frames["failures"].empty
    assert_frame_equal(frames["failures"], expected, check_dtype=False)


def test_permuted_inputs_and_independent_rebuilds_are_byte_stable(tmp_path) -> None:
    """Input ordering and fresh DataFrame objects should not affect bundle bytes."""

    first_store = write_rollout_zarr_store(
        tmp_path / "a.zarr",
        build_rollout_records(horizon=1, num_samples=6, seed=79)[:1],
    ).store_dir
    second_store = write_rollout_zarr_store(
        tmp_path / "b.zarr",
        build_rollout_records(horizon=1, num_samples=6, seed=80)[:1],
    ).store_dir
    first_sidecar = tmp_path / "first" / "evidence.json"
    second_sidecar = tmp_path / "second" / "evidence.json"
    first_sidecar.parent.mkdir()
    second_sidecar.parent.mkdir()
    content = json.dumps({"same": 1}, sort_keys=True)
    first_sidecar.write_text(content, encoding="utf-8")
    second_sidecar.write_text(content, encoding="utf-8")

    first_frames = build_thesis_report_frames(
        [first_store, second_store],
        sidecar_paths=[first_sidecar, second_sidecar],
        evidence_status="pilot",
    )
    rebuilt_frames = build_thesis_report_frames(
        [second_store, first_store],
        sidecar_paths=[second_sidecar, first_sidecar],
        evidence_status="pilot",
    )

    assert serialize_thesis_report_bundle(first_frames) == serialize_thesis_report_bundle(rebuilt_frames)
    assert len(first_frames["sidecars"]) == 2
    assert first_frames["sidecars"]["sha256"].nunique() == 1
    assert first_frames["sidecars"]["sidecar_id"].nunique() == 2
    assert set(first_frames["sidecars"]["path"]) == {"first/evidence.json", "second/evidence.json"}
    assert str(tmp_path) not in serialize_thesis_report_bundle(first_frames).decode()


def test_same_name_different_content_sidecars_remain_distinct(tmp_path) -> None:
    """Portable sidecar identity should distinguish content collisions."""

    store = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr",
        build_rollout_records(horizon=1, num_samples=6, seed=81)[:1],
    ).store_dir
    first_sidecar = tmp_path / "first" / "evidence.json"
    second_sidecar = tmp_path / "second" / "evidence.json"
    first_sidecar.parent.mkdir()
    second_sidecar.parent.mkdir()
    first_sidecar.write_text('{"value":1}', encoding="utf-8")
    second_sidecar.write_text('{"value":2}', encoding="utf-8")

    frames = build_thesis_report_frames(
        [store],
        sidecar_paths=[first_sidecar, second_sidecar],
        evidence_status="pilot",
    )

    assert len(frames["sidecars"]) == 2
    assert set(frames["sidecars"]["name"]) == {"evidence.json"}
    assert frames["sidecars"]["sha256"].nunique() == 2
    assert frames["sidecars"]["sidecar_id"].nunique() == 2


def test_nested_sidecars_round_trip_physical_paths_facts_and_artifacts(tmp_path: Path) -> None:
    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr", build_rollout_records(horizon=1, num_samples=6, seed=8632)[:1]
    )
    sidecars = []
    for directory, logical_name, key, value in (
        (tmp_path / "left" / "nested", "left-analysis", "left.metric", 1.0),
        (tmp_path / "right" / "nested", "right-analysis", "right.metric", 2.0),
    ):
        directory.mkdir(parents=True)
        sidecar = _empirical_sidecar(directory, result).rename(directory / "evidence.json")
        artifact = directory / "artifact.txt"
        (directory / "analysis" / "artifact.txt").rename(artifact)
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
        payload["logical_name"] = logical_name
        payload["empirical_results"][0]["result_id"] = f"{logical_name}-result"
        payload["facts"] = [
            {
                "store_id": result.manifest_sha256,
                "key": key,
                "value": value,
                "unit": "fraction",
                "n": 1,
                "aggregation": "single",
                "provenance": f"{logical_name}/facts.json",
            }
        ]
        sidecar.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        sidecars.append(sidecar)

    frames = build_thesis_report_frames([result.store_dir], sidecar_paths=sidecars, evidence_status="pilot")
    payload = serialize_thesis_report_bundle(frames)
    rebuilt = deserialize_thesis_report_bundle(payload)
    validated = validate_thesis_report_provenance(rebuilt, evidence_root=tmp_path)

    assert set(validated["sidecars"]["path"]) == {
        "left/nested/evidence.json",
        "right/nested/evidence.json",
    }
    assert set(validated["sidecars"]["name"]) == {"left-analysis", "right-analysis"}
    assert validated["sidecars"]["sidecar_id"].nunique() == 2
    assert set(validated["facts"]["key"]) >= {"left.metric", "right.metric"}
    assert set(validated["empirical_results"]["artifact_path"]) == {"artifact.txt"}
    assert serialize_thesis_report_bundle(validated) == payload


def test_report_frames_reject_duplicate_physical_stores_with_same_store_id(tmp_path: Path) -> None:
    result = write_rollout_zarr_store(
        tmp_path / "original.zarr", build_rollout_records(horizon=1, num_samples=6, seed=8633)[:1]
    )
    duplicate = tmp_path / "duplicate.zarr"
    shutil.copytree(result.store_dir, duplicate)

    with pytest.raises(ValueError, match="duplicate store_id identities"):
        build_thesis_report_frames([result.store_dir, duplicate], evidence_status="pilot")


def test_report_frames_preserve_parameters_sidecars_missingness_and_provenance(tmp_path) -> None:
    """Resolved manifests and optional sidecars should remain typed and attributable."""

    context = RolloutStoreManifestContext(
        writer_config={
            "max_samples": 2,
            "threshold": 0.125,
            "enabled": True,
            "optional_limit": None,
            "candidate_mixture": {"components": [{"name": "forward", "count": 4}]},
        },
        invocation=RolloutStoreInvocation(
            mode="cli",
            config_path=".configs/reporting_fixture.toml",
            raw_toml_sha256="config-sha256",
        ),
        runtime={"git": {"commit": "deadbeef", "dirty": False}},
    )
    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr",
        build_rollout_records(horizon=1, num_samples=6, seed=72)[:1],
        manifest_context=context,
    )
    sidecar = tmp_path / "pilot-audit.json"
    sidecar.write_text(
        json.dumps({"metric": 1.5, "missing": None, "records": [{"count": 3, "accepted": True}]}),
        encoding="utf-8",
    )

    frames = build_thesis_report_frames(
        [result.store_dir],
        sidecar_paths=[sidecar],
        evidence_status="pilot",
    )

    assert tuple(frames) == tuple(THESIS_REPORT_TABLE_COLUMNS)
    assert all(tuple(frames[name].columns) == columns for name, columns in THESIS_REPORT_TABLE_COLUMNS.items())
    parameters = frames["parameters"].set_index("key")
    assert parameters.loc["writer_config.max_samples", "value_int"] == 2
    assert parameters.loc["writer_config.threshold", "value_float"] == pytest.approx(0.125)
    assert parameters.loc["writer_config.enabled", "value_bool"]
    assert parameters.loc["writer_config.optional_limit", "is_missing"]
    assert "raw_toml_text" not in parameters.index
    assert parameters.loc["invocation.raw_toml_sha256", "value_text"] == "config-sha256"

    sidecar_values = frames["sidecar_values"].set_index("key")
    assert sidecar_values.loc["metric", "value_float"] == pytest.approx(1.5)
    assert sidecar_values.loc["missing", "is_missing"]
    assert sidecar_values.loc["records[0].count", "value_int"] == 3
    assert sidecar_values.loc["records[0].accepted", "value_bool"]
    expected_hash = hashlib.sha256(sidecar.read_bytes()).hexdigest()
    assert frames["sidecars"].iloc[0]["sha256"] == expected_hash
    assert frames["sidecars"].iloc[0]["path"] == sidecar.name
    assert frames["sidecars"].iloc[0]["status"] == "pilot"
    assert frames["stores"].iloc[0]["manifest_sha256"] == result.manifest_sha256
    assert set(frames["facts"]["status"]) == {"pilot"}
    assert set(frames["facts"]["source"]) == {"inspection.rollout_statistics"}


def test_thesis_report_bundle_is_strict_compact_and_byte_stable(tmp_path) -> None:
    """Identical report frames should produce identical finite JSON bytes and digests."""

    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr",
        build_rollout_records(horizon=1, num_samples=6, seed=73)[:1],
    )
    frames = build_thesis_report_frames([result.store_dir], evidence_status="pilot")

    first = serialize_thesis_report_bundle(frames)
    second = serialize_thesis_report_bundle(frames)
    first_path = tmp_path / "first.json"
    second_path = tmp_path / "second.json"
    first_digest = write_thesis_report_bundle(first_path, frames)
    second_digest = write_thesis_report_bundle(second_path, frames)

    assert first == second == first_path.read_bytes() == second_path.read_bytes()
    assert first_digest == second_digest == hashlib.sha256(first).hexdigest()
    assert b'": "' not in first
    assert b":NaN" not in first
    assert b":Infinity" not in first
    payload = json.loads(first)
    assert payload["tables"]["parameters"]["columns"] == list(THESIS_REPORT_TABLE_COLUMNS["parameters"])
    assert payload["bundle_role"] == "evidence"
    assert any(row["is_missing"] and row["value_text"] is None for row in payload["tables"]["parameters"]["rows"])

    invalid = dict(frames)
    invalid["validity"] = frames["validity"].copy()
    invalid["validity"].loc[0, "fraction_of_full"] = np.inf
    with pytest.raises(ValueError, match="non-finite"):
        serialize_thesis_report_bundle(invalid)


def test_thesis_report_bundle_rejects_schema_drift(tmp_path) -> None:
    """Bundle serialization should fail when a named frame changes shape."""

    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr",
        build_rollout_records(horizon=1, num_samples=6, seed=74)[:1],
    )
    frames = build_thesis_report_frames([result.store_dir], evidence_status="pilot")
    invalid = dict(frames)
    invalid["stores"] = frames["stores"].drop(columns="manifest_sha256")

    with pytest.raises(ValueError, match="columns"):
        serialize_thesis_report_bundle(invalid)


def test_report_frames_reject_missing_optional_sidecar(tmp_path) -> None:
    """Optional means caller-selected, not silently ignored when selected."""

    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr",
        build_rollout_records(horizon=1, num_samples=6, seed=75)[:1],
    )

    with pytest.raises(FileNotFoundError):
        build_thesis_report_frames(
            [result.store_dir],
            sidecar_paths=[tmp_path / "missing.json"],
            evidence_status="pilot",
        )

    with pytest.raises(ValueError, match="evidence_status"):
        build_thesis_report_frames([result.store_dir], evidence_status="draft")  # type: ignore[arg-type]


def test_analysis_fact_sidecar_promotes_typed_facts_with_stable_provenance(tmp_path) -> None:
    """A versioned analysis envelope should promote facts without losing its audit rows."""

    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr",
        build_rollout_records(horizon=1, num_samples=6, seed=82)[:1],
    )
    sidecar = tmp_path / "machine-specific" / "analysis.json"
    sidecar.parent.mkdir()
    facts = [
        ("study.population.scenes", 5, "count", 5, "count"),
        ("candidate_support.no_valid_action_failures", 0, "count", 50, "count"),
        ("policy.paired_scene_endpoint.effect", 0.12, "fraction", 5, "paired_mean"),
        ("headroom_gate.passed", True, "bool", 5, "decision"),
        ("runtime.wall_time_s", 12.5, "s", 1, "total"),
        ("storage.total_bytes", 4096, "byte", 1, "total"),
    ]
    sidecar.write_text(
        json.dumps(
            {
                "schema_version": ANALYSIS_FACT_SIDECAR_VERSION,
                "bundle_role": "analysis_facts",
                "logical_name": "paired-policy-analysis",
                "status": "pilot",
                "facts": [
                    {
                        "store_id": result.manifest_sha256,
                        "key": key,
                        "value": value,
                        "unit": unit,
                        "n": n,
                        "aggregation": aggregation,
                        "provenance": "analysis/paired_policy.json",
                    }
                    for key, value, unit, n, aggregation in facts
                ],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    frames = build_thesis_report_frames(
        [result.store_dir],
        sidecar_paths=[sidecar],
        evidence_status="pilot",
    )

    promoted = frames["facts"].set_index("key")
    for key, value, unit, n, aggregation in facts:
        row = promoted.loc[key]
        assert row["store_id"] == result.manifest_sha256
        assert row["value"] == value
        assert row["unit"] == unit
        assert row["n"] == n
        assert row["aggregation"] == aggregation
        assert row["status"] == "pilot"
        assert row["source"].startswith("analysis/paired_policy.json|sidecar:")
    assert frames["sidecars"].iloc[0]["name"] == "paired-policy-analysis"
    assert frames["sidecars"].iloc[0]["path"] == "analysis.json"
    assert set(frames["sidecar_values"]["sidecar_id"]) == {frames["sidecars"].iloc[0]["sidecar_id"]}


def test_analysis_sidecar_logical_name_round_trips_with_all_promoted_rows(tmp_path: Path) -> None:
    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr", build_rollout_records(horizon=1, num_samples=6, seed=8630)[:1]
    )
    sidecar = _empirical_sidecar(tmp_path, result)
    sidecar = sidecar.rename(tmp_path / "analysis.json")
    (tmp_path / "analysis" / "artifact.txt").rename(tmp_path / "artifact.txt")
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    payload["logical_name"] = "paired-policy-analysis"
    payload["facts"] = [
        {
            "store_id": result.manifest_sha256,
            "key": "policy.paired_scene_endpoint.effect",
            "value": 0.12,
            "unit": "fraction",
            "n": 5,
            "aggregation": "paired_mean",
            "provenance": "analysis/paired_policy.json",
        }
    ]
    sidecar.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")

    frames = build_thesis_report_frames([result.store_dir], sidecar_paths=[sidecar], evidence_status="pilot")
    serialized = serialize_thesis_report_bundle(frames)
    rebuilt = deserialize_thesis_report_bundle(serialized)
    validated = validate_thesis_report_provenance(rebuilt, evidence_root=sidecar.parent)

    sidecar_row = validated["sidecars"].iloc[0]
    assert sidecar_row["path"] == "analysis.json"
    assert sidecar_row["name"] == "paired-policy-analysis"
    assert validated["facts"].query("key == 'policy.paired_scene_endpoint.effect'")["value"].tolist() == [0.12]
    assert not validated["sidecar_values"].empty
    assert validated["empirical_results"].iloc[0]["artifact_path"] == "artifact.txt"
    assert serialize_thesis_report_bundle(validated) == serialized


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("path", "paired-policy-analysis", "does not exist"),
        ("path", "/tmp/analysis.json", "portable relative path"),
        ("name", "other-logical-name", "logical_name"),
        ("sidecar_id", "0" * 64, "sidecar_id"),
    ],
)
def test_report_provenance_rejects_sidecar_path_name_and_id_conflation(
    tmp_path: Path, field: str, value: str, message: str
) -> None:
    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr", build_rollout_records(horizon=1, num_samples=6, seed=8631)[:1]
    )
    sidecar = _empirical_sidecar(tmp_path, result).rename(tmp_path / "analysis.json")
    (tmp_path / "analysis" / "artifact.txt").rename(tmp_path / "artifact.txt")
    payload = json.loads(
        serialize_thesis_report_bundle(
            build_thesis_report_frames([result.store_dir], sidecar_paths=[sidecar], evidence_status="pilot")
        )
    )
    payload["tables"]["sidecars"]["rows"][0][field] = value

    with pytest.raises(ValueError, match=message):
        validate_thesis_report_provenance(payload, evidence_root=tmp_path)


def test_empirical_result_round_trips_strict_identity_and_missingness(tmp_path: Path) -> None:
    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr", build_rollout_records(horizon=1, num_samples=6, seed=86)[:1]
    )
    sidecar = tmp_path / "analysis" / "results.json"
    artifact = sidecar.parent / "artifact.txt"
    artifact.parent.mkdir()
    artifact.write_text("synthetic artifact", encoding="utf-8")
    artifact_sha256 = hashlib.sha256(artifact.read_bytes()).hexdigest()
    fields = {
        "result_id": "pilot-missing-1",
        "store_id": result.manifest_sha256,
        "experimental_unit": "scene",
        "denominator_name": "eligible_scenes",
        "denominator_value": 2,
        "data_identity": "unknown-source-version",
        "split_identity": "unknown-split-manifest",
        "estimand": "difference",
        "estimate": None,
        "unit": "fraction",
        "aggregation": "scene_mean",
        "uncertainty_type": "none",
        "uncertainty_lower": None,
        "uncertainty_upper": None,
        "uncertainty_inapplicable_reason": "pilot result is missing",
        "variability_source": "pilot runs",
        "comparison_family": "paired",
        "outcome": "missing",
        "status": "pilot",
        "actor_visible_inputs_json": ["actor-policy-v1"],
        "oracle_only_inputs_json": [],
        "source_revision": "1" * 40,
        "environment": "synthetic",
        "command": "pytest synthetic",
        "artifact_path": "artifact.txt",
        "artifact_sha256": artifact_sha256,
        "wall_time_s": 1.0,
        "gpu_hours": None,
        "peak_gpu_memory_bytes": None,
        "storage_bytes": 12,
        "provenance": "synthetic fixture",
        "reason": "pilot output was not produced",
    }
    sidecar.write_text(
        json.dumps(
            {
                "schema_version": ANALYSIS_FACT_SIDECAR_VERSION,
                "bundle_role": "analysis_facts",
                "status": "pilot",
                "facts": [],
                "empirical_results": [fields],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    frames = build_thesis_report_frames([result.store_dir], sidecar_paths=[sidecar], evidence_status="pilot")
    bundle = json.loads(serialize_thesis_report_bundle(frames))
    assert bundle["source_revision"] == "1" * 40
    row = bundle["tables"]["empirical_results"]["rows"][0]
    assert row["result_id"] == fields["result_id"]
    assert row["estimate"] is None and row["reason"]
    assert json.loads(row["actor_visible_inputs_json"]) == ["actor-policy-v1"]
    assert json.loads(row["oracle_only_inputs_json"]) == []
    assert row["sidecar_id"] == bundle["tables"]["sidecars"]["rows"][0]["sidecar_id"]

    validated = validate_thesis_report_provenance(
        bundle,
        evidence_root=sidecar.parent,
        expected_source_revision="1" * 40,
    )
    assert_frame_equal(validated["empirical_results"], frames["empirical_results"], check_dtype=False)


def test_empirical_results_require_one_canonical_source_revision(tmp_path: Path) -> None:
    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr", build_rollout_records(horizon=1, num_samples=6, seed=861)[:1]
    )
    sidecar = _empirical_sidecar(tmp_path, result)
    frames = build_thesis_report_frames([result.store_dir], sidecar_paths=[sidecar], evidence_status="pilot")
    mixed = {name: frame.copy() for name, frame in frames.items()}
    mixed["empirical_results"] = pd.concat(
        [
            mixed["empirical_results"],
            mixed["empirical_results"].assign(result_id="pilot-result-2", source_revision="2" * 40),
        ],
        ignore_index=True,
    )
    with pytest.raises(ValueError, match="one source_revision"):
        serialize_thesis_report_bundle(mixed)


def test_report_provenance_rejects_changed_evidence_and_relabelled_paths(tmp_path: Path) -> None:
    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr", build_rollout_records(horizon=1, num_samples=6, seed=862)[:1]
    )
    sidecar = _empirical_sidecar(tmp_path, result)
    frames = build_thesis_report_frames([result.store_dir], sidecar_paths=[sidecar], evidence_status="pilot")
    payload = json.loads(serialize_thesis_report_bundle(frames))
    with pytest.raises(ValueError, match="sidecar.*sha256"):
        sidecar.write_text(sidecar.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        validate_thesis_report_provenance(payload, evidence_root=sidecar.parent)
    sidecar.unlink()
    with pytest.raises(ValueError, match="does not exist"):
        validate_thesis_report_provenance(payload, evidence_root=sidecar.parent)

    relabelled_root = tmp_path / "relabelled"
    relabelled_root.mkdir()
    sidecar = _empirical_sidecar(relabelled_root, result)
    frames = build_thesis_report_frames([result.store_dir], sidecar_paths=[sidecar], evidence_status="pilot")
    payload = json.loads(serialize_thesis_report_bundle(frames))
    payload["tables"]["sidecars"]["rows"][0]["path"] = "../artifact.txt"
    with pytest.raises(ValueError, match="portable relative path"):
        validate_thesis_report_provenance(payload, evidence_root=sidecar.parent)

    artifact = sidecar.parent / "artifact.txt"
    artifact.write_text("changed artifact", encoding="utf-8")
    payload["tables"]["sidecars"]["rows"][0]["path"] = sidecar.name
    with pytest.raises(ValueError, match="artifact_sha256"):
        validate_thesis_report_provenance(payload, evidence_root=sidecar.parent)


def test_report_provenance_rejects_tampered_promoted_sidecar_values(tmp_path: Path) -> None:
    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr", build_rollout_records(horizon=1, num_samples=6, seed=863)[:1]
    )
    sidecar = _empirical_sidecar(tmp_path, result)
    frames = build_thesis_report_frames([result.store_dir], sidecar_paths=[sidecar], evidence_status="pilot")
    payload = json.loads(serialize_thesis_report_bundle(frames))
    sidecar_row = payload["tables"]["sidecars"]["rows"][0]
    value_row = next(
        row for row in payload["tables"]["sidecar_values"]["rows"] if row["key"] == "empirical_results[0].estimate"
    )
    value_row["value_float"] = 99.0

    with pytest.raises(ValueError, match="sidecar_values"):
        validate_thesis_report_provenance(payload, evidence_root=sidecar.parent)
    assert sidecar_row["sha256"] == hashlib.sha256(sidecar.read_bytes()).hexdigest()


def test_report_provenance_rejects_tampered_promoted_empirical_result(tmp_path: Path) -> None:
    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr", build_rollout_records(horizon=1, num_samples=6, seed=864)[:1]
    )
    sidecar = _empirical_sidecar(tmp_path, result)
    frames = build_thesis_report_frames([result.store_dir], sidecar_paths=[sidecar], evidence_status="pilot")
    payload = json.loads(serialize_thesis_report_bundle(frames))
    payload["tables"]["empirical_results"]["rows"][0]["estimate"] = 99.0

    with pytest.raises(ValueError, match="empirical_results"):
        validate_thesis_report_provenance(payload, evidence_root=sidecar.parent)


def test_report_provenance_rejects_tampered_promoted_fact(tmp_path: Path) -> None:
    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr", build_rollout_records(horizon=1, num_samples=6, seed=865)[:1]
    )
    sidecar = tmp_path / "analysis.json"
    sidecar.write_text(
        json.dumps(
            {
                "schema_version": ANALYSIS_FACT_SIDECAR_VERSION,
                "bundle_role": "analysis_facts",
                "status": "pilot",
                "facts": [
                    {
                        "store_id": result.manifest_sha256,
                        "key": "runtime.measured_wall_time_s",
                        "value": 12.5,
                        "unit": "s",
                        "n": 1,
                        "aggregation": "total",
                        "provenance": "analysis.json",
                    }
                ],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    frames = build_thesis_report_frames([result.store_dir], sidecar_paths=[sidecar], evidence_status="pilot")
    payload = json.loads(serialize_thesis_report_bundle(frames))
    sidecar_sha256 = payload["tables"]["sidecars"]["rows"][0]["sha256"]
    promoted = next(row for row in payload["tables"]["facts"]["rows"] if "|sidecar:" in row["source"])
    promoted["value"] = 99.0

    with pytest.raises(ValueError, match="facts"):
        validate_thesis_report_provenance(payload, evidence_root=sidecar.parent)
    assert sidecar_sha256 == hashlib.sha256(sidecar.read_bytes()).hexdigest()


def _empirical_sidecar(tmp_path: Path, result: RolloutZarrWriteResult, **patch: object) -> Path:
    sidecar = tmp_path / "analysis" / f"result-{len(patch)}.json"
    artifact = sidecar.parent / "artifact.txt"
    artifact.parent.mkdir(exist_ok=True)
    artifact.write_text("synthetic artifact", encoding="utf-8")
    fields = {
        "result_id": "pilot-result",
        "store_id": result.manifest_sha256,
        "experimental_unit": "scene",
        "denominator_name": "eligible_scenes",
        "denominator_value": 2,
        "data_identity": "unknown-source-version",
        "split_identity": "unknown-split-manifest",
        "estimand": "difference",
        "estimate": 0.25,
        "unit": "fraction",
        "aggregation": "scene_mean",
        "uncertainty_type": "95% CI",
        "uncertainty_lower": 0.1,
        "uncertainty_upper": 0.4,
        "uncertainty_inapplicable_reason": None,
        "variability_source": "independent pilot runs",
        "comparison_family": "paired",
        "outcome": "supporting",
        "status": "pilot",
        "actor_visible_inputs_json": ["actor-policy-v1"],
        "oracle_only_inputs_json": [],
        "source_revision": "1" * 40,
        "environment": "synthetic",
        "command": "pytest synthetic",
        "artifact_path": "artifact.txt",
        "artifact_sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
        "wall_time_s": 1.0,
        "gpu_hours": None,
        "peak_gpu_memory_bytes": None,
        "storage_bytes": 12,
        "provenance": "synthetic fixture",
        "reason": None,
    }
    fields.update(patch)
    sidecar.write_text(
        json.dumps(
            {
                "schema_version": ANALYSIS_FACT_SIDECAR_VERSION,
                "bundle_role": "analysis_facts",
                "status": fields["status"],
                "facts": [],
                "empirical_results": [fields],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return sidecar


def test_empirical_result_rejects_plausible_but_wrong_store_identity(tmp_path: Path) -> None:
    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr", build_rollout_records(horizon=1, num_samples=6, seed=95)[:1]
    )
    for field, value in (("data_identity", "dataset-v2"), ("split_identity", "held-out-pilot")):
        sidecar = _empirical_sidecar(tmp_path, result, **{field: value})
        with pytest.raises(ValueError, match=field):
            build_thesis_report_frames([result.store_dir], sidecar_paths=[sidecar], evidence_status="pilot")


def test_empirical_result_rejects_caller_sidecar_id(tmp_path: Path) -> None:
    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr", build_rollout_records(horizon=1, num_samples=6, seed=93)[:1]
    )
    sidecar = _empirical_sidecar(tmp_path, result)
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    payload["empirical_results"][0]["sidecar_id"] = "caller-supplied"
    sidecar.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    with pytest.raises(ValueError, match="fields must be"):
        build_thesis_report_frames([result.store_dir], sidecar_paths=[sidecar], evidence_status="pilot")


def test_all_empirical_outcomes_survive_serialized_bundle(tmp_path: Path) -> None:
    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr", build_rollout_records(horizon=1, num_samples=6, seed=94)[:1]
    )
    sidecar = _empirical_sidecar(tmp_path, result)
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    base = payload["empirical_results"][0]
    results = []
    for outcome in ("supporting", "negative", "failed", "missing"):
        row = {**base, "result_id": f"pilot-{outcome}", "outcome": outcome}
        if outcome in {"failed", "missing"}:
            row.update(
                estimate=None,
                uncertainty_lower=None,
                uncertainty_upper=None,
                reason=f"synthetic {outcome} result",
            )
        results.append(row)
    payload["empirical_results"] = results
    sidecar.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")

    frames = build_thesis_report_frames([result.store_dir], sidecar_paths=[sidecar], evidence_status="pilot")
    bundle = json.loads(serialize_thesis_report_bundle(frames))
    rows = bundle["tables"]["empirical_results"]["rows"]
    assert {row["outcome"] for row in rows} == {"supporting", "negative", "failed", "missing"}
    assert {row["result_id"] for row in rows} == {
        f"pilot-{outcome}" for outcome in ("supporting", "negative", "failed", "missing")
    }
    if shutil.which("typst") is None:
        pytest.skip("Typst is required for the producer-to-loader integration proof")
    bundle_path = tmp_path / "generated-report-bundle.json"
    bundle_path.write_bytes(serialize_thesis_report_bundle(frames))
    output_path = tmp_path / "report-data-smoke.pdf"
    subprocess.run(
        [
            "typst",
            "compile",
            "--root",
            "/",
            "--input",
            f"aria-thesis-data={bundle_path}",
            str(Path(__file__).parents[3] / "docs/typst/thesis/tests/report_data_smoke.typ"),
            str(output_path),
        ],
        check=True,
    )
    assert output_path.is_file()


@pytest.mark.parametrize(
    ("patch", "message"),
    [
        ({"denominator_name": "ambiguous"}, "denominator_name"),
        ({"denominator_value": 0}, "positive"),
        ({"denominator_value": float("nan")}, "finite"),
        ({"data_identity": ""}, "data_identity"),
        ({"data_identity": "unknown"}, "data/split identity"),
        ({"split_identity": ""}, "split_identity"),
        ({"split_identity": "none"}, "data/split identity"),
        ({"source_revision": ""}, "source_revision"),
        ({"source_revision": "not-a-revision"}, "source_revision"),
        ({"source_revision": "0" * 40}, "source_revision"),
        ({"artifact_path": "../artifact.txt"}, "portable relative"),
        ({"artifact_path": "/tmp/artifact.txt"}, "portable relative"),
        ({"artifact_sha256": "0" * 64}, "artifact_sha256"),
        ({"actor_visible_inputs_json": ["shared-input"], "oracle_only_inputs_json": ["shared-input"]}, "disjoint"),
        ({"uncertainty_lower": 0.5, "uncertainty_upper": 0.1}, "invalid order"),
        ({"uncertainty_lower": float("nan")}, "finite"),
        ({"uncertainty_lower": None}, "both bounds"),
    ],
)
def test_empirical_result_rejects_high_risk_provenance_and_statistics(
    tmp_path: Path, patch: dict[str, Any], message: str
) -> None:
    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr", build_rollout_records(horizon=1, num_samples=6, seed=87)[:1]
    )
    sidecar = _empirical_sidecar(tmp_path, result, **patch)
    with pytest.raises(ValueError, match=message):
        build_thesis_report_frames([result.store_dir], sidecar_paths=[sidecar], evidence_status="pilot")


@pytest.mark.parametrize("outcome", ["failed", "missing"])
def test_empirical_failed_or_missing_requires_null_estimate_and_reason(tmp_path: Path, outcome: str) -> None:
    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr", build_rollout_records(horizon=1, num_samples=6, seed=88)[:1]
    )
    sidecar = _empirical_sidecar(tmp_path, result, outcome=outcome, estimate=None, reason="not produced")
    frames = build_thesis_report_frames([result.store_dir], sidecar_paths=[sidecar], evidence_status="pilot")
    assert frames["empirical_results"].iloc[0]["outcome"] == outcome
    assert frames["empirical_results"].iloc[0]["estimate"] is None

    invalid = _empirical_sidecar(tmp_path, result, outcome=outcome, estimate=0.1, reason=None)
    with pytest.raises(ValueError, match="null estimate and reason"):
        build_thesis_report_frames([result.store_dir], sidecar_paths=[invalid], evidence_status="pilot")


def test_empirical_supporting_and_negative_results_require_uncertainty_or_rationale(tmp_path: Path) -> None:
    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr", build_rollout_records(horizon=1, num_samples=6, seed=89)[:1]
    )
    for outcome in ("supporting", "negative"):
        sidecar = _empirical_sidecar(
            tmp_path,
            result,
            outcome=outcome,
            uncertainty_lower=None,
            uncertainty_upper=None,
            variability_source="not available for this run",
            uncertainty_inapplicable_reason="single deterministic run",
        )
        frames = build_thesis_report_frames([result.store_dir], sidecar_paths=[sidecar], evidence_status="pilot")
        assert frames["empirical_results"].iloc[0]["outcome"] == outcome


def test_empirical_store_and_sidecar_joins_and_confirmatory_status_are_closed(tmp_path: Path) -> None:
    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr", build_rollout_records(horizon=1, num_samples=6, seed=90)[:1]
    )
    sidecar = _empirical_sidecar(tmp_path, result)
    frames = build_thesis_report_frames([result.store_dir], sidecar_paths=[sidecar], evidence_status="pilot")
    with pytest.raises(ValueError, match="store_id"):
        broken = {name: frame.copy() for name, frame in frames.items()}
        broken["empirical_results"].loc[0, "store_id"] = "unknown-store"
        serialize_thesis_report_bundle(broken)
    with pytest.raises(ValueError, match="sidecar_id"):
        broken = {name: frame.copy() for name, frame in frames.items()}
        broken["empirical_results"].loc[0, "sidecar_id"] = "unknown-sidecar"
        serialize_thesis_report_bundle(broken)
    with pytest.raises(ValueError, match="pilot rows"):
        broken = {name: frame.copy() for name, frame in frames.items()}
        broken["facts"].loc[0, "status"] = "pilot"
        broken["empirical_results"].loc[0, "status"] = "confirmatory"
        serialize_thesis_report_bundle(broken)


def test_empirical_result_ids_must_be_unique_across_bundle(tmp_path: Path) -> None:
    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr", build_rollout_records(horizon=1, num_samples=6, seed=96)[:1]
    )
    first = _empirical_sidecar(tmp_path, result)
    (tmp_path / "second").mkdir()
    second = _empirical_sidecar(tmp_path / "second", result, provenance="second sidecar")
    with pytest.raises(ValueError, match="duplicate result_id"):
        build_thesis_report_frames([result.store_dir], sidecar_paths=[first, second], evidence_status="pilot")


def test_report_bytes_change_for_denominator_source_and_artifact_identity(tmp_path: Path) -> None:
    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr", build_rollout_records(horizon=1, num_samples=6, seed=91)[:1]
    )
    base = _empirical_sidecar(tmp_path, result)
    base_frames = build_thesis_report_frames([result.store_dir], sidecar_paths=[base], evidence_status="pilot")
    base_bytes = serialize_thesis_report_bundle(base_frames)
    for patch in (
        {"denominator_value": 3},
        {"artifact_sha256": "1" * 64},
    ):
        sidecar = _empirical_sidecar(tmp_path, result, **patch)
        if "artifact_sha256" in patch:
            with pytest.raises(ValueError, match="artifact_sha256"):
                build_thesis_report_frames([result.store_dir], sidecar_paths=[sidecar], evidence_status="pilot")
            continue
        changed = serialize_thesis_report_bundle(
            build_thesis_report_frames([result.store_dir], sidecar_paths=[sidecar], evidence_status="pilot")
        )
        assert changed != base_bytes

    revision_frames = {name: frame.copy() for name, frame in base_frames.items()}
    revision_frames["empirical_results"].loc[0, "source_revision"] = "2" * 40
    revision_bytes = serialize_thesis_report_bundle(revision_frames)
    revision_row = json.loads(revision_bytes)["tables"]["empirical_results"]["rows"][0]
    assert revision_row["source_revision"] == "2" * 40
    assert revision_bytes != base_bytes

    second = write_rollout_zarr_store(
        tmp_path / "second.zarr", build_rollout_records(horizon=1, num_samples=6, seed=92)[:1]
    )
    assert serialize_thesis_report_bundle(
        build_thesis_report_frames([second.store_dir], evidence_status="pilot")
    ) != serialize_thesis_report_bundle(build_thesis_report_frames([result.store_dir], evidence_status="pilot"))


@pytest.mark.parametrize(
    ("payload_patch", "message"),
    [
        ({"schema_version": "wrong-version"}, "schema_version"),
        ({"status": "exploratory"}, "status"),
        ({"facts": []}, "facts or empirical_results"),
    ],
)
def test_analysis_fact_sidecar_rejects_envelope_drift(tmp_path, payload_patch, message) -> None:
    """Analysis sidecars should fail closed on schema, status, or shape drift."""

    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr",
        build_rollout_records(horizon=1, num_samples=6, seed=83)[:1],
    )
    payload = {
        "schema_version": ANALYSIS_FACT_SIDECAR_VERSION,
        "bundle_role": "analysis_facts",
        "status": "pilot",
        "facts": [
            {
                "store_id": result.manifest_sha256,
                "key": "runtime.wall_time_s",
                "value": 1.0,
                "unit": "s",
                "n": 1,
                "aggregation": "total",
                "provenance": "analysis.json",
            }
        ],
        **payload_patch,
    }
    sidecar = tmp_path / "analysis.json"
    sidecar.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        build_thesis_report_frames(
            [result.store_dir],
            sidecar_paths=[sidecar],
            evidence_status="pilot",
        )


@pytest.mark.parametrize(
    ("fact_patch", "message"),
    [
        ({"value": float("inf")}, "finite"),
        ({"n": -1}, "non-negative"),
        ({"provenance": ""}, "provenance"),
        ({"unexpected": 1}, "fields"),
    ],
)
def test_analysis_fact_sidecar_rejects_malformed_facts(tmp_path, fact_patch, message) -> None:
    """Promoted analysis facts should be finite, typed, and exact-schema."""

    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr",
        build_rollout_records(horizon=1, num_samples=6, seed=84)[:1],
    )
    fact = {
        "store_id": result.manifest_sha256,
        "key": "runtime.wall_time_s",
        "value": 1.0,
        "unit": "s",
        "n": 1,
        "aggregation": "total",
        "provenance": "analysis.json",
        **fact_patch,
    }
    sidecar = tmp_path / "analysis.json"
    sidecar.write_text(
        json.dumps(
            {
                "schema_version": ANALYSIS_FACT_SIDECAR_VERSION,
                "bundle_role": "analysis_facts",
                "status": "pilot",
                "facts": [fact],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises((TypeError, ValueError), match=message):
        build_thesis_report_frames(
            [result.store_dir],
            sidecar_paths=[sidecar],
            evidence_status="pilot",
        )


def test_analysis_fact_sidecar_rejects_duplicate_and_store_fact_conflicts(tmp_path) -> None:
    """A promoted fact identity may have exactly one authoritative source."""

    result = write_rollout_zarr_store(
        tmp_path / "rollouts.zarr",
        build_rollout_records(horizon=1, num_samples=6, seed=85)[:1],
    )
    base_fact = {
        "store_id": result.manifest_sha256,
        "key": "runtime.wall_time_s",
        "value": 1.0,
        "unit": "s",
        "n": 1,
        "aggregation": "total",
        "provenance": "analysis.json",
    }

    for facts, message in (
        ([base_fact, dict(base_fact)], "duplicate"),
        ([{**base_fact, "key": "candidate_validity.total"}], "conflicts"),
    ):
        sidecar = tmp_path / f"{message}.json"
        sidecar.write_text(
            json.dumps(
                {
                    "schema_version": ANALYSIS_FACT_SIDECAR_VERSION,
                    "bundle_role": "analysis_facts",
                    "status": "pilot",
                    "facts": facts,
                }
            ),
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match=message):
            build_thesis_report_frames(
                [result.store_dir],
                sidecar_paths=[sidecar],
                evidence_status="pilot",
            )


def test_serializer_normalizes_pandas_missing_values() -> None:
    """Pandas missing scalars should become JSON null instead of invalid tokens."""

    frames = {name: pd.DataFrame(columns=columns) for name, columns in THESIS_REPORT_TABLE_COLUMNS.items()}
    frames["parameters"] = pd.DataFrame(
        [
            {
                "store_id": "fixture",
                "key": "missing",
                "value_type": "null",
                "value_bool": pd.NA,
                "value_int": pd.NA,
                "value_float": np.nan,
                "value_text": pd.NA,
                "is_missing": True,
            }
        ],
        columns=THESIS_REPORT_TABLE_COLUMNS["parameters"],
    )

    payload = json.loads(serialize_thesis_report_bundle(frames))

    row = payload["tables"]["parameters"]["rows"][0]
    assert row["value_bool"] is None
    assert row["value_int"] is None
    assert row["value_float"] is None
    assert row["value_text"] is None


def _typed_row_value(row: dict[str, object]) -> object:
    return row.get(f"value_{row['value_type']}")


def _sorted_expected_frame(name: str, rows: list[dict[str, object]]) -> pd.DataFrame:
    columns = THESIS_REPORT_TABLE_COLUMNS[name]
    frame = pd.DataFrame(rows, columns=columns)
    if frame.empty:
        return frame
    return frame.sort_values(list(columns), kind="stable", na_position="last").reset_index(drop=True)
