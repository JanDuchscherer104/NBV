#!/usr/bin/env python3
"""Tests for the explicit upstream skill-source maintenance surface."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import skill_sources  # noqa: E402


class SkillSourceTests(unittest.TestCase):
    def test_repository_manifest_is_valid_and_consumers_name_grounding_ids(self) -> None:
        sources = skill_sources.load_manifest()
        self.assertEqual(len(sources), 6)
        self.assertEqual(len({source.id for source in sources}), len(sources))
        for source in sources:
            for consumer in source.consumers:
                path = ROOT / consumer
                if path.is_file():
                    text = path.read_text(encoding="utf-8")
                    self.assertIn(source.id, text, f"{consumer} omits {source.id}")
                    self.assertNotIn("update-skill-sources", text)

    def test_manifest_validation_is_offline(self) -> None:
        with mock.patch.object(skill_sources.subprocess, "run") as run:
            self.assertEqual(skill_sources.main(["validate"]), 0)
        run.assert_not_called()

    def test_check_reports_drift_without_failing(self) -> None:
        new_revision = "f" * 40
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=f"{new_revision}\trefs/heads/main\n",
            stderr="",
        )
        with mock.patch.object(skill_sources.subprocess, "run", return_value=completed):
            with mock.patch("builtins.print") as output:
                self.assertEqual(skill_sources.main(["check", "senpai-performance-loop"]), 0)
        rendered = "\n".join(" ".join(map(str, call.args)) for call in output.call_args_list)
        self.assertIn("update-available", rendered)
        self.assertIn("/compare/", rendered)

    def test_rejects_missing_consumers_and_path_traversal(self) -> None:
        template = """
            schema_version = 1
            [[sources]]
            id = "example"
            title = "Example"
            kind = "git-adaptation"
            repository = "https://example.com/repo.git"
            tracked_ref = "refs/heads/main"
            reviewed_revision = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
            source_paths = ["{source_path}"]
            consumers = ["{consumer}"]
        """
        cases = (
            ("../SKILL.md", "exists.md"),
            (".git/config", "exists.md"),
            ("SKILL.md", "missing.md"),
        )
        for source_path, consumer in cases:
            with self.subTest(source_path=source_path, consumer=consumer):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    (root / "exists.md").write_text("example", encoding="utf-8")
                    manifest = root / "manifest.toml"
                    manifest.write_text(
                        textwrap.dedent(template).format(
                            source_path=source_path, consumer=consumer
                        ),
                        encoding="utf-8",
                    )
                    with self.assertRaises(skill_sources.ManifestError):
                        skill_sources.load_manifest(manifest, repo_root=root)

    def test_materializes_only_declared_paths_at_an_exact_revision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            upstream = root / "upstream"
            upstream.mkdir()
            subprocess.run(["git", "init", "--quiet"], cwd=upstream, check=True)
            subprocess.run(
                ["git", "config", "user.email", "fixture@example.com"],
                cwd=upstream,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Fixture"], cwd=upstream, check=True
            )
            (upstream / "selected.md").write_text("selected\n", encoding="utf-8")
            (upstream / "ignored.md").write_text("ignored\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=upstream, check=True)
            subprocess.run(
                ["git", "commit", "--quiet", "-m", "fixture"],
                cwd=upstream,
                check=True,
            )
            revision = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=upstream,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            source = skill_sources.Source(
                id="fixture",
                title="Fixture",
                kind="git-adaptation",
                repository=str(upstream),
                tracked_ref="refs/heads/main",
                reviewed_revision=revision,
                source_paths=("selected.md",),
                consumers=("consumer.md",),
            )
            destination = root / "materialized"
            skill_sources.materialize_source(source, revision, destination)
            self.assertEqual(
                (destination / "selected.md").read_text(encoding="utf-8"), "selected\n"
            )
            self.assertFalse((destination / "ignored.md").exists())
            with self.assertRaises(skill_sources.ManifestError):
                skill_sources.materialize_source(source, revision, destination)

    def test_materialization_rejects_a_missing_declared_path(self) -> None:
        source = skill_sources.Source(
            id="fixture",
            title="Fixture",
            kind="git-adaptation",
            repository="https://example.com/repo.git",
            tracked_ref="refs/heads/main",
            reviewed_revision="a" * 40,
            source_paths=("missing.md",),
            consumers=("consumer.md",),
        )
        completed = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "materialized"
            with mock.patch.object(
                skill_sources.subprocess, "run", return_value=completed
            ):
                with self.assertRaisesRegex(RuntimeError, "omits declared paths"):
                    skill_sources.materialize_source(
                        source, source.reviewed_revision, destination
                    )
            self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()
