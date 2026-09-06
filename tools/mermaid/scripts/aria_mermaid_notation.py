#!/usr/bin/env python3
"""Check canonical math and source-bound computational architecture labels.

Typst owns notation; docs/notation.yml is its generated TeX projection. Exact
math matching is separate from the architecture gate. The latter checks label
form and source identity, not the truth of pseudocode or graph dependencies.
"""
from __future__ import annotations

import argparse
import html
import re
from pathlib import Path

SECTION = re.compile(r"^(symbols|equations):\s*$")
KEY = re.compile(r"^  ([A-Za-z0-9_.-]+):\s*$")
TEX = re.compile(r"^    tex: '((?:[^']|'')*)'\s*$")
BIND = re.compile(r"^\s*%% aria-math:\s*(.*?)\s*$")
COMPUTE = re.compile(r"^\s*%% aria-compute:\s*(.*?)\s*$")
MATH = re.compile(r"\$\$(.*?)\$\$")
NODE = re.compile(r'^\s*([A-Za-z][A-Za-z0-9_]*)\["(.*)"\]:::(input|data|compute|output|status)\s*$')
CODE = re.compile(r"<code>(.*?)</code>")
TITLE = re.compile(r"^<b>[^<>]+</b>")
STRICT = "%% aria-notation: strict"
ARCHITECTURE = "%% aria-architecture: symbolic-computational"
TRANSPORT = "%% aria-tex-transport: doubled-backslash"


def read_projection(path: Path) -> dict[str, str]:
    """Read generated single-line TeX records, rejecting duplicate/missing data."""
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


def body_lines(text: str) -> list[tuple[int, str]]:
    """Keep source line numbers while excluding only leading YAML frontmatter."""
    inside = text.startswith("---\n")
    result: list[tuple[int, str]] = []
    for number, line in enumerate(text.splitlines(), 1):
        if inside:
            if number > 1 and line == "---":
                inside = False
            continue
        result.append((number, line))
    return result


def check_math(text: str, records: dict[str, str]) -> list[str]:
    """Bind every single-line math block to an unchanged canonical expression."""
    # Mermaid's math-label path collapses backslash pairs once. Compare the
    # decoded expression, not its transport encoding, with canonical TeX.
    if TRANSPORT in {line.strip() for _, line in body_lines(text)}:
        text = MATH.sub(lambda match: "$$" + match[1].replace("\\\\", "\\") + "$$", text)
    errors: list[str] = []
    pending: list[str] | None = None
    for number, line in body_lines(text):
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


