from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

import graphify_adapter as adapter  # noqa: E402

CONFIG = """schema_version = "aria-graph-v2"
graphify_package = "graphifyy"
graphify_version = "0.9.22"
graphify_upstream_commit = "abff1b1ca4052fcf9d955c5f6a034088723f4536"
canonical_artifacts = ["graphify-out/graph.json", "graphify-out/manifest.json", "graphify-out/GRAPH_REPORT.md"]

[partition.code]
semantic_mode = "structural"
patterns = ["aria_nbv/aria_nbv/**"]
[partition.thesis]
semantic_mode = "reviewed-source-reference"
patterns = ["docs/typst/thesis/**", "docs/typst/shared/**"]
[partition.literature]
semantic_mode = "reviewed-source-reference"
patterns = ["docs/literature/sources.jsonl", "docs/literature/tex-src/**"]
"""


def _write(root: Path, relative: str, text: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "scripts").mkdir()
    for name in ("graphify_adapter.py", "graphify_bridge.py"):
        shutil.copy2(SCRIPTS / name, root / "scripts" / name)
    _write(root, ".graphify.toml", CONFIG)
    _write(root, "aria_nbv/aria_nbv/__init__.py", "")
    _write(root, "aria_nbv/aria_nbv/model.py", "# model\nclass Model:\n    pass\n")
    _write(root, "aria_nbv/tests/test_no.py", "assert True\n")
    _write(root, "docs/typst/shared/symbols.typ", "#let symbol = 1\n")
    _write(
        root,
        "docs/typst/shared/glossary.typ",
        '#let entries = (\n  (key: "term-a", short: "A"),\n'
        '  (key: "term-b", short: "B"),\n)\n',
    )
    _write(
        root,
        "docs/typst/thesis/glossary-overrides.typ",
        '#import "../shared/glossary.typ": entries\n'
        '#let override = (\n  key: "term-a",\n'
        '  custom: (label: "One", nested: (label: "Two")),\n'
        '  short: "Override",\n)\n',
    )
    _write(
        root,
        "docs/typst/thesis/main.typ",
        '#import "../shared/symbols.typ": symbol\n'
        '#import "glossary-overrides.typ": override\n= Thesis\n',
    )
    _write(
        root,
        "docs/literature/sources.jsonl",
        '{"arxiv_id":"1234.5678","tex_dir":"paper-a"}\n',
    )
    _write(
        root,
        "docs/literature/tex-src/paper-a/main.tex",
        "% \\input{commented-missing}\n\\input{active-missing}\n\\input{section}\n",
    )
    _write(root, "docs/literature/tex-src/paper-a/section.tex", "\\section{Method}\n")
    _write(root, "docs/literature/tex-src/not-selected/main.tex", "\\section{No}\n")
    _write(root, "scripts/ignored.py", "BROKEN = True\n")
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.invalid"],
        cwd=root,
        check=True,
    )
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "fixture"], cwd=root, check=True)
    return root


def _require_graphify() -> None:
    if shutil.which("graphify") is None:
        pytest.skip("real Graphify CLI is unavailable")


def _generate(repo: Path) -> dict[str, bytes]:
    _require_graphify()
    return adapter.generate(repo, ["graphify"])


def test_collection_selection_and_source_attributes(repo: Path) -> None:
    config = adapter.load_config(repo)
    assert adapter.selected_literature_dirs(repo) == {"paper-a"}
    sources = adapter.collect_sources(repo, config)
    paths = {source.path for source in sources}
    assert "aria_nbv/aria_nbv/model.py" in paths
    assert "docs/typst/thesis/main.typ" in paths
    assert "docs/literature/sources.jsonl" in paths
    assert "docs/literature/tex-src/paper-a/main.tex" in paths
    assert "docs/literature/tex-src/not-selected/main.tex" not in paths
    assert "aria_nbv/tests/test_no.py" not in paths
    assert "scripts/ignored.py" not in paths
    assert {source.family for source in sources} == set(adapter.FAMILIES)
    assert all(len(source.sha256) == 64 for source in sources)


