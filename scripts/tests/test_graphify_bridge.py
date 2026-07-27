from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

from graphify_bridge import materialize  # noqa: E402

SOURCES = [
    {
        "path": "docs/shared/symbols.typ",
        "text": '#import "symbols/shape.typ": shape\n#let style = red\n',
    },
    {
        "path": "docs/shared/symbols/shape.typ",
        "text": "#let shape = (\n  Nq: 4,\n)\n",
    },
    {
        "path": "docs/shared/equations/scene.typ",
        "text": "#let scene = (\n  memory: 1,\n)\n",
    },
    {
        "path": "docs/shared/glossary.typ",
        "text": '#let entries = (\n  (\n    key: "next-best-view",\n  ),\n)\n',
    },
    {
        "path": "docs/papers/paper.tex",
        "text": (
            "\\input{section}\n\\section{Method}\\label{sec:method}\n"
            "\\subsubsection{Details}\n"
        ),
    },
    {
        "path": "docs/papers/section.tex",
        "text": "Plain TeX source.\n",
    },
    {
        "path": "docs/refs.bib",
        "text": "@article{Paper-Key,\n  eprint={2501.00001},\n}\n",
    },
    {
        "path": "docs/main.typ",
        "text": (
            '#include "shared/symbols.typ"\n'
            '#import "shared/equations/scene.typ": scene\n'
            'appendix: [#include "plain.typ"]\n'
            '= Main\n#let metadata = "x"\n'
            '#thesis_status(\n  [Body],\n  implementation: "planned",\n'
            '  evidence: "pending",\n'
            '  source: "aria_nbv/aria_nbv/rollouts/zarr_store.py",\n'
            '  gate: "G-1",\n)\n'
            "#symb.shape.Nq #eqs.scene.memory @Paper-Key @next-best-view\n"
            "`aria_nbv.vin.Model`\n"
            '#gh("aria_nbv/aria_nbv/viewer.py", body: [`Viewer.render`], '
            "line: 11, end: 13)\n"
            '#gh-wip("aria_nbv/aria_nbv/rollouts/zarr_store.py", '
            "body: [`RolloutZarrStoreReader.q_h_view`], line: 1, end: 2)\n"
            '#gh-symbol("aria_nbv/aria_nbv/vin.py", "Model.predict", line: 1)\n'
            '#gh-symbol-search("aria_nbv.vin.Model.predict")\n'
            '#gh("docs/plain.typ", line: 4)\n'
            '#gh-wip("scripts/tests/test_graphify_bridge.py", line: 1, end: 2)\n'
            '#gh("docs/papers/paper.tex", line: 2)\n'
            '#gh-symbol("aria_nbv/aria_nbv/viewer.py", "Viewer", line: 1)\n'
            '#gh("aria_nbv/aria_nbv/viewer.py")\n'
        ),
    },
    {"path": "docs/plain.typ", "text": "Plain Typst source.\n"},
]


def _materialize(root: Path):
    return materialize(
        SOURCES,
        root,
        paper_by_arxiv={"2501.00001": "docs/papers/paper.tex"},
        source_paths=[
            *(source["path"] for source in SOURCES),
            "scripts/tests/test_graphify_bridge.py",
        ],
    )


