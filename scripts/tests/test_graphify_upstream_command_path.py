#!/usr/bin/env python3
"""Exercise the installed Graphify 0.9.48 extract command through its CLI entry."""

from __future__ import annotations

from contextlib import contextmanager
import io
from importlib.metadata import version
from pathlib import Path
import shutil
import sys
import subprocess
import tempfile
import unittest
from unittest import mock


GRAPHIFY_BIN = shutil.which("graphify")
if GRAPHIFY_BIN:
    GRAPHIFY_PYTHON = Path(Path(GRAPHIFY_BIN).read_text(encoding="utf-8").splitlines()[0][2:])
    PACKAGE_ROOT = subprocess.check_output(
        [str(GRAPHIFY_PYTHON), "-c", "import graphify; print(graphify.__file__)"],
        text=True,
    ).strip()
    sys.path.insert(0, str(Path(PACKAGE_ROOT).parent.parent))

try:
    import graphify.__main__ as graphify_main  # noqa: E402
    from graphify import cache as graphify_cache  # noqa: E402
    from graphify import llm as graphify_llm  # noqa: E402
except ImportError as error:  # pragma: no cover - depends on test environment
    raise unittest.SkipTest(f"pinned Graphify CLI unavailable: {error}")


class PinnedGraphifyCommandPathTests(unittest.TestCase):
    def setUp(self) -> None:
        self.assertEqual(version("graphifyy"), "0.9.48")
        self.cache_directories: list[Path] = []
        self.lookup: list[dict] = []
        self.saves: list[dict] = []
        self.dispatches: list[dict] = []

    @contextmanager
    def command(self, root: Path, *, mode: str | None = None):
        original_lookup = graphify_cache.check_semantic_cache
        original_save = graphify_cache.save_semantic_cache
        original_cache_dir = graphify_cache.cache_dir

        def cache_dir(*args, **kwargs):
            resolved = original_cache_dir(*args, **kwargs)
            self.cache_directories.append(Path(resolved).resolve())
            return resolved

        def lookup(*args, **kwargs):
            self.lookup.append({"mode": kwargs.get("mode"), "prompt": kwargs.get("prompt")})
            return original_lookup(*args, **kwargs)

        def save(*args, **kwargs):
            self.saves.append({"mode": kwargs.get("mode"), "prompt": kwargs.get("prompt")})
            return original_save(*args, **kwargs)

        def extract(files, **kwargs):
            paths = [str(Path(path).resolve()) for path in files]
            self.dispatches.append({"paths": paths, "deep": kwargs.get("deep_mode", False)})
            result = {
                "nodes": [
                    {"id": f"semantic:{Path(path).name}", "label": Path(path).stem,
                     "source_file": path}
                    for path in paths
                ],
                "edges": [],
                "hyperedges": [],
                "input_tokens": 1,
                "output_tokens": 1,
                "failed_chunks": 0,
            }
            callback = kwargs.get("on_chunk_done")
            if callback:
                callback(0, 1, result)
            return result

        argv = ["graphify", "extract", str(root), "--no-viz", "--no-cluster"]
        if mode:
            argv.extend(("--mode", mode))
        with (
            mock.patch.object(graphify_cache, "cache_dir", side_effect=cache_dir),
            mock.patch.object(graphify_cache, "check_semantic_cache", side_effect=lookup),
            mock.patch.object(graphify_cache, "save_semantic_cache", side_effect=save),
            mock.patch.object(graphify_llm, "extract_corpus_parallel", side_effect=extract),
            mock.patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}, clear=False),
            mock.patch.object(sys, "argv", argv),
            mock.patch.object(sys, "stdout", new_callable=io.StringIO) as mock_stdout,
            mock.patch.object(sys, "stderr", new_callable=io.StringIO) as mock_stderr,
        ):
            try:
                graphify_main.main()
            except SystemExit as error:
                if error.code not in (None, 0):
                    raise AssertionError(mock_stdout.getvalue() + mock_stderr.getvalue()) from error
            yield

    def project(self) -> Path:
        root = Path(tempfile.mkdtemp(prefix="graphify-command-path-"))
        (root / "docs").mkdir()
        (root / "docs/a.md").write_text("# A\nalpha\n", encoding="utf-8")
        (root / "docs/b.md").write_text("# B\nbeta\n", encoding="utf-8")
        return root

    def assert_cache_namespace(self, root: Path, name: str) -> None:
        expected = (root / "graphify-out/cache" / name).resolve()
        self.assertTrue(self.cache_directories)
        self.assertTrue(
            all(path.is_relative_to(expected) for path in self.cache_directories),
            self.cache_directories,
        )

    def test_warm_standard_command_dispatches_zero_files(self) -> None:
        root = self.project()
        with self.command(root):
            first = list(self.dispatches)
        first_lookup = list(self.lookup)
        first_saves = list(self.saves)
        self.assert_cache_namespace(root, "semantic")
        self.dispatches.clear()
        self.lookup.clear()
        self.cache_directories.clear()
        with self.command(root):
            pass
        self.assertTrue(first)
        self.assertEqual(self.dispatches, [])
        self.assertEqual({entry["mode"] for entry in first_lookup}, {None})
        self.assertEqual(
            {entry["mode"] for entry in first_saves},
            {None},
        )
        self.assertEqual(
            {graphify_cache.prompt_fingerprint(entry["prompt"]) for entry in first_lookup},
            {graphify_cache.prompt_fingerprint(entry["prompt"]) for entry in first_saves},
        )

    def test_changed_semantic_input_dispatches_only_that_file(self) -> None:
        root = self.project()
        with self.command(root):
            pass
        self.dispatches.clear()
        (root / "docs/a.md").write_text("# A\nchanged\n", encoding="utf-8")
        with self.command(root):
            pass
        self.assertEqual(self.dispatches[0]["paths"], [str((root / "docs/a.md").resolve())])

    def test_deep_mode_isolated_from_standard_namespace_and_warms(self) -> None:
        root = self.project()
        with self.command(root):
            pass
        legacy = graphify_cache.cache_dir(root, "semantic") / (
            f"{graphify_cache.file_hash(root / 'docs/a.md', root)}.json"
        )
        legacy.parent.mkdir(parents=True, exist_ok=True)
        legacy.write_text(
            '{"nodes": [{"id": "legacy", "source_file": "docs/a.md"}], '
            '"edges": [], "hyperedges": []}',
            encoding="utf-8",
        )
        self.dispatches.clear()
        self.lookup.clear()
        self.saves.clear()
        self.cache_directories.clear()
        with self.command(root, mode="deep"):
            pass
        self.assertTrue(self.dispatches)
        self.assertEqual(
            {path for dispatch in self.dispatches for path in dispatch["paths"]},
            {str((root / "docs/a.md").resolve()), str((root / "docs/b.md").resolve())},
        )
        self.assertEqual({item["deep"] for item in self.dispatches}, {True})
        self.assertEqual({item["mode"] for item in self.lookup}, {"deep"})
        self.assertEqual({item["mode"] for item in self.saves}, {"deep"})
        self.assert_cache_namespace(root, "semantic-deep")
        self.assertEqual(
            {graphify_cache.prompt_fingerprint(item["prompt"]) for item in self.lookup},
            {graphify_cache.prompt_fingerprint(item["prompt"]) for item in self.saves},
        )
        self.dispatches.clear()
        self.lookup.clear()
        self.saves.clear()
        self.cache_directories.clear()
        with self.command(root, mode="deep"):
            pass
        self.assertEqual(self.dispatches, [])
        self.assertEqual({item["mode"] for item in self.lookup}, {"deep"})
        self.assertEqual(self.saves, [])
        self.assert_cache_namespace(root, "semantic-deep")


if __name__ == "__main__":
    unittest.main()
