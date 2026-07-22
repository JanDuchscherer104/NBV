#!/usr/bin/env python3
"""Exercise the final WP7 quantitative contract and its failure modes."""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import sys


SCRIPT = Path(__file__).resolve().parents[1] / "scaffold/check_wp7_integration.py"
SPEC = importlib.util.spec_from_file_location("check_wp7_integration", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
wp7 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = wp7
SPEC.loader.exec_module(wp7)


def rejected(
    metrics: dict[str, object], key: str, value: object, fragment: str
) -> None:
    """Require one mutated metric to fail with the expected reason."""
    changed = copy.deepcopy(metrics)
    changed[key] = value
    assert any(fragment in error for error in wp7.validate(changed))


def main() -> None:
    metrics = wp7.measure()
    assert not wp7.validate(metrics)
    rejected(metrics, "active_skill_count", 10, "exactly 9")
    rejected(metrics, "aria_model_visible_skill_count", 8, "model-visible")
    rejected(metrics, "matt_skill_count", 11, "exactly 12")
    rejected(
        metrics,
        "active_scaffold_source_loc",
        metrics["baseline_scaffold_source_loc"],
        "strictly below",
    )
    rejected(
        metrics,
        "model_visible_description_bytes",
        metrics["maximum_description_bytes"] + 1,
        "40 percent",
    )
    rejected(
        metrics,
        "declared_baseline_description_bytes",
        metrics["baseline_description_bytes"] + 1,
        "WP0 baseline",
    )
    rejected(
        metrics,
        "declared_matt_model_visible_description_bytes",
        metrics["matt_model_visible_description_bytes"] + 1,
        "Matt description",
    )
    for path in (
        ".agents/references/future_contract.md",
        ".agents/skills/future-skill/SKILL.md",
        ".codex/skills/graphify/future.py",
        "scripts/scaffold/future_active_validator.py",
    ):
        assert wp7.is_active_scaffold_source(path)
    assert not wp7.is_active_scaffold_source("scripts/tests/test_future.py")
    rejected(
        metrics,
        "canonical_graph_bytes",
        metrics["maximum_canonical_graph_bytes"] + 1,
        "35 MB",
    )
    rejected(
        metrics,
        "tracked_generated_codex_agents",
        [".codex/agents/generated.toml"],
        ".codex/agents",
    )
    rejected(
        metrics,
        "tracked_graphify_wiki",
        ["graphify-out/wiki/index.md"],
        "wiki",
    )
    print("WP7 integration budget self-test passed")


if __name__ == "__main__":
    main()
