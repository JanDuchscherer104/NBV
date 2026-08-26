#!/usr/bin/env python3
"""Contract tests for the setup-owned incremental Graphify reconciler."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import reconcile_graphify_worktree as reconcile  # noqa: E402


class ReconcileGraphifyWorktreeTests(unittest.TestCase):
    @staticmethod
    def git(root: Path, *arguments: str) -> str:
        return subprocess.run(
            ["git", *arguments], cwd=root, check=True, capture_output=True, text=True
        ).stdout.strip()

    @classmethod
    def initialized_repository(cls, root: Path) -> str:
        cls.git(root, "init")
        cls.git(root, "config", "user.email", "tests@example.invalid")
        cls.git(root, "config", "user.name", "ARIA tests")
        (root / "tracked.txt").write_text("fixture\n", encoding="utf-8")
        cls.git(root, "add", "tracked.txt")
        cls.git(root, "commit", "-m", "fixture")
        return cls.git(root, "rev-parse", "HEAD")

    def test_stamps_revision_and_relativizes_trusted_graph_sources(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aria-reconcile-") as temporary:
            root = Path(temporary)
            source = root / "graphify-input/index.md"
            source.parent.mkdir()
            source.write_text("# fixture\n", encoding="utf-8")
            output = root / "graphify-out"
            output.mkdir()
            graph = output / "graph.json"
            graph.write_text(
                json.dumps(
                    {
                        "nodes": [
                            {"source_file": str(source)}, {"source_file": ""}
                        ],
                        "edges": [{"source_file": str(source)}],
                        "hyperedges": [{"source_file": str(source)}],
                    }
                ),
                encoding="utf-8",
            )

            reconcile.stamp_graph_provenance(root, "a" * 40)

            result = json.loads(graph.read_text(encoding="utf-8"))
            self.assertEqual(result["built_at_commit"], "a" * 40)
            for bucket in ("nodes", "edges", "hyperedges"):
                self.assertEqual(result[bucket][0]["source_file"], "graphify-input/index.md")
            self.assertNotIn("source_file", result["nodes"][1])

    def test_rejects_graph_source_that_escapes_the_worktree(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aria-reconcile-") as temporary:
            root = Path(temporary)
            output = root / "graphify-out"
            output.mkdir()
            escaped = root.parent / "outside.md"
            escaped.write_text("outside\n", encoding="utf-8")
            graph = output / "graph.json"
            original = json.dumps({"nodes": [{"source_file": str(escaped)}]})
            graph.write_text(original, encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "escapes repository"):
                reconcile.stamp_graph_provenance(root, "a" * 40)

            self.assertEqual(graph.read_text(encoding="utf-8"), original)

    def test_rejects_hostile_or_noncommit_graph_provenance(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aria-reconcile-") as temporary:
            root = Path(temporary)
            self.initialized_repository(root)
            output = root / "graphify-out"
            output.mkdir()
            graph = output / "graph.json"
            for revision, expected in (
                ("--git-dir=/tmp/hostile", "canonical full commit OID"),
                (self.git(root, "hash-object", "tracked.txt"), "commit object"),
            ):
                graph.write_text(json.dumps({"built_at_commit": revision}), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, expected):
                    reconcile.graph_revision(root)

    def test_parent_head_seed_does_not_suppress_graph_reconciliation(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aria-reconcile-") as temporary:
            root = Path(temporary)
            (root / ".git").mkdir()
            (root / "graphify-input").mkdir()
            (root / "graphify-input/index.md").write_text("# fixture\n", encoding="utf-8")
            output = root / "graphify-out"
            output.mkdir()
            (output / "graph.json").write_text(
                json.dumps({"built_at_commit": "b" * 40, "nodes": [], "links": []}),
                encoding="utf-8",
            )
            # This is the formerly dangerous state: the seed parent and child
            # are at H2, while the inherited graph still represents H1.
            (output / ".aria-worktree-seed.json").write_text(
                json.dumps({"source_worktree_head": "a" * 40}), encoding="utf-8"
            )
            interpreter = root.parent / "trusted-python"
            interpreter.write_text("#!/bin/sh\n", encoding="utf-8")
            interpreter.chmod(0o755)
            cli = root.parent / "trusted-graphify"
            cli.write_text(f"#!{interpreter}\n", encoding="utf-8")
            cli.chmod(0o755)
            commands: list[tuple[str, ...]] = []

            def completed(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
                commands.append(tuple(command))
                return subprocess.CompletedProcess(command, 0, "", "")

            with (
                mock.patch.object(
                    reconcile, "trusted_graphify_runtime", return_value=(cli, interpreter)
                ),
                mock.patch.object(reconcile, "head", return_value="a" * 40),
                mock.patch.object(reconcile, "graph_revision", return_value="b" * 40),
                mock.patch.object(reconcile, "graph_tree_matches_head", return_value=False),
                mock.patch.object(
                    reconcile.freshness, "projection_owner_changes", return_value=["owner changed"]
                ),
                mock.patch.object(reconcile.subprocess, "run", side_effect=completed),
            ):
                reconcile.run(root)

            self.assertIn((str(cli), "extract", str(root.resolve())), commands)

    def test_recognizes_nonancestor_commits_with_the_same_tree(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aria-reconcile-") as temporary:
            root = Path(temporary)
            destination = self.initialized_repository(root)
            tree = self.git(root, "rev-parse", "HEAD^{tree}")
            alternate = self.git(root, "commit-tree", tree, "-m", "other history")

            self.assertNotEqual(destination, alternate)
            self.assertNotEqual(
                subprocess.run(
                    ["git", "merge-base", "--is-ancestor", alternate, destination],
                    cwd=root,
                    check=False,
                ).returncode,
                0,
            )
            self.assertTrue(reconcile.graph_tree_matches_head(root, alternate, destination))

    def test_runs_projection_incremental_update_then_usable_admission(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aria-reconcile-") as temporary:
            root = Path(temporary)
            (root / ".git").mkdir()
            output = root / "graphify-out"
            output.mkdir()
            projection = root / "graphify-input"
            projection.mkdir()
            (projection / "index.md").write_text("# fixture\n", encoding="utf-8")
            (output / "graph.json").write_text(
                json.dumps(
                    {
                        "built_at_commit": "b" * 40,
                        "nodes": [{"_origin": "semantic"}],
                        "links": [{"_origin": "semantic"}],
                    }
                ),
                encoding="utf-8",
            )
            interpreter = root.parent / "trusted-python"
            interpreter.write_text("#!/bin/sh\n", encoding="utf-8")
            interpreter.chmod(0o755)
            (output / ".graphify_python").write_text(
                f"{interpreter}\n", encoding="utf-8"
            )
            graphify = root.parent / "trusted-graphify"
            graphify.write_text(f"#!{interpreter}\n", encoding="utf-8")
            graphify.chmod(0o755)
            recorded: list[tuple[str, ...]] = []

            def completed(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
                recorded.append(tuple(command))
                if command[:3] == ["git", "rev-parse", "--verify"]:
                    return subprocess.CompletedProcess(command, 0, "a" * 40 + "\n", "")
                if command[:3] == [str(interpreter), "-I", "-c"]:
                    if "detect" in command[3]:
                        return subprocess.CompletedProcess(
                            command,
                            0,
                            '{"document": ["graphify-input/index.md"], "paper": [], "image": []}\n',
                            "",
                        )
                    return subprocess.CompletedProcess(
                        command, 0, f"{reconcile.PINNED_GRAPHIFY_VERSION}\n", ""
                    )
                return subprocess.CompletedProcess(command, 0, "", "")

            with (
                mock.patch.object(reconcile.shutil, "which", return_value=str(graphify)),
                mock.patch.object(reconcile, "head", return_value="a" * 40),
                mock.patch.object(reconcile, "graph_revision", return_value="b" * 40),
                mock.patch.object(reconcile, "graph_tree_matches_head", return_value=False),
                mock.patch.object(
                    reconcile.freshness, "projection_owner_changes", return_value=["owner changed"]
                ),
                mock.patch.object(reconcile.subprocess, "run", side_effect=completed),
            ):
                reconcile.run(root)

        self.assertTrue(
            any(
                any("build_graphify_projection.py" in item for item in command)
                for command in recorded
            )
        )
        extract = (str(graphify.resolve()), "extract", str(root.resolve()))
        self.assertIn(extract, recorded)
        self.assertEqual(recorded[-1][-2:], ("--usable", "--quiet"))

    def test_runs_standard_extraction_for_dirty_inputs_at_an_equivalent_head(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aria-reconcile-") as temporary:
            root = Path(temporary)
            (root / ".git").mkdir()
            projection = root / "graphify-input"
            projection.mkdir()
            index = projection / "index.md"
            index.write_text("# fixture\n", encoding="utf-8")
            output = root / "graphify-out"
            output.mkdir()
            graph = output / "graph.json"
            graph.write_text(
                json.dumps(
                    {
                        "built_at_commit": "b" * 40,
                        "nodes": [{"_origin": "semantic"}],
                        "links": [{"_origin": "semantic"}],
                    }
                ),
                encoding="utf-8",
            )
            interpreter = root.parent / "trusted-python"
            interpreter.write_text("#!/bin/sh\n", encoding="utf-8")
            interpreter.chmod(0o755)
            cli = root.parent / "trusted-graphify"
            cli.write_text(f"#!{interpreter}\n", encoding="utf-8")
            cli.chmod(0o755)
            recorded: list[tuple[str, ...]] = []

            def completed(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
                recorded.append(tuple(command))
                return subprocess.CompletedProcess(command, 0, "", "")

            with (
                mock.patch.object(
                    reconcile, "trusted_graphify_runtime", return_value=(cli, interpreter)
                ),
                mock.patch.object(reconcile, "head", return_value="a" * 40),
                mock.patch.object(reconcile, "graph_revision", return_value="b" * 40),
                mock.patch.object(reconcile, "graph_tree_matches_head", return_value=True),
                mock.patch.object(
                    reconcile.freshness, "projection_owner_changes", return_value=[]
                ),
                mock.patch.object(reconcile.subprocess, "run", side_effect=completed),
            ):
                reconcile.run(root)

            self.assertIn((str(cli), "extract", str(root.resolve())), recorded)
            self.assertEqual(
                json.loads(graph.read_text(encoding="utf-8"))["built_at_commit"],
                "a" * 40,
            )

    def test_runs_cold_deep_extraction_even_when_standard_graph_tree_matches(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aria-reconcile-") as temporary:
            root = Path(temporary)
            (root / ".git").mkdir()
            (root / "graphify-input").mkdir()
            (root / "graphify-input/index.md").write_text("# fixture\n", encoding="utf-8")
            output = root / "graphify-out"
            output.mkdir()
            (output / "graph.json").write_text(
                json.dumps({"built_at_commit": "b" * 40, "nodes": [], "links": []}),
                encoding="utf-8",
            )
            interpreter = root.parent / "trusted-python"
            interpreter.write_text("#!/bin/sh\n", encoding="utf-8")
            interpreter.chmod(0o755)
            cli = root.parent / "trusted-graphify"
            cli.write_text(f"#!{interpreter}\n", encoding="utf-8")
            cli.chmod(0o755)
            commands: list[tuple[str, ...]] = []

            def completed(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
                commands.append(tuple(command))
                return subprocess.CompletedProcess(command, 0, "", "")

            with (
                mock.patch.object(
                    reconcile, "trusted_graphify_runtime", return_value=(cli, interpreter)
                ),
                mock.patch.object(reconcile, "head", return_value="a" * 40),
                mock.patch.object(reconcile.freshness, "projection_owner_changes", return_value=[]),
                mock.patch.object(reconcile.subprocess, "run", side_effect=completed),
            ):
                reconcile.run(root, modes=("deep",))

            self.assertIn(
                (str(cli), "extract", str(root.resolve()), "--mode", "deep"), commands
            )

    def test_runs_standard_before_deep_for_both_declared_consumers(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aria-reconcile-") as temporary:
            root = Path(temporary)
            (root / ".git").mkdir()
            (root / "graphify-input").mkdir()
            (root / "graphify-input/index.md").write_text("# fixture\n", encoding="utf-8")
            output = root / "graphify-out"
            output.mkdir()
            (output / "graph.json").write_text(
                json.dumps({"built_at_commit": "b" * 40, "nodes": [], "links": []}),
                encoding="utf-8",
            )
            interpreter = root.parent / "trusted-python"
            interpreter.write_text("#!/bin/sh\n", encoding="utf-8")
            interpreter.chmod(0o755)
            cli = root.parent / "trusted-graphify"
            cli.write_text(f"#!{interpreter}\n", encoding="utf-8")
            cli.chmod(0o755)
            commands: list[tuple[str, ...]] = []

            def completed(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
                commands.append(tuple(command))
                return subprocess.CompletedProcess(command, 0, "", "")

            with (
                mock.patch.object(
                    reconcile, "trusted_graphify_runtime", return_value=(cli, interpreter)
                ),
                mock.patch.object(reconcile, "head", return_value="a" * 40),
                mock.patch.object(
                    reconcile.freshness, "projection_owner_changes", return_value=[]
                ),
                mock.patch.object(reconcile.subprocess, "run", side_effect=completed),
            ):
                reconcile.run(root, modes=("standard", "deep"))

            extracts = [command for command in commands if command[:2] == (str(cli), "extract")]
            self.assertEqual(
                extracts,
                [
                    (str(cli), "extract", str(root.resolve())),
                    (str(cli), "extract", str(root.resolve()), "--mode", "deep"),
                ],
            )

    def test_rejects_invalid_mode_declaration(self) -> None:
        with self.assertRaisesRegex(ValueError, "Graphify modes"):
            reconcile.configured_modes("deep,standard")

    def test_rejects_a_marker_that_differs_from_the_cli_interpreter(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aria-reconcile-") as temporary:
            root = Path(temporary)
            output = root / "graphify-out"
            output.mkdir()
            trusted = root.parent / "trusted-python"
            trusted.write_text("#!/bin/sh\n", encoding="utf-8")
            trusted.chmod(0o755)
            marker = root.parent / "other-python"
            marker.write_text("#!/bin/sh\n", encoding="utf-8")
            marker.chmod(0o755)
            (output / ".graphify_python").write_text(f"{marker}\n", encoding="utf-8")
            cli = root.parent / "trusted-graphify"
            cli.write_text(f"#!{trusted}\n", encoding="utf-8")
            cli.chmod(0o755)
            with mock.patch.object(reconcile.shutil, "which", return_value=str(cli)):
                with self.assertRaisesRegex(ValueError, "does not match"):
                    reconcile.trusted_graphify_runtime(root)

    def test_restores_projection_and_graph_when_incremental_update_fails(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aria-reconcile-") as temporary:
            root = Path(temporary)
            (root / ".git").mkdir()
            projection = root / "graphify-input"
            projection.mkdir()
            index = projection / "index.md"
            index.write_text("# original\n", encoding="utf-8")
            output = root / "graphify-out"
            output.mkdir()
            graph = output / "graph.json"
            graph.write_text(
                json.dumps({"built_at_commit": "b" * 40, "nodes": [], "links": []}), encoding="utf-8"
            )
            interpreter = root.parent / "trusted-python"
            interpreter.write_text("#!/bin/sh\n", encoding="utf-8")
            interpreter.chmod(0o755)
            cli = root.parent / "trusted-graphify"
            cli.write_text(f"#!{interpreter}\n", encoding="utf-8")
            cli.chmod(0o755)

            def mutate_then_fail(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
                if command[0] == str(cli):
                    graph.write_text("{\"mutated\": true}\n", encoding="utf-8")
                    raise subprocess.CalledProcessError(1, command)
                index.write_text("# mutated\n", encoding="utf-8")
                return subprocess.CompletedProcess(command, 0, "", "")

            with (
                mock.patch.object(
                    reconcile, "trusted_graphify_runtime", return_value=(cli, interpreter)
                ),
                mock.patch.object(reconcile, "head", return_value="a" * 40),
                mock.patch.object(reconcile, "graph_revision", return_value="b" * 40),
                mock.patch.object(reconcile, "graph_tree_matches_head", return_value=False),
                mock.patch.object(
                    reconcile.freshness, "projection_owner_changes", return_value=["owner changed"]
                ),
                mock.patch.object(
                    reconcile.subprocess, "run", side_effect=mutate_then_fail
                ),
            ):
                with self.assertRaises(subprocess.CalledProcessError):
                    reconcile.run(root)

            self.assertEqual(index.read_text(encoding="utf-8"), "# original\n")
            self.assertEqual(
                graph.read_text(encoding="utf-8"),
                json.dumps({"built_at_commit": "b" * 40, "nodes": [], "links": []}),
            )

    def test_restores_generation_when_upstream_semantic_reconciliation_fails(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aria-reconcile-") as temporary:
            root = Path(temporary)
            (root / ".git").mkdir()
            projection = root / "graphify-input"
            projection.mkdir()
            index = projection / "index.md"
            index.write_text("# original\n", encoding="utf-8")
            output = root / "graphify-out"
            output.mkdir()
            graph = output / "graph.json"
            original = json.dumps(
                {"built_at_commit": "b" * 40, "nodes": [{"_origin": "semantic"}], "links": []}
            )
            graph.write_text(original, encoding="utf-8")
            interpreter = root.parent / "trusted-python"
            interpreter.write_text("#!/bin/sh\n", encoding="utf-8")
            interpreter.chmod(0o755)
            cli = root.parent / "trusted-graphify"
            cli.write_text(f"#!{interpreter}\n", encoding="utf-8")
            cli.chmod(0o755)

            def drop_semantic(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
                if command[0] == str(cli):
                    graph.write_text(json.dumps({"nodes": [], "links": []}), encoding="utf-8")
                    raise subprocess.CalledProcessError(1, command)
                return subprocess.CompletedProcess(command, 0, "", "")

            with (
                mock.patch.object(
                    reconcile, "trusted_graphify_runtime", return_value=(cli, interpreter)
                ),
                mock.patch.object(reconcile, "head", return_value="a" * 40),
                mock.patch.object(reconcile, "graph_revision", return_value="b" * 40),
                mock.patch.object(reconcile, "graph_tree_matches_head", return_value=False),
                mock.patch.object(
                    reconcile.freshness, "projection_owner_changes", return_value=["owner changed"]
                ),
                mock.patch.object(reconcile.subprocess, "run", side_effect=drop_semantic),
            ):
                with self.assertRaises(subprocess.CalledProcessError):
                    reconcile.run(root)

            self.assertEqual(graph.read_text(encoding="utf-8"), original)

    def test_rejects_an_unpinned_cli_before_update(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aria-reconcile-") as temporary:
            root = Path(temporary)
            (root / ".git").mkdir()
            output = root / "graphify-out"
            output.mkdir()
            interpreter = root.parent / "trusted-python"
            interpreter.write_text("#!/bin/sh\n", encoding="utf-8")
            interpreter.chmod(0o755)
            (output / ".graphify_python").write_text(
                f"{interpreter}\n", encoding="utf-8"
            )
            cli = root.parent / "trusted-graphify"
            cli.write_text(f"#!{interpreter}\n", encoding="utf-8")
            cli.chmod(0o755)
            recorded: list[tuple[str, ...]] = []

            def wrong_version(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
                recorded.append(tuple(command))
                return subprocess.CompletedProcess(command, 0, "0.0.0\n", "")

            with (
                mock.patch.object(reconcile.shutil, "which", return_value=str(cli)),
                mock.patch.object(
                    reconcile.subprocess, "run", side_effect=wrong_version
                ),
            ):
                with self.assertRaisesRegex(ValueError, "not 0.9.48"):
                    reconcile.run(root)
            self.assertEqual(len(recorded), 1)

    def test_rejects_a_repository_local_graphify_cli(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aria-reconcile-") as temporary:
            root = Path(temporary)
            cli = root / "graphify"
            cli.write_text("#!/bin/sh\n", encoding="utf-8")
            cli.chmod(0o755)
            with mock.patch.object(reconcile.shutil, "which", return_value=str(cli)):
                with self.assertRaisesRegex(ValueError, "unsafe"):
                    reconcile.trusted_graphify_cli(root)


if __name__ == "__main__":
    unittest.main()
