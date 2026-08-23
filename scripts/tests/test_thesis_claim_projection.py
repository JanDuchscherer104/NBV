"""Prove Graphify consumes, rather than owns, the validated claim ledger."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import build_graphify_projection as projection  # noqa: E402


def test_claim_pages_are_derived_from_typed_model() -> None:
    checker_spec = importlib.util.spec_from_file_location("check_thesis_claims", ROOT / "scripts/check_thesis_claims.py")
    assert checker_spec and checker_spec.loader
    checker = importlib.util.module_from_spec(checker_spec)
    sys.modules["check_thesis_claims"] = checker
    checker_spec.loader.exec_module(checker)
    model = checker.read_principal_claims()
    data = projection._RenderData(
        revision="HEAD",
        source_tree="tree",
        aria_code_oid="main",
        aria_code_pin_kind="branch",
        closure=(),
        citations_by_source={},
        bib={},
        joined={},
        manifest=(),
        targets={},
        relations=(),
        headings=(),
        warnings=(),
        terms={},
        notation={"symbols": {}, "equations": {}},
        notation_owners={},
        usage_by_source={},
        claims=model,
        claim_extension_status="current",
        claim_extension_error=None,
    )
    pages = projection._make_pages(projection.ProjectionConfig(ROOT), data)
    paths = projection._page_paths(pages)
    projection._populate_claim_pages(data, pages, paths)
    claim = model.claims[0]
    rendered = "\n".join(pages.claims[claim.id].lines)
    assert "release_applicability: required" in rendered
    assert "release_state: withheld" in rendered
    assert "Derived" not in rendered