def check_architecture(text: str, records: dict[str, str]) -> list[str]:
    """Fail closed on prose-only nodes in the intentionally narrow authoring form.

    Supported declarations are one quoted rectangular node per source line,
    with an inline role class. Computational text requires an adjacent equation
    owner; data requires exact math. Status-only terminal outcomes are explicit
    and capped at two. This is a readability/traceability gate, not a theorem
    prover or a complete Mermaid parser; the renderer still owns syntax.
    """
    errors: list[str] = []
    math_keys: list[str] = []
    owner: str | None = None
    nodes: dict[str, str] = {}
    content = body_lines(text)
    for number, line in content:
        if match := BIND.fullmatch(line):
            math_keys = match[1].split()
            continue
        if match := COMPUTE.fullmatch(line):
            if owner is not None:
                errors.append(f"line {number}: unused aria-compute binding")
            owner = match[1]
            if not owner.startswith("equations.") or owner not in records:
                errors.append(f"line {number}: unknown computation equation owner {owner!r}")
            continue
        if not line.strip() or line.lstrip().startswith("%%"):
            continue
        match = NODE.fullmatch(line)
        if match:
            node_id, label, role = match.groups()
            if node_id in nodes:
                errors.append(f"line {number}: duplicate node {node_id}")
            nodes[node_id] = role
            if not TITLE.match(label):
                errors.append(f"line {number}: {node_id} needs one short bold header")
            codes = CODE.findall(label)
            formulas = MATH.findall(label)
            if role == "status":
                if codes or formulas or owner is not None:
                    errors.append(f"line {number}: status is a plain terminal outcome, not data/computation")
            elif role in {"input", "data", "output"} and not formulas:
                errors.append(f"line {number}: {node_id} data/output needs a canonical mathematical body")
            elif role == "compute" and not codes and not any(k.startswith("equations.") for k in math_keys):
                errors.append(f"line {number}: {node_id} needs an equation or computation, not just a name/output symbol")
            if codes and owner is None:
                errors.append(f"line {number}: {node_id} pseudocode needs an aria-compute equation owner")
            if owner is not None and not codes:
                errors.append(f"line {number}: aria-compute has no computational body")
            if codes:
                plain = html.unescape(re.sub(r"<br\s*/?>", " ", " ".join(codes)))
                # A call or pipeline must describe the operation. This only
                # checks form; review the operands/order against the owner.
                if not re.search(r"[A-Za-z_]\w*(?:\.\w+)*\s*\([^)]*\)", plain) and not re.search(r"\w\s*(?:→|->)\s*\w", plain):
                    errors.append(f"line {number}: {node_id} code is prose, not a call or pipeline")
                if "$" in plain or "\\" in plain:
                    errors.append(f"line {number}: TeX cannot bypass canonical checking inside code")
            remainder = TITLE.sub("", label)
            remainder = MATH.sub("", CODE.sub("", remainder))
            remainder = re.sub(r"<br\s*/?>", "", remainder).strip()
            if role != "status" and remainder:
                errors.append(f"line {number}: {node_id} has prose outside its header; move it to the caption")
        else:
            stripped = line.strip()
            if owner is not None:
                errors.append(f"line {number}: aria-compute must bind the next node")
            if not stripped.startswith(("subgraph ", "accTitle:", "accDescr:", "classDef ", "style ")) and re.search(r'\w\s*[\[({]', line):
                errors.append(f"line {number}: use one quoted node with inline semantic class per line")
            if stripped.startswith("class "):
                errors.append(f"line {number}: role classes must be inline so coverage cannot be bypassed")
            if "|" in line:
                for label in re.findall(r'\|"([^"\n]*)"\|', line):
                    if not MATH.search(label) and len(label.split()) > 3:
                        errors.append(f"line {number}: prose-heavy edge; use canonical data or a short qualifier")
        math_keys = []
        owner = None
    if owner is not None:
        errors.append("unused aria-compute binding at end of file")
    if not nodes:
        errors.append("architecture has no checked nodes")
    status_nodes = [node_id for node_id, role in nodes.items() if role == "status"]
    if len(status_nodes) > 2:
        errors.append("at most two terminal conceptual outcomes may use status")
    for node_id in status_nodes:
        if any(re.search(rf"\b{re.escape(node_id)}\s*(?:-->|-\.->|==>)", line) for _, line in content):
            errors.append(f"{node_id}: status must be terminal, not an untyped process")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--notation", type=Path, default=Path(__file__).resolve().parents[3] / "docs/notation.yml")
    parser.add_argument("--require-strict", action="store_true")
    parser.add_argument("--require-architecture", action="store_true", help="require symbolic/computational coverage in every diagram")
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
        directives = {line.strip() for _, line in body_lines(text)}
        if STRICT not in directives:
            if args.require_strict or args.require_architecture or ARCHITECTURE in directives:
                print(f"ERROR {path}: missing {STRICT}")
                failures += 1
            else:
                print(f"SKIP {path}: legacy source; notation not certified")
            continue
        errors = check_math(text, records)
        if args.require_architecture and ARCHITECTURE not in directives:
            errors.append(f"missing {ARCHITECTURE}")
        if ARCHITECTURE in directives:
            errors += check_architecture(text, records)
        for error in errors:
            print(f"ERROR {path}: {error}")
        failures += len(errors)
        if not errors:
            suffix = "; architecture coverage checked" if ARCHITECTURE in directives else ""
            print(f"PASS {path}: canonical math checked{suffix}")
    return int(failures > 0)


if __name__ == "__main__":
    raise SystemExit(main())
