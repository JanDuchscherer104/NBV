"""CLI tests for immutable VIN offline-store inspection."""

# ruff: noqa: S101

from __future__ import annotations

import json

from typer.testing import CliRunner

from aria_nbv.data_handling.vin_store.format import VinOfflineIndexRecord
from aria_nbv.data_handling.vin_store.info_cli import app as offline_info_app
from aria_nbv.data_handling.vin_store.info_cli import main as offline_info_main
from tests.data_handling.test_vin_offline_store import _write_sample_index, _write_test_store

runner = CliRunner()


def test_offline_info_default_summary_text_includes_core_fields(tmp_path, capsys) -> None:
    store = _write_test_store(tmp_path)

    offline_info_main(["--store", str(store.store_dir), "--max-samples", "2"])

    out = capsys.readouterr().out
    assert "version" in out
    assert "7" in out
    assert "candidate_count" in out
    assert "rri" in out
    assert "vin_points" in out


def test_offline_info_summary_json_includes_core_fields(tmp_path) -> None:
    store = _write_test_store(tmp_path, include_backbone=True)

    result = runner.invoke(
        offline_info_app,
        ["summary", "--store", str(store.store_dir), "--max-samples", "2", "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["version"] == 7
    assert payload["num_samples"] == 3
    assert payload["sampled_samples"] == 2
    assert payload["split_counts"] == {"train": 2, "val": 1}
    assert payload["summaries"]["candidate_count"]["count"] == 2
    assert payload["materialized_blocks"]["backbone"] is True


def test_offline_info_tree_reports_manifest_blocks(tmp_path) -> None:
    store = _write_test_store(tmp_path)

    result = runner.invoke(offline_info_app, ["tree", "--store", str(store.store_dir), "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    blocks = payload["shards"][0]["blocks"]
    rri_block = next(block for block in blocks if block["name"] == "oracle.rri")
    assert rri_block["kind"] == "zarr_array"
    assert rri_block["dtype"] == "float32"
    assert rri_block["shape"] == [3, 4]
    assert rri_block["optional"] is False


def test_offline_info_samples_filters_split(tmp_path) -> None:
    store = _write_test_store(tmp_path)

    result = runner.invoke(
        offline_info_app,
        ["samples", "--store", str(store.store_dir), "--split", "val", "--limit", "1", "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["split"] == "val"
    assert payload["num_eligible"] == 1
    assert len(payload["rows"]) == 1
    assert payload["rows"][0]["split"] == "val"
    assert payload["rows"][0]["sample_key"] == "sample-2"


def test_offline_info_samples_compacts_old_ase_atek_ids(tmp_path) -> None:
    store = _write_test_store(tmp_path)
    records = VinOfflineIndexRecord.read_many(store.sample_index_path)
    records[0].sample_key = "81286::AriaSyntheticEnvironment_81286_AtekDataSample_000000"
    records[0].scene_id = "81286"
    records[0].snippet_id = "AriaSyntheticEnvironment_81286_AtekDataSample_000000"
    _write_sample_index(store.sample_index_path, records)

    json_result = runner.invoke(
        offline_info_app,
        ["samples", "--store", str(store.store_dir), "--split", "train", "--limit", "1", "--json"],
    )
    text_result = runner.invoke(
        offline_info_app,
        ["samples", "--store", str(store.store_dir), "--split", "train", "--limit", "1"],
    )
    random_result = runner.invoke(
        offline_info_app,
        ["random-index", "--store", str(store.store_dir), "--split", "train", "--seed", "1", "--json"],
    )

    assert json_result.exit_code == 0
    assert text_result.exit_code == 0
    assert random_result.exit_code == 0
    assert "AriaSyntheticEnvironment" not in json_result.output
    assert "AriaSyntheticEnvironment" not in text_result.output
    assert "AriaSyntheticEnvironment" not in random_result.output
    assert "ASE_81286_Atek_000000" in json_result.output
    assert "ASE_" in text_result.output
    assert "ASE_81286_Atek_000000" in random_result.output


def test_offline_info_random_index_is_deterministic_and_split_local(tmp_path) -> None:
    store = _write_test_store(tmp_path)

    first = runner.invoke(
        offline_info_app,
        ["random-index", "--store", str(store.store_dir), "--split", "train", "--seed", "0"],
    )
    second = runner.invoke(
        offline_info_app,
        ["random-index", "--store", str(store.store_dir), "--split", "train", "--seed", "0"],
    )

    assert first.exit_code == 0
    assert second.exit_code == 0
    assert first.output.strip() == second.output.strip()
    assert int(first.output.strip()) in {0, 1}


def test_offline_info_help_exits_cleanly() -> None:
    result = runner.invoke(offline_info_app, ["--help"])

    assert result.exit_code == 0
    assert "summary" in result.output
