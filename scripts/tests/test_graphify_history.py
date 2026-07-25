#!/usr/bin/env python3
"""Temporary-repository fixtures for Graphify S-to-G history semantics."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

import check_graphify_history as history  # noqa: E402
import graphify_contract as contract  # noqa: E402


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
    shutil.copy(contract.ROOT / ".graphify.toml", root / ".graphify.toml")
    shutil.copy(contract.ROOT / ".graphifyignore", root / ".graphifyignore")
    path = root / "aria_nbv/aria_nbv/model.py"
    path.parent.mkdir(parents=True)
    path.write_text("VALUE = 1\n", encoding="utf-8")
    base = _commit(root, "base")
    return temporary, root, base


def _graph_commit(
    root: Path,
    source_commit: str,
    *,
    digest: str | None = None,
    partitions: tuple[str, ...] = ("code",),
) -> str:
    touched_digest = digest or history._source_tree_digest_at(root, source_commit)
    out = root / "graphify-out"
    out.mkdir(exist_ok=True)
    manifest = {
        "corpus_tree_sha256": touched_digest,
        "sync": {
            "refreshed_partitions": list(partitions),
            "source_tree_sha256": touched_digest,
        },
    }
    (out / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (out / "graph.json").write_text(
        json.dumps({"corpus_tree_sha256": touched_digest}), encoding="utf-8"
    )
    (out / "GRAPH_REPORT.md").write_text("# Graph\n", encoding="utf-8")
    return _commit(root, "graph sync")


def main() -> None:
    temporary, root, _ = _repo()
    with temporary:
        squash_anchor = _graph_commit(root, _git(root, "rev-parse", "HEAD"))
        authoring_range, errors = history.activation_authoring_range(root, "0" * 40)
        assert authoring_range == f"{squash_anchor}..HEAD"
        assert not errors

        source = root / "aria_nbv/aria_nbv/model.py"
        source.write_text("VALUE = 2\n", encoding="utf-8")
        source_commit = _commit(root, "post-squash source")
        (root / "notes.txt").write_text("delay\n", encoding="utf-8")
        delayed = _commit(root, "post-squash delay")
        graph_commit = _graph_commit(root, source_commit)
        authoring_range, errors = history.activation_authoring_range(root, "0" * 40)
        assert authoring_range == f"{squash_anchor}..HEAD"
        assert not errors
        revisions = _git(
            root, "rev-list", "--reverse", "--first-parent", authoring_range
        ).splitlines()
        assert revisions == [source_commit, delayed, graph_commit]
        assert any(
            "lacks immediate" in error
            for error in history.validate_authoring_history(root, revisions)
        )

    temporary, root, base = _repo()
    with temporary:
        operator = root / "AGENTS.md"
        operator.write_text("operator only\n", encoding="utf-8")
        operator_commit = _commit(root, "operator")
        assert history._touched_partitions(root, operator_commit) == set()

        thesis = root / "docs/typst/thesis/main.typ"
        thesis.parent.mkdir(parents=True)
        thesis.write_text("#let thesis = true\n", encoding="utf-8")
        thesis_commit = _commit(root, "thesis")
        assert history._touched_partitions(root, thesis_commit) == {"thesis"}

        source = root / "aria_nbv/aria_nbv/model.py"
        source.write_text("VALUE = 2\n", encoding="utf-8")
        s = _commit(root, "source")
        g = _graph_commit(root, s)
        assert not history.validate_authoring_history(root, [s, g])

        note = root / "notes.txt"
        note.write_text("not corpus\n", encoding="utf-8")
        n = _commit(root, "non corpus")
        assert not history.validate_authoring_history(root, [s, g, n])

    temporary, root, _ = _repo()
    with temporary:
        source = root / "aria_nbv/aria_nbv/model.py"
        source.write_text("VALUE = 2\n", encoding="utf-8")
        s = _commit(root, "source")
        assert any(
            "lacks immediate" in error
            for error in history.validate_authoring_history(root, [s])
        )

        source.write_text("VALUE = 3\n", encoding="utf-8")
        t = _commit(root, "second source")
        errors = history.validate_authoring_history(root, [s, t])
        assert any("lacks immediate" in error for error in errors)

    temporary, root, _ = _repo()
    with temporary:
        source = root / "aria_nbv/aria_nbv/model.py"
        source.write_text("VALUE = 2\n", encoding="utf-8")
        s = _commit(root, "source")
        (root / "notes.txt").write_text("delay\n", encoding="utf-8")
        delayed = _commit(root, "unrelated delay")
        g = _graph_commit(root, s)
        errors = history.validate_authoring_history(root, [s, delayed, g])
        assert any("lacks immediate" in error for error in errors)

    temporary, root, _ = _repo()
    with temporary:
        main_branch = _git(root, "branch", "--show-current")
        subprocess.run(
            ["git", "checkout", "-qb", "corpus-change"], cwd=root, check=True
        )
        source = root / "aria_nbv/aria_nbv/model.py"
        source.write_text("VALUE = 2\n", encoding="utf-8")
        _commit(root, "branch source")
        subprocess.run(["git", "checkout", "-q", main_branch], cwd=root, check=True)
        subprocess.run(
            ["git", "merge", "--no-ff", "-qm", "merge corpus", "corpus-change"],
            cwd=root,
            check=True,
        )
        merge_commit = _git(root, "rev-parse", "HEAD")
        assert history._touched_partitions(root, merge_commit) == {"code"}
        assert any(
            "lacks immediate" in error
            for error in history.validate_authoring_history(root, [merge_commit])
        )

        graph_commit = _graph_commit(root, merge_commit)
        assert not history.validate_authoring_history(
            root, [merge_commit, graph_commit]
        )

    temporary, root, _ = _repo()
    with temporary:
        source = root / "aria_nbv/aria_nbv/model.py"
        source.write_text("VALUE = 2\n", encoding="utf-8")
        s = _commit(root, "source")
        out = root / "graphify-out"
        out.mkdir()
        (out / "manifest.json").write_text("{}", encoding="utf-8")
        source.write_text("VALUE = 3\n", encoding="utf-8")
        mixed = _commit(root, "mixed")
        errors = history.validate_authoring_history(root, [mixed])
        assert any("mixed source" in error for error in errors)

        _graph_commit(root, s, digest="0" * 64)
        g = _git(root, "rev-parse", "HEAD")
        errors = history.validate_authoring_history(root, [s, g])
        assert any("digest does not match" in error for error in errors)

    for operation in ("modify", "delete", "rename"):
        temporary, root, _ = _repo()
        with temporary:
            manifest = root / "docs/literature/sources.jsonl"
            manifest.parent.mkdir(parents=True)
            manifest.write_text('{"tex_dir":"arXiv-selected"}\n', encoding="utf-8")
            source = root / "docs/literature/tex-src/arXiv-selected/main.tex"
            source.parent.mkdir(parents=True)
            source.write_text("selected v1\n", encoding="utf-8")
            _commit(root, "selected literature base")

            if operation == "modify":
                source.write_text("selected v2\n", encoding="utf-8")
            elif operation == "delete":
                source.unlink()
            else:
                subprocess.run(
                    ["git", "mv", source.name, "renamed.tex"],
                    cwd=source.parent,
                    check=True,
                )
            literature_commit = _commit(root, f"{operation} selected literature")
            assert history._touched_partitions(root, literature_commit) == {
                "literature"
            }
            graph_commit = _graph_commit(
                root, literature_commit, partitions=("literature",)
            )
            assert not history.validate_authoring_history(
                root, [literature_commit, graph_commit]
            )


if __name__ == "__main__":
    main()
