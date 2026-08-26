#!/usr/bin/env python3
"""Exercise real linked-worktree Graphify admission with the pinned CLI."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest


ROOT = Path(__file__).resolve().parents[2]
def graphify_interpreter() -> Path:
    cli = Path(shutil.which("graphify") or "").resolve()
    if not cli.is_file():
        raise RuntimeError("Graphify CLI is required for the session-readiness test")
    return Path(cli.read_text(encoding="utf-8").splitlines()[0][2:])


class GraphifySessionReadinessTests(unittest.TestCase):
    def test_parentless_setup_rejects_an_unadmitted_primary(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aria-graphify-session-") as temporary:
            parent = Path(temporary) / "parent"
            child = Path(temporary) / "child"
            for relative in (
                "aria_nbv/.venv/bin",
                ".data/semantic",
                ".data/semantic-deep",
                "docs/thesis",
                "scripts",
                ".codex/environments",
            ):
                (parent / relative).mkdir(parents=True, exist_ok=True)
            (parent / ".gitignore").write_text(
                ".data/\naria_nbv/.venv/\n",
                encoding="utf-8",
            )
            (parent / "aria_nbv/.gitkeep").write_text("", encoding="utf-8")
            shutil.copy2(ROOT / ".graphifyignore", parent / ".graphifyignore")
            for script in (
                "setup_worktree_env.sh",
                "setup_codex_worktree_env.sh",
                "graphify_worktree_seed.py",
                "reconcile_graphify_worktree.py",
                "check_graphify_freshness.py",
            ):
                shutil.copy2(ROOT / "scripts" / script, parent / "scripts" / script)
            shutil.copy2(
                ROOT / ".codex/environments/aria-nbv.toml",
                parent / ".codex/environments/aria-nbv.toml",
            )
            (parent / "scripts/build_graphify_projection.py").write_text(
                "#!/usr/bin/env python3\n"
                "# Hermetic fixture: the parent projection already matches HEAD.\n",
                encoding="utf-8",
            )
            (parent / ".env.example").write_text("", encoding="utf-8")
            owner = parent / "docs/thesis/main.md"
            owner.write_text("fixture\n", encoding="utf-8")
            python = parent / "aria_nbv/.venv/bin/python"
            python.symlink_to(Path(sys.executable))
            self.git(parent, "init", "-q")
            self.git(parent, "config", "user.email", "test@example.invalid")
            self.git(parent, "config", "user.name", "Test")
            self.git(parent, "add", ".")
            self.git(parent, "commit", "-qm", "seed")
            head = self.git_output(parent, "rev-parse", "HEAD")
            self.write_parent_graph(parent, head)
            (parent / "graphify-out/needs_update").write_text(
                "semantic refresh required\n", encoding="utf-8"
            )
            self.git(parent, "worktree", "add", "-qb", "session-child", str(child))

            environment = tomllib.loads(
                (parent / ".codex/environments/aria-nbv.toml").read_text(
                    encoding="utf-8"
                )
            )
            bridge = environment["setup"]["script"].strip()
            self.assertEqual(
                bridge,
                'bash "$CODEX_WORKTREE_PATH/scripts/setup_codex_worktree_env.sh"',
            )
            result = subprocess.run(
                ["bash", "-c", bridge],
                cwd=child,
                env={
                    **os.environ,
                    "CODEX_WORKTREE_PATH": str(child),
                    "CODEX_SOURCE_WORKSPACE_PATH": "",
                },
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                "no query-admissible registered Graphify parent",
                result.stderr,
            )
            self.assertFalse((child / "graphify-out").exists())
            self.assertFalse((child / "graphify-input").exists())

    def git(self, root: Path, *args: str) -> None:
        subprocess.run(["git", *args], cwd=root, check=True)

    def git_output(self, root: Path, *args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=root, check=True, capture_output=True, text=True
        ).stdout.strip()

    def write_parent_graph(self, parent: Path, head: str) -> None:
        projection = parent / "graphify-input/index.md"
        projection.parent.mkdir()
        digest = hashlib.sha256((parent / "docs/thesis/main.md").read_bytes()).hexdigest()
        projection.write_text(
            "---\nowner: generated\n---\n# fixture\n"
            f"source_revision: {head}\nowner_worktree_state: clean\n\n"
            "## Owner digests\n\n"
            f"- docs/thesis/main.md: sha256:{digest}\n\n## Families\n",
            encoding="utf-8",
        )
        output = parent / "graphify-out"
        output.mkdir()
        (output / "graph.json").write_text(
            json.dumps(
                {
                    "built_at_commit": head,
                    "nodes": [
                        {
                            "id": "graphify_input_index",
                            "label": "index.md",
                            "file_type": "document",
                            "source_file": "graphify-input/index.md",
                            "source_location": "L1",
                            "_origin": "ast",
                        }
                    ],
                    "links": [],
                }
            ),
            encoding="utf-8",
        )
        interpreter = graphify_interpreter()
        (output / ".graphify_python").write_text(f"{interpreter}\n", encoding="utf-8")
        (output / ".graphify_root").write_text(f"{parent}\n", encoding="utf-8")
        program = """
import sys
from pathlib import Path
from graphify.detect import detect, save_manifest
root = Path(sys.argv[1])
result = detect(root, follow_symlinks=False, google_workspace=False)
save_manifest(
    result['files'], manifest_path=root / 'graphify-out/manifest.json', root=root,
    scan_corpus={path for paths in result['files'].values() for path in paths},
)
        """
        subprocess.run([str(interpreter), "-c", program, str(parent)], check=True)
        manifest_path = output / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["graphify-input/index.md"] = {"semantic_hash": "fixture"}
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        cache = output / "cache"
        cache.mkdir(exist_ok=True)
        for name in ("semantic", "semantic-deep"):
            (cache / name).symlink_to(parent / ".data" / name, target_is_directory=True)


if __name__ == "__main__":
    unittest.main()
