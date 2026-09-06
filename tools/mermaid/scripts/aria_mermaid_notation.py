#!/usr/bin/env python3
"""Validate every math label against an explicitly selected notation projection.

The reader accepts the single-line, single-quoted TeX records emitted by
scripts/glossary_build.py; it is deliberately not a general YAML parser.
One adjacent aria-math directive binds each $$ block, in order, to a whole
canonical symbol or equation. This proves spelling/projection fidelity, not
mathematical truth, tensor compatibility, or correct use of a symbol.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

SECTION = re.compile(r"^(symbols|equations):\s*$")
KEY = re.compile(r"^  ([A-Za-z0-9_.-]+):\s*$")
TEX = re.compile(r"^    tex: '((?:[^']|'')*)'\s*$")
BIND = re.compile(r"^\s*%% aria-math:\s*(.*?)\s*$")
MATH = re.compile(r"\$\$(.*?)\$\$")
STRICT = "%% aria-notation: strict"


def read_projection(path: Path) -> dict[str, str]:
    """Read generated symbol/equation TeX; reject duplicate or invalid records."""
    records: dict[str, str] = {}
    section = ""
    key: str | None = None
    seen: set[str] = set()
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if match := SECTION.fullmatch(line):
            section = match[1]
            key = None
        elif match := KEY.fullmatch(line):
            if not section:
                raise ValueError(f"{path}:{number}: record outside a notation section")
            key = f"{section}.{match[1]}"
            if key in seen:
                raise ValueError(f"{path}:{number}: duplicate record {key}")
            seen.add(key)
        elif line.startswith("    tex:"):
            match = TEX.fullmatch(line)
            if key is None or match is None or not match[1]:
                raise ValueError(f"{path}:{number}: expected generated single-quoted TeX")
            if key in records:
                raise ValueError(f"{path}:{number}: duplicate TeX for {key}")
            records[key] = match[1].replace("''", "'")
    if not records or seen != records.keys():
        raise ValueError(f"{path}: empty projection or records without TeX: {seen - records.keys()}")
    return records


def check_math(text: str, records: dict[str, str]) -> list[str]:
    """Bind all single-line math blocks; missing, extra and stale labels fail."""
    errors: list[str] = []
    pending: list[str] | None = None
    in_frontmatter = text.startswith("---\n")
    for number, line in enumerate(text.splitlines(), 1):
        if in_frontmatter:
            if number > 1 and line == "---":
                in_frontmatter = False
            continue
        if match := BIND.fullmatch(line):
            if pending is not None:
                errors.append(f"line {number}: unused preceding aria-math binding")
            pending = match[1].split()
            if not pending:
                errors.append(f"line {number}: empty aria-math binding")
            continue
        if not line.strip() or line.lstrip().startswith("%%"):
            continue
        blocks = MATH.findall(line)
        if line.count("$$") != 2 * len(blocks):
            errors.append(f"line {number}: math must be balanced on one source line")
        if blocks and pending is None:
            errors.append(f"line {number}: unbound math label")
        if pending is not None:
            if len(blocks) != len(pending):
                errors.append(f"line {number}: {len(pending)} bindings for {len(blocks)} math blocks")
            for identifier, actual in zip(pending, blocks):
                expected = records.get(identifier)
                if expected is None:
                    errors.append(f"line {number}: unknown canonical key {identifier}")
                elif actual.strip() != expected.strip():
                    errors.append(f"line {number}: TeX differs from {identifier}; expected {expected!r}, got {actual!r}")
            pending = None
    if pending is not None:
        errors.append("unused aria-math binding at end of file")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--notation", type=Path, default=Path(__file__).resolve().parents[3] / "docs/notation.yml")
    parser.add_argument("--require-strict", action="store_true", help="fail rather than skip legacy files")
    args = parser.parse_args()
    try:
        records = read_projection(args.notation)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    failures = 0
    for path in args.files:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as error:
            print(f"ERROR {path}: {error}")
            failures += 1
            continue
        if STRICT not in {line.strip() for line in text.splitlines()}:
            if args.require_strict:
                print(f"ERROR {path}: missing {STRICT}")
                failures += 1
            else:
                print(f"SKIP {path}: legacy source; notation not certified")
            continue
        errors = check_math(text, records)
        for error in errors:
            print(f"ERROR {path}: {error}")
        failures += len(errors)
        if not errors:
            print(f"PASS {path}: every math block matches {args.notation}")
    return int(failures > 0)


if __name__ == "__main__":
    raise SystemExit(main())
