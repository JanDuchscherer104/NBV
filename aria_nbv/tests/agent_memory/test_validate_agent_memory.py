from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "validate_agent_memory.py"
SPEC = importlib.util.spec_from_file_location("validate_agent_memory", SCRIPT_PATH)
assert SPEC is not None
validator = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = validator
SPEC.loader.exec_module(validator)


@pytest.mark.parametrize(
    "path",
    [
        ".omx/context/task.md",
        ".omx/plans/refactor.md",
        ".omx/specs/refactor/report.md",
        ".omx/goals/autoresearch/task.json",
    ],
)
def test_durable_omx_artifacts_may_be_tracked(path: str) -> None:
    assert not validator.is_forbidden_tracked_runtime_path(path)


@pytest.mark.parametrize(
    "path",
    [
        ".omx",
        ".omx/cache/query.json",
        ".omx/logs/run.jsonl",
        ".omx/state/session.json",
        ".omx/tmp/output.txt",
        ".omx/ultragoal/goals.json",
        ".omx/goals/autoresearch/run/artifacts/result.json",
        ".codex/config.toml",
        ".codex/hooks.json",
    ],
)
def test_operator_runtime_state_must_not_be_tracked(path: str) -> None:
    assert validator.is_forbidden_tracked_runtime_path(path)


def test_unrelated_paths_are_outside_the_runtime_policy() -> None:
    assert not validator.is_forbidden_tracked_runtime_path("aria_nbv/aria_nbv/__init__.py")


def test_live_guidance_must_not_route_legacy_state_as_current_truth(
    tmp_path: Path,
) -> None:
    skill = tmp_path / ".agents/skills/example/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(
        "Use `.agents/memory/state/` for durable current truth.\n",
        encoding="utf-8",
    )

    assert validator.check_legacy_state_owner_claims([".agents/skills/example/SKILL.md"], repo_root=tmp_path) == [
        ".agents/skills/example/SKILL.md:1: legacy state journal route lacks an explicit migration-only qualifier"
    ]


def test_legacy_state_may_remain_explicit_migration_evidence(tmp_path: Path) -> None:
    source_order = tmp_path / ".agents/references/source_order.md"
    source_order.parent.mkdir(parents=True)
    source_order.write_text(
        "`.agents/memory/state/` is legacy migration evidence, not current truth.\n",
        encoding="utf-8",
    )

    assert not validator.check_legacy_state_owner_claims([".agents/references/source_order.md"], repo_root=tmp_path)


def test_multiline_and_semantic_legacy_routes_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / ".agents" / "todos.toml"
    path.parent.mkdir(parents=True)
    path.write_text(
        'references = ["repo:.agents/memory/state/DECISIONS.md"]\n'
        'acceptance = ["Update current truth in the decision journal."]\n'
        'notes = ["Do not forget to update GOTCHAS.md after the fix."]\n',
        encoding="utf-8",
    )

    errors = validator.check_legacy_state_owner_claims([".agents/todos.toml"], repo_root=tmp_path)

    assert len(errors) == 2
    assert all("migration-only qualifier" in error for error in errors)


def test_qualifier_does_not_exempt_a_later_owner_route(tmp_path: Path) -> None:
    path = tmp_path / "README.md"
    path.write_text(
        "DECISIONS.md is legacy migration evidence only.\nUpdate DECISIONS.md with durable current truth.\n",
        encoding="utf-8",
    )

    assert validator.check_legacy_state_owner_claims(["README.md"], repo_root=tmp_path) == [
        "README.md:2: legacy state journal route lacks an explicit migration-only qualifier"
    ]


def test_semantic_alias_and_makefile_route_are_rejected(tmp_path: Path) -> None:
    makefile = tmp_path / "Makefile"
    makefile.write_text(
        "owner:\n\t@echo 'canonical memory owns current truth'\n",
        encoding="utf-8",
    )

    errors = validator.check_legacy_state_owner_claims(["Makefile"], repo_root=tmp_path)

    assert errors == ["Makefile:2: legacy state journal route lacks an explicit migration-only qualifier"]


def test_unreadable_tracked_ownership_source_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / ".agents" / "missing.md"
    path.parent.mkdir(parents=True)

    assert validator.check_legacy_state_owner_claims([".agents/missing.md"], repo_root=tmp_path) == [
        ".agents/missing.md: tracked ownership source is unreadable"
    ]
