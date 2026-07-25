#!/usr/bin/env python3
"""Check the pinned Graphify corpus, artifacts, provenance, and wiring."""

from __future__ import annotations

import csv
import fnmatch
import os
import re
import subprocess
import sys
import tomllib
from typing import Any

from graphify_contract import (
    ContractError,
    PARTITION_ORDER,
    ROOT,
    classify_path,
    collect_sources,
    load_canonical,
    load_config,
    validate_graph,
)
from graphify_refresh import graphify_command

MAX_CANONICAL_BYTES = 35 * 1024 * 1024
CANONICAL = {
    "graphify-out/graph.json",
    "graphify-out/manifest.json",
    "graphify-out/GRAPH_REPORT.md",
}
CLOSED_INVENTORY_STATUSES = {"migrate", "promote", "retain"}
LINE_ANCHOR = re.compile(r":\d+(?:-\d+)?$")
CI_GRAPHIFY_OWNER_PATHS = {
    ".agents/**",
    ".claude/**",
    ".codex/**",
    ".codex-plugin/**",
    ".configs/**",
    ".gemini/**",
    ".github/workflows/**",
    ".gitattributes",
    ".gitignore",
    ".graphify.toml",
    ".graphifyignore",
    ".omx/**",
    ".pre-commit-config.yaml",
    "AGENTS.md",
    "CLAUDE.md",
    "Makefile",
    "aria_nbv/**",
    "docs/**",
    "graphify-out/**",
    "scripts/**",
}


def _graphify_version() -> str:
    executable = graphify_command()
    command = subprocess.run(
        [*executable, "--version"], text=True, capture_output=True, check=False
    )
    match = re.search(r"(\d+\.\d+\.\d+)", command.stdout + command.stderr)
    if command.returncode or match is None:
        raise ContractError("graphify executable/version is unavailable")
    return match.group(1)


def _validate_pin(config: dict[str, Any]) -> None:
    version_file = (
        (ROOT / ".codex/skills/graphify/.graphify_version")
        .read_text(encoding="utf-8")
        .strip()
    )
    if version_file != config["graphify_version"]:
        raise ContractError("Graphify version file and capability record differ")
    found = _graphify_version()
    if found != version_file:
        raise ContractError(f"Graphify {version_file} is required; found {found}")


def _validate_tracked_outputs(config: dict[str, Any]) -> None:
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


def _tracked_paths() -> set[str]:
    return set(
        subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True).splitlines()
    )


def _closed_inventory_paths(tracked: set[str], config: dict[str, Any]) -> set[str]:
    inventory = ROOT / ".agents/baselines/scaffold_wp0_inventory.csv"
    with inventory.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    candidates: set[str] = set()
    for row in rows:
        if row.get("status") not in CLOSED_INVENTORY_STATUSES:
            continue
        for token in row["paths"].split(";"):
            path = LINE_ANCHOR.sub("", token.strip())
            if any(character in path for character in "*?["):
                candidates.update(
                    candidate
                    for candidate in tracked
                    if fnmatch.fnmatchcase(candidate, path)
                )
            elif path in tracked:
                candidates.add(path)
            if row["status"] == "retain" and path.startswith(
                ".agents/skills/aria-nbv-context/scripts/"
            ):
                retained_reader = f"scripts/{path.rsplit('/', 1)[-1]}"
                if retained_reader in tracked:
                    candidates.add(retained_reader)
    extensions = set(config["corpus"]["text_extensions"])
    extensionless = {
        ".gitattributes",
        ".gitignore",
        ".graphifyignore",
        "Makefile",
        "scripts/git_hooks/post-commit",
    }
    return {
        path
        for path in candidates
        if path in extensionless or os.path.splitext(path)[1].lower() in extensions
    }


def _registered_omx_paths(tracked: set[str]) -> set[str]:
    registry = tomllib.loads(
        (ROOT / ".agents/omx_artifacts.toml").read_text(encoding="utf-8")
    )
    return {
        path
        for bundle in registry.get("bundles", [])
        for artifact in bundle.get("artifacts", [])
        for key in ("path", "native_path")
        if isinstance((path := artifact.get(key)), str) and path in tracked
    }


