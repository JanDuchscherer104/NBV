from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from validate_agent_memory import (  # noqa: E402
    RETIRED_SOURCE_PATHS,
    allows_retired_canonical_update,
    check_tracked_omx_records,
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
    errors = check_tracked_omx_records(
        [".omx/specs/inventory.json", ".omx/specs/report.html", ".omx/state/runtime.md"]
    )
    assert len(errors) == 3
