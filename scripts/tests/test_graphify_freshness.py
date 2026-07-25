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
from typing import Any, Callable

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

import check_graphify_freshness as freshness  # noqa: E402
import graphify_contract as contract  # noqa: E402
import graphify_refresh as refresh  # noqa: E402


def _write_fixture(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    shutil.copy(contract.ROOT / ".graphify.toml", root / ".graphify.toml")
    shutil.copy(contract.ROOT / ".graphifyignore", root / ".graphifyignore")
    files = {
        "AGENTS.md": "Operator guidance.\n",
        "docs/typst/thesis/main.typ": '#include "../shared/math.typ"\n',
        "docs/typst/shared/math.typ": "#let value = 1\n",
        "docs/literature/sources.jsonl": "{}\n",
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
    config_sha256 = contract.config_digest(config, root)
    graphify = {
        "package": config["graphify_package"],
        "version": config["graphify_version"],
        "upstream_commit": config["graphify_upstream_commit"],
    }
    partitions = {}
    for name in contract.PARTITION_ORDER:
        selected = [source for source in sources if source["partition"] == name]
        source_digest = contract.source_manifest_digest(selected)
        semantic_digest = contract._semantic_digest([], name)
        semantic_mode = config["partition"][name]["semantic_mode"]
        partitions[name] = {
            "source_manifest_sha256": source_digest,
            "accepted_semantic_records_sha256": semantic_digest,
            "semantic_mode": semantic_mode,
            "semantic_complete": True,
            "revision": contract._partition_revision(
                manifest_digest=source_digest,
                config_sha256=config_sha256,
                schema_version=config["schema_version"],
                semantic_mode=semantic_mode,
                accepted_semantic_digest=semantic_digest,
                graphify_version=config["graphify_version"],
            ),
        }
    thesis = next(
        source for source in sources if source["path"] == "docs/typst/thesis/main.typ"
    )
    nodes = [
        {
            "id": contract._file_node_id(source["path"]),
            "label": Path(source["path"]).name,
            "source_file": source["path"],
            "source_digest": source["sha256"],
            "partition": source["partition"],
            "role": source["role"],
            "partition_revision": partitions[source["partition"]]["revision"],
        }
        for source in sources
    ]
    nodes_by_id = {node["id"]: node for node in nodes}
    source_id = contract._file_node_id("docs/typst/thesis/main.typ")
    target_id = contract._file_node_id("docs/literature/sources.jsonl")
    edge = {
        "id": "bridge",
        "source": source_id,
        "target": target_id,
        "origin": "INFERRED",
        "confidence_score": 0.9,
        "source_locators": [
            {
                "path": "docs/typst/thesis/main.typ",
                "locator": "L1",
                "sha256": thesis["sha256"],
            }
        ],
        "bridge_partition_revisions": {
            "thesis": partitions["thesis"]["revision"],
            "literature": partitions["literature"]["revision"],
        },
        "endpoint_provenance": {
            "source": contract._endpoint_provenance(nodes_by_id[source_id]),
            "target": contract._endpoint_provenance(nodes_by_id[target_id]),
        },
        "partition": "thesis",
        "partition_revision": partitions["thesis"]["revision"],
        "extraction_config_sha256": config_sha256,
        "graphify_version": config["graphify_version"],
    }
    tree = contract.corpus_tree_digest(sources)
    graph = {
        "schema_version": config["schema_version"],
        "corpus_tree_sha256": tree,
        "extraction_config_sha256": config_sha256,
        "graphify": graphify,
        "partitions": partitions,
        "nodes": nodes,
        "edges": [edge],
    }
    manifest = {
        "schema_version": config["schema_version"],
        "extraction_config_sha256": config_sha256,
        "graphify": graphify,
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

        original_upstream_extract = contract._upstream_extract
        try:

            def fake_upstream_extract(
                root: Path,
                graphify_command: list[str],
                temporary_root: Path,
            ) -> dict[str, Any]:
                return {"nodes": [], "edges": []}

            contract._upstream_extract = fake_upstream_extract
            rebuilt, rebuilt_manifest, _ = contract.build_canonical(
                root=root,
                semantic_incomplete={"literature"},
            )
            assert not rebuilt["partitions"]["literature"]["semantic_complete"]
            assert rebuilt["partitions"]["code"]["semantic_complete"]
            assert not contract.validate_graph(rebuilt, rebuilt_manifest)
            _, _, mixed_report = contract.build_canonical(
                root=root,
                semantic_incomplete={"literature", "thesis"},
            )
            report_rows = {
                line.split("|")[1].strip(): line
                for line in mixed_report.splitlines()
                if line.startswith("| ")
                and line.split("|")[1].strip() in contract.PARTITION_ORDER
            }
            report_status = {
                name: row.split("|")[3].strip() for name, row in report_rows.items()
            }
            assert report_status == {
                "code": "yes",
                "thesis": "no",
                "literature": "no",
            }
        finally:
            contract._upstream_extract = original_upstream_extract

        pending = root / "graphify-out/pending.json"
        assert refresh._pending(pending) == set()
        corruption_cases = (
            b"{",
            b"\xff",
            b"[]",
            b'{"partitions": "thesis"}',
            b'{"partitions": ["thesis", "thesis"]}',
            b'{"partitions": ["unknown"]}',
            b'{"partitions": [], "unexpected": true}',
        )
        for corrupted in corruption_cases:
            pending.write_bytes(corrupted)
            try:
                refresh._write_pending({"literature"}, pending)
            except contract.ContractError:
                pass
            else:
                raise AssertionError("corrupt pending state must fail closed")
            assert pending.read_bytes() == corrupted
        pending.unlink()
        pending.mkdir()
        try:
            refresh._pending(pending)
        except contract.ContractError:
            pass
        else:
            raise AssertionError("unreadable pending state must fail closed")
        pending.rmdir()
        refresh._write_pending({"thesis"}, pending)
        assert refresh._pending(pending) == {"thesis"}
        valid_pending_bytes = pending.read_bytes()
        try:
            refresh._write_pending({"unknown"}, pending)
        except contract.ContractError:
            pass
        else:
            raise AssertionError("unknown pending partition must fail closed")
        assert pending.read_bytes() == valid_pending_bytes

        malformed_canonical = root / "graphify-out/graph.json"
        original_graph_bytes = malformed_canonical.read_bytes()
        malformed_canonical.write_bytes(b"{")
        try:
            contract.load_validated_canonical(root / "graphify-out", root=root)
        except contract.ContractError:
            pass
        else:
            raise AssertionError("malformed canonical graph must fail closed")
        assert malformed_canonical.read_bytes() == b"{"

        original_graphify_command = refresh.graphify_command
        original_ensure_graphify_pin = refresh.ensure_graphify_pin
        original_load_validated_canonical = refresh._load_validated_canonical
        try:

            def fake_ensure_graphify_pin(command: list[str]) -> None:
                return None

            def load_corrupt_fixture() -> tuple[dict[str, Any], dict[str, Any]]:
                return contract.load_validated_canonical(
                    malformed_canonical.parent,
                    root=malformed_canonical.parents[1],
                )

            refresh.graphify_command = lambda: ["graphify"]
            refresh.ensure_graphify_pin = fake_ensure_graphify_pin
            refresh._load_validated_canonical = load_corrupt_fixture
            try:
                refresh.run(check=False, mode="structural")
            except contract.ContractError:
                pass
            else:
                raise AssertionError(
                    "structural refresh must reject malformed canonical state"
                )
            assert malformed_canonical.read_bytes() == b"{"
        finally:
            refresh.graphify_command = original_graphify_command
            refresh.ensure_graphify_pin = original_ensure_graphify_pin
            refresh._load_validated_canonical = original_load_validated_canonical

        malformed_canonical.write_bytes(original_graph_bytes)

        schema_invalid_graph = copy.deepcopy(graph)
        schema_invalid_graph["nodes"] = []
        malformed_canonical.write_text(
            json.dumps(schema_invalid_graph), encoding="utf-8"
        )
        try:
            contract.load_validated_canonical(root / "graphify-out", root=root)
        except contract.ContractError:
            pass
        else:
            raise AssertionError("schema-invalid canonical graph must fail closed")
        assert (
            json.loads(malformed_canonical.read_text(encoding="utf-8"))["nodes"] == []
        )
        malformed_canonical.write_bytes(original_graph_bytes)

        malformed_edges: dict[str, Callable[[dict[str, Any]], object]] = {
            "missing endpoint": lambda edge: edge.pop("source"),
            "endpoint provenance": lambda edge: edge["endpoint_provenance"][
                "target"
            ].__setitem__("source_digest", "0" * 64),
            "partition revision": lambda edge: edge.__setitem__(
                "partition_revision", "wrong"
            ),
            "extraction configuration": lambda edge: edge.__setitem__(
                "extraction_config_sha256", "wrong"
            ),
            "Graphify version": lambda edge: edge.__setitem__(
                "graphify_version", "0.9.9"
            ),
            "bridge endpoint revisions": lambda edge: edge[
                "bridge_partition_revisions"
            ].pop("thesis"),
        }
        for expected_error, mutate in malformed_edges.items():
            malformed = copy.deepcopy(graph)
            mutate(malformed["edges"][0])
            assert any(
                expected_error in error
                for error in contract.validate_graph(malformed, manifest)
            )
            (root / "graphify-out/graph.json").write_text(
                json.dumps(malformed), encoding="utf-8"
            )
            state = freshness.partition_freshness(root)
            assert set(state.stale) == set(contract.PARTITION_ORDER)
        (root / "graphify-out/graph.json").write_text(
            json.dumps(graph), encoding="utf-8"
        )

        locator_mutations: list[Callable[[dict[str, Any]], object]] = [
            lambda locator: locator.pop("path"),
            lambda locator: locator.pop("locator"),
            lambda locator: locator.pop("sha256"),
            lambda locator: locator.__setitem__("path", "graphify-out/query.json"),
            lambda locator: locator.__setitem__("locator", ""),
            lambda locator: locator.__setitem__("sha256", "not-a-digest"),
            lambda locator: locator.__setitem__("sha256", "0" * 64),
        ]
        for mutate in locator_mutations:
            malformed = copy.deepcopy(graph)
            mutate(malformed["edges"][0]["source_locators"][0])
            errors = contract.validate_graph(malformed, manifest)
            assert any(
                "source locator is not exact manifest provenance" in error
                for error in errors
            )

        malformed_manifest = copy.deepcopy(manifest)
        malformed_manifest["sources"].append(
            {
                "path": "graphify-out/query.json",
                "sha256": "0" * 64,
                "partition": "code",
                "role": "guide",
            }
        )
        errors = contract.validate_graph(graph, malformed_manifest)
        assert any("unknown or outside corpus" in error for error in errors)

        wrong_version_graph = copy.deepcopy(graph)
        wrong_version_manifest = copy.deepcopy(manifest)
        wrong_version_graph["graphify"]["version"] = "0.9.9"
        wrong_version_manifest["graphify"]["version"] = "0.9.9"
        wrong_version_graph["edges"][0]["graphify_version"] = "0.9.9"
        wrong_revisions = {}
        for name, record in wrong_version_graph["partitions"].items():
            revision = contract._partition_revision(
                manifest_digest=record["source_manifest_sha256"],
                config_sha256=graph["extraction_config_sha256"],
                schema_version=graph["schema_version"],
                semantic_mode=record["semantic_mode"],
                accepted_semantic_digest=record["accepted_semantic_records_sha256"],
                graphify_version="0.9.9",
            )
            record["revision"] = revision
            wrong_version_manifest["partitions"][name]["revision"] = revision
            wrong_revisions[name] = revision
        for node in wrong_version_graph["nodes"]:
            node["partition_revision"] = wrong_revisions[node["partition"]]
        wrong_version_graph["edges"][0]["partition_revision"] = wrong_revisions[
            "thesis"
        ]
        wrong_version_graph["edges"][0]["bridge_partition_revisions"] = {
            "thesis": wrong_revisions["thesis"],
            "literature": wrong_revisions["literature"],
        }
        assert not contract.validate_graph(wrong_version_graph, wrong_version_manifest)
        (root / "graphify-out/graph.json").write_text(
            json.dumps(wrong_version_graph), encoding="utf-8"
        )
        (root / "graphify-out/manifest.json").write_text(
            json.dumps(wrong_version_manifest), encoding="utf-8"
        )
        state = freshness.partition_freshness(root)
        assert set(state.stale) == set(contract.PARTITION_ORDER)
        assert all(
            "Graphify version changed" in reasons for reasons in state.stale.values()
        )
        (root / "graphify-out/graph.json").write_text(
            json.dumps(graph), encoding="utf-8"
        )
        (root / "graphify-out/manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )

        wrong_revision_graph = copy.deepcopy(graph)
        wrong_revision_manifest = copy.deepcopy(manifest)
        wrong_revision = "f" * 64
        wrong_revision_graph["partitions"]["thesis"]["revision"] = wrong_revision
        wrong_revision_manifest["partitions"]["thesis"]["revision"] = wrong_revision
        for node in wrong_revision_graph["nodes"]:
            if node["partition"] == "thesis":
                node["partition_revision"] = wrong_revision
        wrong_revision_graph["edges"][0]["partition_revision"] = wrong_revision
        wrong_revision_graph["edges"][0]["bridge_partition_revisions"]["thesis"] = (
            wrong_revision
        )
        errors = contract.validate_graph(wrong_revision_graph, wrong_revision_manifest)
        assert "partition revision is not reproducible: thesis" in errors

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

        roles = {
            source["role"]
            for source in contract.collect_sources(root)
            if source["partition"] == "code"
        }
        assert roles == {"production"}

        thesis_path = root / "docs/typst/thesis/main.typ"
        thesis_path.write_text("#let changed = true\n", encoding="utf-8")
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

        thesis_path.write_text('#include "../shared/math.typ"\n', encoding="utf-8")
        graph["edges"][0]["bridge_partition_revisions"]["thesis"] = "wrong"
        (root / "graphify-out/graph.json").write_text(
            json.dumps(graph), encoding="utf-8"
        )
        state = freshness.partition_freshness(root)
        assert set(state.stale) == set(contract.PARTITION_ORDER)
        assert any(
            "bridge endpoint revisions differ" in reason
            for reasons in state.stale.values()
            for reason in reasons
        )

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

        calls: list[tuple[bool, str, set[str]]] = []
        original_changed_paths = refresh._changed_paths
        original_pending_partitions = refresh._pending_partitions
        original_write_pending = refresh._write_pending
        original_pending = refresh._pending
        original_run = refresh.run
        original_argv = sys.argv
        try:
            pending_partitions = {"code", "literature"}

            def fake_pending_partitions(
                changed: list[Path], root: Path = contract.ROOT
            ) -> set[str]:
                return pending_partitions

            def fake_run(
                *,
                check: bool,
                mode: str,
                semantic_incomplete: set[str] | None = None,
            ) -> list[str]:
                calls.append((check, mode, semantic_incomplete or set()))
                return []

            def fake_write_pending(
                partitions: set[str], path: Path = refresh.PENDING
            ) -> None:
                return None

            def fake_pending(path: Path = refresh.PENDING) -> set[str]:
                return {"literature"}

            refresh._changed_paths = lambda: [Path("code.py"), Path("paper.tex")]
            refresh._pending_partitions = fake_pending_partitions
            refresh._write_pending = fake_write_pending
            refresh._pending = fake_pending
            refresh.run = fake_run
            sys.argv = ["graphify_refresh.py", "--mode", "structural"]
            assert refresh.main() == 0
            assert calls == [(False, "structural", {"literature"})]

            calls.clear()
            pending_partitions = {"literature"}
            assert refresh.main() == 0
            assert not calls
        finally:
            refresh._changed_paths = original_changed_paths
            refresh._pending_partitions = original_pending_partitions
            refresh._write_pending = original_write_pending
            refresh._pending = original_pending
            refresh.run = original_run
            sys.argv = original_argv

        stale_global = root / "bin/graphify"
        stale_global.parent.mkdir()
        stale_global.write_text(
            "#!/bin/sh\nprintf 'graphify 0.9.9\\n'\n", encoding="utf-8"
        )
        stale_global.chmod(0o755)
        old_path = os.environ.get("PATH", "")
        old_override = os.environ.pop("GRAPHIFY_BIN", None)
        original_version = refresh._graphify_version
        try:
            os.environ["PATH"] = f"{stale_global.parent}:{old_path}"
            refresh._graphify_version = lambda command: "graphify 0.9.22"
            assert refresh.graphify_command() == [
                sys.executable,
                "-m",
                "graphify",
            ]
            refresh._graphify_version = lambda command: "graphify 0.9.9"
            assert refresh.graphify_command() == [str(stale_global)]
            refresh._graphify_version = lambda command: "graphify 0.9.220"
            try:
                refresh.ensure_graphify_pin([str(stale_global)])
            except contract.ContractError:
                pass
            else:
                raise AssertionError("Graphify version matching must be exact")
            os.environ["GRAPHIFY_BIN"] = f"{stale_global} --explicit"
            assert refresh.graphify_command() == [str(stale_global), "--explicit"]
        finally:
            refresh._graphify_version = original_version
            os.environ["PATH"] = old_path
            if old_override is None:
                os.environ.pop("GRAPHIFY_BIN", None)
            else:
                os.environ["GRAPHIFY_BIN"] = old_override


if __name__ == "__main__":
    main()
