#!/usr/bin/env python3
"""Exercise the real Codex setup bridge in disposable linked worktrees."""

from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import tomllib
import unittest


ROOT = Path(__file__).resolve().parents[2]
RUN_INTEGRATION = os.environ.get("ARIA_NBV_RUN_GRAPHIFY_SESSION_INTEGRATION") == "1"
PINNED_GRAPHIFY_VERSION = "0.9.48"


def git_dir_for_worktree(worktree: Path) -> Path:
    """Return a worktree's administrative directory without ambient Git config."""
    marker = worktree / ".git"
    if marker.is_dir():
        return marker.resolve()
    gitdir = marker.read_text(encoding="utf-8").strip()
    if not gitdir.startswith("gitdir: "):
        raise AssertionError(f"invalid Git worktree marker: {marker}")
    target = Path(gitdir.removeprefix("gitdir: "))
    return (target if target.is_absolute() else worktree / target).resolve()


class RealGraphifySessionReadinessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not RUN_INTEGRATION:
            raise unittest.SkipTest(
                "run make graphify-session-readiness-integration for disposable-worktree proof"
            )
        cls.source = ROOT.resolve()
        cls.source_git_dir = git_dir_for_worktree(cls.source)
        cls.source_head = cls.git_output("rev-parse", "--verify", "HEAD^{commit}")
        common_dir = Path(cls.git_output("rev-parse", "--git-common-dir"))
        if not common_dir.is_absolute():
            common_dir = (cls.source / common_dir).resolve()
        cls.primary = common_dir.parent
        cls.graphify = Path(shutil.which("graphify") or "").resolve()
        if not cls.graphify.is_file():
            raise AssertionError("real Graphify CLI is unavailable")
        cls.graphify_python = Path(
            cls.graphify.read_text(encoding="utf-8").splitlines()[0][2:]
        )
        if not cls.graphify_python.is_file():
            raise AssertionError("real Graphify CLI interpreter is unavailable")
        installed_version = subprocess.run(
            [
                str(cls.graphify_python),
                "-I",
                "-c",
                "from importlib.metadata import version; print(version('graphifyy'))",
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        if installed_version != PINNED_GRAPHIFY_VERSION:
            raise AssertionError(
                f"expected Graphify {PINNED_GRAPHIFY_VERSION}, got {installed_version}"
            )
        admitted = subprocess.run(
            ["python3", "-I", "scripts/check_graphify_freshness.py", "--usable", "--quiet"],
            cwd=cls.source,
            check=False,
            capture_output=True,
            text=True,
        )
        if admitted.returncode:
            raise AssertionError(admitted.stderr or admitted.stdout)

    @classmethod
    def git(cls, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                "git",
                "-c",
                f"core.worktree={cls.source}",
                f"--git-dir={cls.source_git_dir}",
                f"--work-tree={cls.source}",
                *args,
            ],
            check=check,
            capture_output=True,
            text=True,
        )

    @classmethod
    def git_output(cls, *args: str) -> str:
        return cls.git(*args).stdout.strip()

    @contextmanager
    def disposable_worktree(self, path: Path):
        self.git("worktree", "add", "--detach", str(path), self.source_head)
        try:
            yield path
        finally:
            self.git("worktree", "remove", "--force", str(path), check=False)

    def assert_ready(self, child: Path, source_value: str) -> None:
        environment = tomllib.loads(
            (child / ".codex/environments/aria-nbv.toml").read_text(encoding="utf-8")
        )
        bridge = environment["setup"]["script"].strip()
        self.assertEqual(
            bridge, 'bash "$CODEX_WORKTREE_PATH/scripts/setup_codex_worktree_env.sh"'
        )
        setup = subprocess.run(
            ["bash", "-c", bridge],
            cwd=child,
            env={
                **os.environ,
                "CODEX_WORKTREE_PATH": str(child),
                "CODEX_SOURCE_WORKSPACE_PATH": source_value,
            },
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(setup.returncode, 0, setup.stderr or setup.stdout)
        self.assertEqual(setup.stdout, "")
        self.assertEqual(setup.stderr, "")

        query = subprocess.run(
            [str(self.graphify), "query", "Graphify worktree setup", "--budget", "120"],
            cwd=child,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(query.returncode, 0, query.stderr or query.stdout)
        self.assertTrue(query.stdout.strip())

        for namespace in ("semantic", "semantic-deep"):
            link = child / "graphify-out/cache" / namespace
            target = self.primary / ".data/graphify-semantic-cache" / namespace
            self.assertTrue(link.is_symlink())
            self.assertEqual(link.resolve(), target.resolve())
            self.assertTrue(link.resolve().is_relative_to(self.primary / ".data"))

    def test_explicit_and_parentless_codex_setup_are_silent_and_queryable(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aria-graphify-session-real-") as temporary:
            root = Path(temporary)
            with self.subTest(source="explicit"):
                with self.disposable_worktree(root / "explicit") as child:
                    self.assert_ready(child, str(self.source))
            with self.subTest(source="absent"):
                with self.disposable_worktree(root / "absent") as child:
                    self.assert_ready(child, "")


if __name__ == "__main__":
    unittest.main()
