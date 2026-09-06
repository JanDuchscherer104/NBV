#!/usr/bin/env python3
"""Expand Typst owner references into ordinary, validated Mermaid math.

Authored source: $$#symb.rl.budget$$ or $$#eqs.rl.qh_doubleq_target$$.
The generated notation adapter's typst field is the lookup key. We neither
execute Typst expressions nor maintain a second symbol-to-TeX dictionary.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from aria_mermaid_notation import (
    ARCHITECTURE, KEY, SECTION, STRICT, body_lines, check_architecture,
    check_math, read_projection,
)

OWNERS = "%% aria-notation: typst"
REFERENCE = re.compile(r"#(?:symb|eqs)\.[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+")
OWNER_FIELD = re.compile(r"^    typst: '((?:[^']|'')*)'\s*$")
MATH = re.compile(r"\$\$(.*?)\$\$")


def read_owners(path: Path) -> tuple[dict[str, str], dict[str, str]]:
    """Return canonical TeX records and exact Typst-reference-to-record bindings."""
    records = read_projection(path)
    owners: dict[str, str] = {}
    fields: set[str] = set()
    section = ""
    key: str | None = None
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if match := SECTION.fullmatch(line):
            section, key = match[1], None
        elif match := KEY.fullmatch(line):
            key = f"{section}.{match[1]}"
        elif line.startswith("    typst:"):
            match = OWNER_FIELD.fullmatch(line)
            if key is None or match is None:
                raise ValueError(f"{path}:{number}: invalid generated Typst owner")
            owner = match[1].replace("''", "'")
            prefix = "#symb." if section == "symbols" else "#eqs."
            # Detect a corrupt/stale adapter rather than accepting arbitrary aliases.
            expected = prefix + key.partition(".")[2]
            if not REFERENCE.fullmatch(owner) or owner != expected:
                raise ValueError(f"{path}:{number}: expected {expected}, got {owner}")
            if owner in owners or key in fields:
                raise ValueError(f"{path}:{number}: duplicate Typst owner {owner}")
            owners[owner] = key
            fields.add(key)
    if fields != records.keys():
        raise ValueError(f"{path}: missing Typst owner fields: {records.keys() - fields}")
    return records, owners


def compile_source(text: str, records: dict[str, str], owners: dict[str, str]) -> tuple[str, list[str]]:
    """Lower complete owner expressions, rejecting handwritten math/pseudocode.

    Source uses the existing quoted-node architecture subset. The lowered text
    passes the existing strict math and computational-coverage checks. No
    slicing, eval, suffixes, free TeX or unregistered local aliases are allowed.
    """
    content = body_lines(text)
    directives = {line.strip() for _, line in content}
    if OWNERS not in directives or ARCHITECTURE not in directives:
        raise ValueError(f"owner source requires {OWNERS} and {ARCHITECTURE}")
    if STRICT in directives:
        raise ValueError("do not mix copied-TeX strict mode and Typst owner mode")
    body_numbers = {number for number, _ in content}
    output: list[str] = []
    used: set[str] = set()
    for number, line in enumerate(text.splitlines(), 1):
        if number not in body_numbers:
            if "$$" in line or "#symb." in line or "#eqs." in line:
                raise ValueError(f"line {number}: math references belong in labels, not frontmatter")
            output.append(line)
            continue
        if line.strip() == OWNERS:
            output.append("  " + STRICT)
            continue
        if line.lstrip().startswith(("%% aria-math:", "%% aria-compute:")):
            raise ValueError(f"line {number}: owner mode generates bindings; remove copied binding")
        if line.lstrip().startswith("%%"):
            output.append(line)
            continue
        if "<code" in line.lower():
            raise ValueError(f"line {number}: use a shared equation, not a pseudocode escape hatch")
        blocks = MATH.findall(line)
        if line.count("$$") != 2 * len(blocks):
            raise ValueError(f"line {number}: math must be balanced on one source line")
        remainder = MATH.sub("", line)
        if "#symb." in remainder or "#eqs." in remainder:
            raise ValueError(f"line {number}: owner reference outside a math block")
        bindings: list[str] = []
        for block in blocks:
            reference = block.strip()
            if not REFERENCE.fullmatch(reference):
                raise ValueError(f"line {number}: each math block must contain one whole #symb or #eqs reference, got {block!r}")
            if reference not in owners:
                raise ValueError(f"line {number}: unregistered Typst owner {reference}")
            bindings.append(owners[reference])
            used.add(reference)
        if bindings:
            output.append("  %% aria-math: " + " ".join(bindings))
            index = iter(bindings)
            # Callable replacement keeps TeX backslashes literal.
            line = MATH.sub(lambda _: "$$" + records[next(index)] + "$$", line)
        output.append(line)
    generated = "\n".join(output) + "\n"
    issues = check_math(generated, records) + check_architecture(generated, records)
    if issues:
        raise ValueError("\n".join(issues))
    return generated, sorted(used)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--notation", type=Path, default=Path(__file__).resolve().parents[3] / "docs/notation.yml")
    parser.add_argument("--output", type=Path, help="generated Mermaid, never the authored source")
    parser.add_argument("--receipt", type=Path, help="optional dependency/hash receipt")
    args = parser.parse_args()
    try:
        protected = {args.source.resolve(), args.notation.resolve()}
        outputs = [p.resolve() for p in (args.output, args.receipt) if p is not None]
        if len(outputs) != len(set(outputs)) or protected.intersection(outputs):
            raise ValueError("output/receipt must be distinct and cannot overwrite source or notation")
        records, owners = read_owners(args.notation)
        text = args.source.read_text(encoding="utf-8")
        generated, used = compile_source(text, records, owners)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(generated, encoding="utf-8")
        if args.receipt:
            args.receipt.parent.mkdir(parents=True, exist_ok=True)
            args.receipt.write_text(json.dumps({
                "source": str(args.source), "notation": str(args.notation),
                "source_sha256": hashlib.sha256(args.source.read_bytes()).hexdigest(),
                "notation_sha256": hashlib.sha256(args.notation.read_bytes()).hexdigest(),
                "generated_sha256": hashlib.sha256(generated.encode()).hexdigest(),
                "owners": [{"typst": owner, "key": owners[owner]} for owner in used],
                "scope": "projection identity and architecture coverage, not semantic equivalence",
            }, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError) as error:
        parser.exit(1, f"ERROR: {error}\n")
    print(f"PASS {args.source}: {len(used)} Typst owners resolved; all math and process nodes checked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
