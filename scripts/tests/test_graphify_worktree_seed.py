#!/usr/bin/env python3
"""Hermetic contract tests for linked-worktree Graphify artifact seeding."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SEEDER = ROOT / "scripts" / "graphify_worktree_seed.py"


class GraphifyWorktreeSeedTest(unittest.TestCase):
    """Exercise the seed boundary with two real worktrees in one Git repository."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="graphify-worktree-seed-")
        self.sandbox = Path(self.tmp.name)
        self.source = self.sandbox / "source"
        self.destination = self.sandbox / "destination"
        self.source.mkdir()
        self.git("init", "-q")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "Graphify Seed Test")
        (self.source / "README.md").write_text("seed fixture\n", encoding="utf-8")
        self.git("add", "README.md")
        self.git("commit", "-qm", "seed fixture")
        self.git("worktree", "add", "--detach", str(self.destination), "HEAD")
        self.graphify_python = self.sandbox / "fake-graphify-python"
        self.graphify_python.write_text(
            "#!/usr/bin/env sh\nprintf '%s\\n' 0.9.48\n",
            encoding="utf-8",
        )
        self.graphify_python.chmod(0o755)
        self.write_valid_source()

    def tearDown(self) -> None:
        subprocess.run(
            [
                "git",
                "-C",
                str(self.source),
                "worktree",
                "remove",
                "--force",
                str(self.destination),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.tmp.cleanup()

    def git(self, *args: str) -> None:
        subprocess.run(
            ["git", "-C", str(self.source), *args],
            check=True,
            capture_output=True,
            text=True,
        )

    def git_output(self, *args: str) -> str:
        return subprocess.run(
            ["git", "-C", str(self.source), *args],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    def write_valid_source(self) -> None:
        output = self.source / "graphify-out"
        projection = self.source / "graphify-input"
        (output / "cache").mkdir(parents=True)
        projection.mkdir()
        (output / "graph.json").write_text(
            json.dumps(
                {
                    "nodes": [{"id": "aria", "source_file": "graphify-input/index.md"}],
                    "built_at_commit": "abc123",
                }
            ),
            encoding="utf-8",
        )
        (output / "manifest.json").write_text(
            json.dumps(
                {
                    "files": {
                        "graphify-input/index.md": {"semantic_hash": "one"},
                        "graphify-input/owners.md": {"semantic_hash": "two"},
                        "docs/not-projection.md": {"semantic_hash": "three"},
                    }
                }
            ),
            encoding="utf-8",
        )
        (output / ".graphify_python").write_text(
            f"{self.graphify_python}\n", encoding="utf-8"
        )
        (projection / "index.md").write_text("# index\n", encoding="utf-8")
        (projection / "owners.md").write_text("# owners\n", encoding="utf-8")
        (projection / "unlisted.md").write_text("# not seeded\n", encoding="utf-8")
        (output / "cache" / "stat-index.json").write_text("{}\n", encoding="utf-8")
        (output / ".graphify_ast.json").write_text("{}\n", encoding="utf-8")
        (output / "GRAPH_REPORT.md").write_text("# report\n", encoding="utf-8")

    def seed(self, *extra: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(SEEDER),
                "--source",
                str(self.source),
                "--destination",
                str(self.destination),
                *extra,
            ],
            check=check,
            capture_output=True,
            text=True,
        )

    def prepare_cache(
        self, *extra: str, check: bool = True
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(SEEDER),
                "--prepare-cache",
                "--destination",
                str(self.destination),
                *extra,
            ],
            check=check,
            capture_output=True,
            text=True,
        )

    def test_copies_only_manifest_backed_durable_artifacts_and_rebinds_child(
        self,
    ) -> None:
        self.seed()

        copied = {
            Path("graphify-out/graph.json"),
            Path("graphify-out/manifest.json"),
            Path("graphify-out/.graphify_python"),
            Path("graphify-input/index.md"),
            Path("graphify-input/owners.md"),
        }
        for relative in copied:
            child = self.destination / relative
            self.assertTrue(child.is_file(), relative)
            self.assertFalse(child.is_symlink(), relative)
            self.assertEqual(child.read_bytes(), (self.source / relative).read_bytes())

        for relative in (
            "graphify-input/unlisted.md",
            "graphify-out/cache/stat-index.json",
            "graphify-out/.graphify_ast.json",
            "graphify-out/GRAPH_REPORT.md",
        ):
            self.assertFalse((self.destination / relative).exists(), relative)

        self.assertEqual(
            (self.destination / "graphify-out/.graphify_root").read_text(
                encoding="utf-8"
            ),
            f"{self.destination.resolve()}\n",
        )
        sentinel = json.loads(
            (self.destination / "graphify-out/.aria-worktree-seed.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(sentinel["schema_version"], 1)
        self.assertEqual(sentinel["source_worktree"], str(self.source.resolve()))
        self.assertEqual(sentinel["target_root"], str(self.destination.resolve()))
        self.assertEqual(sentinel["source_graph_revision"], "abc123")
        self.assertEqual(
            sentinel["source_worktree_head"], self.git_output("rev-parse", "HEAD")
        )
        self.assertEqual(
            set(sentinel["files"]),
            {str(path) for path in copied} | {"graphify-out/.graphify_root"},
        )

        child_graph = self.destination / "graphify-out/graph.json"
        child_graph.write_text("child-only\n", encoding="utf-8")
        self.assertNotEqual(
            child_graph.read_bytes(),
            (self.source / "graphify-out/graph.json").read_bytes(),
        )

    def test_check_and_idempotent_seed_do_not_write_child_state(self) -> None:
        self.seed()
        owned = [
            Path("graphify-out/graph.json"),
            Path("graphify-out/manifest.json"),
            Path("graphify-out/.graphify_python"),
            Path("graphify-input/index.md"),
            Path("graphify-input/owners.md"),
            Path("graphify-out/.graphify_root"),
            Path("graphify-out/.aria-worktree-seed.json"),
        ]
        before = {
            relative: (self.destination / relative).stat().st_mtime_ns
            for relative in owned
        }
        self.seed("--check")
        self.assertEqual(
            before,
            {
                relative: (self.destination / relative).stat().st_mtime_ns
                for relative in owned
            },
        )
        self.seed()
        self.assertEqual(
            before,
            {
                relative: (self.destination / relative).stat().st_mtime_ns
                for relative in owned
            },
        )
        (self.source / "graphify-out/graph.json").unlink()
        self.seed("--check")

    def test_prepares_only_a_regular_local_cache_parent(self) -> None:
        self.prepare_cache()
        cache = self.destination / "graphify-out/cache"
        self.assertTrue(cache.is_dir())
        self.assertFalse(cache.is_symlink())
        self.assertEqual(list(cache.iterdir()), [])
        self.prepare_cache("--check")

    def test_prepare_cache_rejects_external_or_dangling_parent_symlinks(self) -> None:
        for relative in (Path("graphify-out"), Path("graphify-out/cache")):
            for target_exists in (True, False):
                with self.subTest(relative=relative, target_exists=target_exists):
                    parent = self.destination / relative
                    if parent.parent != self.destination:
                        parent.parent.mkdir()
                    external = self.sandbox / (
                        f"prepare-{relative.as_posix().replace('/', '-')}-{target_exists}"
                    )
                    if target_exists:
                        external.mkdir()
                        (external / "keep").write_bytes(b"preserve\x00bytes")
                        before = {
                            path.relative_to(external): path.read_bytes()
                            for path in external.rglob("*")
                            if path.is_file()
                        }
                    parent.symlink_to(external, target_is_directory=True)
                    try:
                        result = self.prepare_cache(check=False)

                        self.assertNotEqual(result.returncode, 0)
                        self.assertIn("unsafe destination parent", result.stderr)
                        if target_exists:
                            after = {
                                path.relative_to(external): path.read_bytes()
                                for path in external.rglob("*")
                                if path.is_file()
                            }
                            self.assertEqual(after, before)
                        else:
                            self.assertFalse(external.exists())
                    finally:
                        if parent.is_symlink():
                            parent.unlink()
                        if parent.parent != self.destination:
                            parent.parent.rmdir()

    def test_owned_root_marker_accepts_only_exact_absolute_path_with_optional_newline(
        self,
    ) -> None:
        self.seed()
        marker = self.destination / "graphify-out/.graphify_root"
        marker.write_text(str(self.destination.resolve()), encoding="utf-8")
        self.seed("--check")
        for suffix in (" ", "\n\n"):
            with self.subTest(suffix=suffix):
                marker.write_text(
                    f"{self.destination.resolve()}{suffix}", encoding="utf-8"
                )
                result = self.seed("--check", check=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("child .graphify_root", result.stderr)

    def test_rejects_destination_parent_symlinks_without_external_writes(self) -> None:
        for top_level in ("graphify-out", "graphify-input"):
            with self.subTest(top_level=top_level):
                external = self.sandbox / f"external-{top_level}"
                external.mkdir()
                target = self.destination / top_level
                target.symlink_to(external, target_is_directory=True)

                result = self.seed(check=False)

                self.assertNotEqual(result.returncode, 0)
                self.assertIn("unsafe destination parent", result.stderr)
                self.assertEqual(list(external.iterdir()), [])
                target.unlink()

                missing = self.sandbox / f"missing-{top_level}"
                target.symlink_to(missing, target_is_directory=True)
                result = self.seed(check=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("unsafe destination parent", result.stderr)
                self.assertFalse(missing.exists())
                target.unlink()

    def test_rejects_parent_symlinks_for_owned_check_without_external_writes(
        self,
    ) -> None:
        self.seed()
        for top_level in ("graphify-out", "graphify-input"):
            with self.subTest(top_level=top_level):
                target = self.destination / top_level
                external = self.sandbox / f"owned-{top_level}"
                target.rename(external)
                target.symlink_to(external, target_is_directory=True)
                before = {
                    path.relative_to(external): path.read_bytes()
                    for path in external.rglob("*")
                    if path.is_file()
                }

                result = self.seed("--check", check=False)

                self.assertNotEqual(result.returncode, 0)
                self.assertIn("unsafe destination parent", result.stderr)
                after = {
                    path.relative_to(external): path.read_bytes()
                    for path in external.rglob("*")
                    if path.is_file()
                }
                self.assertEqual(after, before)
                target.unlink()
                external.rename(target)

    def test_rejects_symlinked_source_parents(self) -> None:
        for top_level in ("graphify-out", "graphify-input"):
            with self.subTest(top_level=top_level):
                source_parent = self.source / top_level
                external = self.sandbox / f"source-{top_level}"
                source_parent.rename(external)
                source_parent.symlink_to(external, target_is_directory=True)

                result = self.seed(check=False)

                self.assertNotEqual(result.returncode, 0)
                self.assertIn("unsafe source parent", result.stderr)
                self.assertFalse(
                    (self.destination / "graphify-out/graph.json").exists()
                )
                source_parent.unlink()
                external.rename(source_parent)

    def test_rejects_non_directory_destination_parent(self) -> None:
        parent = self.destination / "graphify-out"
        parent.write_text("preserve\n", encoding="utf-8")

        result = self.seed(check=False)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unsafe destination parent", result.stderr)
        self.assertEqual(parent.read_text(encoding="utf-8"), "preserve\n")

    def test_rejects_collision_and_partial_owned_state_without_overwrite(self) -> None:
        collision = self.destination / "graphify-out/graph.json"
        collision.parent.mkdir()
        collision.write_text("preserve me\n", encoding="utf-8")
        result = self.seed(check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("destination collision", result.stderr)
        self.assertEqual(collision.read_text(encoding="utf-8"), "preserve me\n")
        self.assertFalse(
            (self.destination / "graphify-out/.aria-worktree-seed.json").exists()
        )

        collision.unlink()
        collision.parent.rmdir()
        self.seed()
        (self.destination / "graphify-out/manifest.json").unlink()
        result = self.seed(check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("seeded artifact must be a regular local file", result.stderr)
        self.assertFalse((self.destination / "graphify-out/manifest.json").exists())

    def test_allows_non_projection_manifest_entries_but_rejects_unsafe_paths(
        self,
    ) -> None:
        manifest = self.source / "graphify-out/manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "files": {
                        "graphify-input/index.md": {"semantic_hash": "good"},
                        "docs/not-projection.md": {"semantic_hash": "allowed"},
                    }
                }
            ),
            encoding="utf-8",
        )

        self.seed()
        self.assertFalse((self.destination / "docs/not-projection.md").exists())

        manifest.write_text(
            json.dumps({"files": {"../outside.md": {"semantic_hash": "unsafe"}}}),
            encoding="utf-8",
        )
        other = self.sandbox / "unsafe-destination"
        self.git("worktree", "add", "--detach", str(other), "HEAD")
        result = subprocess.run(
            [
                sys.executable,
                str(SEEDER),
                "--source",
                str(self.source),
                "--destination",
                str(other),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unsafe manifest path", result.stderr)
        self.assertFalse((other / "graphify-out/.aria-worktree-seed.json").exists())
        subprocess.run(
            [
                "git",
                "-C",
                str(self.source),
                "worktree",
                "remove",
                "--force",
                str(other),
            ],
            check=True,
        )


if __name__ == "__main__":
    unittest.main()
