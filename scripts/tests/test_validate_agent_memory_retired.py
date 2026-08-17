from __future__ import annotations

import sys
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import validate_agent_memory as validator  # noqa: E402
from validate_agent_memory import (
    RETIRED_SOURCE_PATHS,
    allows_retired_canonical_update,
    check_history_records,
    check_tracked_omx_records,
    destination_anchor_exists,
)


def test_only_frozen_retired_sources_are_accepted_as_historical_receipts() -> None:
    assert "docs/contents/thesis/roadmap.qmd" in RETIRED_SOURCE_PATHS
    assert ".agents/memory/state/DECISIONS.md" in RETIRED_SOURCE_PATHS
    assert "docs/contents/thesis/current.qmd" not in RETIRED_SOURCE_PATHS
    assert ".agents/memory/state/NEW_STATE.md" not in RETIRED_SOURCE_PATHS


def test_only_exact_historical_records_can_target_retired_paths(
    tmp_path: Path,
) -> None:
    retired = ".agents/memory/state/DECISIONS.md"
    root = Path(__file__).resolve().parents[2]
    known_path = root / ".agents/memory/history/2026/03/2026-03-30_quarto_agent_scaffold_pages.md"
    assert allows_retired_canonical_update({}, retired, known_path)

    active_path = root / ".agents/memory/history/2026/08/2026-08-16_ownership_migration_receipt.md"
    assert not allows_retired_canonical_update(
        {}, retired, active_path
    )

    backdated = tmp_path / "backdated.md"
    backdated.write_text(
        "---\nid: invented\ndate: 2026-01-01\nstatus: done\n---\n",
        encoding="utf-8",
    )
    assert not allows_retired_canonical_update(
        {"id": "invented", "date": "2026-01-01", "status": "done"},
        retired,
        backdated,
    )
    renamed = tmp_path / "renamed.md"
    renamed.write_bytes(known_path.read_bytes())
    assert not allows_retired_canonical_update({}, retired, renamed)
    assert not allows_retired_canonical_update(
        {}, "docs/typst/thesis/main.typ", known_path
    )


def test_same_path_modified_record_is_rejected(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    record = repo / ".agents/memory/history/2026/03/record.md"
    record.parent.mkdir(parents=True)
    record.write_text("original\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.email=test@example.com",
            "-c",
            "user.name=Test",
            "commit",
            "-qm",
            "cutover",
        ],
        cwd=repo,
        check=True,
    )
    cutover = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    monkeypatch.setattr(validator, "REPO_ROOT", repo)
    monkeypatch.setattr(validator, "RETIREMENT_CUTOVER_COMMIT", cutover)
    assert allows_retired_canonical_update({}, ".agents/memory/state/DECISIONS.md", record)
    record.write_text("modified\n", encoding="utf-8")
    assert not allows_retired_canonical_update(
        {}, ".agents/memory/state/DECISIONS.md", record
    )


def test_legacy_imported_record_cannot_introduce_retired_reference(
    tmp_path: Path, monkeypatch
) -> None:
    history = tmp_path / "history"
    history.mkdir()
    record = history / "new.md"
    record.write_text(
        "---\nstatus: legacy-imported\ncanonical_updates_needed: [.agents/memory/state/DECISIONS.md]\n---\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(validator, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(validator, "HISTORY_ROOT", history)
    assert any("retired canonical update" in error for error in check_history_records())


def test_generated_omx_outputs_cannot_be_tracked() -> None:
    assert check_tracked_omx_records([".omx/plans/current.md"]) == []
    assert (
        check_tracked_omx_records(
            [".omx/specs/inventory.json", ".omx/specs/report.html"]
        )
        == []
    )
    errors = check_tracked_omx_records(
        [
            ".omx/specs/ownership-branch-consolidation-inventory.json",
            ".omx/specs/ownership-branch-consolidation-inventory.html",
            ".omx/state/runtime.md",
        ]
    )
    assert len(errors) == 3


def test_receipt_destination_anchors_are_resolved_by_owner_format(
    tmp_path: Path,
) -> None:
    markdown = tmp_path / "owner.md"
    markdown.write_text("## Commands and owners\n", encoding="utf-8")
    typst = tmp_path / "owner.typ"
    typst.write_text(
        "== Research <rq2>\n#eqs.rl.finite_horizon_return\n", encoding="utf-8"
    )
    python = tmp_path / "owner.py"
    python.write_text("class OwnerSymbol:\n    pass\n", encoding="utf-8")
    workflow = tmp_path / "owner.yml"
    workflow.write_text("name: Root Verification\n", encoding="utf-8")

    assert destination_anchor_exists(markdown, "Commands-and-owners")
    assert destination_anchor_exists(typst, "rq2")
    assert destination_anchor_exists(typst, "eqs.rl.finite_horizon_return")
    assert destination_anchor_exists(python, "OwnerSymbol")
    assert destination_anchor_exists(workflow, "workflow:name=Root Verification")
    assert not destination_anchor_exists(markdown, "missing-heading")
