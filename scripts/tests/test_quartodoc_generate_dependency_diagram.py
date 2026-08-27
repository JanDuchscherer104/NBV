#!/usr/bin/env python3
"""Lock the generated API dependency diagram's self-contained contrast style."""

from __future__ import annotations

import sys
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import quartodoc_generate_dependency_diagram as diagram  # noqa: E402


class DependencyDiagramMermaidTests(unittest.TestCase):
    def test_package_diagram_owns_readable_base_theme_style(self) -> None:
        rendered = diagram.render_mermaid(
            ["configs", "utils"], [("configs", "utils", 3)]
        )

        self.assertIn("theme: base", rendered)
        self.assertIn("flowchart LR", rendered)
        self.assertIn('configs -->|"3"| utils', rendered)
        self.assertIn('primaryTextColor: "#1F2937"', rendered)
        self.assertIn('lineColor: "#64748B"', rendered)
        self.assertIn('edgeLabelBackground: "#ffffff"', rendered)
        self.assertIn(".edgeLabel { color: #1F2937; background-color: #ffffff; }", rendered)
        self.assertIn(
            "classDef package fill:#E1D5E7,stroke:#9673A6,color:#1F2937,font-weight:600",
            rendered,
        )
        for unused in ("input", "output", "compute", "data"):
            self.assertNotIn(f"classDef {unused}", rendered)


if __name__ == "__main__":
    unittest.main()
