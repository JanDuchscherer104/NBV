from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from validate_agent_memory import RETIRED_SOURCE_PATHS  # noqa: E402


def test_only_frozen_retired_sources_are_accepted_as_historical_receipts() -> None:
    assert "docs/contents/thesis/roadmap.qmd" in RETIRED_SOURCE_PATHS
    assert ".agents/memory/state/DECISIONS.md" in RETIRED_SOURCE_PATHS
    assert "docs/contents/thesis/current.qmd" not in RETIRED_SOURCE_PATHS
    assert ".agents/memory/state/NEW_STATE.md" not in RETIRED_SOURCE_PATHS
