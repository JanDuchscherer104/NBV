"""Regression tests for Typst-owned glossary notation adapters."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location(
    "glossary_build", ROOT / "scripts/glossary_build.py"
)
assert _SPEC is not None and _SPEC.loader is not None
glossary_build = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(glossary_build)


def test_notation_registry_is_derived_from_shared_typst_facades() -> None:
    """The generated registry has no independent YAML notation owner."""

    notation = glossary_build._load_typst_notation(
        ROOT / "docs/typst/shared/symbols.typ",
        ROOT / "docs/typst/shared/equations.typ",
    )

    assert notation["symbols"]["oracle.err"] == {
        "tex": "D",
        "typst": "#symb.oracle.err",
        "description": "Aggregate point-mesh reconstruction error used by RRI definitions.",
        "thesis_list": True,
        "order": 100,
    }
    assert notation["symbols"]["rl.acquisition_cost"] == {
        "tex": "C(\\tau)",
        "typst": "#symb.rl.acquisition_cost",
        "description": "Acquisition cost of a selected trajectory.",
        "thesis_list": True,
        "order": 420,
    }
    assert "rri.cd_value" not in notation["symbols"]
    assert notation["equations"]["rri.cd"]["typst"] == "#eqs.rri.cd"


def test_generated_notation_yaml_is_a_lossless_runtime_adapter(tmp_path: Path) -> None:
    """The checked-in YAML can be regenerated solely from canonical Typst."""

    notation = glossary_build._load_typst_notation(
        ROOT / "docs/typst/shared/symbols.typ",
        ROOT / "docs/typst/shared/equations.typ",
    )
    output = tmp_path / "notation.yml"
    glossary_build._render_notation_yaml(notation, output)

    assert "do not edit by hand" in output.read_text(encoding="utf-8")
    assert yaml.safe_load(output.read_text(encoding="utf-8")) == notation
    assert glossary_build.load_notation(output) == notation
