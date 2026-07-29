#!/usr/bin/env python3
"""Mechanical, phase-aware LOC audit frozen at the Q_H H baseline."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence


@dataclass(frozen=True)
class CountedTarget:
    """One source region that contributes physical and logical LOC."""

    owner: str
    path: str
    start_line: int
    end_line: int
    physical_loc: int
    logical_loc: int


def _fail(message: str) -> None:
    raise ValueError(message)


def _source_tree(path: Path) -> ast.Module:
    try:
        return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError, UnicodeDecodeError) as error:
        _fail(f"Cannot parse audit target {path}: {error}")


def _logical_loc(node: ast.AST) -> int:
    return sum(isinstance(child, ast.stmt) for child in ast.walk(node))


def _symbol_nodes(tree: ast.Module, name: str, kind: str) -> list[ast.AST]:
    nodes: list[ast.AST] = []
    for node in ast.walk(tree):
        if (
            kind == "function"
            and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == name
        ):
            nodes.append(node)
        elif kind == "class" and isinstance(node, ast.ClassDef) and node.name == name:
            nodes.append(node)
    return nodes


def _count_file(
    repo_root: Path, item: dict[str, Any], *, phase: str
) -> CountedTarget | None:
    relative = item["path"]
    target = repo_root / relative
    if not target.is_file():
        if phase == "final" and item.get("zero_when_missing_in_final"):
            return None
        _fail(f"Required audit path is missing: {relative}")
    tree = _source_tree(target)
    lines = target.read_text(encoding="utf-8").splitlines()
    return CountedTarget(
        owner=item["owner"],
        path=relative,
        start_line=1,
        end_line=len(lines),
        physical_loc=len(lines),
        logical_loc=_logical_loc(tree),
    )


def _count_symbol(
    repo_root: Path, item: dict[str, Any], *, phase: str
) -> CountedTarget | None:
    relative = item["path"]
    target = repo_root / relative
    required = phase == "final"
    if not target.is_file():
        if required:
            _fail(f"Required final audit symbol path is missing: {relative}")
        return None
    tree = _source_tree(target)
    nodes = _symbol_nodes(tree, item["name"], item["kind"])
    if phase == "baseline":
        if nodes:
            _fail(
                f"Baseline requires future symbol {item['name']} to be absent, found {len(nodes)} occurrence(s)."
            )
        return None
    if len(nodes) != 1:
        _fail(
            f"Final requires exactly one {item['kind']} {item['name']}, found {len(nodes)}."
        )
    node = nodes[0]
    start_line = int(node.lineno)
    end_line = int(getattr(node, "end_lineno", node.lineno))
    return CountedTarget(
        owner=item["owner"],
        path=relative,
        start_line=start_line,
        end_line=end_line,
        physical_loc=end_line - start_line + 1,
        logical_loc=_logical_loc(node),
    )


def _reject_overlaps(targets: Iterable[CountedTarget]) -> None:
    by_path: dict[str, list[CountedTarget]] = {}
    for target in targets:
        by_path.setdefault(target.path, []).append(target)
    for path, regions in by_path.items():
        ordered = sorted(regions, key=lambda item: (item.start_line, item.end_line))
        for previous, current in zip(ordered, ordered[1:]):
            if current.start_line <= previous.end_line:
                _fail(
                    f"Audit double counts overlapping regions in {path}: {previous.owner} and {current.owner}."
                )


def audit(repo_root: Path, config_path: Path, *, phase: str) -> dict[str, Any]:
    """Audit the frozen baseline or the final refactor surface."""

    config = json.loads(config_path.read_text(encoding="utf-8"))
    if phase not in {"baseline", "final"}:
        _fail(f"Unsupported audit phase: {phase}")
    files = config.get("files")
    symbols = config.get("future_symbols")
    if not isinstance(files, list) or not isinstance(symbols, list):
        _fail("Audit config requires files and future_symbols lists.")
    target_ids = [(item.get("path"), item.get("owner")) for item in files]
    if len(target_ids) != len(set(target_ids)):
        _fail("Audit config contains duplicate whole-file targets.")
    symbol_ids = [
        (item.get("path"), item.get("kind"), item.get("name")) for item in symbols
    ]
    if len(symbol_ids) != len(set(symbol_ids)):
        _fail("Audit config contains duplicate symbol targets.")
    targets = [
        item
        for item in (_count_file(repo_root, item, phase=phase) for item in files)
        if item is not None
    ]
    targets.extend(
        item
        for item in (_count_symbol(repo_root, item, phase=phase) for item in symbols)
        if item is not None
    )
    _reject_overlaps(targets)
    total = sum(item.physical_loc for item in targets)
    baseline_total = config["baseline_total"]
    if phase == "baseline" and total != baseline_total:
        _fail(f"Baseline LOC mismatch: expected {baseline_total}, measured {total}.")
    return {
        "schema_version": config["schema_version"],
        "phase": phase,
        "baseline_total": baseline_total,
        "total_physical_loc": total,
        "total_logical_loc": sum(item.logical_loc for item in targets),
        "owners": [item.__dict__ for item in targets],
        "config_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--config", type=Path, default=Path(".configs/evidence/qh/qh_loc_audit.json")
    )
    parser.add_argument("--phase", choices=("baseline", "final"), default="baseline")
    arguments = parser.parse_args(argv)
    try:
        result = audit(arguments.repo_root, arguments.config, phase=arguments.phase)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"qh LOC audit failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
