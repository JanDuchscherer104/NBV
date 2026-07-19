#!/usr/bin/env python3
"""Regression checks for the local Graphify freshness contract."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile

SCRIPT = Path(__file__).resolve().parents[1] / "check_graphify_freshness.py"
SPEC = importlib.util.spec_from_file_location("check_graphify_freshness", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
freshness = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(freshness)

REFRESH_SCRIPT = Path(__file__).resolve().parents[1] / "graphify_refresh.py"
REFRESH_SPEC = importlib.util.spec_from_file_location(
    "graphify_refresh", REFRESH_SCRIPT
)
assert REFRESH_SPEC is not None and REFRESH_SPEC.loader is not None
refresh = importlib.util.module_from_spec(REFRESH_SPEC)
REFRESH_SPEC.loader.exec_module(refresh)


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


def main() -> None:
    assert refresh._is_code(Path("aria_nbv/aria_nbv/model.py"))
    assert refresh._is_code(Path(".agents/issues.toml"))
    assert refresh._is_code(Path("Makefile"))
    assert refresh._is_semantic(Path("aria_nbv/README.md"))
    assert refresh._is_semantic(Path("docs/typst/thesis/main.typ"))
    assert refresh._is_semantic(Path(".graphifyignore"))

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        subprocess.run(
            ["git", "config", "user.email", "freshness@example.invalid"],
            cwd=root,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "freshness-test"], cwd=root, check=True
        )
        policy = root / ".graphifyignore"
        policy.write_text("graphify-out/\n", encoding="utf-8")
        subprocess.run(["git", "add", ".graphifyignore"], cwd=root, check=True)
        subprocess.run(["git", "commit", "-qm", "initial"], cwd=root, check=True)
        head = _git(root, "rev-parse", "HEAD")

        out = root / "graphify-out"
        out.mkdir()
        (out / "graph.json").write_text(
            json.dumps({"built_at_commit": head}), encoding="utf-8"
        )
        (out / "aria_nbv_freshness.json").write_text(
            json.dumps(
                {
                    "built_at_commit": head,
                    "corpus_policy_sha256": hashlib.sha256(
                        policy.read_bytes()
                    ).hexdigest(),
                    "semantic_pending": False,
                }
            ),
            encoding="utf-8",
        )
        freshness.ROOT = root
        freshness.OUT = out
        assert freshness.freshness_errors() == []

        policy.write_text("graphify-out/\ndocs/_site/\n", encoding="utf-8")
        assert ".graphifyignore changed" in " ".join(freshness.freshness_errors())
        policy.write_text("graphify-out/\n", encoding="utf-8")
        (out / "needs_update").touch()
        assert "extraction is pending" in " ".join(freshness.freshness_errors())

        refresh.ROOT = root
        refresh.OUT = out
        refresh.STATE = out / "aria_nbv_freshness.json"
        refresh.shutil.which = lambda _: "/usr/bin/true"
        refresh.os.environ["GRAPHIFY_CHANGED"] = "aria_nbv/aria_nbv/model.py"
        assert refresh.main() == 0
        state = json.loads(refresh.STATE.read_text(encoding="utf-8"))
        assert state["semantic_pending"] is True
        assert (out / "needs_update").exists()

        captured: list[str] = []

        class _Completed:
            returncode = 0

        def _run(command: list[str], **_: object) -> _Completed:
            captured.extend(command)
            return _Completed()

        (out / "needs_update").unlink()
        refresh.STATE.unlink()
        refresh.shutil.which = lambda _: None
        refresh.subprocess.run = _run
        refresh._git_head = lambda: head
        assert refresh.main() == 0
        assert captured[:3] == [refresh.sys.executable, "-m", "graphify"]


if __name__ == "__main__":
    main()
