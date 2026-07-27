#!/usr/bin/env python3
"""Inventory direct thesis references before glossary or notation pruning.

The report deliberately distinguishes a definition being registered or printed
from a reader-facing reference.  A zero direct-reference count is review
evidence only: canonical glossary, symbol, and equation owners stay intact.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
THESIS_ROOT = ROOT / "docs/typst/thesis"
GLOSSARY = ROOT / "docs/typst/shared/glossary.typ"
NOTATION = ROOT / "docs/notation.yml"
REGISTRY = THESIS_ROOT / "prune_targets.typ"
DEFAULT_REPORT = ROOT / ".cache/thesis-prune-audit.json"
DEFAULT_INCLUDE = THESIS_ROOT / "prune_targets.generated.typ"
DEFAULT_TRIAGE = THESIS_ROOT / "prune_triage.generated.typ"

IMPORT_RE = re.compile(r'^\s*#(?:include|import)\s+"([^"]+)"', re.MULTILINE)
TERM_RE = re.compile(r"@([a-z0-9][a-z0-9-]*)")
NOTATION_RE = re.compile(
    r"\b(?P<kind>symb|eqs)\.([a-z][a-z0-9_]*)\.([A-Za-z][A-Za-z0-9_]*)"
)
RAW_SOURCE_PATH_RE = re.compile(
    r"\b(?:aria_nbv|docs|scripts)/[A-Za-z0-9_./-]+\.(?:py|typ|toml|ya?ml|json|qmd|sh)\b"
)
SOURCE_SYMBOL_RE = re.compile(
    r"\baria_nbv(?:\.[a-z][A-Za-z0-9_]*){2,}\.[A-Z][A-Za-z0-9_]*\b"
)
GH_CALL_RE = re.compile(r"#(?:gh|gh-wip|gh-symbol)\([^\n]*?\)")
REGISTRY_ENTRY_RE = re.compile(
    r"\(\s*kind:\s*\"(?P<kind>[^\"]+)\"\s*,\s*key:\s*\"(?P<key>[^\"]+)\""
    r"\s*,\s*label:\s*\"(?P<label>[^\"]+)\"\s*,\s*reason:\s*\"(?P<reason>[^\"]+)\"",
    re.DOTALL,
)
TRIAGE_ENTRY_RE = re.compile(
    r"\(kind: \"(?P<kind>[^\"]+)\", key: \"(?P<key>[^\"]+)\", "
    r"status: \"(?P<status>[^\"]+)\", reason: \"(?P<reason>[^\"]+)\"\)",
)


def _without_comments(source: str) -> str:
    """Remove Typst line and block comments without treating prose as code."""
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    return re.sub(r"//.*$", "", source, flags=re.MULTILINE)


def thesis_closure(main: Path) -> list[Path]:
    """Return the deterministic local import/include closure from ``main``."""
    pending = [main.resolve()]
    seen: set[Path] = set()
    closure: list[Path] = []
    while pending:
        path = pending.pop()
        if path in seen or not path.is_file():
            continue
        seen.add(path)
        closure.append(path)
        source = _without_comments(path.read_text(encoding="utf-8"))
        for relative in IMPORT_RE.findall(source):
            candidate = (path.parent / relative).resolve()
            if candidate.is_relative_to(ROOT):
                pending.append(candidate)
    return sorted(closure)


def _glossary_keys(path: Path) -> set[str]:
    return set(
        re.findall(
            r'^\s*key:\s*"([^"]+)"', path.read_text(encoding="utf-8"), re.MULTILINE
        )
    )


def _notation_entries(path: Path) -> dict[str, dict[str, dict[str, Any]]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return {kind: entries or {} for kind, entries in data.items()}


def _direct_counts(
    closure: list[Path],
    glossary_keys: set[str],
    notation: dict[str, dict[str, dict[str, Any]]],
) -> tuple[Counter[str], Counter[str], Counter[str]]:
    """Count calls in thesis-owned files, excluding shared definition facades."""
    terms: Counter[str] = Counter()
    symbols: Counter[str] = Counter()
    equations: Counter[str] = Counter()
    for path in closure:
        if not path.is_relative_to(THESIS_ROOT):
            continue
        source = _without_comments(path.read_text(encoding="utf-8"))
        terms.update(key for key in TERM_RE.findall(source) if key in glossary_keys)
        for match in NOTATION_RE.finditer(source):
            key = f"{match.group(2)}.{match.group(3)}"
            if match.group("kind") == "symb" and key in notation["symbols"]:
                symbols[key] += 1
            if match.group("kind") == "eqs" and key in notation["equations"]:
                equations[key] += 1
    return terms, symbols, equations


def validate_reader_visible_source_links(closure: list[Path]) -> None:
    """Reject unlinked repository paths or Python source symbols in thesis prose."""
    violations: list[str] = []
    for path in closure:
        if (
            not path.is_relative_to(THESIS_ROOT)
            or "/tests/" in str(path)
            or path.name in {"glossary-overrides.typ", "draft_markers.typ"}
            or path.name.startswith("prune_")
        ):
            continue
        source = _without_comments(path.read_text(encoding="utf-8"))
        for line_number, line in enumerate(source.splitlines(), start=1):
            unlinked = GH_CALL_RE.sub("", line)
            for pattern in (RAW_SOURCE_PATH_RE, SOURCE_SYMBOL_RE):
                if match := pattern.search(unlinked):
                    violations.append(
                        f"{path.relative_to(ROOT)}:{line_number}: {match.group(0)}"
                    )
    if violations:
        raise ValueError(
            "reader-visible repository paths/symbols must use #gh, #gh-wip, or #gh-symbol:\n"
            + "\n".join(violations)
        )


def build_inventory(main: Path = THESIS_ROOT / "main.typ") -> dict[str, Any]:
    """Build the stable, source-level audit report for the active thesis."""
    closure = thesis_closure(main)
    validate_reader_visible_source_links(closure)
    glossary_keys = _glossary_keys(GLOSSARY)
    notation = _notation_entries(NOTATION)
    term_counts, symbol_counts, equation_counts = _direct_counts(
        closure, glossary_keys, notation
    )

    def rows(
        kind: str, entries: dict[str, Any], counts: Counter[str], listed: bool
    ) -> list[dict[str, Any]]:
        return [
            {
                "key": key,
                "owner": str(
                    (GLOSSARY if kind == "glossary" else NOTATION).relative_to(ROOT)
                ),
                "static_occurrences": counts[key],
                "build_occurrences": "not available",
                "registered": True,
                "rendered_in_list": listed
                if kind == "glossary"
                else bool(entry.get("thesis_list", False)),
                "candidate_status": "review" if counts[key] == 0 else "referenced",
            }
            for key, entry in sorted(entries.items())
        ]

    return {
        "schema_version": 1,
        "count_semantics": {
            "static_occurrences": "direct executable calls in thesis-owned files in the main.typ closure",
            "build_occurrences": "not available: the reader-facing Glossarium list disables back-references",
        },
        "include_closure": [str(path.relative_to(ROOT)) for path in closure],
        "glossary": rows(
            "glossary", {key: {} for key in glossary_keys}, term_counts, True
        ),
        "symbols": rows("symbols", notation["symbols"], symbol_counts, False),
        "equations": rows("equations", notation["equations"], equation_counts, False),
    }


def _registry_entries(path: Path) -> list[dict[str, str]]:
    return [
        match.groupdict()
        for match in REGISTRY_ENTRY_RE.finditer(path.read_text(encoding="utf-8"))
    ]


def _zero_use_rows(inventory: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """Return all and only audit rows that require a keyed triage decision."""
    return [
        (kind, row)
        for kind in ("glossary", "symbols", "equations")
        for row in inventory[kind]
        if row["static_occurrences"] == 0
    ]


def _triage_status(
    kind: str, row: dict[str, Any], prune_keys: set[tuple[str, str]]
) -> tuple[str, str]:
    if (kind, row["key"]) in prune_keys:
        return "prune", "evidence-backed trivial acronym/tooling candidate"
    if row["rendered_in_list"]:
        return (
            "transitively displayed",
            "shown by a registry-driven thesis list despite no direct thesis call",
        )
    return (
        "retain pending evidence",
        "shared notation may be expanded through prose, a parent equation, or another document",
    )


def render_triage_include(inventory: dict[str, Any], registry: Path = REGISTRY) -> str:
    """Render a complete keyed triage registry for every zero-use audit item."""
    prune_keys = {
        (entry["kind"], entry["key"]) for entry in _registry_entries(registry)
    }
    lines = [
        "// Generated by scripts/thesis_prune_audit.py; do not edit by hand.",
        "// Every zero-direct-use audit row has exactly one triage decision.",
        "#let prune_triage_registry = (",
    ]
    for kind, row in _zero_use_rows(inventory):
        status, reason = _triage_status(kind, row, prune_keys)
        lines.append(
            f'  (kind: "{kind}", key: "{row["key"]}", status: "{status}", '
            f'reason: "{reason}"),'
        )
    lines.append(")")
    return "\n".join(lines) + "\n"


def validate_triage_coverage(inventory: dict[str, Any], triage_source: str) -> None:
    """Reject missing, duplicate, stale, or unclassified zero-use triage rows."""
    entries = [match.groupdict() for match in TRIAGE_ENTRY_RE.finditer(triage_source)]
    actual = [(entry["kind"], entry["key"]) for entry in entries]
    expected = [(kind, row["key"]) for kind, row in _zero_use_rows(inventory)]
    if len(actual) != len(set(actual)):
        raise ValueError("prune triage registry contains duplicate keys")
    if set(actual) != set(expected):
        missing = sorted(set(expected) - set(actual))
        stale = sorted(set(actual) - set(expected))
        raise ValueError(
            f"prune triage coverage mismatch: missing={missing}, stale={stale}"
        )
    valid_statuses = {"prune", "retain pending evidence", "transitively displayed"}
    if {entry["status"] for entry in entries} - valid_statuses:
        raise ValueError("prune triage registry contains an unknown status")


def render_prune_include(inventory: dict[str, Any], registry: Path = REGISTRY) -> str:
    """Render only hand-approved prune targets, with generated occurrence data."""
    counts = {
        "glossary": {row["key"]: row for row in inventory["glossary"]},
        "symbol": {row["key"]: row for row in inventory["symbols"]},
        "equation": {row["key"]: row for row in inventory["equations"]},
    }
    lines = [
        "// Generated by scripts/thesis_prune_audit.py; edit prune_targets.typ.",
        '#import "draft_markers.typ": prune_target',
        "",
        "#heading(numbering: none, outlined: false)[Prune targets (development review)]",
        "#text(size: 8.5pt, fill: gray)[These are evidence-backed review targets, not canonical-definition deletions. Static counts exclude registry definitions; the current reader-facing build does not expose a per-term runtime count.]",
        "",
    ]
    for entry in _registry_entries(registry):
        row = counts[entry["kind"]][entry["key"]]
        lines.append(
            "#prune_target(["
            + entry["label"]
            + "], "
            + f'key: "{entry["kind"]}.{entry["key"]}", '
            + f'reason: "{entry["reason"]}", '
            + f"static_occurrences: {row['static_occurrences']}, "
            + 'build_occurrences: "not available")'
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--main", type=Path, default=THESIS_ROOT / "main.typ")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--include", type=Path, default=DEFAULT_INCLUDE)
    parser.add_argument("--triage", type=Path, default=DEFAULT_TRIAGE)
    parser.add_argument("--registry", type=Path, default=REGISTRY)
    args = parser.parse_args()

    inventory = build_inventory(args.main)
    triage = render_triage_include(inventory, args.registry)
    validate_triage_coverage(inventory, triage)
    triage_entries = [match.groupdict() for match in TRIAGE_ENTRY_RE.finditer(triage)]
    inventory["triage_coverage"] = {
        "expected_zero_use_items": len(_zero_use_rows(inventory)),
        "registered_items": len(triage_entries),
        "status_counts": dict(Counter(entry["status"] for entry in triage_entries)),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(inventory, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    args.include.write_text(
        render_prune_include(inventory, args.registry), encoding="utf-8"
    )
    args.triage.write_text(triage, encoding="utf-8")
    print(
        "Thesis prune audit: "
        + ", ".join(
            f"{kind}={len(inventory[kind])}"
            for kind in ("glossary", "symbols", "equations")
        )
    )


if __name__ == "__main__":
    main()
