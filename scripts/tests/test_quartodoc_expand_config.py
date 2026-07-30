"""Regression tests for worktree-local Quartodoc config expansion."""

from scripts.quartodoc_expand_config import discover_modules


def test_qh_modules_are_discovered_for_api_generation() -> None:
    discovered = {name for name, _is_package in discover_modules()}
    qh_modules = {
        name
        for name in discovered
        if name.startswith(("data_handling.qh", "lightning.qh", "rollouts.qh"))
        or name == "vin.models.target_finite_horizon"
    }

    assert qh_modules == {
        "data_handling.qh",
        "lightning.qh_datamodule",
        "lightning.qh_module",
        "rollouts.qh_reader",
        "vin.models.target_finite_horizon",
    }
