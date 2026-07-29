"""Regression tests for worktree-local Quartodoc config expansion."""

from scripts.quartodoc_expand_config import discover_modules


def test_qh_modules_are_discovered_for_api_generation() -> None:
    discovered = {name for name, _is_package in discover_modules()}

    assert {
        "data_handling.offline.actor",
        "data_handling.qh",
        "lightning.qh_cli",
        "lightning.qh_datamodule",
        "lightning.qh_experiment",
        "lightning.qh_module",
        "rollouts.qh_reader",
        "vin.models.target_finite_horizon",
    } <= discovered
