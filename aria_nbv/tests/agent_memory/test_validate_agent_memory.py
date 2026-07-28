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
        ".agents/skills/example/SKILL.md:1: legacy state journals must not be routed as current-truth owners"
    ]


def test_legacy_state_may_remain_explicit_migration_evidence(tmp_path: Path) -> None:
    source_order = tmp_path / ".agents/references/source_order.md"
    source_order.parent.mkdir(parents=True)
    source_order.write_text(
        "`.agents/memory/state/` is legacy migration evidence, not current truth.\n",
        encoding="utf-8",
    )

    assert not validator.check_legacy_state_owner_claims([".agents/references/source_order.md"], repo_root=tmp_path)
