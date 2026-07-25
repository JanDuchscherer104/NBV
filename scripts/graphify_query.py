#!/usr/bin/env python3
"""Query fresh Graphify evidence or fall back to exact tracked sources."""

from __future__ import annotations

import argparse
from collections import deque
from pathlib import Path
import re
import sys
from typing import Any

from check_graphify_freshness import partition_freshness
from graphify_contract import (
    ContractError,
    PARTITION_ORDER,
    ROOT,
    collect_sources,
    load_canonical,
)

STOP_TERMS = {
    "a",
    "an",
    "and",
    "for",
    "from",
    "in",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
}


def _meaningful_terms(query: str) -> list[str]:
    return list(
        dict.fromkeys(
            normalized
            for term in re.findall(r"[A-Za-z0-9_.-]+", query)
            if ((normalized := term.casefold()) not in STOP_TERMS)
            and (len(normalized) > 2 or any(character.isdigit() for character in term))
        )
    )


def exact_source_fallback(query: str, root: Path = ROOT, limit: int = 20) -> list[str]:
    """Return ranked literal-term matches from canonical corpus sources."""
    terms = _meaningful_terms(query)
    if not terms:
        return []
    ranked: list[tuple[int, int, str]] = []
    for source in collect_sources(root):
        path = root / source["path"]
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError):
            continue
        path_score = sum(term in source["path"].casefold() for term in terms)
        if path_score:
            ranked.append((-path_score, 0, f"{source['path']}:1:path match"))
        for line_number, line in enumerate(lines, start=1):
            score = sum(term in line.casefold() for term in terms)
            if score:
                ranked.append(
                    (
                        -score,
                        1,
                        f"{source['path']}:{line_number}:{line.strip()}",
                    )
                )
    return [item[2] for item in sorted(ranked)[:limit]]


def _fallback_for_terms(*terms: str, root: Path = ROOT) -> list[str]:
    matches: list[str] = []
    for term in terms:
        for match in exact_source_fallback(term, root):
            if match not in matches:
                matches.append(match)
    return matches


def _matching_nodes(
    graph: dict[str, Any], query: str, fresh: set[str]
) -> list[dict[str, Any]]:
    terms = _meaningful_terms(query)
    ranked = []
    role_rank = {"production": 0, "test": 1, "config": 2, "guide": 3}
    for node in graph.get("nodes", []):
        if node.get("partition") not in fresh:
            continue
        haystack = f"{node.get('label', '')} {node.get('source_file', '')}".casefold()
        score = sum(term in haystack for term in terms)
        if score:
            ranked.append((-score, role_rank.get(node.get("role"), 4), node))
    return [
        item[2]
        for item in sorted(ranked, key=lambda item: (item[0], item[1], item[2]["id"]))
    ]


def search(query: str, root: Path = ROOT) -> tuple[bool, list[str], list[str]]:
    state = partition_freshness(root)
    try:
        graph, _ = load_canonical(root / "graphify-out")
    except ContractError:
        return False, exact_source_fallback(query, root), list(PARTITION_ORDER)
    nodes = _matching_nodes(graph, query, set(state.fresh))
    results = [
        f"{node['partition']}:{node['role']}:{node['source_file']}:{node.get('source_location', 'L1')}"
        for node in nodes[:20]
    ]
    if results:
        return True, results, sorted(state.stale)
    results = exact_source_fallback(query, root)
    return not state.stale and bool(results), results, sorted(state.stale)


def explain(term: str, root: Path = ROOT) -> tuple[bool, list[str]]:
    state = partition_freshness(root)
    try:
        graph, _ = load_canonical(root / "graphify-out")
    except ContractError:
        return False, _fallback_for_terms(term, root=root)
    all_matches = _matching_nodes(graph, term, set(PARTITION_ORDER))
    if not all_matches:
        return False, _fallback_for_terms(term, root=root)
    node = all_matches[0]
    if node["partition"] not in state.fresh:
        return False, [
            f"explain rejected: {node['partition']} partition is stale",
            *_fallback_for_terms(term, root=root),
        ]
    return True, [
        f"{node['label']} — {node['source_file']}:{node.get('source_location', 'L1')}"
    ]


def path_between(start: str, end: str, root: Path = ROOT) -> tuple[bool, list[str]]:
    state = partition_freshness(root)
    try:
        graph, _ = load_canonical(root / "graphify-out")
    except ContractError:
        return False, _fallback_for_terms(start, end, root=root)
    starts = _matching_nodes(graph, start, set(PARTITION_ORDER))
    ends = _matching_nodes(graph, end, set(PARTITION_ORDER))
    if not starts or not ends:
        return False, _fallback_for_terms(start, end, root=root)
    source, target = starts[0], ends[0]
    required = {source["partition"], target["partition"]}
    if not required <= state.fresh:
        return False, [
            "path rejected: stale partition(s): "
            + ", ".join(sorted(required - state.fresh)),
            *_fallback_for_terms(start, end, root=root),
        ]
    adjacency: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for edge in graph.get("edges", []):
        if edge.get("bridge_partition_revisions") and any(
            error.startswith(str(edge.get("id"))) for error in state.bridge_errors
        ):
            continue
        adjacency.setdefault(edge["source"], []).append((edge["target"], edge))
        adjacency.setdefault(edge["target"], []).append((edge["source"], edge))
    queue = deque([(source["id"], [source["id"]])])
    seen = {source["id"]}
    while queue:
        current, route = queue.popleft()
        if current == target["id"]:
            nodes = {node["id"]: node for node in graph["nodes"]}
            return True, [
                f"{nodes[node_id]['label']} ({nodes[node_id]['partition']})"
                for node_id in route
            ]
        for neighbor, _ in adjacency.get(current, []):
            if neighbor not in seen:
                seen.add(neighbor)
                queue.append((neighbor, [*route, neighbor]))
    return False, [
        "no fresh path found; inspect exact source owners",
        *_fallback_for_terms(start, end, root=root),
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="operation", required=True)
    search_parser = sub.add_parser("query", aliases=["search"])
    search_parser.add_argument("query")
    explain_parser = sub.add_parser("explain")
    explain_parser.add_argument("term")
    path_parser = sub.add_parser("path")
    path_parser.add_argument("start")
    path_parser.add_argument("end")
    args = parser.parse_args()
    try:
        if args.operation in {"query", "search"}:
            allowed, lines, stale = search(args.query)
            if stale:
                print("excluded stale partitions: " + ", ".join(stale), file=sys.stderr)
        elif args.operation == "explain":
            allowed, lines = explain(args.term)
        else:
            allowed, lines = path_between(args.start, args.end)
    except ContractError as exc:
        print(
            f"Graphify unavailable: {exc}; exact-source fallback required",
            file=sys.stderr,
        )
        return 1
    print("\n".join(lines))
    return int(not allowed)


if __name__ == "__main__":
    raise SystemExit(main())
