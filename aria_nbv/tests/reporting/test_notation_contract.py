"""Canonical notation ownership tests for report results."""

from pathlib import Path

import pytest

from aria_nbv.reporting.notation import TheoryReferences, TheoryResolutionError, notation_sha256, resolve_theory


def test_report_notation_resolves_typst_owned_symbol() -> None:
    root = Path(__file__).parents[3]

    resolved = resolve_theory(TheoryReferences(symbol_ids=("rl.qh",)), root=root)

    assert resolved.symbols[0].typst == "#symb.rl.qh"
    assert len(notation_sha256(root=root)) == 64


def test_unknown_report_symbol_fails_closed() -> None:
    with pytest.raises(TheoryResolutionError, match="unknown canonical symbol"):
        resolve_theory(TheoryReferences(symbol_ids=("unknown.symbol",)), root=Path(__file__).parents[3])
