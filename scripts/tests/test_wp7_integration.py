#!/usr/bin/env python3
"""Exercise the final WP7 quantitative contract and its failure modes."""

from __future__ import annotations

import copy
import importlib.util
import json
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
    assert metrics["baseline_commit"] == wp7.BASELINE_COMMIT
    assert metrics["measured_baseline_scaffold_source_loc"] == 27550
    assert len(metrics["baseline_scaffold_source_paths"]) == 237
    assert (
        metrics["baseline_scaffold_source_paths_sha256"]
        == "e6231cadac6f173049a9b792b5489bda9149dd79bea5b1fe28fb2aa1bec65bda"
    )
    assert metrics["baseline_outline_scripts"] == [
        ".agents/skills/aria-nbv-context/scripts/nbv_qmd_outline.py",
        ".agents/skills/aria-nbv-context/scripts/nbv_qmd_outline.sh",
        ".agents/skills/aria-nbv-context/scripts/nbv_typst_includes.py",
        "scripts/nbv_qmd_outline.sh",
    ]
    assert metrics["active_outline_scripts"] == [
        ".agents/skills/aria-nbv-context/scripts/nbv_qmd_outline.py",
        ".agents/skills/aria-nbv-context/scripts/nbv_qmd_outline.sh",
        ".agents/skills/aria-nbv-context/scripts/nbv_typst_includes.py",
        "scripts/nbv_qmd_outline.sh",
        "scripts/nbv_typst_includes.py",
    ]
    assert (
        metrics["active_scaffold_source_loc"] < metrics["baseline_scaffold_source_loc"]
    )
    active_paths = set(metrics["active_scaffold_source_paths"])
    for path in (
        ".graphify.toml",
        ".graphifyignore",
        "scripts/check_graphify_history.py",
        "scripts/graphify_contract.py",
        "scripts/graphify_merge_driver.py",
        "scripts/git_hooks/post-commit",
        "scripts/nbv_typst_includes.py",
        "scripts/scaffold/bootstrap_matt_skills.py",
        "scripts/scaffold/check_wp7_integration.py",
        "scripts/scaffold/matt_skills_policy.py",
        "scripts/scaffold/run_scoped_uml.py",
        "scripts/scaffold/validate_omx_artifacts.py",
    ):
        assert path in active_paths
    for prefix in ("scripts/tests/", "graphify-out/", ".omx/"):
        assert any(
            path.startswith(prefix)
            for path in metrics["active_scaffold_excluded_paths"]
        )
    rejected(metrics, "baseline_commit", "0" * 40, "baseline commit")
    rejected(
        metrics,
        "active_outline_scripts",
        metrics["active_outline_scripts"][1:],
        "outline scripts",
    )
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
        "missing_required_loc_include_globs",
        ["scripts/scaffold/**"],
        "required source families",
    )
    rejected(
        metrics,
        "active_source_coverage_gaps",
        ["scripts/scaffold/future_gate.py"],
        "evade LOC accounting",
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
    synthetic_tree = {
        ".omx/archive/accepted-bundles/task--0123456789abcdef/evidence.md": (
            "100644",
            "a",
        ),
        ".omx/plans/current-evidence.md": ("100644", "b"),
        "graphify-out/graph.json": ("100644", "c"),
        "owned/source.py": ("100644", "d"),
        "scripts/tests/test_owned.py": ("100644", "e"),
        "unowned/readme.md": ("100644", "f"),
        "vendor/submodule": ("160000", "g"),
    }
    synthetic_rules = {
        "include_globs": ["owned/**", "scripts/**", "graphify-out/**", ".omx/**"],
        "exclude_globs": ["scripts/tests/**", "graphify-out/**", ".omx/**"],
    }
    included, excluded = wp7.accounting_path_sets(synthetic_tree, synthetic_rules)
    assert included == ["owned/source.py"]
    assert excluded == [
        ".omx/archive/accepted-bundles/task--0123456789abcdef/evidence.md",
        ".omx/plans/current-evidence.md",
        "graphify-out/graph.json",
        "scripts/tests/test_owned.py",
    ]
    future_active_tree = {
        ".graphify.future.toml": ("100644", "a"),
        "scripts/check_graphify_future.py": ("100644", "b"),
        "scripts/git_hooks/pre-commit": ("100755", "c"),
        "scripts/nbv_future_outline.py": ("100644", "d"),
        "scripts/scaffold/future_gate.py": ("100644", "e"),
        "scripts/tests/test_graphify_future.py": ("100644", "f"),
    }
    baseline = json.loads(wp7.BASELINE.read_text(encoding="utf-8"))
    rules = baseline["counting_rules"]["active_scaffold_source_loc"]
    future_included, future_excluded = wp7.accounting_path_sets(
        future_active_tree, rules
    )
    assert future_included == [
        ".graphify.future.toml",
        "scripts/check_graphify_future.py",
        "scripts/git_hooks/pre-commit",
        "scripts/nbv_future_outline.py",
        "scripts/scaffold/future_gate.py",
    ]
    assert future_excluded == ["scripts/tests/test_graphify_future.py"]
    assert not wp7.active_source_coverage_gaps(future_active_tree, rules)
    weakened_rules = copy.deepcopy(rules)
    weakened_rules["include_globs"] = [
        pattern
        for pattern in weakened_rules["include_globs"]
        if pattern != "scripts/scaffold/**"
    ]
    assert wp7.active_source_coverage_gaps(future_active_tree, weakened_rules) == [
        "scripts/scaffold/future_gate.py"
    ]
    for path in (
        ".agents/references/future_contract.md",
        ".agents/skills/future-skill/SKILL.md",
        ".codex/skills/graphify/future.py",
        ".graphify.toml",
        "scripts/check_graphify_future.py",
        "scripts/git_hooks/pre-commit",
        "scripts/nbv_future_outline.py",
        "scripts/scaffold/future_gate.py",
    ):
        assert wp7.is_active_scaffold_source(path)
    assert not wp7.is_active_scaffold_source("scripts/tests/test_future.py")
    assert not wp7.is_active_scaffold_source("graphify-out/future.json")
    assert not wp7.is_active_scaffold_source(".omx/plans/future.md")
    assert not wp7.is_active_scaffold_source(
        ".omx/archive/accepted-bundles/task--0123456789abcdef/future.md"
    )
    assert all(
        not path.startswith(("scripts/tests/", "graphify-out/", ".omx/"))
        for path in metrics["active_scaffold_source_paths"]
    )
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
