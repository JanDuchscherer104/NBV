"""Regression tests for the rendered Typst PDF column-bound contract."""

from __future__ import annotations

from contextlib import redirect_stderr
import importlib.util
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "check_typst_pdf_column_bounds.py"
SPEC = importlib.util.spec_from_file_location("check_typst_pdf_column_bounds", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


_BBOX_XML = """<?xml version="1.0"?>
<doc>
  <page width="600" height="800">
    <flow>
      <block xMin="90" yMin="100" xMax="500" yMax="112">
        <line xMin="90" yMin="100" xMax="500" yMax="112"><word>inside</word></line>
      </block>
      <block xMin="70" yMin="200" xMax="530" yMax="212">
        <line xMin="70" yMin="200" xMax="530" yMax="212"><word>too-wide equation</word></line>
      </block>
      <block xMin="40" yMin="10" xMax="560" yMax="22">
        <line xMin="40" yMin="10" xMax="560" yMax="22"><word>header exempt</word></line>
      </block>
    </flow>
  </page>
</doc>
"""


class PdfColumnBoundTests(unittest.TestCase):
    """Keep rendered-page detection independent from Poppler subprocess tests."""

    def test_detects_one_body_line_outside_the_declared_column(self) -> None:
        lines = MODULE.parse_bbox_layout(_BBOX_XML)

        findings = MODULE.find_column_overflows(
            lines,
            left_margin_pt=85.0,
            right_margin_pt=85.0,
            tolerance_pt=2.0,
            top_exempt_pt=40.0,
            bottom_exempt_pt=40.0,
        )

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].line.page, 1)
        self.assertIn("too-wide equation", findings[0].line.text)
        self.assertIn("left by", findings[0].format(pdf=Path("thesis.pdf")))
        self.assertIn("right by", findings[0].format(pdf=Path("thesis.pdf")))

    def test_rejects_incomplete_bbox_geometry(self) -> None:
        with self.assertRaisesRegex(ValueError, "xMax"):
            MODULE.parse_bbox_layout("<doc><page width='1' height='1'><line xMin='0'>x</line></page></doc>")

    def test_warn_only_reports_findings_without_failing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            pdf = Path(temporary_directory) / "thesis.pdf"
            pdf.touch()
            standard_error = io.StringIO()
            with patch.object(MODULE, "_bbox_xml", return_value=_BBOX_XML), redirect_stderr(standard_error):
                exit_code = MODULE.main(
                    [
                        str(pdf),
                        "--left-margin-mm",
                        "30",
                        "--right-margin-mm",
                        "30",
                        "--warn-only",
                    ]
                )

        self.assertEqual(exit_code, 0)
        self.assertIn("reported 1 rendered line", standard_error.getvalue())

    def test_strict_mode_fails_on_the_same_finding(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            pdf = Path(temporary_directory) / "thesis.pdf"
            pdf.touch()
            standard_error = io.StringIO()
            with patch.object(MODULE, "_bbox_xml", return_value=_BBOX_XML), redirect_stderr(standard_error):
                exit_code = MODULE.main(
                    [
                        str(pdf),
                        "--left-margin-mm",
                        "30",
                        "--right-margin-mm",
                        "30",
                    ]
                )

        self.assertEqual(exit_code, 1)
        self.assertIn("split or re-layout", standard_error.getvalue())


if __name__ == "__main__":
    unittest.main()
