#!/usr/bin/env python3
"""Corpus, provenance, deterministic serialization, and pin fixtures."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import sys

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

import graphify_contract as contract  # noqa: E402


def main() -> None:
    config = contract.load_config()
    assert config["graphify_version"] == "0.9.22"
    assert config["graphify_upstream_commit"] == "abff1b1ca4052fcf9d955c5f6a034088723f4536"

    assert contract.classify_path("aria_nbv/aria_nbv/model.py", config) == "code"
    assert contract.classify_path("aria_nbv/tests/test_model.py", config) == "code"
    assert contract.classify_path("AGENTS.md", config) == "scaffold"
    assert contract.classify_path("docs/AGENTS.md", config) == "scaffold"
    assert contract.classify_path("docs/contents/thesis/topic.qmd", config) == "thesis"
    assert contract.classify_path("docs/contents/literature/topic.qmd", config) == "literature"
    assert contract.classify_path("graphify-out/wiki/index.md", config) is None
    assert contract.classify_path(".omx/state/runtime.json", config) is None

    graph, manifest = contract.load_canonical()
    assert not contract.validate_graph(graph, manifest)
    assert contract.canonical_bytes(graph, manifest, "report") == contract.canonical_bytes(
        json.loads(json.dumps(graph)), json.loads(json.dumps(manifest)), "report"
    )

    origins = {edge["origin"] for edge in graph["edges"]}
    assert "EXTRACTED" in origins
    assert origins <= contract.ORIGINS
    assert all(isinstance(edge["confidence_score"], (int, float)) for edge in graph["edges"])

    inferred = next((edge for edge in graph["edges"] if edge["origin"] == "INFERRED"), None)
    assert inferred is not None, "source-backed inferred edge fixture is required"
    nodes = {node["id"]: node for node in graph["nodes"]}
    preserved = contract._preserved_semantic_edges(graph, manifest["sources"], nodes)
    assert inferred["id"] in {edge["id"] for edge in preserved}

    changed_sources = copy.deepcopy(manifest["sources"])
    locator_path = inferred["source_locators"][0]["path"]
    next(source for source in changed_sources if source["path"] == locator_path)["sha256"] = "0" * 64
    invalidated = contract._preserved_semantic_edges(graph, changed_sources, nodes)
    assert inferred["id"] not in {edge["id"] for edge in invalidated}

    invalid = copy.deepcopy(graph)
    bad = copy.deepcopy(inferred)
    bad["id"] = "bad-query-edge"
    bad["source_locators"] = [
        {"path": "graphify-out/query.json", "locator": "L1", "sha256": "0" * 64}
    ]
    invalid["edges"].append(bad)
    errors = contract.validate_graph(invalid, manifest)
    assert any("source digest" in error or "non-corpus" in error for error in errors)


if __name__ == "__main__":
    main()
