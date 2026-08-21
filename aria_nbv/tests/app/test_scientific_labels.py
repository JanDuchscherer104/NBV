"""Tests for shared scientific label formatting and fail-closed resolution."""

from __future__ import annotations

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


def test_unknown_theory_labels_fail_closed(tmp_path: Path) -> None:
    _write_registry(tmp_path)
    with pytest.raises(TheoryResolutionError):
        symbol_label("missing_value", root=tmp_path)
    with pytest.raises(TheoryResolutionError):
        equation_label("missing_equation", root=tmp_path)


def test_scientific_inventory_formats_only_at_the_presentation_boundary(tmp_path: Path) -> None:
    _write_registry(tmp_path)
    label = ScientificLabel("raw_metric_key", "Observed change", "demo.value", "fraction")

    assert format_scientific_label(label, mode="Symbols", surface="markdown", root=tmp_path) == (
        r"$\Delta_t$ (fraction)"
    )
    assert format_scientific_label(label, mode="Both", surface="markdown", root=tmp_path) == (
        r"$\Delta_t$ — Observed change (fraction)"
    )
    assert format_scientific_label(label, mode="Symbols", surface="plain", root=tmp_path) == (
        "Observed change (fraction)"
    )
    assert format_scientific_label("unknown_metric", root=tmp_path) == "Unknown Metric"
    assert SCIENTIFIC_LABELS["cumulative_target_root_gain"].symbol_key == ("rl.observed_cumulative_root_gain")


def test_chart_notation_uses_markdown_surface_only_when_requested(monkeypatch) -> None:
    from aria_nbv.app.panels import common

    captions: list[str] = []
    monkeypatch.setattr(common, "get_label_display_mode", lambda: "Both")
    monkeypatch.setattr(common.st, "caption", captions.append)
    common.render_scientific_notation("cumulative_target_root_gain")

    assert captions == [r"**Notation:** $G_{0:s,\mathrm{root}}^e$ — Cumulative target root gain (fraction)"]

    monkeypatch.setattr(common, "get_label_display_mode", lambda: "Text")
    common.render_scientific_notation("cumulative_target_root_gain")
    assert len(captions) == 1


def test_ui_label_warns_and_uses_no_formula_when_registry_resolution_fails(monkeypatch) -> None:
    from aria_nbv.app.panels import common

    warnings: list[str] = []
    monkeypatch.setattr(common, "get_label_display_mode", lambda: "Both")
    monkeypatch.setattr(
        common,
        "format_scientific_label",
        lambda *args, **kwargs: (_ for _ in ()).throw(TheoryResolutionError("missing canonical symbol")),
    )
    monkeypatch.setattr(common.st, "warning", warnings.append)

    label = common.current_scientific_label("cumulative_target_root_gain", surface="markdown")

    assert label == "Cumulative target root gain (fraction)"
    assert warnings == ["Canonical notation is unavailable for 'cumulative_target_root_gain': missing canonical symbol"]


def test_every_configured_symbol_key_resolves_exactly() -> None:
    references = TheoryReferences(
        symbol_ids=tuple(
            sorted({label.symbol_key for label in SCIENTIFIC_LABELS.values() if label.symbol_key is not None})
        )
    )

    resolved = resolve_theory(references)

    assert {symbol.identifier for symbol in resolved.symbols} == set(references.symbol_ids)
    assert all(symbol.typst == f"#symb.{symbol.identifier}" for symbol in resolved.symbols)


def test_persisted_point_mesh_components_use_their_canonical_meanings() -> None:
    assert SCIENTIFIC_LABELS["pm_acc_after"].symbol_key == "oracle.dist_pm"
    assert SCIENTIFIC_LABELS["pm_comp_after"].symbol_key == "oracle.dist_mp"
