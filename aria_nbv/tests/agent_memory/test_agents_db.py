from __future__ import annotations

import importlib.util
import sys
import tomllib
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "agents_db.py"
SPEC = importlib.util.spec_from_file_location("agents_db", SCRIPT_PATH)
assert SPEC is not None
agents_db = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = agents_db
SPEC.loader.exec_module(agents_db)

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_validate_rejects_active_id_reused_by_resolved_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    issues_path = tmp_path / "issues.toml"
    todos_path = tmp_path / "todos.toml"
    refactors_path = tmp_path / "refactors.toml"
    resolved_path = tmp_path / "resolved.toml"
    issues_path.write_text(
        """
[[issue]]
id = "issue-001"
title = "Active issue"
description = "An active issue record."
type = "bug"
priority = "high"
status = "open"
labels = ["rri"]
context = ["Active issue context."]
references = ["repo:scripts/agents_db.py"]
""",
        encoding="utf-8",
    )
    todos_path.write_text("", encoding="utf-8")
    refactors_path.write_text("", encoding="utf-8")
    resolved_path.write_text('[[issue]]\nid = "issue-001"\n', encoding="utf-8")
    monkeypatch.setattr(
        agents_db,
        "ACTIVE_FILES",
        {
            "issue": issues_path,
            "todo": todos_path,
            "refactor": refactors_path,
        },
    )
    monkeypatch.setattr(agents_db, "RESOLVED_FILE", resolved_path)

    assert agents_db.validate(quiet=True) == 1
    captured = capsys.readouterr()
    assert "issue-001: active id reuses a resolved record id" in captured.err


@pytest.mark.parametrize(
    ("relative", "table", "record_id"),
    [
        (".agents/issues.toml", "issue", "issue-033"),
        (".agents/refactors.toml", "refactor", "refactor-019"),
    ],
)
def test_scaffold_records_reference_existing_accepted_artifacts(relative: str, table: str, record_id: str) -> None:
    payload = tomllib.loads((REPO_ROOT / relative).read_text(encoding="utf-8"))
    record = next(item for item in payload[table] if item["id"] == record_id)

    for reference in record["references"]:
        if not reference.startswith("repo:.omx/"):
            continue
        target = reference.removeprefix("repo:").split("#", maxsplit=1)[0]
        assert (REPO_ROOT / target).exists(), reference
