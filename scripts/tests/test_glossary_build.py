from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

import glossary_build  # noqa: E402


def _write_section(root: Path, source: str) -> None:
    path = root / "docs/typst/thesis/sections/chapter.typ"
    path.parent.mkdir(parents=True)
    path.write_text(source, encoding="utf-8")


def test_thesis_notation_allows_native_shared_equation_display(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_section(tmp_path, "$\n  #eqs.metrics.closest_point_witness\n$\n")
    monkeypatch.setattr(glossary_build, "ROOT", tmp_path)

    glossary_build._validate_thesis_notation_ownership()


def test_thesis_notation_rejects_locally_owned_display_math(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_section(tmp_path, "$\n  x = y + 1\n$\n")
    monkeypatch.setattr(glossary_build, "ROOT", tmp_path)

    with pytest.raises(glossary_build.GlossaryError, match="raw display equation"):
        glossary_build._validate_thesis_notation_ownership()
