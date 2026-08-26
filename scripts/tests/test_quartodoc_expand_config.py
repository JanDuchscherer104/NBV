"""Regression tests for worktree-local Quartodoc config expansion."""

from scripts.quartodoc_expand_config import discover_modules


def test_qh_modules_are_discovered_for_api_generation() -> None:
    discovered = {name for name, _is_package in discover_modules()}
    qh_modules = {name for name in discovered if name.startswith(("data_handling.qh", "lightning.qh", "rollouts.qh"))}

    assert qh_modules == {
        "data_handling.qh_data",
        "data_handling.qh_data.batching",
        "data_handling.qh_data.dataset",
        "data_handling.qh_data.materialization",
        "data_handling.qh_data.views",
        "lightning.qh_datamodule",
        "lightning.qh_experiment",
        "lightning.qh_module",
        "lightning.qh_q2_certification",
        "rollouts.qh_geometry",
        "rollouts.qh_reader",
    }


def test_renamed_data_modules_are_discovered_for_api_generation() -> None:
    discovered = {name for name, _is_package in discover_modules()}

    assert {name for name in discovered if name.startswith("data_handling.ase_efm")} == {
        "data_handling.ase_efm",
        "data_handling.ase_efm.dataset",
        "data_handling.ase_efm.loader",
        "data_handling.ase_efm.views",
    }
    assert {name for name in discovered if name.startswith("data_handling.vin_store")} == {
        "data_handling.vin_store",
        "data_handling.vin_store.adapter",
        "data_handling.vin_store.batch",
        "data_handling.vin_store.dataset",
        "data_handling.vin_store.diagnostics",
        "data_handling.vin_store.format",
        "data_handling.vin_store.info_cli",
        "data_handling.vin_store.inventory",
        "data_handling.vin_store.source",
        "data_handling.vin_store.store",
        "data_handling.vin_store.target_inventory",
        "data_handling.vin_store.views",
        "data_handling.vin_store.writer",
    }
