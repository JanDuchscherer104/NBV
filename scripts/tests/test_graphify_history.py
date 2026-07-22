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


def _repo() -> tuple[tempfile.TemporaryDirectory, Path, str]:
    temporary = tempfile.TemporaryDirectory()
    root = Path(temporary.name)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "graph@example.invalid"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "graph-test"], cwd=root, check=True)
    shutil.copy(contract.ROOT / ".graphify.toml", root / ".graphify.toml")
    shutil.copy(contract.ROOT / ".graphifyignore", root / ".graphifyignore")
    path = root / "aria_nbv/aria_nbv/model.py"
    path.parent.mkdir(parents=True)
    path.write_text("VALUE = 1\n", encoding="utf-8")
    base = _commit(root, "base")
    return temporary, root, base


def _graph_commit(root: Path, source_commit: str, *, digest: str | None = None) -> str:
    touched_digest = digest or history._source_tree_digest_at(root, source_commit)
    out = root / "graphify-out"
    out.mkdir(exist_ok=True)
    manifest = {
        "corpus_tree_sha256": touched_digest,
        "sync": {"refreshed_partitions": ["code"], "source_tree_sha256": touched_digest},
    }
    (out / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (out / "graph.json").write_text(json.dumps({"corpus_tree_sha256": touched_digest}), encoding="utf-8")
    (out / "GRAPH_REPORT.md").write_text("# Graph\n", encoding="utf-8")
    return _commit(root, "graph sync")


def main() -> None:
    temporary, root, base = _repo()
    with temporary:
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
        assert any("lacks immediate" in error for error in history.validate_authoring_history(root, [s]))

        source.write_text("VALUE = 3\n", encoding="utf-8")
        t = _commit(root, "second source")
        errors = history.validate_authoring_history(root, [s, t])
        assert any("unsynchronized" in error for error in errors)

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


if __name__ == "__main__":
    main()
