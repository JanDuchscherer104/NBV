"""Regression tests for Typst-owned glossary notation adapters."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest import mock

import yaml
import pytest


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


def test_thesis_list_rejects_duplicate_rendered_tex() -> None:
    """The List of Symbols has one canonical entry per rendered notation."""

    notation = {
        "symbols": {
            "rl.reward": {
                "tex": "r_t^e",
                "description": "Reward.",
                "thesis_list": True,
            },
            "entity.reward": {
                "tex": " r_t^e ",
                "description": "Duplicate reward.",
                "thesis_list": True,
            },
        },
        "equations": {},
    }

    with pytest.raises(glossary_build.GlossaryError, match="duplicate thesis-list TeX"):
        glossary_build._validate_notation_metadata(notation)


def test_notation_expression_validation_imports_selected_facades(
    tmp_path: Path,
) -> None:
    """Custom facade metadata is compiled against those same custom facades."""

    symbols = tmp_path / "symbols.typ"
    equations = tmp_path / "equations.typ"
    symbols.write_text("#let symb = ()\n", encoding="utf-8")
    equations.write_text("#let eqs = ()\n", encoding="utf-8")
    compiled: list[str] = []

    def compile_fixture(command: list[str], **_: object) -> mock.Mock:
        fixture = Path(command[-2])
        compiled.append(fixture.read_text(encoding="utf-8"))
        return mock.Mock(returncode=0, stdout="", stderr="")

    with mock.patch.object(glossary_build.subprocess, "run", compile_fixture):
        glossary_build._validate_typst_notation_expressions(
            {
                "symbols": {
                    "custom.value": {
                        "typst": "#symb.custom.value",
                    }
                },
                "equations": {},
            },
            symbols_path=symbols,
            equations_path=equations,
        )

    assert len(compiled) == 1
    source = compiled[0]
    assert "/tmp/pytest-" in source
    assert 'symbols.typ": symb' in source
    assert 'equations.typ": eqs' in source
