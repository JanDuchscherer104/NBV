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

    assert len(errors) == 3
    assert all("migration-only qualifier" in error for error in errors)


def test_qualifier_does_not_exempt_a_later_owner_route(tmp_path: Path) -> None:
    path = tmp_path / "README.md"
    path.write_text(
        "DECISIONS.md is legacy migration evidence only.\n\nUpdate DECISIONS.md with durable current truth.\n",
        encoding="utf-8",
    )

    assert validator.check_legacy_state_owner_claims(["README.md"], repo_root=tmp_path) == [
        "README.md:3: legacy state journal route lacks an explicit migration-only qualifier"
    ]


def test_semantic_alias_and_makefile_route_are_rejected(tmp_path: Path) -> None:
    makefile = tmp_path / "Makefile"
    makefile.write_text(
        "owner:\n\t@echo 'canonical memory owns current truth'\n",
        encoding="utf-8",
    )

    errors = validator.check_legacy_state_owner_claims(["Makefile"], repo_root=tmp_path)

    assert errors == ["Makefile:2: legacy state journal route lacks an explicit migration-only qualifier"]


def test_migration_phrase_does_not_exempt_same_line_owner_assertion(tmp_path: Path) -> None:
    path = tmp_path / "README.md"
    path.write_text(
        "The decision journal is legacy migration evidence; update it with current truth.\n",
        encoding="utf-8",
    )

    assert validator.check_legacy_state_owner_claims(["README.md"], repo_root=tmp_path) == [
        "README.md:1: legacy state journal route lacks an explicit migration-only qualifier"
    ]


def test_bare_uppercase_legacy_alias_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "owner.typ"
    path.write_text("#let sources = [roadmap; DECISIONS]\n", encoding="utf-8")

    assert validator.check_legacy_state_owner_claims([path.name], repo_root=tmp_path) == [
        "owner.typ:1: legacy state journal route lacks an explicit migration-only qualifier"
    ]


@pytest.mark.parametrize("suffix", [".qmd", ".typ"])
def test_wrapped_and_alternative_owner_claims_are_rejected(tmp_path: Path, suffix: str) -> None:
    path = tmp_path / f"owner{suffix}"
    path.write_text(
        "The decision journals are legacy migration evidence, but remain\nauthoritative for current decisions.\n",
        encoding="utf-8",
    )

    assert validator.check_legacy_state_owner_claims([path.name], repo_root=tmp_path) == [
        f"{path.name}:1: legacy state journal route lacks an explicit migration-only qualifier"
    ]


@pytest.mark.parametrize(
    "claim",
    [
        "The decision journals are migration evidence; update them with current truth.",
        "DECISIONS.md is migration evidence but owns current truth.",
        "DECISIONS.md is migration evidence; use it as the source of truth.",
        "The state journal is migration evidence but remains canonical.",
        "PROJECT_STATE.md is migration evidence but remains the source of truth.",
    ],
)
def test_migration_qualifier_does_not_exempt_owner_variants(tmp_path: Path, claim: str) -> None:
    path = tmp_path / "README.md"
    path.write_text(f"{claim}\n", encoding="utf-8")

    errors = validator.check_legacy_state_owner_claims(["README.md"], repo_root=tmp_path)

    assert errors == ["README.md:1: legacy state journal route lacks an explicit migration-only qualifier"]


@pytest.mark.parametrize(
    ("body", "expected_errors"),
    [
        (
            "#let note = [\n"
            "  The decision journals are retained only as\n"
            "  legacy migration evidence while the replacement\n"
            "  owners are validated. They are not current truth.\n"
            "]\n",
            0,
        ),
        (
            "#let note = [\n"
            "  The decision journals are retained only as\n"
            "  legacy migration evidence while the replacement\n"
            "  owners are validated, but they remain\n"
            "  authoritative for current decisions.\n"
            "]\n",
            1,
        ),
    ],
)
def test_typst_balanced_records_are_classified_as_a_unit(tmp_path: Path, body: str, expected_errors: int) -> None:
    path = tmp_path / "owner.typ"
    path.write_text(body, encoding="utf-8")

    errors = validator.check_legacy_state_owner_claims([path.name], repo_root=tmp_path)

    assert len(errors) == expected_errors


@pytest.mark.parametrize(
    ("body", "expected_errors"),
    [
        (
            'notes = [\n  "DECISIONS is legacy migration evidence",\n  "and is not current truth.",\n]\n',
            0,
        ),
        (
            'notes = [\n  "DECISIONS is legacy migration evidence",\n'
            '  "while replacement owners are validated",\n'
            '  "but remains authoritative for current decisions.",\n]\n',
            1,
        ),
    ],
)
def test_toml_array_values_are_classified_as_a_unit(tmp_path: Path, body: str, expected_errors: int) -> None:
    path = tmp_path / "owner.toml"
    path.write_text(body, encoding="utf-8")

    errors = validator.check_legacy_state_owner_claims([path.name], repo_root=tmp_path)

    assert len(errors) == expected_errors


def test_unreadable_tracked_ownership_source_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / ".agents" / "missing.md"
    path.parent.mkdir(parents=True)

    assert validator.check_legacy_state_owner_claims([".agents/missing.md"], repo_root=tmp_path) == [
        ".agents/missing.md: tracked ownership source is unreadable"
    ]
