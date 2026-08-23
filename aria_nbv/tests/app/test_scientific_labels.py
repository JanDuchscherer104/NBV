"""Regression tests for canonical scientific explanation references."""

from pathlib import Path

from aria_nbv.app.scientific_labels import TheoryReferences, resolve_theory


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