def test_real_generation_is_deterministic_native_and_exact(repo: Path) -> None:
    first = _generate(repo)
    second = _generate(repo)
    assert first == second
    assert set(first) == {"graph.json", "manifest.json", "GRAPH_REPORT.md"}
    graph = json.loads(first["graph.json"])
    manifest = json.loads(first["manifest.json"])
    assert set(graph) == adapter.UPSTREAM_KEYS
    assert "edges" not in graph
    assert manifest["node_count"] == len(graph["nodes"])
    assert manifest["link_count"] == len(graph["links"])
    assert manifest["graphify_version"] == "0.9.22"
    assert manifest["adapter_schema_version"] == 1
    assert manifest["adapter_sha256"] == adapter._adapter_digest(repo)
    assert graph["built_at_commit"] == manifest["built_source_commit"]
    assert (
        f"- Built from commit: `{manifest['built_source_commit']}`".encode()
        in first["GRAPH_REPORT.md"]
    )
    assert set(manifest) == {
        "adapter_sha256",
        "adapter_schema_version",
        "built_source_commit",
        "config_sha256",
        "graphify_version",
        "link_count",
        "node_count",
        "source_digest",
        "sources",
    }
    assert [node["id"] for node in graph["nodes"]] == sorted(
        node["id"] for node in graph["nodes"]
    )
    assert graph["links"] == sorted(
        graph["links"],
        key=lambda link: (link["source"], link["target"], link["relation"]),
    )
    model = next(node for node in graph["nodes"] if node["label"] == "Model")
    thesis = next(
        node for node in graph["nodes"] if node["label"].startswith("heading_1")
    )
    assert (model["source_file"], model["source_location"]) == (
        "aria_nbv/aria_nbv/model.py",
        "L2",
    )
    assert (thesis["source_file"], thesis["source_location"]) == (
        "docs/typst/thesis/main.typ",
        "L3",
    )
    assert any(node["label"].endswith("main.typ") for node in graph["nodes"])
    assert any(node["label"].endswith("main.tex") for node in graph["nodes"])
    adapter.validate(first, root=repo)


def test_real_generation_covers_three_families_and_normalizes_report(
    repo: Path,
) -> None:
    artifacts = _generate(repo)
    graph = json.loads(artifacts["graph.json"])
    manifest = json.loads(artifacts["manifest.json"])
    family_by_path = {
        source["path"]: source["family"] for source in manifest["sources"]
    }
    assert {family_by_path[node["source_file"]] for node in graph["nodes"]} == set(
        adapter.FAMILIES
    )
    report = artifacts["GRAPH_REPORT.md"]
    assert report.startswith(b"# Graph Report - ARIA-NBV\n\n## Corpus Check\n")
    assert b"cluster-only mode" in report
    assert str(repo).encode() not in report
    assert b"aria_nbv/model.py" not in report
    assert b"docs/typst/thesis/main.py" not in report
    assert b"docs/literature/tex-src/paper-a/main.py" not in report
    assert b"## Graph Freshness\n" in report
    assert b"## Suggested Questions\n" in report

    broken_graph = dict(graph)
    broken_graph["nodes"] = [
        node
        for node in graph["nodes"]
        if family_by_path[node["source_file"]] != "literature"
    ]
    broken_graph["links"] = [
        link
        for link in graph["links"]
        if family_by_path[link["source_file"]] != "literature"
    ]
    broken_manifest = dict(manifest)
    broken_manifest["node_count"] = len(broken_graph["nodes"])
    broken_manifest["link_count"] = len(broken_graph["links"])
    broken = dict(artifacts)
    broken["graph.json"] = adapter._json_bytes(broken_graph)
    broken["manifest.json"] = adapter._json_bytes(broken_manifest)
    with pytest.raises(
        adapter.AdapterError, match="at least one node from each family"
    ):
        adapter.validate(broken, repo)


def test_empty_code_module_file_node_maps_to_authoritative_path(repo: Path) -> None:
    artifacts = _generate(repo)
    graph = json.loads(artifacts["graph.json"])
    module = next(
        node
        for node in graph["nodes"]
        if node["source_file"] == "aria_nbv/aria_nbv/__init__.py"
    )
    assert module["source_location"] == "L1"
    assert module["label"] == "__init__.py"


def test_freshness_changes_for_each_family_and_config(repo: Path) -> None:
    artifacts = _generate(repo)
    adapter._write(artifacts, repo)
    assert adapter.is_fresh(repo)
    for relative in (
        "aria_nbv/aria_nbv/model.py",
        "docs/typst/thesis/main.typ",
        "docs/literature/tex-src/paper-a/main.tex",
    ):
        target = repo / relative
        original = target.read_text()
        target.write_text(original + "\n", encoding="utf-8")
        assert not adapter.is_fresh(repo)
        target.write_text(original, encoding="utf-8")
        assert adapter.is_fresh(repo)
    config = repo / ".graphify.toml"
    config.write_text(config.read_text() + '\n[history]\nactivation_commit = "abc"\n')
    assert not adapter.is_fresh(repo)


