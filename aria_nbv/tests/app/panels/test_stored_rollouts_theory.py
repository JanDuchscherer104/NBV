"""Tests for canonical theory references in stored-rollout explanations."""

# ruff: noqa: S101, SLF001

from __future__ import annotations

import os
from pathlib import Path

import pytest

from aria_nbv.app.panels._stored_rollouts import theory


def _write_registry(root: Path, *, equation_tex: str = "x=y") -> None:
    docs = root / "docs"
    (docs / "glossary").mkdir(parents=True, exist_ok=True)
    (docs / "notation.yml").write_text(
        "symbols:\n"
        "  demo.value:\n"
        "    tex: 'x'\n"
        "    typst: '#symb.demo.value'\n"
        "    description: Demo value.\n"
        "equations:\n"
        "  demo.identity:\n"
        f"    tex: '{equation_tex}'\n"
        "    typst: '#eqs.demo.identity'\n",
        encoding="utf-8",
    )
    (docs / "glossary" / "terms.yml").write_text(
        "- id: demo-term\n"
        "  label: Demo Term\n"
        "  short: demo\n"
        "  definition_short: A compact generated glossary definition.\n",
        encoding="utf-8",
    )


def test_theory_registry_resolves_equations_symbols_terms_and_sources(tmp_path: Path) -> None:
    _write_registry(tmp_path)

    resolved = theory.resolve_theory(
        theory.TheoryReferences(
            equation_ids=("demo.identity",),
            symbol_ids=("demo.value",),
            term_ids=("demo-term",),
        ),
        root=tmp_path,
    )

    assert resolved.equations[0].tex == "x=y"
    assert resolved.equations[0].source_url.endswith("docs/typst/shared/equations/demo.typ")
    assert resolved.symbols[0].description == "Demo value."
    assert resolved.symbols[0].source_url.endswith("docs/typst/shared/symbols/demo.typ")
    assert resolved.terms[0].definition == "A compact generated glossary definition."
    assert resolved.terms[0].source_url.endswith("docs/typst/shared/glossary.typ")


def test_theory_registry_cache_invalidates_when_notation_content_changes_without_stat_change(tmp_path: Path) -> None:
    _write_registry(tmp_path, equation_tex="x=y")
    references = theory.TheoryReferences(equation_ids=("demo.identity",))
    first = theory.resolve_theory(references, root=tmp_path)

    notation = tmp_path / "docs" / "notation.yml"
    original_stat = notation.stat()
    _write_registry(tmp_path, equation_tex="x=z")
    os.utime(notation, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
    second = theory.resolve_theory(references, root=tmp_path)

    assert first.equations[0].tex == "x=y"
    assert second.equations[0].tex == "x=z"


def test_theory_registry_cache_invalidates_when_glossary_content_changes_without_stat_change(tmp_path: Path) -> None:
    _write_registry(tmp_path)
    references = theory.TheoryReferences(term_ids=("demo-term",))
    first = theory.resolve_theory(references, root=tmp_path)

    terms = tmp_path / "docs" / "glossary" / "terms.yml"
    original_stat = terms.stat()
    terms.write_text(terms.read_text(encoding="utf-8").replace("Demo Term", "Alt. Term"), encoding="utf-8")
    os.utime(terms, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
    second = theory.resolve_theory(references, root=tmp_path)

    assert first.terms[0].label == "Demo Term"
    assert second.terms[0].label == "Alt. Term"


@pytest.mark.parametrize("malformation", ["missing", "invalid-yaml", "unknown-key"])
def test_theory_registry_fails_closed_with_actionable_error(tmp_path: Path, malformation: str) -> None:
    references = theory.TheoryReferences(equation_ids=("demo.identity",))
    if malformation != "missing":
        _write_registry(tmp_path)
    if malformation == "invalid-yaml":
        (tmp_path / "docs" / "notation.yml").write_text("equations: [", encoding="utf-8")
    if malformation == "unknown-key":
        references = theory.TheoryReferences(equation_ids=("demo.missing",))

    with pytest.raises(theory.TheoryResolutionError, match="canonical theory"):
        theory.resolve_theory(references, root=tmp_path)


def test_scientific_guide_warns_and_continues_for_invalid_registry_encoding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_registry(tmp_path)
    (tmp_path / "docs" / "notation.yml").write_bytes(b"equations:\n  demo.identity: \xff")
    warnings: list[str] = []
    rendered: list[str] = []
    monkeypatch.setattr(shared.st, "warning", warnings.append)
    monkeypatch.setattr(shared.st, "markdown", lambda body, **_kwargs: rendered.append(body))
    monkeypatch.setattr(
        shared,
        "resolve_theory",
        lambda references: theory.resolve_theory(references, root=tmp_path),
    )

    shared._render_scientific_guide(
        shared.ScientificExplanation(
            question="What does the equation mean?",
            answer="The plot remains available while canonical theory is unavailable.",
            sections=(shared.ExplanationSection("Interpretation", "Use the factual plot values."),),
            theory=theory.TheoryReferences(equation_ids=("demo.identity",)),
            evidence_role="oracle/evaluation",
            source_fields=("steps/value",),
        )
    )

    assert len(warnings) == 1
    assert warnings[0].startswith("Canonical theory unavailable: cannot load canonical theory metadata")
    assert "### Interpretation" in rendered
