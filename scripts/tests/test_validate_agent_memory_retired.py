from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from validate_agent_memory import (  # noqa: E402
    RETIRED_SOURCE_PATHS,
    allows_retired_canonical_update,
    check_tracked_omx_records,
    destination_anchor_exists,
)


def test_only_frozen_retired_sources_are_accepted_as_historical_receipts() -> None:
    assert "docs/contents/thesis/roadmap.qmd" in RETIRED_SOURCE_PATHS
    assert ".agents/memory/state/DECISIONS.md" in RETIRED_SOURCE_PATHS
    assert "docs/contents/thesis/current.qmd" not in RETIRED_SOURCE_PATHS
    assert ".agents/memory/state/NEW_STATE.md" not in RETIRED_SOURCE_PATHS


def test_new_or_nonlegacy_records_cannot_target_retired_paths() -> None:
    retired = ".agents/memory/state/DECISIONS.md"
    assert allows_retired_canonical_update(
        {"date": "2026-07-30", "status": "done"}, retired
    )
    assert not allows_retired_canonical_update(
        {"date": "2026-08-14", "status": "done"}, retired
    )
    assert not allows_retired_canonical_update(
        {"date": "2026-07-30", "status": "todo"}, retired
    )
    assert not allows_retired_canonical_update(
        {"date": "2026-08-14", "status": "done"}, "docs/typst/thesis/main.typ"
    )


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
