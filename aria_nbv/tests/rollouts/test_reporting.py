"""Deterministic rollout reporting tests."""

# ruff: noqa: S101

from __future__ import annotations

import hashlib
import json

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
    _corpus_temporal_summary,
    build_thesis_report_frames,
    serialize_thesis_report_bundle,
    write_thesis_report_bundle,
)
from aria_nbv.rollouts.zarr_store import RolloutZarrStoreReader, write_rollout_zarr_store
from tests.rollout_fixtures import build_rollout_records


def test_corpus_temporal_summary_facets_outer_contracts(monkeypatch) -> None:
    """Outer compatibility fields stay separate from the inner temporal vocabulary."""

    def contract(_frames, store_id, profile):
        suffix = "a" if store_id == "store-a" else "b"
        return {"id": f"contract-{suffix}", "label": f"contract-{suffix}", "profile": profile}

    monkeypatch.setattr("aria_nbv.rollouts.reporting._persisted_rollout_contract", contract)
    steps = pd.DataFrame(
        [
            {
                "step_index": 0,
                "policy": "temperature_softmax",
                "temperature": 1.0,
                "horizon": 1,
                "branch_factor": 1,
                "beam_width": 1,
                "cumulative_target_root_gain": 0.1,
                "selected_target_root_gain": 0.1,
                "selected_probability": 1.0,
                "selected_entropy": 0.0,
                "cumulative_target_rri": 0.1,
                "num_valid_candidates": 10,
                "invalid_fraction": 0.0,
            }
        ]
    )
    frames = [{"steps": steps.copy()}, {"steps": steps.copy()}]
    included = [
        {"path": "/a", "store_id": "store-a", "profile": "profile-a"},
        {"path": "/b", "store_id": "store-b", "profile": "profile-b"},
    ]

    summary = _corpus_temporal_summary(frames, included)

    assert set(summary["contract_id"]) == {"contract-a", "contract-b"}
    assert set(summary["profile"]) == {"profile-a", "profile-b"}
    assert set(summary["store_count"]) == {1}


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

    frames = build_thesis_report_frames([result.store_dir], evidence_status="confirmatory")

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
        evidence_status="confirmatory",
    )
    rebuilt_frames = build_thesis_report_frames(
        [second_store, first_store],
        sidecar_paths=[second_sidecar, first_sidecar],
        evidence_status="confirmatory",
    )

    assert serialize_thesis_report_bundle(first_frames) == serialize_thesis_report_bundle(rebuilt_frames)
    assert len(first_frames["sidecars"]) == 1
    assert first_frames["sidecars"]["sha256"].nunique() == 1
    assert first_frames["sidecars"]["sidecar_id"].nunique() == 1
    assert first_frames["sidecars"].iloc[0]["path"] == "evidence.json"
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
                "status": "confirmatory",
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
        evidence_status="confirmatory",
    )

    promoted = frames["facts"].set_index("key")
    for key, value, unit, n, aggregation in facts:
        row = promoted.loc[key]
        assert row["store_id"] == result.manifest_sha256
        assert row["value"] == value
        assert row["unit"] == unit
        assert row["n"] == n
        assert row["aggregation"] == aggregation
        assert row["status"] == "confirmatory"
        assert row["source"].startswith("analysis/paired_policy.json|sidecar:")
    assert frames["sidecars"].iloc[0]["name"] == "paired-policy-analysis"
    assert frames["sidecars"].iloc[0]["path"] == "paired-policy-analysis"
    assert set(frames["sidecar_values"]["sidecar_id"]) == {frames["sidecars"].iloc[0]["sidecar_id"]}


@pytest.mark.parametrize(
    ("payload_patch", "message"),
    [
        ({"schema_version": "wrong-version"}, "schema_version"),
        ({"status": "pilot"}, "status"),
        ({"facts": []}, "non-empty"),
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
        "status": "confirmatory",
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
            evidence_status="confirmatory",
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
                "status": "confirmatory",
                "facts": [fact],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises((TypeError, ValueError), match=message):
        build_thesis_report_frames(
            [result.store_dir],
            sidecar_paths=[sidecar],
            evidence_status="confirmatory",
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
                    "status": "confirmatory",
                    "facts": facts,
                }
            ),
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match=message):
            build_thesis_report_frames(
                [result.store_dir],
                sidecar_paths=[sidecar],
                evidence_status="confirmatory",
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
