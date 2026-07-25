#!/usr/bin/env python3
"""Run deterministic structural or explicit Graphify synchronization."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from typing import Any

from graphify_contract import (
    ContractError,
    OUT,
    PARTITION_ORDER,
    ROOT,
    build_canonical,
    canonical_bytes,
    classify_path,
    load_config,
    load_canonical,
    load_validated_canonical,
    selected_literature_dirs,
    write_canonical,
)

PENDING = OUT / "pending.json"


def _changed_paths() -> list[Path]:
    return [
        Path(line.strip())
        for line in os.environ.get("GRAPHIFY_CHANGED", "").splitlines()
        if line.strip()
    ]


def graphify_command() -> list[str]:
    configured = os.environ.get("GRAPHIFY_BIN")
    if configured:
        return shlex.split(configured)
    module = [sys.executable, "-m", "graphify"]
    if "0.9.22" in _graphify_version(module):
        return module
    executable = shutil.which("graphify")
    return [executable] if executable else module


def _graphify_version(command: list[str]) -> str:
    result = subprocess.run(
        [*command, "--version"], text=True, capture_output=True, check=False
    )
    return result.stdout + result.stderr


def ensure_graphify_pin(command: list[str]) -> None:
    version = _graphify_version(command)
    if not re.search(r"(?<![0-9.])0\.9\.22(?![0-9.])", version):
        raise ContractError(
            "Graphify 0.9.22 is required; set GRAPHIFY_BIN to the pinned executable"
        )


def _pending_partitions(changed: list[Path], root: Path = ROOT) -> set[str]:
    config = load_config(root)
    literature_dirs = selected_literature_dirs(root)
    selected: set[str] = set()
    for path in changed:
        try:
            partition = classify_path(
                path.as_posix(),
                config,
                selected_literature_dirs=literature_dirs,
            )
        except ContractError:
            partition = None
        if partition:
            selected.add(partition)
    return selected


def _pending(path: Path = PENDING) -> set[str]:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return set()
    except (OSError, UnicodeError) as exc:
        raise ContractError(f"cannot read Graphify pending state: {exc}") from exc
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ContractError(f"Graphify pending state is malformed JSON: {exc}") from exc
    if not isinstance(value, dict) or set(value) != {"partitions"}:
        raise ContractError(
            "Graphify pending state must be an object containing only 'partitions'"
        )
    partitions = value["partitions"]
    if (
        not isinstance(partitions, list)
        or any(not isinstance(partition, str) for partition in partitions)
        or len(set(partitions)) != len(partitions)
    ):
        raise ContractError(
            "Graphify pending state 'partitions' must be a list of unique strings"
        )
    unknown = set(partitions) - set(PARTITION_ORDER)
    if unknown:
        raise ContractError(
            "Graphify pending state contains unknown partition(s): "
            + ", ".join(sorted(unknown))
        )
    return set(partitions)


def _write_pending(partitions: set[str], path: Path = PENDING) -> None:
    if not partitions:
        return
    unknown = partitions - set(PARTITION_ORDER)
    if unknown:
        raise ContractError(
            "cannot write unknown Graphify pending partition(s): "
            + ", ".join(sorted(unknown))
        )
    path.parent.mkdir(exist_ok=True)
    existing = _pending(path)
    payload = {"partitions": sorted(existing | partitions)}
    with tempfile.NamedTemporaryFile(
        mode="w",
        dir=path.parent,
        delete=False,
        encoding="utf-8",
    ) as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")
        temporary = Path(handle.name)
    temporary.replace(path)


def _compare_generated(generated: dict[str, bytes]) -> list[str]:
    differences: list[str] = []
    for name, expected in generated.items():
        path = OUT / name
        try:
            actual = path.read_bytes()
        except OSError:
            differences.append(f"missing canonical artifact: {path.relative_to(ROOT)}")
            continue
        if actual != expected:
            differences.append(
                f"canonical regeneration differs: {path.relative_to(ROOT)}"
            )
    return differences


def _load_validated_canonical() -> tuple[dict[str, Any], dict[str, Any]]:
    return load_validated_canonical()


def run(
    *, check: bool, mode: str, semantic_incomplete: set[str] | None = None
) -> list[str]:
    command = graphify_command()
    ensure_graphify_pin(command)
    old_graph = None
    if mode == "structural":
        old_graph, _ = _load_validated_canonical()
    else:
        try:
            old_graph, _ = load_canonical()
        except ContractError:
            pass
    graph, manifest, report = build_canonical(
        graphify_command=command,
        old_graph=old_graph,
        semantic_incomplete=semantic_incomplete if mode == "structural" else set(),
    )
    generated = canonical_bytes(graph, manifest, report)
    if check:
        return _compare_generated(generated)
    write_canonical(graph, manifest, report)
    if mode == "sync":
        PENDING.unlink(missing_ok=True)
    return []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("structural", "sync"), default="structural")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    changed = _changed_paths()
    touched = _pending_partitions(changed)
    semantic = touched - {"code"}
    try:
        if args.mode == "structural" and semantic:
            _write_pending(semantic)
        if args.mode == "structural" and touched and "code" not in touched:
            return 0
        differences = run(
            check=args.check,
            mode=args.mode,
            semantic_incomplete=_pending(),
        )
    except ContractError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if differences:
        print("Graphify canonical regeneration is not deterministic/current:")
        for difference in differences:
            print(f"- {difference}")
        return 1
    if args.check:
        print("Graphify canonical regeneration is deterministic (no diff).")
    else:
        print(f"Graphify {args.mode} refresh wrote canonical artifacts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
