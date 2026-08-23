"""Ensure the claim ledger points at current Typst and code owners."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("check_thesis_claims", ROOT / "scripts/check_thesis_claims.py")
assert SPEC and SPEC.loader
CHECK = importlib.util.module_from_spec(SPEC)
sys.modules["check_thesis_claims"] = CHECK
SPEC.loader.exec_module(CHECK)


def test_claim_owners_are_active_and_code_evidence_is_not_campaign_semantics() -> None:
    model = CHECK.read_principal_claims()
    assert all(item.owner.kind == "typst-anchor" for item in model.claims)
    assert all(evidence.locator.kind == "code" for item in model.claims for evidence in item.evidence)
    assert not any("campaign.py" in evidence.locator.path for item in model.claims for evidence in item.evidence)
    assert all(item.release_state == "withheld" for item in model.claims)
