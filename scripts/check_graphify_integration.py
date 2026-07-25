#!/usr/bin/env python3
"""Check the pinned Graphify corpus, artifacts, provenance, and wiring."""

from __future__ import annotations

import re
import subprocess
import sys
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
    if {item["role"] for item in partitions["code"]} != {"production"}:
        raise ContractError("code partition must contain production sources only")
    paths = {item["path"] for item in sources}
    allowed_roots = (
        "aria_nbv/aria_nbv/",
        "docs/typst/thesis/",
        "docs/typst/shared/",
        "docs/literature/sources.jsonl",
        "docs/literature/tex-src/",
    )
    forbidden = {path for path in paths if not path.startswith(allowed_roots)}
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
    if classify_path("aria_nbv/aria_nbv/model.py", config) != "code":
        raise ContractError("Graphify hook does not classify production code")
    for path in (
        "AGENTS.md",
        ".configs/app.yaml",
        ".omx/plans/example.md",
        "scripts/graphify_contract.py",
    ):
        if classify_path(path, config) is not None:
            raise ContractError(f"Graphify hook classifies operator surface: {path}")
    attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")
    if "graphify-out/graph.json merge=graphify" not in attributes:
        raise ContractError("Graphify merge driver is not assigned in .gitattributes")
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    if "graphify-setup:" not in makefile or "merge-driver %O %A %B" not in makefile:
        raise ContractError(
            "graphify-setup does not configure the upstream merge driver"
        )
    if "graphify_merge_driver.py" in makefile:
        raise ContractError("graphify-setup still routes through the obsolete wrapper")
    if (ROOT / "scripts/graphify_merge_driver.py").exists():
        raise ContractError("obsolete Graphify merge driver wrapper remains")


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
