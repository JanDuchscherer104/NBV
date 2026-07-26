#!/usr/bin/env python3
"""Check that the local Graphify index supports the project navigation routes."""

from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[2]
GRAPH = ROOT / "graphify-out/graph.json"
DESCRIPTOR_PLAN = (
    "docs/typst/thesis/sections/04-method/04-02-descriptor-and-encoding-plan.typ"
)


def main() -> None:
    graph = json.loads(GRAPH.read_text(encoding="utf-8"))
    assert set(graph) == {
        "built_at_commit",
        "directed",
        "graph",
        "hyperedges",
        "links",
        "multigraph",
        "nodes",
    }
    labels = {node["id"]: node["label"] for node in graph["nodes"]}
    edges = graph["links"]
    assert all(edge["source"] in labels and edge["target"] in labels for edge in edges)
    assert all(node.get("community") is not None for node in graph["nodes"])

    assert not any(
        label.startswith(
            ("symb_use_", "eqs_use_", "citation_use_", "term_use_", "code_reference_")
        )
        for label in labels.values()
    )

    def linked(owner: str, target: str, relation: str) -> bool:
        return any(
            edge.get("source_file") == owner
            and edge["relation"] == relation
            and target in labels.get(edge["target"], "")
            for edge in edges
        )

    assert linked(DESCRIPTOR_PLAN, "RolloutZarrStoreReader", "imports")
    assert linked(DESCRIPTOR_PLAN, "MultiStepCandidateScorer", "imports")
    assert linked(DESCRIPTOR_PLAN, "q_h_view", "calls")
    assert linked("docs/typst/thesis/main.typ", "appendix/index.typ", "imports_from")
    assert linked("docs/typst/thesis/main.typ", "04-method/index.typ", "imports_from")
    assert linked(
        "docs/literature/tex-src/arXiv-VIN-NBV/main.tex",
        "3_methods.tex",
        "imports_from",
    )
    assert any(
        node["label"].startswith("paper_arxiv_")
        and node["source_file"] == "docs/literature/tex-src/arXiv-VIN-NBV/main.tex"
        for node in graph["nodes"]
    )

    with tempfile.TemporaryDirectory(prefix="aria-graph-tree-") as directory:
        output = Path(directory) / "tree.html"
        subprocess.run(
            [
                "graphify",
                "tree",
                "--graph",
                str(GRAPH),
                "--root",
                ".",
                "--output",
                str(output),
                "--label",
                "ARIA-NBV",
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        text = output.read_text(encoding="utf-8")
        match = re.search(r"const initialJsonData = (\{.*\});", text)
        assert match is not None
        tree = json.loads(match.group(1))
        assert [child["name"] for child in tree["children"]] == ["aria_nbv", "docs"]

    explained = subprocess.run(
        ["graphify", "explain", "q_h_view", "--graph", str(GRAPH)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "pre-#1504" not in explained.stderr
    assert "rollouts/zarr_store.py" in explained.stdout
    assert DESCRIPTOR_PLAN in explained.stdout

    benchmark = subprocess.run(
        ["graphify", "benchmark", str(GRAPH)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "token reduction benchmark" in benchmark.stdout
    print("Graphify retrieval contract passed")


if __name__ == "__main__":
    main()
