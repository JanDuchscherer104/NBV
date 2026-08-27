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
    Path("docs/typst/thesis/sections/01-introduction.typ"): 3,
    Path("docs/typst/thesis/sections/01-research-questions.typ"): 10,
    Path("docs/typst/thesis/development/roadmap.typ"): 10,
    Path("docs/typst/thesis/development/m1-contract-report.typ"): 4,
}
LABEL_PREFIXES = ("ch:", "fig:", "tab:", "sec:", "ssec:")
METADATA_LABELS = {"outcome"}
PREEXISTING_LABELS = {"sec:thesis-research-questions"}
LABEL_RE = re.compile(r"<([A-Za-z][A-Za-z0-9_:-]*)>")

# These are deliberately domain identifiers, rather than generic English
# words such as "implemented".  Code spans and guarded development prose are
# valid places to show an exact owner key.
RAW_PROSE_PATTERNS = (
    re.compile(
        r"\b(?:valid_action_mask|actor_action_mask|oracle_label_mask|q_train_mask)\b"
    ),
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

# Table policy is derived from every active authored Typst family rather than a
# second hand-maintained file inventory. The template owns title-page layout;
# archived sources and package manuals are historical/reference material.
TABLE_PACKAGE_IMPORT_RE = re.compile(
    r'(?m)^[ \t]*#import\s+"@preview/([^":]+)(?::[^" ]+)?"', re.IGNORECASE
)
TABLE_CALL_RE = re.compile(
    r"(?<![\w-])(?:#)?(table|publication-table|development-table|presentation-table)\s*\("
)
TABLE_ALIAS_RE = re.compile(
    r"(?m)^[ \t]*#?let\s+[A-Za-z_][\w-]*\s*=\s*"
    r"(?:table|publication-table|development-table|presentation-table)\b"
)
TABLE_PACKAGE_NAMES = {"booktabs", "tablex", "tblr", "tabularx", "tabut"}
SHARED_TABLE_IMPORT_RE = re.compile(
    r'(?m)^[ \t]*#import\s+"(?:tables\.typ|(?:\.\./)+shared/tables\.typ)"\s*:\s*([^\n]+)'
)
SHARED_TABLE_ALIAS_IMPORT_RE = re.compile(
    r'(?m)^[ \t]*#import\s+"(?:tables\.typ|(?:\.\./)+shared/tables\.typ)"'
    r"(?:\s+as\s+[A-Za-z_][\w-]*|\s*:[^\n]*\bas\b)"
)


@dataclass(frozen=True)
class TableCall:
    """One active table constructor call and its source span."""

    path: Path
    line: int
    constructor: str
    body: str


def _table_source_paths() -> list[Path]:
    """Return every active authored table surface with narrow exclusions."""
    roots = (
        THESIS_ROOT / "sections",
        THESIS_ROOT / "appendix",
        THESIS_ROOT / "development",
        ROOT / "docs/typst/seminar_paper",
        ROOT / "docs/typst/seminar_slides",
        ROOT / "docs/typst/thesis_slides",
    )
    discovered = [
        path
        for root in roots
        for path in sorted(root.rglob("*.typ"))
        if "generated" not in path.parts
        and "assets" not in path.parts
        and "tests" not in path.parts
    ]
    return sorted(
        set(discovered)
        | {
            THESIS_ROOT / "main.typ",
            ROOT / "docs/typst/shared/notation.typ",
            ROOT / "docs/typst/shared/slide-template.typ",
        }
    )


def _table_surface(path: Path) -> str | None:
    """Classify one authored source by the shared constructor it must use."""
    relative = _relative(path)
    if relative == Path("docs/typst/shared/notation.typ"):
        return "publication"
    if relative.parts[:3] == ("docs", "typst", "seminar_paper"):
        return "publication"
    if relative.parts[:3] in {
        ("docs", "typst", "seminar_slides"),
        ("docs", "typst", "thesis_slides"),
    }:
        return "presentation"
    if relative.parts[:4] == ("docs", "typst", "thesis", "development"):
        return "development"
    if relative.parts[:4] in {
        ("docs", "typst", "thesis", "sections"),
        ("docs", "typst", "thesis", "appendix"),
    }:
        return "publication"
    return None


def _table_call_at(text: str, match: re.Match[str]) -> str:
    """Return the balanced constructor body, tolerating quoted strings."""
    opening = text.find("(", match.start(), match.end())
    depth = 0
    quoted = False
    escaped = False
    for index in range(opening, len(text)):
        char = text[index]
        if char == '"' and not escaped:
            quoted = not quoted
        escaped = char == "\\" and not escaped
        if quoted:
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return text[opening + 1 : index]
        if char != "\\":
            escaped = False
    return text[opening + 1 :]


def _mask_typst_non_code(text: str, *, mask_strings: bool = True) -> str:
    """Mask comments and optionally strings while preserving source offsets."""
    output = list(text)
    index = 0
    block_depth = 0
    while index < len(text):
        if block_depth:
            if text.startswith("/*", index):
                output[index : index + 2] = "  "
                block_depth += 1
                index += 2
            elif text.startswith("*/", index):
                output[index : index + 2] = "  "
                block_depth -= 1
                index += 2
            else:
                if text[index] != "\n":
                    output[index] = " "
                index += 1
            continue
        if text.startswith("//", index):
            while index < len(text) and text[index] != "\n":
                output[index] = " "
                index += 1
            continue
        if text.startswith("/*", index):
            output[index : index + 2] = "  "
            block_depth = 1
            index += 2
            continue
        if text[index] == '"':
            if mask_strings:
                output[index] = " "
            index += 1
            escaped = False
            while index < len(text):
                char = text[index]
                if mask_strings and char != "\n":
                    output[index] = " "
                index += 1
                if char == '"' and not escaped:
                    break
                escaped = char == "\\" and not escaped
                if char != "\\":
                    escaped = False
            continue
        index += 1
    return "".join(output)


def _table_calls(path: Path, text: str) -> list[TableCall]:
    calls: list[TableCall] = []
    for match in TABLE_CALL_RE.finditer(_mask_typst_non_code(text)):
        line = text.count("\n", 0, match.start()) + 1
        calls.append(TableCall(path, line, match.group(1), _table_call_at(text, match)))
    return calls


def scan_table_style_text(path: Path, text: str) -> list[Violation]:
    """Check table ownership, semantic headers, and package boundaries."""
    relative = _relative(path)
    surface = _table_surface(path)
    active_support_file = relative in {
        Path("docs/typst/thesis/main.typ"),
        Path("docs/typst/shared/slide-template.typ"),
    }
    if surface is None and not active_support_file:
        return []

    violations: list[Violation] = []
    code = _mask_typst_non_code(text)
    comment_free = _mask_typst_non_code(text, mask_strings=False)
    calls = _table_calls(path, text)
    required = {
        "publication": "publication-table",
        "development": "development-table",
        "presentation": "presentation-table",
    }.get(surface)
    imported = {
        name.strip()
        for match in SHARED_TABLE_IMPORT_RE.finditer(comment_free)
        for name in match.group(1).split(",")
    }
    for match in TABLE_ALIAS_RE.finditer(code):
        violations.append(
            Violation(
                path,
                text.count("\n", 0, match.start()) + 1,
                "table-constructor-alias",
                "call the shared table constructor directly",
            )
        )
    for number, line in enumerate(comment_free.splitlines(), 1):
        if SHARED_TABLE_ALIAS_IMPORT_RE.search(line):
            violations.append(
                Violation(
                    path,
                    number,
                    "table-constructor-alias",
                    "import the shared table constructor without an alias",
                )
            )
    if (
        calls
        and required is not None
        and required not in imported
        and "*" not in imported
    ):
        violations.append(
            Violation(
                path,
                calls[0].line,
                "table-owner-import",
                f"import {required} from the shared tables owner",
            )
        )
    for call in calls:
        if call.constructor != required:
            rule = f"{surface}-table-owner"
            violations.append(
                Violation(path, call.line, rule, f"use shared {required} constructor")
            )
        if "header:" not in call.body:
            violations.append(
                Violation(
                    path,
                    call.line,
                    "semantic-table-header",
                    "every active table needs a shared semantic header",
                )
            )

    for number, line in enumerate(comment_free.splitlines(), 1):
        package = TABLE_PACKAGE_IMPORT_RE.search(line)
        if package and package.group(1).lower() in TABLE_PACKAGE_NAMES:
            violations.append(
                Violation(
                    path,
                    number,
                    "table-package-import",
                    "import the shared tables API, not a table package",
                )
            )
    return violations


def scan_table_style_paths(paths: list[Path] | None = None) -> list[Violation]:
    """Scan the derived active table inventory, or explicitly supplied paths."""
    targets = _table_source_paths() if paths is None else paths
    violations: list[Violation] = []
    for path in targets:
        violations.extend(scan_table_style_text(path, path.read_text(encoding="utf-8")))
    return violations


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
    if re.search(r"#(?:fact-value|metadata|let|assert|json)\b", line) or re.search(
        r"\b(?:key|low-key|high-key|denominator-key):\s*\"", line
    ):
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
                        Violation(
                            path,
                            number,
                            "raw-display",
                            "use a shared #eqs.* equation consumer",
                        )
                    )
            continue
        if stripped == delimiter:
            if not any("#eqs." in item for item in body):
                violations.append(
                    Violation(
                        path,
                        start,
                        "raw-display",
                        "use a shared #eqs.* equation consumer",
                    )
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
    violations: list[Violation] = scan_table_style_text(path, text)
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
                    Violation(
                        path,
                        number,
                        "label-prefix",
                        f"{scope} label <{label}> lacks an approved prefix",
                    )
                )

    if _file_is_code_context(relative):
        return violations
    for number, line in enumerate(lines, 1):
        if "#eqs." not in line and "#symb." not in line:
            for pattern in RECURRING_RAW_PATTERNS:
                match = pattern.search(line)
                if match and not _token_is_explicit_code(line, match):
                    violations.append(
                        Violation(
                            path,
                            number,
                            "shared-notation",
                            f"use a shared facade for {match.group(0)}",
                        )
                    )
        for pattern in RAW_PROSE_PATTERNS:
            match = pattern.search(line)
            if match and not _token_is_explicit_code(line, match):
                violations.append(
                    Violation(
                        path,
                        number,
                        "scientific-prose",
                        f"implementation/status token {match.group(0)!r} needs an explicit code or development context",
                    )
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
        self.assertEqual(
            scan_text(path, '#fact-value(store, "candidate_validity.valid")'), []
        )
        self.assertEqual(
            scan_text(path, '#import "draft_markers.typ": thesis_status'), []
        )
        development = ROOT / "docs/typst/thesis/development/fixture.typ"
        self.assertEqual(scan_text(development, "V0 is a development baseline."), [])

    def test_labels_require_prefix_but_metadata_is_excluded(self) -> None:
        path = ROOT / "docs/typst/thesis/sections/01-research-questions.typ"
        self.assertTrue(scan_text(path, "= Heading <rq1>"))
        self.assertEqual(scan_text(path, "= Heading <sec:rq1>"), [])
        roadmap = ROOT / "docs/typst/thesis/development/roadmap.typ"
        self.assertEqual(
            scan_text(roadmap, '#metadata("roadmap-outcome") <outcome>'), []
        )

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
        self.assertEqual(totals, {"submission": 13, "development": 14})

    def test_active_table_inventory_is_derived_and_scoped(self) -> None:
        """All authored scientific tables are covered; layout tables are not."""
        calls = [
            call
            for path in _table_source_paths()
            for call in _table_calls(path, path.read_text(encoding="utf-8"))
        ]
        publication = [
            call for call in calls if _table_surface(call.path) == "publication"
        ]
        development = [
            call for call in calls if _table_surface(call.path) == "development"
        ]
        presentation = [
            call for call in calls if _table_surface(call.path) == "presentation"
        ]
        self.assertEqual(len(publication), 29)
        self.assertEqual(len(development), 1)
        self.assertEqual(len(presentation), 12)
        titlepage = ROOT / "docs/typst/thesis/template/layout/titlepage.typ"
        self.assertEqual(
            _table_calls(titlepage, titlepage.read_text(encoding="utf-8")), []
        )

    def test_live_authored_table_surfaces_use_shared_styles(self) -> None:
        self.assertEqual(scan_table_style_paths(), [])

    def test_publication_table_requires_shared_constructor(self) -> None:
        path = ROOT / "docs/typst/thesis/sections/fixture.typ"
        violations = scan_table_style_text(
            path, "table(table.header([*Header*]), [value])"
        )
        self.assertTrue(
            any(item.rule == "publication-table-owner" for item in violations)
        )

    def test_shared_constructor_requires_authoritative_import(self) -> None:
        path = ROOT / "docs/typst/thesis/sections/fixture.typ"
        text = "#let publication-table(..args) = table(..args)\n#publication-table(header: ([*Header*],))"
        violations = scan_table_style_text(path, text)
        self.assertTrue(any(item.rule == "table-owner-import" for item in violations))

    def test_active_table_requires_semantic_header(self) -> None:
        path = ROOT / "docs/typst/thesis/sections/fixture.typ"
        violations = scan_table_style_text(path, "publication-table([value])")
        self.assertTrue(
            any(item.rule == "semantic-table-header" for item in violations)
        )

    def test_shared_table_owner_emits_semantic_header(self) -> None:
        owner = ROOT / "docs/typst/shared/tables.typ"
        text = owner.read_text(encoding="utf-8")
        self.assertIn("table.header(..header)", text)
        self.assertIn("assert(header.len() > 0", text)

    def test_nested_raw_table_is_rejected(self) -> None:
        path = ROOT / "docs/typst/thesis/sections/fixture.typ"
        violations = scan_table_style_text(
            path, "#align(center, table(table.header([*Header*]), [value]))"
        )
        self.assertTrue(
            any(item.rule == "publication-table-owner" for item in violations)
        )

    def test_table_constructor_alias_is_rejected(self) -> None:
        path = ROOT / "docs/typst/thesis/sections/fixture.typ"
        violations = scan_table_style_text(path, "#let t = table\n#t([value])")
        self.assertTrue(
            any(item.rule == "table-constructor-alias" for item in violations)
        )

    def test_shared_constructor_import_alias_is_rejected(self) -> None:
        path = ROOT / "docs/typst/thesis/sections/fixture.typ"
        text = '#import "../../shared/tables.typ": publication-table as styled\n#styled([value])'
        violations = scan_table_style_text(path, text)
        self.assertTrue(
            any(item.rule == "table-constructor-alias" for item in violations)
        )

    def test_commented_table_example_is_ignored(self) -> None:
        path = ROOT / "docs/typst/thesis/sections/fixture.typ"
        self.assertEqual(scan_table_style_text(path, "// table([example])"), [])

    def test_block_commented_table_imports_are_ignored(self) -> None:
        path = ROOT / "docs/typst/thesis/sections/fixture.typ"
        text = (
            '/* #import "@preview/tablex:0.1.0": tablex\n'
            '#import "../../shared/tables.typ": publication-table as styled */\n'
            '#import "../../shared/tables.typ": publication-table\n'
            "#publication-table(header: ([*Header*],), rows: ([value],))"
        )
        self.assertEqual(scan_table_style_text(path, text), [])

    def test_active_table_rejects_unapproved_package_import(self) -> None:
        path = ROOT / "docs/typst/thesis/sections/fixture.typ"
        violations = scan_table_style_text(
            path, '#import "@preview/tablex:0.1.0": tablex'
        )
        self.assertTrue(any(item.rule == "table-package-import" for item in violations))

    def test_development_table_uses_development_constructor(self) -> None:
        path = ROOT / "docs/typst/thesis/development/fixture.typ"
        self.assertEqual(
            scan_table_style_text(
                path,
                '#import "../../shared/tables.typ": development-table\n'
                "development-table(header: ([*Header*],), rows: ([value],))",
            ),
            [],
        )

    def test_slide_table_uses_presentation_constructor(self) -> None:
        path = ROOT / "docs/typst/seminar_slides/fixture.typ"
        self.assertEqual(
            scan_table_style_text(
                path,
                '#import "../shared/tables.typ": presentation-table\n'
                "presentation-table(header: ([*Header*],), rows: ([value],))",
            ),
            [],
        )

    def test_structural_titlepage_tables_are_excluded(self) -> None:
        path = ROOT / "docs/typst/thesis/template/layout/titlepage.typ"
        self.assertEqual(scan_table_style_text(path, "table([layout])"), [])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scan", nargs="*", type=Path, help="scan Typst files/directories"
    )
    parser.add_argument(
        "--examples", action="store_true", help="run positive/negative fixtures"
    )
    parser.add_argument(
        "--table-scan",
        action="store_true",
        help="scan every active authored table surface",
    )
    args = parser.parse_args(argv)
    if args.table_scan:
        violations = scan_table_style_paths()
        for violation in violations:
            print(violation, file=sys.stderr)
        return 1 if violations else 0
    if args.scan is not None:
        paths = [path if path.is_absolute() else ROOT / path for path in args.scan]
        violations = scan_paths(paths or [THESIS_ROOT])
        for violation in violations:
            print(violation, file=sys.stderr)
        return 1 if violations else 0
    result = unittest.main(module=__name__, argv=[sys.argv[0]], exit=False, verbosity=2)
    return 0 if result.result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
