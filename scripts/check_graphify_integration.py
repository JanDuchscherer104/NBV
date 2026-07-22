#!/usr/bin/env python3
"""Check the pinned Graphify corpus, artifacts, provenance, and wiring."""

from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys

from graphify_contract import (
    ContractError,
    PARTITION_ORDER,
    ROOT,
    collect_sources,
    load_canonical,
    load_config,
    validate_graph,
)

MAX_CANONICAL_BYTES = 35 * 1024 * 1024
CANONICAL = {
    "graphify-out/graph.json",
    "graphify-out/manifest.json",
    "graphify-out/GRAPH_REPORT.md",
}


def _graphify_version() -> str:
    executable = shlex.split(os.environ.get("GRAPHIFY_BIN", "graphify"))
    command = subprocess.run(
        [*executable, "--version"], text=True, capture_output=True, check=False
    )
    match = re.search(r"(\d+\.\d+\.\d+)", command.stdout + command.stderr)
    if command.returncode or match is None:
        raise ContractError("graphify executable/version is unavailable")
    return match.group(1)


def _validate_pin(config: dict) -> None:
    version_file = (ROOT / ".codex/skills/graphify/.graphify_version").read_text(
        encoding="utf-8"
    ).strip()
    if version_file != config["graphify_version"]:
        raise ContractError("Graphify version file and capability record differ")
    found = _graphify_version()
    if found != version_file:
        raise ContractError(f"Graphify {version_file} is required; found {found}")


def _validate_tracked_outputs(config: dict) -> None:
    expected = set(config["canonical_artifacts"])
    if expected != CANONICAL:
        raise ContractError("canonical Graphify artifact allowlist drifted")
    tracked = set(
        subprocess.check_output(
            ["git", "ls-files", "graphify-out"], cwd=ROOT, text=True
        ).splitlines()
    )
    if tracked != expected:
        raise ContractError(
            "tracked Graphify output must equal canonical allowlist; found "
            + ", ".join(sorted(tracked))
        )
    size = sum((ROOT / path).stat().st_size for path in expected)
    if size > MAX_CANONICAL_BYTES:
        raise ContractError(f"canonical Graphify output exceeds 35 MB: {size} bytes")
    forbidden = [
        path
        for path in tracked
        if "wiki" in path.casefold() or path.endswith((".html", "cost.json"))
    ]
    if forbidden:
        raise ContractError("tracked wiki/cache/render output is forbidden")


def _validate_corpus(config: dict) -> None:
    sources = collect_sources(ROOT, config)
    partitions = {name: [] for name in PARTITION_ORDER}
    for source in sources:
        partitions[source["partition"]].append(source)
    missing = [name for name, values in partitions.items() if not values]
    if missing:
        raise ContractError("empty Graphify partitions: " + ", ".join(missing))
    code_roles = {item["role"] for item in partitions["code"]}
    if not {"production", "test", "config", "guide"} <= code_roles:
        raise ContractError(
            "code partition lacks production/test/config/guide role coverage"
        )
    paths = {item["path"] for item in sources}
    forbidden = {
        path
        for path in paths
        if path.startswith(("graphify-out/", ".omx/state/", "docs/_site/"))
        or "/wiki/" in path
    }
    if forbidden:
        raise ContractError("forbidden Graphify corpus sources: " + ", ".join(sorted(forbidden)))


def _validate_hook_and_merge() -> None:
    hook = (ROOT / "scripts/git_hooks/post-commit").read_text(encoding="utf-8")
    required = ("GRAPHIFY_CHANGED", "graphify_refresh.py", "start_new_session=True")
    if any(value not in hook for value in required):
        raise ContractError("post-commit lacks asynchronous Graphify dispatch contract")
    forbidden = ("git add", "git commit", "--mode sync", "save-result", "reflect")
    if any(value in hook for value in forbidden):
        raise ContractError("post-commit performs forbidden mutation/semantic work")
    attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")
    if "graphify-out/graph.json merge=graphify" not in attributes:
        raise ContractError("Graphify merge driver is not assigned in .gitattributes")
    if not (ROOT / "scripts/graphify_merge_driver.py").is_file():
        raise ContractError("Graphify merge driver wrapper is absent")


def run_check() -> tuple[int, int, int]:
    config = load_config()
    _validate_pin(config)
    _validate_tracked_outputs(config)
    _validate_corpus(config)
    _validate_hook_and_merge()
    graph, manifest = load_canonical()
    errors = validate_graph(graph, manifest)
    if errors:
        raise ContractError("canonical graph provenance errors:\n- " + "\n- ".join(errors[:30]))
    return len(manifest["sources"]), len(graph["nodes"]), len(graph["edges"])


def main() -> int:
    try:
        sources, nodes, edges = run_check()
    except (ContractError, OSError, subprocess.CalledProcessError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"Graphify integration OK: {sources} sources, {nodes} nodes, {edges} edges")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