def test_mapping_determinism_and_supported_constructs(tmp_path: Path) -> None:
    first = _materialize(tmp_path / "first")
    second = _materialize(tmp_path / "second")
    assert [path.relative_to(tmp_path / "first") for path in first.output_paths] == [
        Path("docs/main.py"),
        Path("docs/papers/paper.py"),
        Path("docs/papers/section.py"),
        Path("docs/plain.py"),
        Path("docs/refs.py"),
        Path("docs/shared/equations/scene.py"),
        Path("docs/shared/glossary.py"),
        Path("docs/shared/symbols.py"),
        Path("docs/shared/symbols/shape.py"),
    ]
    for left, right in zip(first.output_paths, second.output_paths):
        assert left.read_text() == right.read_text()
        left_map = first.line_map[left]
        right_map = second.line_map[right]
        assert left_map == right_map
        assert set(left_map) == set(range(1, len(left.read_text().splitlines()) + 1))
    main = first.output_paths[0].read_text()
    assert "marker_implementation" in main
    assert "marker_evidence" in main
    assert "marker_source" in main
    assert "marker_gate" in main
    assert "from .refs import citation_Paper_Key" in main
    assert "import aria_nbv.aria_nbv.rollouts.zarr_store" in main
    assert "from aria_nbv.aria_nbv.vin import Model" in main
    assert "from aria_nbv.aria_nbv.viewer import Viewer" in main
    assert "RolloutZarrStoreReader.q_h_view()" in main
    assert "Viewer.render()" in main
    assert "Model.predict()" in main
    assert "Viewer()" in main
    assert "source_file_aria_nbv_aria_nbv_viewer()" in main
    assert "github_reference_L15" in main
    assert "github_reference_L16" in main
    assert "github_reference_L17" in main
    assert "github_symbol_search_L18" in main
    assert "github_reference_L19" in main
    assert "github_reference_L20" in main
    assert "github_reference_L21" in main
    assert "github_reference_L22" in main
    assert "github_reference_L23" in main
    assert "gh_11_13_aria_nbv" in main
    assert "gh_wip_1_2_aria_nbv" in main
    assert "gh_4_docs_plain_typ" in main
    assert "gh_wip_1_2_scripts_tests" in main
    assert "from .plain import source_plain" in main
    assert "from .papers.paper import source_paper" in main
    assert (
        "from scripts.tests.test_graphify_bridge import "
        "source_file_scripts_tests_test_graphify_bridge" in main
    )
    assert "def let_L5" in main
    paper = first.output_paths[1].read_text()
    assert "subsubsection" in paper and "label" in paper
    assert "paper_arxiv__2501_00001" in paper
    plain_path = tmp_path / "first/docs/plain.py"
    assert plain_path.read_text() == "def source_plain():\n    pass\n"
    assert first.line_map[plain_path] == {
        1: ("docs/plain.typ", 1),
        2: ("docs/plain.typ", 1),
    }


def test_exact_generated_line_mapping(tmp_path: Path) -> None:
    result = materialize([{"path": "chapter.typ", "text": "= Heading\n"}], tmp_path)
    output = tmp_path / "chapter.py"
    assert output.read_text().splitlines() == [
        "def source_chapter():",
        "    pass",
        "def heading_1_L1_1_Heading_a3089b7f(): pass",
    ]
    assert result.line_map[output] == {
        1: ("chapter.typ", 1),
        2: ("chapter.typ", 1),
        3: ("chapter.typ", 1),
    }


