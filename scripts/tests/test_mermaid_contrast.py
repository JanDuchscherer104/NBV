"""Regression tests for readable semantic Mermaid node labels."""

from __future__ import annotations

import re
from pathlib import Path

from scripts.quartodoc_generate_dependency_diagram import render_mermaid

REPO_ROOT = Path(__file__).resolve().parents[2]
SEMANTIC_CLASS_DEF = re.compile(
    r"classDef\s+(?:input|output|compute|data|package)\s+([^;]+);"
)
REQUIRED_LABEL_COLOR = "color:#17202A"


def _semantic_style_definitions(path: Path) -> list[str]:
    """Return semantic class definitions authored in one Mermaid-bearing file."""
    return SEMANTIC_CLASS_DEF.findall(path.read_text(encoding="utf-8"))


def test_authored_semantic_diagrams_pin_a_readable_label_color() -> None:
    """Prevent Quarto's dark Mermaid theme from muting text on pale node fills."""
    sources = [
        *sorted((REPO_ROOT / "docs" / "figures" / "diagrams").rglob("*.mmd")),
        *sorted((REPO_ROOT / "tools" / "mermaid").rglob("*.mmd")),
        REPO_ROOT / "aria_nbv" / "aria_nbv" / "lightning" / "README.md",
        REPO_ROOT / "aria_nbv" / "aria_nbv" / "vin" / "README.md",
    ]
    definitions = [
        definition
        for source in sources
        for definition in _semantic_style_definitions(source)
    ]

    assert definitions
    assert all(REQUIRED_LABEL_COLOR in definition for definition in definitions)


def test_generated_package_dependency_diagram_pins_the_same_color() -> None:
    """Keep the generated public-reference diagram aligned with authored sources."""
    definitions = SEMANTIC_CLASS_DEF.findall(render_mermaid(["vin"], []))

    assert definitions
    assert all(REQUIRED_LABEL_COLOR in definition for definition in definitions)
