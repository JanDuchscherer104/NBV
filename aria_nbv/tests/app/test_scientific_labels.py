"""Tests for shared scientific label formatting and fail-closed resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from aria_nbv.app.scientific_labels import (
    TheoryReferences,
    TheoryResolutionError,
    equation_label,
    format_identifier,
    resolve_theory,
    symbol_label,
)


def _write_registry(root: Path) -> None:
    docs = root / "docs"
    (docs / "glossary").mkdir(parents=True)
    (docs / "notation.yml").write_text(
        "symbols:\n"
        "  demo.value:\n"
        "    tex: '\\Delta_t'\n"
        "    typst: '#symb.demo.value'\n"
        "    description: Observed change.\n"
        "equations:\n"
        "  demo.identity:\n"
        "    tex: 'x=y'\n"
        "    typst: '#eqs.demo.identity'\n",
        encoding="utf-8",
    )
    (docs / "glossary" / "terms.yml").write_text("[]\n", encoding="utf-8")


def test_label_modes_share_one_registry_backed_formatter(tmp_path: Path) -> None:
    _write_registry(tmp_path)

    assert format_identifier("target_root_gain") == "Target Root Gain"
    assert symbol_label("demo.value", mode="Symbols", root=tmp_path) == r"$\Delta_t$"
    assert symbol_label("demo.value", mode="Text", root=tmp_path) == "Observed change."
    assert symbol_label("demo.value", mode="Both", root=tmp_path) == r"$\Delta_t$ — Observed change."
    assert symbol_label("demo.value", mode="Both", math_capable=False, root=tmp_path) == "Observed change."
    assert equation_label("demo.identity", mode="Text", root=tmp_path) == "Demo.Identity"


def test_unknown_labels_fail_closed_to_readable_identifier(tmp_path: Path) -> None:
    _write_registry(tmp_path)
    assert symbol_label("missing_value", root=tmp_path) == "Missing Value"
    with pytest.raises(TheoryResolutionError):
        resolve_theory(TheoryReferences(symbol_ids=("missing_value",)), root=tmp_path)
