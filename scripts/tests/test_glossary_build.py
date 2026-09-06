"""Regression tests for Typst-owned glossary notation adapters."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest import mock

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


def test_typst_term_adapter_reads_canonical_entries_without_copying_definitions(
    tmp_path: Path,
) -> None:
    """Legacy term constants project the canonical source at Typst runtime."""

    output = tmp_path / "glossary.generated.typ"
    glossary_build._render_typst(
        [
            {
                "id": "example-term",
                "label": "Canonical Long Definition",
                "short": "CT",
                "anchor": "term-example-term",
                "definition_short": "A definition that must not be copied.",
                "typst_macro": "CT",
            }
        ],
        output,
    )

    source = output.read_text(encoding="utf-8")
    assert '#import "glossary.typ": aria-glossary-entries' in source
    assert '#let CT = _canonical-short("example-term")' in source
    assert '#let CT_full = _canonical-long("example-term")' in source
    assert "Canonical Long Definition" not in source
    assert "A definition that must not be copied." not in source
    assert "#let glossary =" not in source
    assert "glossary-list" not in source


def test_typst_notation_adapter_serializes_each_entry_once(tmp_path: Path) -> None:
    """The Typst projection exposes only the list consumed by notation.typ."""

    output = tmp_path / "notation.generated.typ"
    glossary_build._render_notation_typst(
        {
            "symbols": {
                "example.value": {
                    "tex": "x",
                    "typst": "#symb.example.value",
                    "description": "One canonical projection.",
                    "thesis_list": True,
                    "order": 1,
                }
            },
            "equations": {},
        },
        output,
    )

    source = output.read_text(encoding="utf-8")
    assert "#let notation-symbols-list =" in source
    assert "#let notation-symbols =" not in source
    assert source.count('key: "example.value"') == 1


def test_counterfactual_state_and_value_metadata_keep_abstract_contracts() -> None:
    """Public notation must not revive concrete-CF0 or fixed-H legacy formulas."""

    notation = glossary_build._load_typst_notation(
        ROOT / "docs/typst/shared/symbols.typ",
        ROOT / "docs/typst/shared/equations.typ",
    )
    state_tex = notation["equations"]["rl.s_cf0"]["tex"]
    value_tex = notation["equations"]["rl.q_h"]["tex"]

    assert "\\boldsymbol{\\Phi}_t^{\\mathrm{scene}}" in state_tex
    assert "\\boldsymbol{\\phi}_e" in state_tex
    assert "\\mathcal{P}_t" not in state_tex
    assert "Q_{h,e}^{\\star}" in value_tex
    assert "\\Pi^{\\mathrm{act}}" in value_tex
    assert "1\\le h\\le b_t\\le H_{\\max}" in value_tex
    assert "Q_H(s_t^{\\mathrm{cf0}}" not in value_tex
