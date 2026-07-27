from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

import thesis_prune_audit  # noqa: E402


def test_closure_and_counts_ignore_comments_and_shared_definitions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    thesis = tmp_path / "docs/typst/thesis"
    shared = tmp_path / "docs/typst/shared"
    thesis.mkdir(parents=True)
    shared.mkdir(parents=True)
    (thesis / "main.typ").write_text(
        '#import "../shared/macros.typ": *\n#include "chapter.typ"\n', encoding="utf-8"
    )
    (thesis / "chapter.typ").write_text(
        "@term-a #symb.group.symbol #eqs.group.equation // @term-b #symb.group.other\n",
        encoding="utf-8",
    )
    (shared / "macros.typ").write_text("@term-b #symb.group.other\n", encoding="utf-8")
    glossary = shared / "glossary.typ"
    glossary.write_text('key: "term-a"\nkey: "term-b"\n', encoding="utf-8")
    notation = tmp_path / "docs/notation.yml"
    notation.write_text(
        "symbols:\n  group.symbol: {thesis_list: true}\n  group.other: {thesis_list: true}\n"
        "equations:\n  group.equation: {thesis_list: false}\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(thesis_prune_audit, "ROOT", tmp_path)
    monkeypatch.setattr(thesis_prune_audit, "THESIS_ROOT", thesis)
    monkeypatch.setattr(thesis_prune_audit, "GLOSSARY", glossary)
    monkeypatch.setattr(thesis_prune_audit, "NOTATION", notation)
    report = thesis_prune_audit.build_inventory(thesis / "main.typ")

    assert [row for row in report["glossary"] if row["key"] == "term-a"][0][
        "static_occurrences"
    ] == 1
    assert [row for row in report["glossary"] if row["key"] == "term-b"][0][
        "static_occurrences"
    ] == 0
    assert [row for row in report["symbols"] if row["key"] == "group.symbol"][0][
        "static_occurrences"
    ] == 1
    assert [row for row in report["symbols"] if row["key"] == "group.other"][0][
        "static_occurrences"
    ] == 0
    assert [row for row in report["equations"] if row["key"] == "group.equation"][0][
        "static_occurrences"
    ] == 1


def test_triage_coverage_rejects_a_missing_zero_use_item() -> None:
    inventory = {
        "glossary": [
            {"key": "unused", "static_occurrences": 0, "rendered_in_list": True}
        ],
        "symbols": [],
        "equations": [],
    }
    with pytest.raises(ValueError, match="coverage mismatch"):
        thesis_prune_audit.validate_triage_coverage(
            inventory, "#let prune_triage_registry = ()\n"
        )


def test_reader_visible_repository_paths_must_use_a_link_macro(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    thesis = tmp_path / "docs/typst/thesis"
    thesis.mkdir(parents=True)
    source = thesis / "chapter.typ"
    source.write_text("The source is aria_nbv/aria_nbv/example.py.\n", encoding="utf-8")
    monkeypatch.setattr(thesis_prune_audit, "ROOT", tmp_path)
    monkeypatch.setattr(thesis_prune_audit, "THESIS_ROOT", thesis)
    with pytest.raises(ValueError, match="must use #gh"):
        thesis_prune_audit.validate_reader_visible_source_links([source])

    source.write_text('#gh("aria_nbv/aria_nbv/example.py")\n', encoding="utf-8")
    thesis_prune_audit.validate_reader_visible_source_links([source])


def test_reader_visible_python_source_symbols_must_use_a_symbol_link(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    thesis = tmp_path / "docs/typst/thesis"
    thesis.mkdir(parents=True)
    source = thesis / "chapter.typ"
    monkeypatch.setattr(thesis_prune_audit, "ROOT", tmp_path)
    monkeypatch.setattr(thesis_prune_audit, "THESIS_ROOT", thesis)

    source.write_text("aria_nbv.rollouts.reader.RolloutReader\n", encoding="utf-8")
    with pytest.raises(ValueError, match="#gh-symbol"):
        thesis_prune_audit.validate_reader_visible_source_links([source])

    source.write_text(
        '#gh-symbol("aria_nbv.rollouts.reader.RolloutReader")\n', encoding="utf-8"
    )
    thesis_prune_audit.validate_reader_visible_source_links([source])
