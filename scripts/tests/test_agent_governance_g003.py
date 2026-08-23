#!/usr/bin/env python3
"""Current-owner and behavior checks for G003 guidance."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def _normalized(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def _setup_target_functions(relative: str) -> set[str]:
    tree = ast.parse(_read(relative))
    owners: set[str] = set()
    stack: list[str] = []

    class Visitor(ast.NodeVisitor):
        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            stack.append(node.name)
            self.generic_visit(node)
            stack.pop()

        def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
            stack.append(node.name)
            if any(
                isinstance(item, ast.Call)
                and isinstance(item.func, ast.Attribute)
                and item.func.attr == "setup_target"
                for item in ast.walk(node)
            ):
                owners.add(".".join(stack))
            self.generic_visit(node)
            stack.pop()

        visit_FunctionDef = _visit_function
        visit_AsyncFunctionDef = _visit_function

    Visitor().visit(tree)
    return owners


def test_pointer_preservation_contract_is_mechanical() -> None:
    guide = _normalized(_read(".agents/skills/README.md"))
    for phrase in (
        "explicit activation condition",
        "link directly to the leaf",
        "one named branch index",
        "reachable, non-orphaned",
        "at most two hops",
        "old owner must no longer carry",
        "positive routing case",
        "near-miss",
    ):
        assert phrase in guide


def test_graphify_is_the_only_accepted_pinned_bundle_in_this_change() -> None:
    guide = _read(".agents/skills/README.md")
    boundary = _read(
        ".agents/skills/aria-nbv-context/references/graphify-aria-boundary.md"
    )
    assert "accepted per-bundle decision" in guide
    assert "#accepted-bundle-manifest" in guide
    for value in (
        "https://github.com/Graphify-Labs/graphify",
        "b2cd36267456c166788c95be6e68574064a92a42",
        "graphify/skill-codex.md",
        "2b19efe36ad87d1fe84e396dc7065de512b37bc3",
        ".agents/skills/graphify/",
        "6943c772de908bdac1dc0d1b7f73fa7ed285433a",
        "graphify install --project --platform agents",
        "make graphify-skill-upstream-self-test",
    ):
        assert value in boundary


def test_config_factory_has_one_non_competing_lifecycle_owner() -> None:
    package = _read("aria_nbv/AGENTS.md")
    conventions = _normalized(
        _read(".agents/skills/python-standards/references/general_conventions.md")
    )
    assert "Before deciding where any `.setup_target()` call belongs" in package
    assert "general_conventions.md#config-as-factory-and-lifecycle" in package
    for phrase in (
        "once per owning lifecycle",
        "Inject the constructed dependency",
        "reuse and teardown",
        "device, rank, checkpoint, and worker hooks",
    ):
        assert phrase in conventions


def test_current_composition_roots_construct_targets() -> None:
    expected = {
        "aria_nbv/aria_nbv/streamlit_app.py": {"main"},
        "aria_nbv/aria_nbv/oracle/pipelines/cli.py": {"_campaign"},
        "aria_nbv/aria_nbv/lightning/aria_nbv_experiment.py": {
            "AriaNBVExperimentConfig._init_module_for_resume"
        },
        "aria_nbv/aria_nbv/app/controller.py": {
            "PipelineController.get_sample",
            "PipelineController.get_candidates",
            "PipelineController.get_depths",
        },
    }
    for relative, owners in expected.items():
        assert owners <= _setup_target_functions(relative)


def test_forward_and_scoring_hot_paths_do_not_construct_targets() -> None:
    for path in (ROOT / "aria_nbv/aria_nbv").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name not in {"forward", "score", "_score", "scoring"}:
                continue
            assert not any(
                isinstance(item, ast.Call)
                and isinstance(item.func, ast.Attribute)
                and item.func.attr == "setup_target"
                for item in ast.walk(node)
            ), f"{path.relative_to(ROOT)}:{node.lineno} constructs in {node.name}"


def test_app_interpretation_is_verdict_first_and_conditional() -> None:
    app = _read("aria_nbv/aria_nbv/app/AGENTS.md")
    rubric = _read("aria_nbv/aria_nbv/app/references/scientific-interpretation.md")
    assert "Lead with the answer or readiness verdict" in app
    assert "references/scientific-interpretation.md" in app
    assert "do not load the scientific rubric" in app
    assert "only when" in rubric
    assert "Never fabricate" in rubric


def test_g003_routing_cases_cover_positive_and_near_miss_behavior() -> None:
    routing = json.loads(_read("scripts/scaffold/fixtures/routing.json"))
    fixtures = {fixture["id"]: fixture for fixture in routing["fixtures"]}
    expected = {
        "config-factory-composition-root",
        "config-factory-hot-path-near-miss",
        "helper-single-consumer-local",
        "helper-shared-domain-owner",
        "graphify-accepted-bundle-refresh",
        "app-scientific-metric-interpretation",
        "app-operational-count-near-miss",
    }
    assert expected <= set(fixtures)
    for trial_id in expected:
        fixture = fixtures[trial_id]
        assert fixture["expected_owner_paths"]
        assert fixture["required_outcomes"]
        assert fixture["forbidden_outcomes"]
