from __future__ import annotations

from scripts.validate_agent_memory import RETIRED_SOURCE_PATHS


def test_only_frozen_retired_sources_are_accepted_as_historical_receipts() -> None:
    assert "docs/contents/thesis/roadmap.qmd" in RETIRED_SOURCE_PATHS
    assert ".agents/memory/state/DECISIONS.md" in RETIRED_SOURCE_PATHS
    assert "docs/contents/thesis/current.qmd" not in RETIRED_SOURCE_PATHS
    assert ".agents/memory/state/NEW_STATE.md" not in RETIRED_SOURCE_PATHS
