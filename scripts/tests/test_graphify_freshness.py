#!/usr/bin/env python3
"""Hermetic contract tests for the upstream-first Graphify freshness gate."""

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
from check_graphify_freshness import _detector_stale_sources  # noqa: E402


def graphify_python() -> Path:
    """Use the local marker when present, otherwise CI's pinned interpreter."""
    marker = ROOT / "graphify-out/.graphify_python"
    candidate = (
        Path(marker.read_text().strip()) if marker.is_file() else Path(sys.executable)
    )
    result = subprocess.run(
        [
            str(candidate),
            "-c",
            "import graphify; from importlib.metadata import version; print(version('graphifyy'))",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode or result.stdout.strip() != "0.9.31":
        raise RuntimeError("Graphify 0.9.31 is required for freshness tests")
    return candidate


class FreshnessTests(unittest.TestCase):
    """Use Graphify's own manifest writer; tests never reproduce its hashes."""

    OWNER = "docs/thesis/main.md"

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory(prefix="aria-freshness-")
        self.root = Path(self.directory.name)
        self.graphify_python = graphify_python()
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.invalid"],
            cwd=self.root,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"], cwd=self.root, check=True
        )
        for relative, content in {
            self.OWNER: "owner\n",
            "src/example.py": "def example(): return 1\n",
            "seed.md": "seed\n",
        }.items():
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-qm", "seed"], cwd=self.root, check=True)
        self.head = self.git("rev-parse", "HEAD")
        self._write_projection()
        self._write_graph()
        self._save_upstream_manifest()

    def tearDown(self) -> None:
        self.directory.cleanup()

    def git(self, *args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=self.root, check=True, capture_output=True, text=True
        ).stdout.strip()

    def _write_projection(self) -> None:
        owner = self.root / self.OWNER
        digest = hashlib.sha256(owner.read_bytes()).hexdigest()
        index = self.root / "graphify-input/index.md"
        index.parent.mkdir(parents=True, exist_ok=True)
        index.write_text(
            "---\nowner: generated\n---\n# graphify-projection:index\n"
            f"source_revision: {self.head}\n"
            "owner_worktree_state: clean\n\n"
            "## Owner digests\n\n"
            f"- {self.OWNER}: sha256:{digest}\n\n## Families\n",
            encoding="utf-8",
        )

    def _write_graph(
        self, revision: str | None = None, *, index_node: bool = True
    ) -> None:
        output = self.root / "graphify-out"
        output.mkdir(exist_ok=True)
        (output / "graph.json").write_text(
            json.dumps(
                {
                    "built_at_commit": revision or self.head,
                    "nodes": [{"source_file": "graphify-input/index.md"}]
                    if index_node
                    else [],
                }
            ),
            encoding="utf-8",
        )
        (output / ".graphify_python").write_text(
            f"{self.graphify_python}\n", encoding="utf-8"
        )
        root_marker = output / ".graphify_root"
        root_marker.unlink(missing_ok=True)
        root_marker.write_text(f"{self.root.resolve()}\n", encoding="utf-8")

    def _write_unsafe_graph(self) -> None:
        (self.root / "graphify-out/graph.json").write_text(
            json.dumps(
                {
                    "built_at_commit": self.head,
                    "nodes": [{"source_file": "C:\\outside\\index.md"}],
                }
            ),
            encoding="utf-8",
        )

    def _save_upstream_manifest(self) -> None:
        program = """
import sys
from pathlib import Path
from graphify.detect import detect, save_manifest
root = Path(sys.argv[1])
manifest = sys.argv[2]
result = detect(root, follow_symlinks=False, google_workspace=False)
corpus = {path for paths in result['files'].values() for path in paths}
save_manifest(result['files'], manifest_path=manifest, root=root, scan_corpus=corpus)
"""
        subprocess.run(
            [
                str(self.graphify_python),
                "-c",
                program,
                str(self.root),
                str(self.root / "graphify-out/manifest.json"),
            ],
            check=True,
            capture_output=True,
            text=True,
        )

    def run_checker(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(self.graphify_python), str(CHECKER), *args],
            cwd=self.root,
            capture_output=True,
            text=True,
        )

    def payload(self) -> dict[str, object]:
        result = self.run_checker("--json")
        return json.loads(result.stdout)

    def test_fresh_and_detector_does_not_mutate_graphify_artifacts(self) -> None:
        before = {
            path.relative_to(self.root): path.read_bytes()
            for path in (self.root / "graphify-out").rglob("*")
            if path.is_file()
        }
        result = self.run_checker("--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.payload()["state"], "fresh")
        after = {
            path.relative_to(self.root): path.read_bytes()
            for path in (self.root / "graphify-out").rglob("*")
            if path.is_file()
        }
        self.assertEqual(after, before)

    def test_ast_and_semantic_drift_use_their_respective_upstream_hashes(self) -> None:
        code = self.root / "src/example.py"
        code.write_text("def example(): return 2\n", encoding="utf-8")
        code_payload = self.payload()
        self.assertEqual(code_payload["state"], "usable-stale", code_payload)
        self.assertIn("src/example.py", code_payload["stale_sources"])

        self._save_upstream_manifest()
        index = self.root / "graphify-input/index.md"
        manifest_path = self.root / "graphify-out/manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["graphify-input/index.md"]["semantic_hash"] = ""
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        semantic_payload = self.payload()
        self.assertEqual(semantic_payload["state"], "usable-stale")
        self.assertIn("graphify-input/index.md", semantic_payload["stale_sources"])
        self.assertTrue(index.exists())

    def test_ancestor_snapshot_is_usable_stale_and_usable_cli_succeeds(self) -> None:
        (self.root / "unrelated.md").write_text("later\n", encoding="utf-8")
        subprocess.run(["git", "add", "unrelated.md"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-qm", "later"], cwd=self.root, check=True)
        strict = self.run_checker("--quiet")
        usable = self.run_checker("--quiet", "--usable")
        self.assertEqual(strict.returncode, 1)
        self.assertEqual(usable.returncode, 0)
        self.assertEqual(self.payload()["state"], "usable-stale")

    def test_corrupt_nonancestor_marker_projection_and_detector_failures_are_unusable(
        self,
    ) -> None:
        cases = {
            "corrupt": lambda: (self.root / "graphify-out/graph.json").write_text(
                "{", encoding="utf-8"
            ),
            "nonancestor": lambda: self._write_graph("deadbeef"),
            "missing-node": lambda: self._write_graph(index_node=False),
            "marker": lambda: (self.root / "graphify-out/needs_update").write_text(
                "pending\n", encoding="utf-8"
            ),
            "deleted": lambda: (self.root / "src/example.py").unlink(),
            "excluded": lambda: (self.root / ".graphifyignore").write_text(
                "src/example.py\n", encoding="utf-8"
            ),
            "video": lambda: (self.root / "clip.mp4").write_bytes(b"video"),
            "unsafe-path": self._write_unsafe_graph,
        }
        for name, mutate in cases.items():
            with self.subTest(name=name):
                self._write_graph()
                (self.root / "graphify-out/needs_update").unlink(missing_ok=True)
                (self.root / "src/example.py").write_text(
                    "def example(): return 1\n", encoding="utf-8"
                )
                (self.root / ".graphifyignore").unlink(missing_ok=True)
                (self.root / "clip.mp4").unlink(missing_ok=True)
                self._save_upstream_manifest()
                mutate()
                self.assertEqual(self.payload()["state"], "unusable")

    def test_projection_index_symlink_is_unusable_even_when_target_is_in_root(
        self,
    ) -> None:
        index = self.root / "graphify-input/index.md"
        target = self.root / "graphify-input/index-target.md"
        target.write_bytes(index.read_bytes())
        index.unlink()
        index.symlink_to(target.name)

        self.assertEqual(self.payload()["state"], "unusable")

    def test_graphify_root_must_be_regular_and_exactly_bound(self) -> None:
        marker = self.root / "graphify-out/.graphify_root"
        outside = self.root / "root-marker-target"
        cases = {
            "missing": lambda: marker.unlink(),
            "wrong": lambda: marker.write_text("/wrong/root\n", encoding="utf-8"),
            "extra-newline": lambda: marker.write_text(
                f"{self.root.resolve()}\n\n", encoding="utf-8"
            ),
            "trailing-space": lambda: marker.write_text(
                f"{self.root.resolve()} ", encoding="utf-8"
            ),
            "symlink": lambda: (
                outside.write_text(f"{self.root.resolve()}\n", encoding="utf-8"),
                marker.unlink(),
                marker.symlink_to(outside),
            ),
        }
        for name, mutate in cases.items():
            with self.subTest(name=name):
                self._write_graph()
                mutate()
                self.assertEqual(self.payload()["state"], "unusable")

    def test_graphify_root_accepts_exact_absolute_path_without_newline(self) -> None:
        marker = self.root / "graphify-out/.graphify_root"
        marker.write_text(str(self.root.resolve()), encoding="utf-8")

        self.assertEqual(self.payload()["state"], "fresh")

    def test_nonempty_detector_coverage_gaps_are_unusable(self) -> None:
        empty_files = {
            kind: [] for kind in ("code", "document", "paper", "image", "video")
        }
        base = {
            "files": empty_files,
            "new_files": empty_files,
            "deleted_files": [],
            "excluded_files": [],
            "unclassified": [],
            "walk_errors": [],
            "skipped_sensitive": [],
            "scan_root": str(self.root.resolve()),
        }
        for field in ("unclassified", "walk_errors", "skipped_sensitive"):
            with self.subTest(field=field):
                result = {**base, field: ["coverage-gap"]}
                with self.assertRaisesRegex(ValueError, field):
                    _detector_stale_sources(self.root, result, base)

        unhandled = {
            **base,
            "new_files": {**empty_files, "audio": []},
        }
        with self.assertRaisesRegex(ValueError, "new_files"):
            _detector_stale_sources(self.root, unhandled, base)

        benign_metadata = {
            **base,
            "ignored": ["ignored.txt"],
            "pruned_noise_dirs": ["cache"],
            "total_files": 0,
            "warning": "informational",
        }
        self.assertEqual(
            _detector_stale_sources(self.root, benign_metadata, benign_metadata), []
        )


if __name__ == "__main__":
    unittest.main()
