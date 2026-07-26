"""Deterministic temporary-repository tests for Graphify S-to-G history."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

import check_graphify_history as history  # noqa: E402
import graphify_adapter as adapter  # noqa: E402

CONFIG = """schema_version = "aria-graph-v2"
graphify_package = "graphifyy"
graphify_version = "0.9.22"
graphify_upstream_commit = "test"
canonical_artifacts = ["graphify-out/graph.json", "graphify-out/manifest.json", "graphify-out/GRAPH_REPORT.md"]
[history]
activation_commit = "0000000000000000000000000000000000000000"
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


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


def _commit(root: Path, message: str) -> str:
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", message], cwd=root, check=True)
    return _git(root, "rev-parse", "HEAD")


def _repo() -> tuple[tempfile.TemporaryDirectory[str], Path, str]:
    temporary = tempfile.TemporaryDirectory()
    root = Path(temporary.name)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(
        ["git", "config", "user.email", "graph@example.invalid"], cwd=root, check=True
    )
    subprocess.run(["git", "config", "user.name", "graph-test"], cwd=root, check=True)
    for name in ("graphify_adapter.py", "graphify_bridge.py"):
        target = root / "scripts" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(SCRIPTS / name, target)
    _write(root, ".graphify.toml", CONFIG)
    _write(root, "aria_nbv/aria_nbv/model.py", "VALUE = 1\n")
    _write(root, "docs/typst/thesis/main.typ", "= Thesis\n")
    _write(
        root,
        "docs/literature/sources.jsonl",
        '{"arxiv_id":"1234.5678","tex_dir":"paper-a"}\n',
    )
    _write(root, "docs/literature/tex-src/paper-a/main.tex", "\\section{Paper}\n")
    return temporary, root, _commit(root, "base")


def _artifacts(root: Path, source_commit: str) -> dict[str, bytes]:
    sources = adapter.collect_sources(root)
    nodes = [
        {
            "id": family,
            "label": family,
            "norm_label": family,
            "source_file": next(
                source.path for source in sources if source.family == family
            ),
            "source_location": "L1",
        }
        for family in adapter.FAMILIES
    ]
    graph = {
        "built_at_commit": source_commit,
        "directed": False,
        "graph": {},
        "hyperedges": [],
        "links": [],
        "multigraph": False,
        "nodes": nodes,
    }
    manifest = adapter._manifest(root, sources, graph, source_commit)
    return {
        "graph.json": adapter._json_bytes(graph),
        "manifest.json": adapter._json_bytes(manifest),
        "GRAPH_REPORT.md": f"# Graph Report - ARIA-NBV\n\n- Built from commit: `{source_commit}`\n".encode(),
    }


def _graph_commit(
    root: Path,
    source_commit: str,
    *,
    manifest_change: tuple[str, str] | None = None,
    omit: str | None = None,
    extra: bool = False,
) -> str:
    artifacts = _artifacts(root, source_commit)
    if manifest_change:
        manifest = json.loads(artifacts["manifest.json"])
        manifest[manifest_change[0]] = manifest_change[1]
        artifacts["manifest.json"] = adapter._json_bytes(manifest)
    out = root / "graphify-out"
    out.mkdir(exist_ok=True)
    for name, content in artifacts.items():
        if name != omit:
            (out / name).write_bytes(content)
    if extra:
        (out / "extra.json").write_text("{}\n", encoding="utf-8")
    return _commit(root, "graph sync")


def _change(root: Path, relative: str, text: str) -> str:
    _write(root, relative, text)
    return _commit(root, f"change {relative}")


def _assert_error(errors: list[str], fragment: str) -> None:
    assert any(fragment in error for error in errors), errors


def test_classification_and_valid_pairs() -> None:
    cases = (
        ("aria_nbv/aria_nbv/model.py", "VALUE = 2\n"),
        ("docs/typst/thesis/main.typ", "= Changed\n"),
        (
            "docs/literature/sources.jsonl",
            '{"arxiv_id":"1234.5678","tex_dir":"paper-a"}\n\n',
        ),
        ("docs/literature/tex-src/paper-a/main.tex", "\\section{Changed}\n"),
        (
            "scripts/graphify_adapter.py",
            (SCRIPTS / "graphify_adapter.py").read_text() + "\n# changed\n",
        ),
        (".graphify.toml", CONFIG + "\n# changed\n"),
    )
    for path, text in cases:
        temporary, root, _ = _repo()
        with temporary:
            source = _change(root, path, text)
            assert history._corpus_commit(root, source)
            graph = _graph_commit(root, source)
            assert not history.validate_authoring_history(root, [source, graph])

    temporary, root, _ = _repo()
    with temporary:
        operator = _change(root, "AGENTS.md", "operator only\n")
        assert not history._corpus_commit(root, operator)
        assert not history.validate_authoring_history(root, [operator])