def test_upstream_ast_extracts_distinct_nodes_and_edges(tmp_path: Path) -> None:
    if shutil.which("graphify") is None:
        pytest.skip("graphify CLI is unavailable")
    root = tmp_path / "corpus"
    _materialize(root)
    code = root / "aria_nbv/aria_nbv/rollouts/zarr_store.py"
    code.parent.mkdir(parents=True)
    code.write_text(
        "class RolloutZarrStoreReader:\n    def q_h_view(self):\n        pass\n",
        encoding="utf-8",
    )
    viewer = root / "aria_nbv/aria_nbv/viewer.py"
    viewer.write_text(
        "class Viewer:\n    def render(self):\n        pass\n\n"
        "def source_file_aria_nbv_aria_nbv_viewer():\n    pass\n",
        encoding="utf-8",
    )
    dotted = root / "aria_nbv/aria_nbv/vin.py"
    dotted.write_text(
        "class Model:\n    def predict(self):\n        pass\n", encoding="utf-8"
    )
    test_target = root / "scripts/tests/test_graphify_bridge.py"
    test_target.parent.mkdir(parents=True)
    test_target.write_text(
        "def target():\n    pass\n\n"
        "def source_file_scripts_tests_test_graphify_bridge():\n    pass\n",
        encoding="utf-8",
    )
    out = tmp_path / "extract"
    subprocess.run(
        [
            "graphify",
            "extract",
            ".",
            "--code-only",
            "--no-cluster",
            "--no-gitignore",
            "--out",
            str(out),
        ],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    graph = json.loads((out / "graphify-out/graph.json").read_text())
    nodes = graph["nodes"]
    assert len({node["id"] for node in nodes}) == len(nodes)
    labels = {node["id"]: node["label"] for node in nodes}
    marker_ids = {
        node_id for node_id, label in labels.items() if label.startswith("marker_")
    }
    assert len(marker_ids) == 5
    call_edges = [edge for edge in graph["edges"] if edge["relation"] == "calls"]
    assert len([edge for edge in call_edges if edge["source"] in marker_ids]) == 4
    assert any(
        "paper_arxiv__2501_00001" in labels.get(edge["target"], "")
        for edge in call_edges
    )
    imports = [
        edge
        for edge in graph["edges"]
        if edge["relation"] in {"imports", "imports_from"}
    ]
    assert any("zarr_store" in edge["target"] for edge in imports)
    for target in (
        "citation_Paper_Key",
        "symb_shape_Nq",
        "eqs_scene_memory",
        "term_next_best_view",
        "Model",
        "Viewer",
    ):
        assert any(target in labels.get(edge["target"], "") for edge in imports)
    assert any(
        edge["source"].endswith("docs_main")
        and edge["target"].endswith("docs_shared_symbols")
        for edge in imports
    )
    assert any(
        edge["source"].endswith("docs_main") and edge["target"].endswith("docs_plain")
        for edge in imports
    )
    assert any(
        edge["source"].endswith("docs_papers_paper")
        and edge["target"].endswith("docs_papers_section")
        for edge in imports
    )
    assert any(
        "source_main" in labels.get(edge["source"], "")
        and "q_h_view" in labels.get(edge["target"], "")
        for edge in call_edges
    )
    assert any(
        "github_reference" in labels.get(edge["source"], "")
        and "render" in labels.get(edge["target"], "")
        for edge in call_edges
    )
    assert any(
        "github_reference" in labels.get(edge["source"], "")
        and "predict" in labels.get(edge["target"], "")
        for edge in call_edges
    )
    assert any("github_symbol_search" in label for label in labels.values())
    assert any(
        "github_reference" in labels.get(edge["source"], "")
        and "Viewer" in labels.get(edge["target"], "")
        for edge in call_edges
    )
    assert any(
        "github_reference" in labels.get(edge["source"], "")
        and "source_file_aria_nbv_aria_nbv_viewer" in labels.get(edge["target"], "")
        for edge in call_edges
    )
    assert any(
        "github_reference" in label and "docs_plain_typ" in label
        for label in labels.values()
    )
    assert any(
        "github_reference" in label and "scripts_tests" in label
        for label in labels.values()
    )
    assert any(
        "source_main" in labels.get(edge["source"], "")
        and "source_plain" in labels.get(edge["target"], "")
        for edge in call_edges
    )
    assert any(
        "source_main" in labels.get(edge["source"], "")
        and "source_paper" in labels.get(edge["target"], "")
        for edge in call_edges
    )
    assert any(
        edge["source"].endswith("docs_main")
        and edge["target"].endswith("scripts_tests_test_graphify_bridge")
        for edge in imports
    )
    assert not any(
        labels[node_id].startswith(("symb_use_", "eqs_use_", "code_reference_"))
        for node_id in labels
    )


@pytest.mark.parametrize(
    ("sources", "message"),
    [
        ([{"path": "bad.md", "text": "# title"}], "unsupported source suffix"),
        (
            [{"path": "main.typ", "text": '#include "missing.typ"'}],
            "unresolved relative include",
        ),
        ([{"path": "same.typ", "text": "#let x = 1"}] * 2, "duplicate source path"),
        ([{"path": "empty.typ", "text": "   \n"}], "empty conversion"),
        ([], "empty conversion"),
    ],
)
def test_failures(tmp_path: Path, sources: list[dict[str, str]], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        materialize(sources, tmp_path)


def test_unresolved_paper_mapping_fails(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unresolved paper module"):
        materialize(
            [{"path": "refs.bib", "text": "@article{A, eprint={1}}"}],
            tmp_path,
            paper_by_arxiv={"1": "missing.tex"},
        )
