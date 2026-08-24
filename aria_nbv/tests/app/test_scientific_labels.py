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
            equation_ids=("rl.target_root_gain_reward",),
            symbol_ids=("oracle.rri",),
            term_ids=("target-rri-reward",),
        ),
        root=Path(__file__).parents[3],
    )

    assert theory.equations[0].typst == "#eqs.rl.target_root_gain_reward"
    assert theory.symbols[0].typst == "#symb.oracle.rri"
    assert theory.equations[0].source_url.endswith("/docs/typst/shared/equations/rl.typ")
    assert theory.terms[0].label == "Target-Specific RRI"
    source_urls = [item.source_url for item in theory.equations]
    source_urls.extend(item.source_url for item in theory.symbols)
    source_urls.extend(item.source_url for item in theory.terms)
    assert all(source_url.startswith("https://github.com/") for source_url in source_urls)


def test_persisted_metric_labels_use_current_entity_symbol_owners() -> None:
    assert SCIENTIFIC_LABELS["selected_target_rri"].symbol_key == "entity.target_rri_marginal"
    assert SCIENTIFIC_LABELS["cumulative_target_rri"].symbol_key == "entity.target_rri_cumulative"
    assert SCIENTIFIC_LABELS["selected_target_root_gain"].symbol_key == "entity.target_reward"
    assert SCIENTIFIC_LABELS["target_root_gain"].symbol_key == "entity.target_reward"
    assert SCIENTIFIC_LABELS["cumulative_target_root_gain"].symbol_key == "entity.target_root_gain_cumulative"
    assert SCIENTIFIC_LABELS["return_h"].symbol_key == "entity.return_h"


def test_every_scientific_label_symbol_resolves_from_canonical_registry() -> None:
    root = Path(__file__).parents[3]
    symbol_ids = {label.symbol_key for label in SCIENTIFIC_LABELS.values() if label.symbol_key is not None}

    for symbol_id in sorted(symbol_ids):
        resolved = resolve_theory(TheoryReferences(symbol_ids=(symbol_id,)), root=root).symbols
        assert len(resolved) == 1
        assert resolved[0].identifier == symbol_id


def test_scientific_label_modes_resolve_at_the_presentation_boundary(tmp_path: Path) -> None:
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


def test_unknown_scientific_label_fails_closed(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    (docs / "glossary").mkdir(parents=True)
    (docs / "notation.yml").write_text("symbols: {}\nequations: {}\n", encoding="utf-8")
    (docs / "glossary" / "terms.yml").write_text("[]\n", encoding="utf-8")
    with pytest.raises(TheoryResolutionError):
        symbol_label("missing", root=tmp_path)


def test_theory_registry_cache_invalidates_on_content_replacement(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    (docs / "glossary").mkdir(parents=True)
    notation = docs / "notation.yml"
    notation.write_text(
        "symbols:\n  demo.value:\n    tex: 'x'\n    typst: '#symb.demo.value'\nequations: {}\n",
        encoding="utf-8",
    )
    (docs / "glossary" / "terms.yml").write_text("[]\n", encoding="utf-8")
    assert symbol_label("demo.value", mode="Symbols", root=tmp_path) == "$x$"
    notation.write_text(
        "symbols:\n  demo.value:\n    tex: 'y'\n    typst: '#symb.demo.value'\nequations: {}\n",
        encoding="utf-8",
    )
    assert symbol_label("demo.value", mode="Symbols", root=tmp_path) == "$y$"


def test_invalid_utf8_theory_registry_fails_closed(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    (docs / "glossary").mkdir(parents=True)
    (docs / "notation.yml").write_bytes(b"symbols: \xff\nequations: {}\n")
    (docs / "glossary" / "terms.yml").write_text("[]\n", encoding="utf-8")
    with pytest.raises(TheoryResolutionError):
        symbol_label("missing", root=tmp_path)


def test_narrative_explanation_requires_ordered_content() -> None:
    from aria_nbv.app.panels._stored_rollouts.shared import ExplanationSection, ScientificExplanation

    empty = ScientificExplanation(
        question="q", answer="a", sections=(), evidence_role="provenance", source_fields=("x",)
    )
    assert empty.sections == ()
    explanation = ScientificExplanation(
        question="What does this show?",
        answer="It describes persisted evidence.",
        sections=(ExplanationSection("Metric", "A descriptive count."),),
        evidence_role="provenance",
        source_fields=("inspection.rows",),
    )
    assert explanation.sections[0].title == "Metric"
