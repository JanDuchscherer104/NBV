#!/usr/bin/env python3
"""Self-test the WP0 baseline validator and closed-row guards."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "validate_scaffold_wp0_baseline.py"
SPEC = importlib.util.spec_from_file_location("validate_scaffold_wp0_baseline", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
baseline_validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(baseline_validator)


def main() -> None:
    baseline = json.loads(baseline_validator.BASELINE_PATH.read_text(encoding="utf-8"))
    tree = baseline_validator._tree(baseline["source_state"]["commit"])
    active_paths = baseline_validator._active_scaffold_paths(baseline, tree)
    computed = baseline_validator.compute_repository_baseline(baseline)
    assert computed == baseline["measurements"]
    assert not baseline_validator.validate_counting_rules(baseline, tree, active_paths)
    assert not baseline_validator.validate_failure_allowlist(baseline)
    assert not baseline_validator.validate_graphify_snapshot(baseline)

    invalid_failure_digest = copy.deepcopy(baseline)
    invalid_failure_digest["verification_snapshot"][0]["output_sha256"] = "invalid"
    errors = baseline_validator.validate_failure_allowlist(invalid_failure_digest)
    assert any("invalid output digest" in error for error in errors)

    missing_graph_count = copy.deepcopy(baseline)
    del missing_graph_count["graphify"]["edge_count"]
    errors = baseline_validator.validate_graphify_snapshot(missing_graph_count)
    assert any("missing fields" in error for error in errors)

    available_without_graph = copy.deepcopy(baseline)
    available_without_graph["graphify"]["node_count"] = {
        "state": "available",
        "value": 0,
    }
    errors = baseline_validator.validate_graphify_snapshot(available_without_graph)
    assert any("deterministic absent-graph value" in error for error in errors)

    synthetic_tree = dict(tree)
    for path in (
        ".agents/baselines/scaffold_wp0_baseline.json",
        ".agents/baselines/scaffold_wp0_inventory.csv",
        "scripts/validate_scaffold_wp0_baseline.py",
    ):
        synthetic_tree[path] = ("100644", "")
    synthetic_paths = baseline_validator._active_scaffold_paths(
        baseline, synthetic_tree
    )
    assert {
        ".agents/baselines/scaffold_wp0_baseline.json",
        ".agents/baselines/scaffold_wp0_inventory.csv",
        "scripts/validate_scaffold_wp0_baseline.py",
    } <= synthetic_paths

    rows = baseline_validator._load_inventory()
    expected_skills = {skill["name"] for skill in computed["aria_skills"]}
    assert not baseline_validator.validate_inventory(
        rows,
        baseline["source_state"]["commit"],
        expected_skills,
        tree,
        active_paths,
    )

    def inventory_errors(candidate_rows: list[dict[str, str]]) -> list[str]:
        return baseline_validator.validate_inventory(
            candidate_rows,
            baseline["source_state"]["commit"],
            expected_skills,
            tree,
            active_paths,
        )

    open_rows = copy.deepcopy(rows)
    open_rows[0]["status"] = "unresolved"
    errors = inventory_errors(open_rows)
    assert any("open/unknown status" in error for error in errors)

    wrong_rollback = copy.deepcopy(rows)
    wrong_rollback[0]["rollback_commit"] = "0" * 40
    errors = inventory_errors(wrong_rollback)
    assert any("rollback commit differs" in error for error in errors)

    omitted = [row for row in copy.deepcopy(rows) if row["id"] != "hook-gemini-settings"]
    errors = inventory_errors(omitted)
    assert any("hook inventory mismatch" in error for error in errors)

    omitted_context_consumer = copy.deepcopy(rows)
    guidance_consumers = next(
        row for row in omitted_context_consumer if row["id"] == "context-consumer-guidance"
    )
    guidance_consumers["paths"] = ";".join(
        path
        for path in guidance_consumers["paths"].split(";")
        if path != "aria_nbv/AGENTS.md"
    )
    errors = inventory_errors(omitted_context_consumer)
    assert any("context-consumer inventory mismatch" in error for error in errors)

    invalid_path = copy.deepcopy(rows)
    invalid_path[0]["paths"] = "does/not/exist.md"
    errors = inventory_errors(invalid_path)
    assert any("path is absent from baseline tree" in error for error in errors)

    invalid_anchor = copy.deepcopy(rows)
    next(row for row in invalid_anchor if row["id"] == "hook-install")["paths"] = (
        "Makefile:9999"
    )
    errors = inventory_errors(invalid_anchor)
    assert any("invalid line anchor" in error for error in errors)

    duplicate = copy.deepcopy(rows)
    duplicate_row = copy.deepcopy(duplicate[0])
    duplicate_row["id"] = "duplicate-guidance-row"
    duplicate.append(duplicate_row)
    errors = inventory_errors(duplicate)
    assert any("category/surface pairs are not unique" in error for error in errors)

    placeholder = copy.deepcopy(rows)
    placeholder[0]["owner"] = "TBD owner"
    errors = inventory_errors(placeholder)
    assert any("placeholder owner" in error for error in errors)

    incomplete_rules = copy.deepcopy(baseline)
    incomplete_rules["counting_rules"]["active_scaffold_source_loc"][
        "include_globs"
    ].remove("Makefile")
    incomplete_paths = baseline_validator._active_scaffold_paths(incomplete_rules, tree)
    errors = baseline_validator.validate_counting_rules(
        incomplete_rules, tree, incomplete_paths
    )
    assert any("Makefile" in error for error in errors)

    missing_validator_rule = copy.deepcopy(baseline)
    missing_validator_rule["counting_rules"]["active_scaffold_source_loc"][
        "include_globs"
    ].remove("scripts/validate_scaffold_wp0_baseline.py")
    missing_validator_paths = baseline_validator._active_scaffold_paths(
        missing_validator_rule, tree
    )
    errors = baseline_validator.validate_counting_rules(
        missing_validator_rule, tree, missing_validator_paths
    )
    assert any("scripts/validate_scaffold_wp0_baseline.py" in error for error in errors)


if __name__ == "__main__":
    main()
