#!/usr/bin/env python3
"""Executable, scope-aware hygiene checks for ARIA-NBV Typst authoring.

The checker is deliberately conservative: it audits authored thesis surfaces,
not generated projections, fixtures, or the shared equation implementations.
It is also a unittest module so the positive/negative context boundaries remain
executable documentation for future rule changes.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
THESIS_ROOT = ROOT / "docs" / "typst" / "thesis"
LABEL_SCOPE = {
    Path("docs/typst/thesis/sections/01-introduction.typ"): "submission",
    Path("docs/typst/thesis/sections/01-research-questions.typ"): "submission",
    Path("docs/typst/thesis/development/roadmap.typ"): "development",
    Path("docs/typst/thesis/development/m1-contract-report.typ"): "development",
}
EXPECTED_LABEL_COUNTS = {
    Path("docs/typst/thesis/sections/01-introduction.typ"): 5,
    Path("docs/typst/thesis/sections/01-research-questions.typ"): 12,
    Path("docs/typst/thesis/development/roadmap.typ"): 10,
    Path("docs/typst/thesis/development/m1-contract-report.typ"): 4,
}
LABEL_PREFIXES = ("ch:", "fig:", "tab:", "sec:", "ssec:", "claim-")
METADATA_LABELS = {"outcome"}
PREEXISTING_LABELS = {"sec:thesis-research-questions"}
LABEL_RE = re.compile(r"<([A-Za-z][A-Za-z0-9_:-]*)>")

# These are deliberately domain identifiers, rather than generic English
# words such as "implemented".  Code spans and guarded development prose are
# valid places to show an exact owner key.
RAW_PROSE_PATTERNS = (
    re.compile(r"\b(?:valid_action_mask|actor_action_mask|oracle_label_mask|q_train_mask)\b"),
    re.compile(r"\b(?:candidate_validity|candidate_support|candidate_row_id)\b"),
    re.compile(r"\b(?:V0|V1)\b"),
    re.compile(r"\bnot implemented\b", re.IGNORECASE),
    re.compile(r"\bthesis_status\b"),
)
RECURRING_RAW_PATTERNS = (
    re.compile(r"\bbold\(z\)_e\b"),
    re.compile(r"\bQ_\(H,theta\)\b"),
    re.compile(r"\bDelta_t\^e\b"),
    re.compile(r"\bJ_e\^\(H\)\b"),
    re.compile(r"\bG_t\^\(H\)\b"),
    re.compile(r'\bbold\(F\)_t\^"EVL"\b'),
    re.compile(r'\bbold\(O\)_t\^"pred"\b'),
)


@dataclass(frozen=True)
class Violation:
    path: Path
    line: int
    rule: str
    detail: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.rule}: {self.detail}"


def _relative(path: Path) -> Path:
    try:
        return path.resolve().relative_to(ROOT.resolve())
    except ValueError:
        return path


def _file_is_code_context(relative: Path) -> bool:
    return (
        "typst/thesis/development/" in relative.as_posix()
        or "typst/thesis/figures/" in relative.as_posix()
        or relative.name
        in {"draft_markers.typ", "experiment_data.typ", "glossary-overrides.typ"}
    )


def _token_is_explicit_code(line: str, match: re.Match[str]) -> bool:
    """Return whether one matched token is inside an explicit code span.

    Inline backticks and raw/code blocks are token-scoped. A formatting call
    such as ``#strong[V1]`` is intentionally *not* an exemption: it remains
    scientific prose and must not hide a status token on the same line.
    """
    start, end = match.span()
    for left, right in ((m.start(), m.end()) for m in re.finditer(r"`[^`]*`", line)):
        if left <= start and end <= right:
            return True
    for block in re.finditer(r"#(?:raw|code)\s*(?:\([^)]*\)|\[[^]]*\])", line):
        if block.start() <= start and end <= block.end():
            return True
    if re.search(r"#(?:import|thesis_status)\b", line):
        return True
    # Schema/report accessors are executable Typst code; only their quoted
    # field arguments receive the exemption, never neighboring prose.
    if re.search(r"#(?:fact-value|metadata|let|assert|json)\b", line):
        for quoted in re.finditer(r'"[^"\n]*"', line):
            if quoted.start() <= start and end <= quoted.end():
                return True
    return False


def _raw_display_violations(path: Path, lines: list[str]) -> list[Violation]:
    """Find standalone ``$``/``$$`` displays not delegated to ``#eqs.*``."""
    violations: list[Violation] = []
    in_display = False
    delimiter = ""
    start = 0
    body: list[str] = []
    for number, line in enumerate(lines, 1):
        stripped = line.strip()
        if not in_display:
            if stripped in {"$", "$$"}:
                in_display = True
                delimiter = stripped
                start = number
                body = []
            elif line.count("$$") >= 2:
                if "#eqs." not in line:
                    violations.append(
                        Violation(path, number, "raw-display", "use a shared #eqs.* equation consumer")
                    )
            continue
        if stripped == delimiter:
            if not any("#eqs." in item for item in body):
                violations.append(
                    Violation(path, start, "raw-display", "use a shared #eqs.* equation consumer")
                )
            in_display = False
            delimiter = ""
            body = []
        else:
            body.append(line)
    if in_display:
        violations.append(
            Violation(path, start, "raw-display", "unterminated raw display block")
        )
    return violations


