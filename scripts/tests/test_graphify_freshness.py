#!/usr/bin/env python3
"""Partition-staleness, bridge, role, and exact-source fallback fixtures."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

import check_graphify_freshness as freshness  # noqa: E402
import graphify_contract as contract  # noqa: E402
import graphify_query as query  # noqa: E402


def _write_fixture(root: Path) -> tuple[dict, dict]:
    shutil.copy(contract.ROOT / ".graphify.toml", root / ".graphify.toml")
    shutil.copy(contract.ROOT / ".graphifyignore", root / ".graphifyignore")
    files = {
        "AGENTS.md": "See `docs/page.qmd`.\n",
        "docs/page.qmd": "# Thesis\n",
        "docs/literature/sources.jsonl": "",
        "aria_nbv/aria_nbv/model.py": "VALUE = 1\n",
        "aria_nbv/tests/test_model.py": "def test_value(): pass\n",
        "aria_nbv/pyproject.toml": "[project]\nname='fixture'\n",
        "aria_nbv/README.md": "# Package guide\n",
    }
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    config = contract.load_config(root)
    sources = contract.collect_sources(root, config)
    partitions = {}
    for name in contract.PARTITION_ORDER:
        selected = [source for source in sources if source["partition"] == name]
        partitions[name] = {
            "source_manifest_sha256": contract.source_manifest_digest(selected),
            "semantic_complete": True,
            "revision": f"revision-{name}",
        }
    scaffold = next(source for source in sources if source["path"] == "AGENTS.md")
    scaffold_node = {
        "id": "scaffold",
        "label": "AGENTS.md",
        "source_file": "AGENTS.md",
        "partition": "scaffold",
        "role": "guide",
        "partition_revision": "revision-scaffold",
    }
    thesis_node = {
        "id": "thesis",
        "label": "page.qmd",
        "source_file": "docs/page.qmd",
        "partition": "thesis",
        "role": "guide",
        "partition_revision": "revision-thesis",
    }
    edge = {
        "id": "bridge",
        "source": "scaffold",
        "target": "thesis",
        "origin": "INFERRED",
        "confidence_score": 0.9,
        "source_locators": [
            {"path": "AGENTS.md", "locator": "L1", "sha256": scaffold["sha256"]}
        ],
        "bridge_partition_revisions": {
            "scaffold": "revision-scaffold",
            "thesis": "revision-thesis",
        },
    }
    tree = contract.corpus_tree_digest(sources)
    graph = {
        "corpus_tree_sha256": tree,
        "partitions": partitions,
        "nodes": [scaffold_node, thesis_node],
        "edges": [edge],
    }
    manifest = {
        "extraction_config_sha256": contract.config_digest(config, root),
        "corpus_tree_sha256": tree,
        "partitions": partitions,
        "sources": sources,
    }
    out = root / "graphify-out"
    out.mkdir()
    (out / "graph.json").write_text(json.dumps(graph), encoding="utf-8")
    (out / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return graph, manifest


def main() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        graph, _ = _write_fixture(root)
        state = freshness.partition_freshness(root)
        assert state.fresh == frozenset(contract.PARTITION_ORDER)
        assert not state.bridge_errors

        roles = {source["role"] for source in contract.collect_sources(root) if source["partition"] == "code"}
        assert roles == {"production", "test", "config", "guide"}

        (root / "docs/page.qmd").write_text("# Changed thesis\n", encoding="utf-8")
        state = freshness.partition_freshness(root)
        assert set(state.stale) == {"thesis"}
        allowed, reason = freshness.require_partitions(
            set(contract.PARTITION_ORDER), operation="search", root=root
        )
        assert allowed and "thesis" in reason
        allowed, reason = freshness.require_partitions(
            {"thesis"}, operation="explain", root=root
        )
        assert not allowed and "stale" in reason

        results, excluded = query.search("Changed thesis", root)
        assert excluded == ["thesis"]
        assert any("docs/page.qmd:1" in result for result in results)

        (root / "docs/page.qmd").write_text("# Thesis\n", encoding="utf-8")
        graph["edges"][0]["bridge_partition_revisions"]["thesis"] = "wrong"
        (root / "graphify-out/graph.json").write_text(json.dumps(graph), encoding="utf-8")
        state = freshness.partition_freshness(root)
        assert state.fresh == frozenset(contract.PARTITION_ORDER)
        assert state.bridge_errors == ("bridge: endpoint revision mismatch",)

        (root / "graphify-out/graph.json").unlink()
        fallback, excluded = query.search("Package guide", root)
        assert excluded == list(contract.PARTITION_ORDER)
        assert any("aria_nbv/README.md:1" in result for result in fallback)


if __name__ == "__main__":
    main()
