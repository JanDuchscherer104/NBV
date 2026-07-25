#!/usr/bin/env python3
"""Validate ARIA-NBV Graphify partitions and bridge revisions."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import sys

from graphify_contract import (
    ContractError,
    PARTITION_ORDER,
    ROOT,
    collect_sources,
    config_digest,
    load_canonical,
    load_config,
    source_manifest_digest,
    validate_graph,
)


@dataclass(frozen=True)
class Freshness:
    """Partition-local graph trust state."""

    fresh: frozenset[str]
    stale: dict[str, tuple[str, ...]]
    bridge_errors: tuple[str, ...]


def partition_freshness(root: Path = ROOT) -> Freshness:
    """Recompute current source/config state against canonical provenance."""
    try:
        config = load_config(root)
        graph, manifest = load_canonical(root / "graphify-out")
        sources = collect_sources(root, config)
    except ContractError as exc:
        return Freshness(
            frozenset(),
            {name: (str(exc),) for name in PARTITION_ORDER},
            (),
        )
    graph_errors = validate_graph(graph, manifest)
    if graph_errors:
        graph_reasons = tuple(
            f"invalid canonical graph: {error}" for error in graph_errors
        )
        return Freshness(
            frozenset(),
            {name: graph_reasons for name in PARTITION_ORDER},
            (),
        )
    stale: dict[str, tuple[str, ...]] = {}
    fresh: set[str] = set()
    current_config = config_digest(config, root)
    recorded_config = manifest.get("extraction_config_sha256")
    recorded_graphify = manifest.get("graphify", {})
    recorded_partitions = manifest.get("partitions", {})
    for name in PARTITION_ORDER:
        reasons: list[str] = []
        current_sources = [item for item in sources if item["partition"] == name]
        current_manifest = source_manifest_digest(current_sources)
        recorded = recorded_partitions.get(name, {})
        if current_config != recorded_config:
            reasons.append("extraction configuration changed")
        if recorded_graphify.get("version") != config.get("graphify_version"):
            reasons.append("Graphify version changed")
        if current_manifest != recorded.get("source_manifest_sha256"):
            reasons.append("source manifest changed")
        if not recorded.get("semantic_complete"):
            reasons.append("semantic review is incomplete")
        if reasons:
            stale[name] = tuple(reasons)
        else:
            fresh.add(name)

    bridge_errors: list[str] = []
    nodes = {
        node.get("id"): node
        for node in graph.get("nodes", [])
        if isinstance(node, dict)
    }
    for edge in graph.get("edges", []):
        if not isinstance(edge, dict) or "bridge_partition_revisions" not in edge:
            continue
        source = nodes.get(edge.get("source"), {})
        target = nodes.get(edge.get("target"), {})
        endpoint_partitions = {source.get("partition"), target.get("partition")}
        if not endpoint_partitions <= fresh:
            bridge_errors.append(f"{edge.get('id')}: stale endpoint partition")
            continue
        expected = {
            name: recorded_partitions.get(name, {}).get("revision")
            for name in endpoint_partitions
        }
        if edge.get("bridge_partition_revisions") != expected:
            bridge_errors.append(f"{edge.get('id')}: endpoint revision mismatch")
    return Freshness(frozenset(fresh), stale, tuple(sorted(bridge_errors)))


def freshness_errors(root: Path = ROOT) -> list[str]:
    """Return stable human-readable reasons graph evidence is incomplete."""
    state = partition_freshness(root)
    errors = [
        f"{name} partition is stale: {', '.join(state.stale[name])}"
        for name in PARTITION_ORDER
        if name in state.stale
    ]
    errors.extend(f"bridge is stale: {reason}" for reason in state.bridge_errors)
    return errors


def require_partitions(
    required: set[str], *, operation: str, root: Path = ROOT
) -> tuple[bool, str]:
    """Apply search-vs-path/explain fail-closed freshness semantics."""
    state = partition_freshness(root)
    stale = sorted(required - state.fresh)
    if not stale:
        return True, ""
    if operation == "search" and state.fresh:
        return True, "excluded stale partitions: " + ", ".join(stale)
    return False, f"{operation} requires stale partition(s): {', '.join(stale)}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--operation", choices=("search", "path", "explain"))
    parser.add_argument("--partition", action="append", choices=PARTITION_ORDER)
    args = parser.parse_args()
    if args.operation:
        required = set(args.partition or PARTITION_ORDER)
        allowed, reason = require_partitions(required, operation=args.operation)
        if reason and not args.quiet:
            print(reason)
        return int(not allowed)
    errors = freshness_errors()
    if errors and not args.quiet:
        print("Graphify is stale; use only fresh partitions or exact sources:")
        for error in errors:
            print(f"- {error}")
    elif not errors and not args.quiet:
        print("Graphify partitions and bridge revisions are fresh.")
    return int(bool(errors))


if __name__ == "__main__":
    sys.exit(main())
