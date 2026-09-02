#!/usr/bin/env python3
"""Report rendered Typst body content that crosses declared PDF column bounds.

Typst accepts a too-wide equation as a valid layout.  This checker consumes
Poppler's ``pdftotext -bbox-layout`` output after compilation and verifies that
each rendered text line remains inside the document's declared body column.
It intentionally checks rendered geometry rather than source heuristics: a
shared equation, table, or figure caption can overflow only after all Typst
styles, fonts, and attachments have been resolved.

The caller supplies left and right body margins in millimetres.  Header and
footer bands can be excluded because title pages and page numbers may use a
different layout contract.  A non-zero exit makes the warning CI-blocking;
``--warn-only`` is available while introducing a new contract to an existing
document with known layout debt.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as etree


POINTS_PER_MM = 72.0 / 25.4


@dataclass(frozen=True, slots=True)
class RenderedLine:
    """One non-empty PDF text line and its physical page-space bounds."""

    page: int
    page_width_pt: float
    page_height_pt: float
    x_min_pt: float
    x_max_pt: float
    y_min_pt: float
    y_max_pt: float
    text: str


@dataclass(frozen=True, slots=True)
class ColumnOverflow:
    """One rendered line crossing the configured left or right body edge."""

    line: RenderedLine
    left_bound_pt: float
    right_bound_pt: float

    def format(self, *, pdf: Path) -> str:
        sides: list[str] = []
        if self.line.x_min_pt < self.left_bound_pt:
            sides.append(f"left by {self.left_bound_pt - self.line.x_min_pt:.1f}pt")
        if self.line.x_max_pt > self.right_bound_pt:
            sides.append(f"right by {self.line.x_max_pt - self.right_bound_pt:.1f}pt")
        excerpt = " ".join(self.line.text.split())
        if len(excerpt) > 140:
            excerpt = excerpt[:137] + "..."
        return (
            f"WARNING typst-column-overflow: {pdf}:page {self.line.page}: "
            f"x=[{self.line.x_min_pt:.1f}, {self.line.x_max_pt:.1f}]pt outside "
            f"[{self.left_bound_pt:.1f}, {self.right_bound_pt:.1f}]pt "
            f"({', '.join(sides)}): {excerpt!r}"
        )


def _required_float(element: etree.Element, attribute: str) -> float:
    """Read one finite Poppler geometry attribute with a clear failure."""

    value = element.get(attribute)
    if value is None:
        raise ValueError(f"bbox XML line lacks {attribute!r}.")
    try:
        return float(value)
    except ValueError as error:
        raise ValueError(f"bbox XML line has non-numeric {attribute}={value!r}.") from error


def parse_bbox_layout(xml_text: str) -> tuple[RenderedLine, ...]:
    """Return text-line bounds from Poppler ``-bbox-layout`` XHTML output."""

    try:
        root = etree.fromstring(xml_text)
    except etree.ParseError as error:
        raise ValueError(f"pdftotext emitted invalid bbox XML: {error}.") from error
    pages = root.findall(".//{*}page")
    if not pages:
        raise ValueError("pdftotext bbox XML contains no pages.")
    lines: list[RenderedLine] = []
    for page_number, page in enumerate(pages, start=1):
        page_width = _required_float(page, "width")
        page_height = _required_float(page, "height")
        for line in page.findall(".//{*}line"):
            text = "".join(line.itertext()).strip()
            if not text:
                continue
            lines.append(
                RenderedLine(
                    page=page_number,
                    page_width_pt=page_width,
                    page_height_pt=page_height,
                    x_min_pt=_required_float(line, "xMin"),
                    x_max_pt=_required_float(line, "xMax"),
                    y_min_pt=_required_float(line, "yMin"),
                    y_max_pt=_required_float(line, "yMax"),
                    text=text,
                )
            )
    return tuple(lines)


def find_column_overflows(
    lines: tuple[RenderedLine, ...],
    *,
    left_margin_pt: float,
    right_margin_pt: float,
    tolerance_pt: float,
    top_exempt_pt: float,
    bottom_exempt_pt: float,
) -> tuple[ColumnOverflow, ...]:
    """Return body-band lines that exceed the rendered document column."""

    if min(left_margin_pt, right_margin_pt, tolerance_pt, top_exempt_pt, bottom_exempt_pt) < 0.0:
        raise ValueError("Margins, tolerance, and exempt bands must be non-negative.")
    findings: list[ColumnOverflow] = []
    for line in lines:
        if line.y_min_pt < top_exempt_pt or line.y_max_pt > line.page_height_pt - bottom_exempt_pt:
            continue
        left_bound = left_margin_pt - tolerance_pt
        right_bound = line.page_width_pt - right_margin_pt + tolerance_pt
        if line.x_min_pt < left_bound or line.x_max_pt > right_bound:
            findings.append(ColumnOverflow(line, left_bound, right_bound))
    return tuple(findings)


def _bbox_xml(pdf: Path, *, executable: str) -> str:
    """Extract Poppler line geometry for one already-compiled PDF."""

    if shutil.which(executable) is None:
        raise RuntimeError(f"Required PDF geometry tool {executable!r} is not available on PATH.")
    with tempfile.TemporaryDirectory(prefix="aria-typst-bbox-") as temporary:
        output = Path(temporary) / "bbox.xhtml"
        completed = subprocess.run(
            [executable, "-bbox-layout", str(pdf), str(output)],
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip()
            raise RuntimeError(f"{executable} failed for {pdf}: {detail}")
        return output.read_text(encoding="utf-8")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path, help="compiled Typst PDF to inspect")
    parser.add_argument("--left-margin-mm", type=float, required=True, help="declared body left margin in millimetres")
    parser.add_argument("--right-margin-mm", type=float, required=True, help="declared body right margin in millimetres")
    parser.add_argument("--tolerance-pt", type=float, default=2.0, help="per-side floating-point tolerance in points")
    parser.add_argument("--top-exempt-mm", type=float, default=15.0, help="ignore header/title band in millimetres")
    parser.add_argument("--bottom-exempt-mm", type=float, default=15.0, help="ignore footer/page-number band in millimetres")
    parser.add_argument("--pdftotext", default="pdftotext", help="Poppler pdftotext executable")
    parser.add_argument("--warn-only", action="store_true", help="print warnings but exit successfully")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the rendered-column contract and return a shell-compatible status."""

    args = _parser().parse_args(argv)
    pdf = args.pdf.resolve()
    if not pdf.is_file():
        print(f"ERROR typst-column-overflow: PDF does not exist: {pdf}", file=sys.stderr)
        return 2
    try:
        lines = parse_bbox_layout(_bbox_xml(pdf, executable=args.pdftotext))
        findings = find_column_overflows(
            lines,
            left_margin_pt=args.left_margin_mm * POINTS_PER_MM,
            right_margin_pt=args.right_margin_mm * POINTS_PER_MM,
            tolerance_pt=args.tolerance_pt,
            top_exempt_pt=args.top_exempt_mm * POINTS_PER_MM,
            bottom_exempt_pt=args.bottom_exempt_mm * POINTS_PER_MM,
        )
    except (OSError, RuntimeError, ValueError) as error:
        print(f"ERROR typst-column-overflow: {error}", file=sys.stderr)
        return 2
    for finding in findings:
        print(finding.format(pdf=pdf), file=sys.stderr)
    if findings and args.warn_only:
        print(
            f"WARNING typst-column-overflow: reported {len(findings)} rendered line(s); "
            "the warning baseline remains to be repaired before strict gating.",
            file=sys.stderr,
        )
        return 0
    if findings:
        print(
            "ERROR typst-column-overflow: rendered content exceeds the configured body column; "
            "split or re-layout the object, then recompile.",
            file=sys.stderr,
        )
        return 1
    print(f"Typst column-bound check passed: {pdf} ({len(lines)} rendered text lines).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
