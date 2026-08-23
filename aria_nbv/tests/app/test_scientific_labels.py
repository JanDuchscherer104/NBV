"""Regression tests for canonical scientific explanation references."""

from pathlib import Path

import pytest

from aria_nbv.app.scientific_labels import (
    SCIENTIFIC_LABELS,
    ScientificLabel,
    TheoryReferences,
    TheoryResolutionError,
    equation_label,
    format_identifier,
    format_scientific_label,
    resolve_theory,
    symbol_label,
)


def test_resolve_theory_uses_current_typst_registries() -> None:
    theory = resolve_theory(
        TheoryReferences(
            equation_ids=("rl.target_rri_reward",),
            symbol_ids=("entity.target_error",),
            term_ids=("target-rri-reward",),
        ),
        root=Path(__file__).parents[3],
    )

    assert theory.equations[0].typst == "#eqs.rl.target_root_gain_reward"
    assert theory.symbols[0].typst == "#eqs.entity.target_error"
    assert theory.terms[0].label == "Target-Specific RRI"
    assert all(
        item.source_url.startswith("https://github.com/")
        for item in (*theory.equations, *theory.symbols, *theory.terms)
    )


def test_scientific_label_modes_resolve_at_the_presentation_boundary(tmp_path) -> None:
    docs = tmp_path / "docs"
    (docs / "glossary").mkdir(parents=True)
    (docs / "notation.yml").write_text(
        "symbols:\n  demo.value:\n    tex: '\\Delta_t'\n    typst: '#symb.demo.value'\n    description: Observed change.\n"
        "equations:\n  demo.identity:\n    tex: 'x=y'\n    typst: '#eqs.demo.identity'\n",
        encoding="utf-8",
    )
    (docs / "glossary" / "terms.yml").write_text("[]\n", encoding="utf-8")

    assert format_identifier("target_root_gain") == "Target Root Gain"
    assert symbol_label("demo.value", mode="Symbols", root=tmp_path) == r"$\Delta_t$"
    assert symbol_label("demo.value", mode="Both", root=tmp_path) == r"$\Delta_t$ — Observed change."
    assert equation_label("demo.identity", mode="Text", root=tmp_path) == "Demo.Identity"
    label = ScientificLabel("gain", "Observed change", "demo.value", "fraction")
    assert format_scientific_label(label, mode="Both", surface="markdown", root=tmp_path) == (
        r"$\Delta_t$ — Observed change (fraction)"
    )


def test_unknown_scientific_label_fails_closed(tmp_path) -> None:
    docs = tmp_path / "docs"
    (docs / "glossary").mkdir(parents=True)
    (docs / "notation.yml").write_text("symbols: {}\nequations: {}\n", encoding="utf-8")
    (docs / "glossary" / "terms.yml").write_text("[]\n", encoding="utf-8")
    with pytest.raises(TheoryResolutionError):
        symbol_label("missing", root=tmp_path)
    assert SCIENTIFIC_LABELS["cumulative_target_root_gain"].symbol_key == "rl.observed_cumulative_root_gain"
