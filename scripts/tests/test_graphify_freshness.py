#!/usr/bin/env python3
"""Hermetic regression tests for the Graphify freshness gate."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
CHECKER = ROOT / "scripts/check_graphify_freshness.py"
sys.path.insert(0, str(ROOT / "scripts"))
from check_graphify_freshness import _upstream_file_hash  # noqa: E402


class FreshnessTests(unittest.TestCase):
    OWNER_PATHS = (
        "docs/typst/thesis/main.typ",
        "docs/typst/shared/style.typ",
        "docs/references.bib",
        "docs/references-qh.bib",
        "docs/literature/sources.jsonl",
    )

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.invalid"],
            cwd=self.root,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"], cwd=self.root, check=True
        )
        (self.root / "seed").write_text("seed\n", encoding="utf-8")
        for relative in self.OWNER_PATHS:
            owner = self.root / relative
            owner.parent.mkdir(parents=True, exist_ok=True)
            owner.write_text(f"owner: {relative}\n", encoding="utf-8")
        subprocess.run(["git", "add", "seed"], cwd=self.root, check=True)
        subprocess.run(["git", "add", "docs"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-qm", "seed"], cwd=self.root, check=True)
        self.head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        self._write_fresh_fixture()

    def tearDown(self) -> None:
        self.directory.cleanup()

    def _write_fresh_fixture(self) -> None:
        index = self.root / "graphify-input/index.md"
        index.parent.mkdir(parents=True, exist_ok=True)
        owner_rows = "\n".join(
            f"- {relative}: sha256:"
            f"{hashlib.sha256((self.root / relative).read_bytes()).hexdigest()}"
            for relative in self.OWNER_PATHS
        )
        index.write_text(
            f"---\nowner: generated\n---\n# graphify-projection:index\n"
            f"source_revision: {self.head}\n"
            "owner_worktree_state: clean\n\n"
            f"## Owner digests\n\n{owner_rows}\n\n## Families\n",
            encoding="utf-8",
        )
        digest = _upstream_file_hash(index.read_bytes(), "graphify-input/index.md")
        output = self.root / "graphify-out"
        (output / "cache").mkdir(parents=True, exist_ok=True)
        (output / "graph.json").write_text(
            json.dumps(
                {
                    "built_at_commit": self.head,
                    "nodes": [{"source_file": "./graphify-input/index.md"}],
                }
            ),
            encoding="utf-8",
        )
        (output / "cache/stat-index.json").write_text(
            json.dumps(
                {
                    "graphify-input/index.md": {
                        "hashes": {"graphify-input/index.md": digest}
                    }
                }
            ),
            encoding="utf-8",
        )

    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(CHECKER), *args],
            cwd=self.root,
            capture_output=True,
            text=True,
        )

    def _json(self) -> dict[str, object]:
        result = self._run("--json")
        return json.loads(result.stdout)

    def test_fresh_json_and_quiet_forms(self) -> None:
        result = self._run("--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            set(json.loads(result.stdout)),
            {"state", "fresh", "head", "reasons", "next_action"},
        )
        self.assertEqual(json.loads(result.stdout)["state"], "fresh")
        quiet = self._run("--quiet")
        self.assertEqual(quiet.returncode, 0)
        self.assertEqual(quiet.stdout, "")
        self.assertEqual(quiet.stderr, "")

    def test_digest_uses_frontmatter_stripping_and_path_salt(self) -> None:
        index = self.root / "graphify-input/index.md"
        raw = index.read_bytes()
        salted = _upstream_file_hash(raw, "graphify-input/index.md")
        self.assertNotEqual(salted, hashlib.sha256(raw).hexdigest())
        stat_index = self.root / "graphify-out/cache/stat-index.json"
        stat_index.write_text(
            json.dumps(
                {
                    "graphify-input/index.md": {
                        "hashes": {
                            "graphify-input/index.md": hashlib.sha256(raw).hexdigest()
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        self.assertEqual(
            json.loads(self._run("--json").stdout)["state"], "structural-stale"
        )

    def test_digest_path_salt_is_case_normalized(self) -> None:
        content = b"# projection\n"
        self.assertEqual(
            _upstream_file_hash(content, "Graphify-Input/INDEX.md"),
            _upstream_file_hash(content, "graphify-input/index.md"),
        )

    def test_nodes_without_source_metadata_do_not_invalidate_a_graph(self) -> None:
        graph_path = self.root / "graphify-out/graph.json"
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
        graph["nodes"].append({"id": "community_summary"})
        graph_path.write_text(json.dumps(graph), encoding="utf-8")
        result = self._run("--json")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)["state"], "fresh")

    def test_near_collision_and_windows_source_paths_fail_closed(self) -> None:
        graph_path = self.root / "graphify-out/graph.json"
        for source, state in (
            (".graphify-input/index.md", "structural-stale"),
            ("C:\\repo\\graphify-input\\index.md", "invalid"),
        ):
            with self.subTest(source=source):
                self._write_fresh_fixture()
                graph = json.loads(graph_path.read_text(encoding="utf-8"))
                graph["nodes"] = [{"source_file": source}]
                graph_path.write_text(json.dumps(graph), encoding="utf-8")
                result = self._run("--json")
                self.assertEqual(result.returncode, 1)
                self.assertEqual(json.loads(result.stdout)["state"], state)

    def test_structural_staleness_predicates_fail_closed(self) -> None:
        cases = {
            "projection": lambda: (self.root / "graphify-input/index.md").write_text(
                (self.root / "graphify-input/index.md")
                .read_text(encoding="utf-8")
                .replace(self.head, "wrong", 1),
                encoding="utf-8",
            ),
            "graph": lambda: (self.root / "graphify-out/graph.json").write_text(
                json.dumps(
                    {
                        "built_at_commit": "wrong",
                        "nodes": [{"source_file": "graphify-input/index.md"}],
                    }
                ),
                encoding="utf-8",
            ),
            "digest": lambda: (
                self.root / "graphify-out/cache/stat-index.json"
            ).write_text(
                json.dumps(
                    {
                        "graphify-input/index.md": {
                            "hashes": {"graphify-input/index.md": "wrong"}
                        }
                    }
                ),
                encoding="utf-8",
            ),
            "node": lambda: (self.root / "graphify-out/graph.json").write_text(
                json.dumps(
                    {
                        "built_at_commit": self.head,
                        "nodes": [{"source_file": "docs/index.md"}],
                    }
                ),
                encoding="utf-8",
            ),
        }
        for name, mutate in cases.items():
            with self.subTest(name=name):
                self._write_fresh_fixture()
                mutate()
                result = self._run("--json")
                self.assertEqual(result.returncode, 1)
                self.assertEqual(json.loads(result.stdout)["state"], "structural-stale")

    def test_dirty_live_owner_classes_fail_closed(self) -> None:
        for relative in self.OWNER_PATHS:
            with self.subTest(relative=relative):
                owner = self.root / relative
                original = owner.read_text(encoding="utf-8")
                owner.write_text(original + "dirty\n", encoding="utf-8")
                payload = self._json()
                self.assertEqual(payload["state"], "structural-stale")
                self.assertTrue(
                    any(relative in reason for reason in payload["reasons"])
                )
                self.assertIn("projection owner worktree is dirty", payload["reasons"])
                owner.write_text(original, encoding="utf-8")

    def test_owner_symlink_escaping_repository_is_invalid(self) -> None:
        relative = self.OWNER_PATHS[-1]
        owner = self.root / relative
        outside = self.root.parent / "outside-owner"
        outside.write_bytes(owner.read_bytes())
        owner.unlink()
        owner.symlink_to(outside)

        payload = self._json()

        self.assertEqual(payload["state"], "invalid")
        self.assertTrue(
            any("owner escapes repository" in reason for reason in payload["reasons"])
        )

    def test_semantic_marker_wins_over_structural_staleness(self) -> None:
        (self.root / "graphify-out/needs_update").write_text(
            "pending\n", encoding="utf-8"
        )
        index = self.root / "graphify-input/index.md"
        index.write_text(
            index.read_text(encoding="utf-8").replace(self.head, "wrong", 1),
            encoding="utf-8",
        )
        result = self._run("--json")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["state"], "semantic-stale")

    def test_invalid_and_missing_precedence(self) -> None:
        (self.root / "graphify-out/graph.json").write_text("not json", encoding="utf-8")
        result = self._run("--json")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["state"], "invalid")
        (self.root / "graphify-out/graph.json").unlink()
        result = self._run("--json")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["state"], "missing")

    def test_invalid_existing_artifact_beats_another_missing_artifact(self) -> None:
        (self.root / "graphify-out/graph.json").write_text("not json", encoding="utf-8")
        (self.root / "graphify-out/cache/stat-index.json").unlink()
        result = self._run("--json")
        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(payload["state"], "invalid")
        self.assertTrue(
            any("missing stat index" in reason for reason in payload["reasons"])
        )

    def test_available_structural_reasons_survive_an_invalid_artifact(self) -> None:
        index = self.root / "graphify-input/index.md"
        index.write_text(
            index.read_text(encoding="utf-8").replace(self.head, "wrong", 1),
            encoding="utf-8",
        )
        (self.root / "graphify-out/graph.json").write_text("not json", encoding="utf-8")
        payload = self._json()
        self.assertEqual(payload["state"], "invalid")
        self.assertTrue(
            any("projection source_revision" in reason for reason in payload["reasons"])
        )
        self.assertTrue(any("invalid graph" in reason for reason in payload["reasons"]))

    def test_missing_artifact_and_option_conflict_fail_closed(self) -> None:
        (self.root / "graphify-input/index.md").unlink()
        result = self._run()
        self.assertEqual(result.returncode, 1)
        self.assertIn("missing", result.stdout)
        conflict = self._run("--quiet", "--json")
        self.assertNotEqual(conflict.returncode, 0)


if __name__ == "__main__":
    unittest.main()
