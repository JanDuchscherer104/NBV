#!/usr/bin/env python3
"""Partition-staleness, bridge, role, and exact-source fallback fixtures."""

from __future__ import annotations

import copy
import json
import os
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
import graphify_refresh as refresh  # noqa: E402


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
    nodes = [
        {
            "id": contract._file_node_id(source["path"]),
            "label": Path(source["path"]).name,
            "source_file": source["path"],
            "source_digest": source["sha256"],
            "partition": source["partition"],
            "role": source["role"],
            "partition_revision": f"revision-{source['partition']}",
        }
        for source in sources
    ]
    edge = {
        "id": "bridge",
        "source": contract._file_node_id("AGENTS.md"),
        "target": contract._file_node_id("docs/page.qmd"),
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
        "nodes": nodes,
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
        graph, manifest = _write_fixture(root)
        state = freshness.partition_freshness(root)
        assert state.fresh == frozenset(contract.PARTITION_ORDER)
        assert not state.bridge_errors

        empty_graph = dict(graph)
        empty_graph["nodes"] = []
        empty_graph["edges"] = []
        (root / "graphify-out/graph.json").write_text(
            json.dumps(empty_graph), encoding="utf-8"
        )
        state = freshness.partition_freshness(root)
        assert set(state.stale) == set(contract.PARTITION_ORDER)
        assert any(
            "graph contains no canonical nodes" in reason
            for reasons in state.stale.values()
            for reason in reasons
        )
        (root / "graphify-out/graph.json").write_text(
            json.dumps(graph), encoding="utf-8"
        )

        partial_graph = copy.deepcopy(graph)
        removed_id = contract._file_node_id(manifest["sources"][0]["path"])
        partial_graph["nodes"] = [
            node for node in partial_graph["nodes"] if node["id"] != removed_id
        ]
        partial_graph["edges"] = [
            edge
            for edge in partial_graph["edges"]
            if removed_id not in {edge["source"], edge["target"]}
        ]
        (root / "graphify-out/graph.json").write_text(
            json.dumps(partial_graph), encoding="utf-8"
        )
        state = freshness.partition_freshness(root)
        assert set(state.stale) == set(contract.PARTITION_ORDER)
        assert any(
            "graph lacks canonical source node" in reason
            for reasons in state.stale.values()
            for reason in reasons
        )
        (root / "graphify-out/graph.json").write_text(
            json.dumps(graph), encoding="utf-8"
        )

        assert query._meaningful_terms("do V0 V1") == ["v0", "v1"]
        ranked = query._matching_nodes(
            {
                "nodes": [
                    {
                        "id": "a-docs-noise",
                        "label": "overview",
                        "source_file": "docs/overview.qmd",
                        "partition": "thesis",
                        "role": "guide",
                    },
                    {
                        "id": "z-relevant",
                        "label": "macros",
                        "source_file": "docs/typst/shared/macros.typ",
                        "partition": "thesis",
                        "role": "guide",
                    },
                ]
            },
            "do macros",
            {"thesis"},
        )
        assert [node["id"] for node in ranked] == ["z-relevant"]

        allowed, no_evidence, excluded = query.search(
            "unfindable evidence phrase", root
        )
        assert not allowed
        assert not no_evidence
        assert not excluded

        roles = {
            source["role"]
            for source in contract.collect_sources(root)
            if source["partition"] == "code"
        }
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

        allowed, results, excluded = query.search("Changed thesis", root)
        assert not allowed
        assert excluded == ["thesis"]
        assert any("docs/page.qmd:1" in result for result in results)
        allowed, explanation = query.explain("page.qmd", root)
        assert not allowed
        assert any("docs/page.qmd:1:path match" in line for line in explanation)
        allowed, route = query.path_between("AGENTS.md", "page.qmd", root)
        assert not allowed
        assert any("AGENTS.md:1:path match" in line for line in route)
        assert any("docs/page.qmd:1:path match" in line for line in route)

        (root / "docs/page.qmd").unlink()
        allowed, explanation = query.explain("page.qmd", root)
        assert not allowed
        assert not any("docs/page.qmd:1:path match" in line for line in explanation)

        (root / "docs/page.qmd").write_text("# Thesis\n", encoding="utf-8")
        graph["edges"][0]["bridge_partition_revisions"]["thesis"] = "wrong"
        (root / "graphify-out/graph.json").write_text(
            json.dumps(graph), encoding="utf-8"
        )
        state = freshness.partition_freshness(root)
        assert state.fresh == frozenset(contract.PARTITION_ORDER)
        assert state.bridge_errors == ("bridge: endpoint revision mismatch",)

        (root / "graphify-out/graph.json").unlink()
        allowed, fallback, excluded = query.search("Package source guide", root)
        assert not allowed
        assert excluded == list(contract.PARTITION_ORDER)
        assert any("aria_nbv/README.md:1" in result for result in fallback)
        assert not query.exact_source_fallback("no exact evidence anywhere", root)
        allowed, fallback = query.explain("Package guide", root)
        assert not allowed
        assert any("aria_nbv/README.md:1" in result for result in fallback)
        allowed, fallback = query.path_between("Package guide", "Thesis", root)
        assert not allowed
        assert any("aria_nbv/README.md:1" in result for result in fallback)
        assert any("docs/page.qmd:1" in result for result in fallback)

        selected_manifest = root / "docs/literature/sources.jsonl"
        selected_manifest.write_text('{"tex_dir":"arXiv-selected"}\n', encoding="utf-8")
        selected_tex = root / "docs/literature/tex-src/arXiv-selected/main.tex"
        selected_tex.parent.mkdir(parents=True)
        selected_tex.write_text("selected\n", encoding="utf-8")
        assert refresh._pending_partitions(
            [Path("docs/literature/tex-src/arXiv-selected/main.tex")], root
        ) == {"literature"}
        assert not refresh._pending_partitions(
            [Path("docs/literature/tex-src/arXiv-unselected/main.tex")], root
        )

        stale_global = root / "bin/graphify"
        stale_global.parent.mkdir()
        stale_global.write_text(
            "#!/bin/sh\nprintf 'graphify 0.9.9\\n'\n", encoding="utf-8"
        )
        stale_global.chmod(0o755)
        old_path = os.environ.get("PATH", "")
        old_override = os.environ.pop("GRAPHIFY_BIN", None)
        try:
            os.environ["PATH"] = f"{stale_global.parent}:{old_path}"
            assert refresh.graphify_command() == [
                sys.executable,
                "-m",
                "graphify",
            ]
            os.environ["GRAPHIFY_BIN"] = f"{stale_global} --explicit"
            assert refresh.graphify_command() == [str(stale_global), "--explicit"]
        finally:
            os.environ["PATH"] = old_path
            if old_override is None:
                os.environ.pop("GRAPHIFY_BIN", None)
            else:
                os.environ["GRAPHIFY_BIN"] = old_override


if __name__ == "__main__":
    main()