def scan_text(path: Path, text: str) -> list[Violation]:
    """Return blocking violations for one authored Typst source file."""
    relative = _relative(path)
    violations: list[Violation] = []
    lines = text.splitlines()

    # Standalone `$` and `$$` displays are the audited authored-display forms.
    # Shared equation modules are owners and are intentionally outside the
    # thesis consumer scan.
    if relative.parts[:3] == ("docs", "typst", "thesis"):
        violations.extend(_raw_display_violations(path, lines))

    scope = LABEL_SCOPE.get(relative)
    if scope is not None and "generated" not in relative.parts:
        for number, line in enumerate(lines, 1):
            if "#metadata" in line or "#query" in line:
                continue
            for label in LABEL_RE.findall(line):
                if label in METADATA_LABELS or label.startswith(LABEL_PREFIXES):
                    continue
                violations.append(
                    Violation(path, number, "label-prefix", f"{scope} label <{label}> lacks an approved prefix")
                )

    if _file_is_code_context(relative):
        return violations
    for number, line in enumerate(lines, 1):
        if "#eqs." not in line and "#symb." not in line:
            for pattern in RECURRING_RAW_PATTERNS:
                match = pattern.search(line)
                if match and not _token_is_explicit_code(line, match):
                    violations.append(
                        Violation(path, number, "shared-notation", f"use a shared facade for {match.group(0)}")
                    )
        for pattern in RAW_PROSE_PATTERNS:
            match = pattern.search(line)
            if match and not _token_is_explicit_code(line, match):
                violations.append(
                    Violation(path, number, "scientific-prose", f"implementation/status token {match.group(0)!r} needs an explicit code or development context")
                )
    return violations


def scan_paths(paths: list[Path]) -> list[Violation]:
    violations: list[Violation] = []
    for target in paths:
        if target.is_file() and target.suffix == ".typ":
            violations.extend(scan_text(target, target.read_text(encoding="utf-8")))
        elif target.is_dir():
            for path in sorted(target.rglob("*.typ")):
                if "generated" in path.parts or "assets" in path.parts:
                    continue
                violations.extend(scan_text(path, path.read_text(encoding="utf-8")))
    return violations


class HygieneTests(unittest.TestCase):
    def test_raw_display_is_blocking(self) -> None:
        path = ROOT / "docs/typst/thesis/sections/fixture.typ"
        self.assertTrue(scan_text(path, "$$\nx = 1\n$$"))
        self.assertTrue(scan_text(path, "$\nx = 1\n$"))

    def test_shared_equation_consumer_is_allowed(self) -> None:
        path = ROOT / "docs/typst/thesis/sections/fixture.typ"
        self.assertEqual(scan_text(path, "$#eqs.rri.error$"), [])
        self.assertEqual(scan_text(path, "$\n#eqs.rri.error\n$"), [])

    def test_local_binders_are_not_global_notation_obligations(self) -> None:
        path = ROOT / "docs/typst/thesis/sections/fixture.typ"
        self.assertEqual(scan_text(path, "$sum_(i in cal(I)) x_i$"), [])

    def test_prose_boundary_allows_code_and_development(self) -> None:
        path = ROOT / "docs/typst/thesis/sections/fixture.typ"
        self.assertTrue(scan_text(path, "The q_train_mask is used."))
        self.assertEqual(scan_text(path, "The `q_train_mask` field is serialized."), [])
        self.assertTrue(scan_text(path, "The `field` V1 descriptor is planned."))
        self.assertTrue(scan_text(path, "#strong[V1] remains planned."))
        self.assertEqual(scan_text(path, "#raw[V1]"), [])
        self.assertEqual(scan_text(path, '#fact-value(store, "candidate_validity.valid")'), [])
        self.assertEqual(scan_text(path, "#import \"draft_markers.typ\": thesis_status"), [])
        development = ROOT / "docs/typst/thesis/development/fixture.typ"
        self.assertEqual(scan_text(development, "V0 is a development baseline."), [])

    def test_labels_require_prefix_but_metadata_is_excluded(self) -> None:
        path = ROOT / "docs/typst/thesis/sections/01-research-questions.typ"
        self.assertTrue(scan_text(path, "= Heading <rq1>"))
        self.assertEqual(scan_text(path, "= Heading <sec:rq1>"), [])
        roadmap = ROOT / "docs/typst/thesis/development/roadmap.typ"
        self.assertEqual(scan_text(roadmap, "#metadata(\"roadmap-outcome\") <outcome>"), [])

    def test_live_label_inventory_is_stable(self) -> None:
        totals = {"submission": 0, "development": 0}
        for relative, expected in EXPECTED_LABEL_COUNTS.items():
            path = ROOT / relative
            labels = [
                label
                for label in LABEL_RE.findall(path.read_text(encoding="utf-8"))
                if label not in METADATA_LABELS and label not in PREEXISTING_LABELS
            ]
            self.assertEqual(len(labels), expected, relative)
            totals[LABEL_SCOPE[relative]] += len(labels)
        self.assertEqual(totals, {"submission": 17, "development": 14})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scan", nargs="*", type=Path, help="scan Typst files/directories")
    parser.add_argument("--examples", action="store_true", help="run positive/negative fixtures")
    args = parser.parse_args(argv)
    if args.scan is not None:
        paths = [path if path.is_absolute() else ROOT / path for path in args.scan]
        violations = scan_paths(paths or [THESIS_ROOT])
        for violation in violations:
            print(violation, file=sys.stderr)
        return 1 if violations else 0
    result = unittest.main(
        module=__name__, argv=[sys.argv[0]], exit=False, verbosity=2
    )
    return 0 if result.result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