def _workflow_paths(event: str) -> set[str]:
    lines = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8").splitlines()
    event_header = f"  {event}:"
    start = lines.index(event_header)
    paths_start = lines.index("    paths:", start)
    paths: set[str] = set()
    for line in lines[paths_start + 1 :]:
        if line.startswith("  ") and not line.startswith("      "):
            break
        match = re.fullmatch(r'\s{6}- "([^"]+)"', line)
        if match:
            paths.add(match.group(1))
    return paths


def _validate_ci_triggers() -> None:
    for event in ("pull_request", "push"):
        missing = CI_GRAPHIFY_OWNER_PATHS - _workflow_paths(event)
        if missing:
            raise ContractError(
                f"{event} paths omit Graphify/gate owners: "
                + ", ".join(sorted(missing))
            )


def _validate_corpus(config: dict[str, Any]) -> None:
    sources = collect_sources(ROOT, config)
    partitions: dict[str, list[dict[str, Any]]] = {name: [] for name in PARTITION_ORDER}
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
    scaffold_paths = {item["path"] for item in partitions["scaffold"]}
    tracked = _tracked_paths()
    inventory_paths = _closed_inventory_paths(tracked, config)
    missing_inventory = inventory_paths - paths
    if missing_inventory:
        raise ContractError(
            "closed inventory sources are absent from the Graphify corpus: "
            + ", ".join(sorted(missing_inventory))
        )
    missing_registry = _registered_omx_paths(tracked) - scaffold_paths
    if missing_registry:
        raise ContractError(
            "registered OMX sources are absent from the scaffold partition: "
            + ", ".join(sorted(missing_registry))
        )
    forbidden = {
        path
        for path in paths
        if path.startswith(("graphify-out/", ".omx/state/", "docs/_site/"))
        or "/wiki/" in path
    }
    if forbidden:
        raise ContractError(
            "forbidden Graphify corpus sources: " + ", ".join(sorted(forbidden))
        )


def _validate_hook_and_merge() -> None:
    hook = (ROOT / "scripts/git_hooks/post-commit").read_text(encoding="utf-8")
    required = (
        "GRAPHIFY_CHANGED",
        "classify_path",
        "graphify_refresh.py",
        "start_new_session=True",
    )
    if any(value not in hook for value in required):
        raise ContractError("post-commit lacks asynchronous Graphify dispatch contract")
    forbidden = ("git add", "git commit", "--mode sync", "save-result", "reflect")
    if any(value in hook for value in forbidden):
        raise ContractError("post-commit performs forbidden mutation/semantic work")
    config = load_config()
    for path in (
        ".agents/skills/demo/SKILL.md",
        ".omx/plans/example.md",
        "AGENTS.md",
        ".graphify.toml",
        "scripts/graphify_contract.py",
    ):
        if classify_path(path, config) is None:
            raise ContractError(f"Graphify hook corpus fixture is unclassified: {path}")
    attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")
    if "graphify-out/graph.json merge=graphify" not in attributes:
        raise ContractError("Graphify merge driver is not assigned in .gitattributes")
    if not (ROOT / "scripts/graphify_merge_driver.py").is_file():
        raise ContractError("Graphify merge driver wrapper is absent")


def _validate_query_routing() -> None:
    guidance = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    contract = (ROOT / ".agents/references/graphify_contract.md").read_text(
        encoding="utf-8"
    )
    context_skill = (ROOT / ".agents/skills/aria-nbv-context/SKILL.md").read_text(
        encoding="utf-8"
    )
    required = (
        'graphify query "<question>"',
        'graphify path "<A>" "<B>"',
        'graphify explain "<concept>"',
    )
    if any(value not in guidance for value in required):
        raise ContractError("AGENTS.md does not route through upstream Graphify CLI")
    if "pinned upstream public CLI directly" not in contract:
        raise ContractError("Graphify contract does not own upstream CLI routing")
    if "scripts/graphify_query.py" in context_skill:
        raise ContractError("context skill still routes through the obsolete wrapper")
    if (ROOT / "scripts/graphify_query.py").exists():
        raise ContractError("obsolete local Graphify query implementation remains")


def run_check() -> tuple[int, int, int]:
    config = load_config()
    _validate_pin(config)
    _validate_tracked_outputs(config)
    _validate_corpus(config)
    _validate_ci_triggers()
    _validate_hook_and_merge()
    _validate_query_routing()
    graph, manifest = load_canonical()
    errors = validate_graph(graph, manifest)
    if errors:
        raise ContractError(
            "canonical graph provenance errors:\n- " + "\n- ".join(errors[:30])
        )
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