@pytest.mark.parametrize("name", ("graphify_adapter.py", "graphify_bridge.py"))
def test_implementation_digest_drift_is_stale(repo: Path, name: str) -> None:
    artifacts = _generate(repo)
    adapter._write(artifacts, repo)
    assert adapter.is_fresh(repo)
    implementation = repo / "scripts" / name
    implementation.write_bytes(implementation.read_bytes() + b"\n# parser drift\n")
    assert not adapter.is_fresh(repo)
    with pytest.raises(adapter.AdapterError, match="manifest does not match"):
        adapter.validate(artifacts, repo)


def test_graph_only_child_keeps_generation_identical_and_fresh(repo: Path) -> None:
    source_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repo, text=True
    ).strip()
    artifacts = _generate(repo)
    adapter._write(artifacts, repo)
    subprocess.run(["git", "add", "graphify-out"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "graph-only child"], cwd=repo, check=True)
    assert (
        subprocess.check_output(
            ["git", "rev-parse", "HEAD^"], cwd=repo, text=True
        ).strip()
        == source_commit
    )
    assert _generate(repo) == artifacts
    assert adapter.is_fresh(repo)


def test_manifest_records_exact_selected_sources(repo: Path) -> None:
    manifest = json.loads(_generate(repo)["manifest.json"])
    assert manifest["sources"] == [
        {"family": source.family, "path": source.path, "sha256": source.sha256}
        for source in adapter.collect_sources(repo)
    ]
    assert not any(
        source["path"].startswith("docs/literature/tex-src/not-selected/")
        for source in manifest["sources"]
    )
    assert (
        manifest["built_source_commit"]
        == subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo, text=True
        ).strip()
    )


def test_unmapped_and_zero_family_fail_closed(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    graph = {
        "built_at_commit": "x",
        "directed": False,
        "graph": {},
        "hyperedges": [],
        "links": [],
        "multigraph": False,
        "nodes": [
            {
                "id": "x",
                "label": "x",
                "source_file": "missing.py",
                "source_location": "L1",
            }
        ],
    }
    with pytest.raises(adapter.AdapterError, match="unmapped upstream source"):
        adapter._rewrite_graph(graph, {}, "0" * 40, Path("/tmp/materialized"))
    monkeypatch.setattr(
        adapter,
        "collect_sources",
        lambda root, config=None: [
            adapter.Source("aria_nbv/aria_nbv/model.py", "code", "0" * 64, "pass\n")
        ],
    )
    monkeypatch.setattr(adapter, "ensure_graphify_pin", lambda command, root: None)
    with pytest.raises(
        adapter.AdapterError, match="nonempty code, thesis, and literature"
    ):
        adapter.generate(repo, ["graphify"])


def test_manifest_uses_main_or_first_tex(repo: Path) -> None:
    sources = adapter.collect_sources(repo)
    manifest = next(
        source for source in sources if source.path == "docs/literature/sources.jsonl"
    )
    assert adapter._paper_map(manifest, sources) == {
        "1234.5678": "docs/literature/tex-src/paper-a/main.tex"
    }
    (repo / "docs/literature/tex-src/paper-a/main.tex").unlink()
    sources = adapter.collect_sources(repo)
    manifest = next(
        source for source in sources if source.path == "docs/literature/sources.jsonl"
    )
    assert adapter._paper_map(manifest, sources) == {
        "1234.5678": "docs/literature/tex-src/paper-a/section.tex"
    }


def test_pin_and_command_are_public(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GRAPHIFY_COMMAND", "graphify")
    assert adapter.graphify_command() == ["graphify"]
    adapter.ensure_graphify_pin(["graphify"], repo)
    config = repo / ".graphify.toml"
    config.write_text(
        config.read_text().replace(
            'graphify_version = "0.9.22"', 'graphify_version = "0.0.0"'
        )
    )
    with pytest.raises(adapter.AdapterError, match="does not match pin 0.0.0"):
        adapter.ensure_graphify_pin(["graphify"], repo)
