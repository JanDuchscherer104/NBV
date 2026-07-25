#!/usr/bin/env python3
"""Corpus, provenance, deterministic serialization, and pin fixtures."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

import graphify_contract as contract  # noqa: E402
import check_graphify_integration as integration  # noqa: E402


def main() -> None:
    config = contract.load_config()
    assert config["graphify_version"] == "0.9.22"
    assert (
        config["graphify_upstream_commit"] == "abff1b1ca4052fcf9d955c5f6a034088723f4536"
    )
    assert (
        config["history"]["activation_commit"]
        == "c5e8ad862072505bcfc45642664c689d64290872"
    )

    assert contract.classify_path("aria_nbv/aria_nbv/model.py", config) == "code"
    assert contract.classify_path("aria_nbv/tests/test_model.py", config) == "code"
    assert contract.classify_path("AGENTS.md", config) == "scaffold"
    assert contract.classify_path("docs/AGENTS.md", config) == "scaffold"
    assert (
        contract.classify_path("scripts/scaffold/validate_omx_artifacts.py", config)
        == "scaffold"
    )
    assert (
        contract.classify_path("scripts/tests/test_validate_omx_artifacts.py", config)
        == "scaffold"
    )
    assert (
        contract.classify_path("aria_nbv/tests/agent_memory/test_agents_db.py", config)
        == "scaffold"
    )
    assert (
        contract.classify_path(".github/workflows/quarto-publish.yml", config)
        == "scaffold"
    )
    assert contract.classify_path("docs/contents/thesis/topic.qmd", config) == "thesis"
    assert (
        contract.classify_path("docs/contents/literature/topic.qmd", config)
        == "literature"
    )
    assert contract.classify_path("graphify-out/wiki/index.md", config) is None
    assert contract.classify_path(".omx/state/runtime.json", config) is None
    assert (
        contract.classify_path(".omx/specs/scaffold/decision-record.md", config)
        == "scaffold"
    )
    assert contract.classify_path("scripts/nbv_qmd_outline.sh", config) == "scaffold"
    assert contract.classify_path("scripts/nbv_typst_includes.py", config) == "scaffold"

    for event in ("pull_request", "push"):
        assert integration.CI_GRAPHIFY_OWNER_PATHS <= integration._workflow_paths(event)

    tracked = integration._tracked_paths()
    expected_inventory = integration._closed_inventory_paths(tracked, config)
    all_sources = {source["path"] for source in contract.collect_sources()}
    scaffold_sources = {
        source["path"]
        for source in contract.collect_sources()
        if source["partition"] == "scaffold"
    }
    assert expected_inventory <= all_sources
    assert integration._registered_omx_paths(tracked) <= scaffold_sources

    selected = {"arXiv-selected"}
    assert (
        contract.classify_path(
            "docs/literature/tex-src/arXiv-selected/main.tex",
            config,
            selected_literature_dirs=selected,
        )
        == "literature"
    )
    assert (
        contract.classify_path(
            "docs/literature/tex-src/arXiv-unselected/main.tex",
            config,
            selected_literature_dirs=selected,
        )
        is None
    )

    graph, manifest = contract.load_canonical()
    assert not contract.validate_graph(graph, manifest)
    assert contract.canonical_bytes(
        graph, manifest, "report"
    ) == contract.canonical_bytes(
        json.loads(json.dumps(graph)), json.loads(json.dumps(manifest)), "report"
    )

    origins = {edge["origin"] for edge in graph["edges"]}
    assert "EXTRACTED" in origins
    assert origins <= contract.ORIGINS
    assert all(
        isinstance(edge["confidence_score"], (int, float)) for edge in graph["edges"]
    )

    inferred = next(
        (edge for edge in graph["edges"] if edge["origin"] == "INFERRED"), None
    )
    assert inferred is not None, "source-backed inferred edge fixture is required"
    nodes = {node["id"]: node for node in graph["nodes"]}
    preserved = contract._preserved_semantic_edges(graph, manifest["sources"], nodes)
    assert inferred["id"] in {edge["id"] for edge in preserved}

    changed_sources = copy.deepcopy(manifest["sources"])
    locator_path = inferred["source_locators"][0]["path"]
    next(source for source in changed_sources if source["path"] == locator_path)[
        "sha256"
    ] = "0" * 64
    invalidated = contract._preserved_semantic_edges(graph, changed_sources, nodes)
    assert inferred["id"] not in {edge["id"] for edge in invalidated}

    missing_digest_graph = copy.deepcopy(graph)
    missing_digest_edge = next(
        edge for edge in missing_digest_graph["edges"] if edge["id"] == inferred["id"]
    )
    missing_digest_edge["source_locators"][0].pop("sha256")
    invalidated = contract._preserved_semantic_edges(
        missing_digest_graph, manifest["sources"], nodes
    )
    assert inferred["id"] not in {edge["id"] for edge in invalidated}

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source_paths = {
            "docs/typst/thesis/main.typ": '#include "../shared/macros.typ"\n',
            "docs/typst/shared/macros.typ": "#let thesis-title = [ARIA-NBV]\n",
        }
        sources = []
        nodes = {}
        for source_path, content in source_paths.items():
            path = root / source_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
            source = {
                "path": source_path,
                "sha256": digest,
                "partition": "thesis",
                "role": "guide",
            }
            sources.append(source)
            node_id = contract._file_node_id(source_path)
            nodes[node_id] = {
                "id": node_id,
                "source_file": source_path,
                "source_digest": digest,
                "partition": "thesis",
            }
        reference_edges = contract._reference_edges(root, sources, nodes)
        assert len(reference_edges) == 1
        assert reference_edges[0]["target"] == contract._file_node_id(
            "docs/typst/shared/macros.typ"
        )

    invalid = copy.deepcopy(graph)
    bad = copy.deepcopy(inferred)
    bad["id"] = "bad-query-edge"
    bad["source_locators"] = [{"path": "graphify-out/query.json", "locator": "L1"}]
    invalid["edges"].append(bad)
    errors = contract.validate_graph(invalid, manifest)
    assert any("exact manifest provenance" in error for error in errors)


if __name__ == "__main__":
    main()
