#!/usr/bin/env python3
"""Hermetic contract tests for the upstream-first Graphify freshness gate."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
CHECKER = ROOT / "scripts/check_graphify_freshness.py"
sys.path.insert(0, str(ROOT / "scripts"))
import check_graphify_freshness as freshness  # noqa: E402
from check_graphify_freshness import _detector_stale_sources  # noqa: E402


def _clean_detector_payload(root: Path) -> dict[str, object]:
    empty_files = {kind: [] for kind in ("code", "document", "paper", "image", "video")}
    return {
        "files": empty_files,
        "new_files": empty_files,
        "deleted_files": [],
        "excluded_files": [],
        "unclassified": [],
        "walk_errors": [],
        "skipped_sensitive": [],
        "scan_root": str(root.resolve()),
    }


def _clean_snapshot_detector(
    scan_root: Path, **_: object
) -> tuple[dict[str, object], dict[str, object]]:
    detector = _clean_detector_payload(scan_root)
    return detector, detector


def _graphify_out_bytes(root: Path) -> dict[Path, bytes]:
    output = root / "graphify-out"
    return {
        path.relative_to(output): path.read_bytes()
        for path in output.rglob("*")
        if path.is_file() and not path.is_symlink()
    }


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
    if result.returncode or result.stdout.strip() != "0.9.48":
        raise RuntimeError("Graphify 0.9.48 is required for freshness tests")
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
            check=False,
        )

    def payload(self) -> dict[str, object]:
        result = self.run_checker("--json")
        return json.loads(result.stdout)

    def test_fresh_and_detector_does_not_mutate_graphify_artifacts(self) -> None:
        before = _graphify_out_bytes(self.root)
        result = self.run_checker("--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.payload()["state"], "fresh")
        self.assertEqual(_graphify_out_bytes(self.root), before)

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

    def test_ancestor_snapshot_without_detector_drift_is_fresh(
        self,
    ) -> None:
        subprocess.run(
            ["git", "commit", "--allow-empty", "-qm", "later"],
            cwd=self.root,
            check=True,
        )

        with mock.patch.object(
            freshness,
            "_detect_incremental",
            side_effect=_clean_snapshot_detector,
        ):
            payload = freshness.check(self.root)
        self.assertEqual(payload["state"], "fresh", payload)
        self.assertEqual(payload["stale_sources"], [])

    def test_nonancestor_same_tree_snapshot_is_fresh(self) -> None:
        tree = self.git("rev-parse", f"{self.head}^{{tree}}")
        rebased = subprocess.run(
            ["git", "commit-tree", tree, "-m", "same tree rebase"],
            cwd=self.root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        subprocess.run(
            ["git", "update-ref", "HEAD", rebased], cwd=self.root, check=True
        )

        with mock.patch.object(
            freshness, "_detect_incremental", side_effect=_clean_snapshot_detector
        ):
            payload = freshness.check(self.root)
        self.assertEqual(payload["state"], "fresh", payload)
        self.assertEqual(payload["next_action"], 'graphify query "<question>"')

    def test_legacy_missing_projection_revision_fails_with_exact_repair_command(
        self,
    ) -> None:
        index = self.root / "graphify-input/index.md"
        index.write_text(
            index.read_text(encoding="utf-8").replace(
                f"source_revision: {self.head}\n",
                "source_revision: deadbeef\n",
            ),
            encoding="utf-8",
        )

        payload = self.payload()
        self.assertEqual(payload["state"], "unusable", payload)
        self.assertEqual(payload["next_action"], "git fetch --all --prune")
        self.assertIn("git fetch --all --prune", payload["reasons"][-1])

    def test_revision_identity_requires_existing_commit_object(self) -> None:
        tree = self.git("rev-parse", f"{self.head}^{{tree}}")
        subprocess.run(
            ["git", "tag", "-a", "-m", "annotated", "v-identity", self.head],
            cwd=self.root,
            check=True,
        )
        tag = self.git("rev-parse", "v-identity^{tag}")
        for label, revision in (
            ("symbolic-head", "HEAD"),
            ("tree", tree),
            ("tag", tag),
            ("missing", "0" * 40),
        ):
            with self.subTest(label=label):
                index = self.root / "graphify-input/index.md"
                index.write_text(
                    index.read_text(encoding="utf-8").replace(
                        f"source_revision: {self.head}\n",
                        f"source_revision: {revision}\n",
                    ),
                    encoding="utf-8",
                )
                payload = self.payload()
                self.assertEqual(payload["state"], "unusable", payload)
                expected_reason = "full OID" if label == "symbolic-head" else "commit"
                self.assertIn(expected_reason, " ".join(payload["reasons"]))
                index.write_text(
                    index.read_text(encoding="utf-8").replace(
                        f"source_revision: {revision}\n",
                        f"source_revision: {self.head}\n",
                    ),
                    encoding="utf-8",
                )

    def test_merge_base_operational_error_is_not_treated_as_nonancestor(self) -> None:
        result = subprocess.CompletedProcess(
            ["git", "merge-base"], 2, "", "fatal: unavailable"
        )
        with mock.patch.object(freshness.subprocess, "run", return_value=result):
            with self.assertRaisesRegex(ValueError, "merge-base failed"):
                freshness._is_ancestor(self.root, self.head, self.head)

    def test_malicious_interpreter_marker_is_not_executed(self) -> None:
        marker = self.root / "graphify-out/.graphify_python"
        executed = self.root / "marker-executed"
        malicious = self.root / "malicious-interpreter"
        malicious.write_text(f"#!/usr/bin/env sh\ntouch {executed}\n", encoding="utf-8")
        malicious.chmod(0o755)
        marker.write_text(f"{malicious}\n", encoding="utf-8")
        payload = self.payload()
        self.assertEqual(payload["state"], "unusable", payload)
        self.assertIn("inside repository", " ".join(payload["reasons"]))
        self.assertFalse(executed.exists())

    def test_relative_interpreter_marker_is_rejected(self) -> None:
        marker = self.root / "graphify-out/.graphify_python"
        marker.write_text("python3\n", encoding="utf-8")

        payload = self.payload()

        self.assertEqual(payload["state"], "unusable", payload)
        self.assertIn("invalid Graphify interpreter marker", payload["reasons"])

    def test_repo_local_graphify_shadow_is_not_imported(self) -> None:
        executed = self.root / "graphify-shadow-executed"
        (self.root / "graphify.py").write_text(
            f"from pathlib import Path\nPath({str(executed)!r}).touch()\n",
            encoding="utf-8",
        )

        with mock.patch.dict(
            os.environ,
            {"PYTHONPATH": str(self.root)},
        ):
            payload = self.payload()

        self.assertNotEqual(payload["state"], "unusable", payload)
        self.assertFalse(executed.exists())

    def test_repo_local_graphify_cli_is_not_executed(self) -> None:
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        executed = self.root / "graphify-cli-executed"
        cli = bin_dir / "graphify"
        cli.write_text(f"#!/bin/sh\ntouch {executed}\n", encoding="utf-8")
        cli.chmod(0o755)
        with mock.patch.dict(
            os.environ,
            {"PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"},
        ):
            payload = self.payload()

        self.assertEqual(payload["state"], "unusable", payload)
        self.assertIn("inside repository", " ".join(payload["reasons"]))
        self.assertFalse(executed.exists())

    def test_unresolved_cli_shebang_inside_repository_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix=f"{self.root.name}-bin-", dir=self.root.parent
        ) as bin_tmp:
            bin_dir = Path(bin_tmp)
            cli = bin_dir / "graphify"
            cli.write_text(
                f"#!{self.root / 'missing-graphify-python'}\n", encoding="utf-8"
            )
            cli.chmod(0o755)
            with mock.patch.dict(
                os.environ,
                {"PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"},
            ):
                payload = self.payload()

        self.assertEqual(payload["state"], "unusable", payload)
        self.assertIn("inside repository", " ".join(payload["reasons"]))

    def test_recorded_source_tree_cannot_override_resolvable_revision_tree(
        self,
    ) -> None:
        index = self.root / "graphify-input/index.md"
        index.write_text(
            index.read_text(encoding="utf-8").replace(
                f"source_revision: {self.head}\n",
                f"source_revision: {self.head}\nsource_tree: {'0' * 40}\n",
            ),
            encoding="utf-8",
        )

        payload = self.payload()
        self.assertEqual(payload["state"], "unusable", payload)
        self.assertIn("does not match", payload["reasons"][-1])

    def test_same_tree_admission_still_reports_tracked_byte_drift(self) -> None:
        tree = self.git("rev-parse", f"{self.head}^{{tree}}")
        rebased = subprocess.run(
            ["git", "commit-tree", tree, "-m", "same tree rebase"],
            cwd=self.root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        subprocess.run(
            ["git", "update-ref", "HEAD", rebased], cwd=self.root, check=True
        )
        (self.root / "src/example.py").write_text(
            "def example(): return 2\n", encoding="utf-8"
        )

        payload = self.payload()
        self.assertNotEqual(payload["state"], "fresh", payload)
        self.assertIn("src/example.py", payload["stale_sources"])

    def test_nonancestor_ignored_plan_change_is_fresh_from_corpus_identity(
        self,
    ) -> None:
        ignored = self.root / ".omx/plans/plan.md"
        ignored.parent.mkdir(parents=True, exist_ok=True)
        ignored.write_text("first\n", encoding="utf-8")
        (self.root / ".graphifyignore").write_text(".omx/**\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=self.root, check=True)
        subprocess.run(
            ["git", "commit", "-qm", "ignored baseline"], cwd=self.root, check=True
        )
        self._write_projection()
        self._write_graph()
        self._save_upstream_manifest()
        ignored.write_text("second\n", encoding="utf-8")
        subprocess.run(["git", "add", str(ignored)], cwd=self.root, check=True)
        tree = self.git("write-tree")
        rebased = subprocess.run(
            ["git", "commit-tree", tree, "-m", "ignored plan rebase"],
            cwd=self.root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        subprocess.run(
            ["git", "update-ref", "HEAD", rebased], cwd=self.root, check=True
        )

        with mock.patch.object(
            freshness, "_detect_incremental", side_effect=_clean_snapshot_detector
        ):
            payload = freshness.check(self.root)
        self.assertEqual(payload["state"], "fresh", payload)

    def test_nonancestor_admitted_source_change_is_unusable(self) -> None:
        source = self.root / "src/example.py"
        source.write_text("def example(): return 2\n", encoding="utf-8")
        subprocess.run(["git", "add", str(source)], cwd=self.root, check=True)
        tree = self.git("write-tree")
        rebased = subprocess.run(
            ["git", "commit-tree", tree, "-m", "source rebase"],
            cwd=self.root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        subprocess.run(
            ["git", "update-ref", "HEAD", rebased], cwd=self.root, check=True
        )

        payload = self.payload()
        self.assertEqual(payload["state"], "unusable", payload)
        self.assertIn("src/example.py", payload["stale_sources"])
        self.assertEqual(payload["next_action"], freshness.STALE_ACTION)

    def test_nonancestor_committed_source_drift_is_seen_after_worktree_restore(
        self,
    ) -> None:
        source = self.root / "src/example.py"
        original = source.read_bytes()
        source.write_text("def example(): return 2\n", encoding="utf-8")
        subprocess.run(["git", "add", str(source)], cwd=self.root, check=True)
        tree = self.git("write-tree")
        rebased = subprocess.run(
            ["git", "commit-tree", tree, "-m", "committed source drift"],
            cwd=self.root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        subprocess.run(
            ["git", "update-ref", "HEAD", rebased], cwd=self.root, check=True
        )
        source.write_bytes(original)
        before_head = self.git("rev-parse", "HEAD")
        before_status = self.git("status", "--porcelain=v1", "--untracked-files=all")
        before_graphify_out = _graphify_out_bytes(self.root)

        payload = self.payload()

        self.assertEqual(payload["state"], "unusable", payload)
        self.assertIn("src/example.py", payload["stale_sources"])
        self.assertEqual(self.git("rev-parse", "HEAD"), before_head)
        self.assertEqual(
            self.git("status", "--porcelain=v1", "--untracked-files=all"),
            before_status,
        )
        self.assertEqual(
            before_graphify_out,
            _graphify_out_bytes(self.root),
        )

    def test_head_snapshot_reads_raw_git_blobs_without_worktree_filters(self) -> None:
        asset = self.root / "ignored-large.bin"
        pointer = b"version https://git-lfs.github.com/spec/v1\noid sha256:deadbeef\n"
        asset.write_bytes(pointer)
        (self.root / ".gitattributes").write_text(
            "ignored-large.bin filter=sentinel\n", encoding="utf-8"
        )
        (self.root / "linked-asset").symlink_to(asset.name)
        subprocess.run(["git", "add", "."], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-qm", "filtered asset"], cwd=self.root, check=True)
        marker = self.root / "filter-ran"
        subprocess.run(
            [
                "git",
                "config",
                "filter.sentinel.smudge",
                f"sh -c 'touch {marker}; cat'",
            ],
            cwd=self.root,
            check=True,
        )

        snapshot = freshness._raw_commit_snapshot(
            self.root,
            self.git("rev-parse", "HEAD"),
            self.root / "graphify-input",
        )
        try:
            self.assertEqual((Path(snapshot.name) / asset.name).read_bytes(), pointer)
            self.assertFalse((Path(snapshot.name) / "linked-asset").exists())
            self.assertFalse(marker.exists())
        finally:
            snapshot.cleanup()

    def test_same_tree_admission_rejects_excluded_tracked_byte_drift(self) -> None:
        tree = self.git("rev-parse", f"{self.head}^{{tree}}")
        rebased = subprocess.run(
            ["git", "commit-tree", tree, "-m", "same tree rebase"],
            cwd=self.root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        subprocess.run(
            ["git", "update-ref", "HEAD", rebased], cwd=self.root, check=True
        )
        (self.root / ".graphifyignore").write_text("src/example.py\n", encoding="utf-8")
        (self.root / "src/example.py").write_text(
            "def example(): return 2\n", encoding="utf-8"
        )

        payload = self.payload()
        self.assertEqual(payload["state"], "unusable", payload)
        self.assertTrue(
            any(
                "Graphify detector reported" in reason for reason in payload["reasons"]
            ),
            payload,
        )

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