def test_pair_failures() -> None:
    temporary, root, _ = _repo()
    with temporary:
        source = _change(root, "aria_nbv/aria_nbv/model.py", "VALUE = 2\n")
        _assert_error(
            history.validate_authoring_history(root, [source]), "missing immediate"
        )

        _write(root, "graphify-out/manifest.json", "{}\n")
        mixed = _change(root, "aria_nbv/aria_nbv/model.py", "VALUE = 3\n")
        _assert_error(history.validate_authoring_history(root, [mixed]), "mixed source")

    for kwargs in ({"omit": "GRAPH_REPORT.md"}, {"extra": True}):
        temporary, root, _ = _repo()
        with temporary:
            source = _change(root, "aria_nbv/aria_nbv/model.py", "VALUE = 2\n")
            graph = _graph_commit(root, source, **kwargs)
            _assert_error(
                history.validate_authoring_history(root, [source, graph]),
                "artifact set",
            )

    for key in (
        "built_source_commit",
        "source_digest",
        "config_sha256",
        "adapter_sha256",
    ):
        temporary, root, _ = _repo()
        with temporary:
            source = _change(root, "aria_nbv/aria_nbv/model.py", "VALUE = 2\n")
            graph = _graph_commit(root, source, manifest_change=(key, "wrong"))
            _assert_error(
                history.validate_authoring_history(root, [source, graph]), key
            )

    temporary, root, _ = _repo()
    with temporary:
        source = _change(root, "aria_nbv/aria_nbv/model.py", "VALUE = 2\n")
        delay = _change(root, "notes.txt", "delay\n")
        graph = _graph_commit(root, source)
        errors = history.validate_authoring_history(root, [source, delay, graph])
        _assert_error(errors, "artifact set")
        _assert_error(
            history.validate_authoring_history(root, [source, graph]),
            "single-parent child",
        )


def test_merge_follow_up_and_final_tree() -> None:
    temporary, root, _ = _repo()
    with temporary:
        branch = _git(root, "branch", "--show-current")
        subprocess.run(["git", "checkout", "-qb", "corpus"], cwd=root, check=True)
        _change(root, "aria_nbv/aria_nbv/model.py", "VALUE = 2\n")
        subprocess.run(["git", "checkout", "-q", branch], cwd=root, check=True)
        _change(root, "notes.txt", "main divergence\n")
        subprocess.run(
            ["git", "merge", "--no-ff", "-qm", "merge corpus", "corpus"],
            cwd=root,
            check=True,
        )
        merge = _git(root, "rev-parse", "HEAD")
        assert history._corpus_commit(root, merge)
        _assert_error(
            history.validate_authoring_history(root, [merge]), "missing immediate"
        )
        graph = _graph_commit(root, merge)
        assert not history.validate_authoring_history(root, [merge, graph])
        assert not history.validate_final_tree(root)
        _write(root, "aria_nbv/aria_nbv/model.py", "STALE = True\n")
        _assert_error(history.validate_final_tree(root), "stale or invalid")


def test_activation_range_after_squash() -> None:
    temporary, root, base = _repo()
    with temporary:
        anchor = _graph_commit(root, base)
        source = _change(root, "aria_nbv/aria_nbv/model.py", "VALUE = 2\n")
        graph = _graph_commit(root, source)
        authoring_range, errors = history.activation_authoring_range(root, "0" * 40)
        assert authoring_range == f"{anchor}..HEAD"
        assert not errors
        revisions = _git(
            root, "rev-list", "--reverse", "--first-parent", authoring_range
        ).splitlines()
        assert revisions == [source, graph]


def main() -> None:
    test_classification_and_valid_pairs()
    test_pair_failures()
    test_merge_follow_up_and_final_tree()
    test_activation_range_after_squash()


if __name__ == "__main__":
    main()
