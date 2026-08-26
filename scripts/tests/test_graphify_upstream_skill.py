#!/usr/bin/env python3
"""Verify that the project Graphify skill is the exact upstream bundle."""

from __future__ import annotations

import hashlib
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from skill_sources import load_manifest  # noqa: E402


ROOT = Path(__file__).resolve().parents[2]
ROOT_GUIDANCE = ROOT / "AGENTS.md"
TARGET_STATE = (
    ROOT / ".omx/specs/deep-interview-aria-nbv-agent-scaffold-target-state.md"
)
SKILL_ROOT = ROOT / ".agents/skills/graphify"
CONTEXT_SKILL = ROOT / ".agents/skills/aria-nbv-context/SKILL.md"
ARIA_BOUNDARY = (
    ROOT / ".agents/skills/aria-nbv-context/references/graphify-aria-boundary.md"
)
EXPECTED_UPSTREAM_COMMIT = "b2cd36267456c166788c95be6e68574064a92a42"
GRAPHIFY_SOURCE = next(
    source for source in load_manifest() if source.id == "graphify-skill-bundle"
)
UPSTREAM_COMMIT = GRAPHIFY_SOURCE.reviewed_revision
assert UPSTREAM_COMMIT == EXPECTED_UPSTREAM_COMMIT
assert GRAPHIFY_SOURCE.source_paths == ("skills/graphify",)
assert ".agents/skills/graphify" in GRAPHIFY_SOURCE.consumers
UPSTREAM_BLOBS = {
    ".graphify_version": "2d72c8d340b915a70b4c553e2a7fe6c8a9b7ea35",
    "SKILL.md": "af3f723c7878b8ca9252af511270511002086ed4",
    "references/add-watch.md": "77844343e140553b7f1bf419e32640568c2014ff",
    "references/exports.md": "242ff868e015b158504dda3ea1992e4cd9686843",
    "references/extraction-spec.md": "4b278b28d3681400286c66af4d61ca2e48bcc211",
    "references/github-and-merge.md": "a41ea06e17c1676483356a2a06504a1bfb0870e4",
    "references/hooks.md": "438b8b16be18480a1e77759b3e74fc8a9e97eae7",
    "references/query.md": "56565eb782951a1f0e1279f851b8a022292f3ac3",
    "references/transcribe.md": "b967f8379998b890945706b3c95fef23b2ec402f",
    "references/update.md": "3632fd41266964bdcf04b58d4359f9364cedfbce",
}


def _git_blob_id(content: bytes) -> str:
    header = f"blob {len(content)}\0".encode()
    return hashlib.sha1(header + content, usedforsecurity=False).hexdigest()


class UpstreamGraphifySkillTests(unittest.TestCase):
    def test_bundle_is_byte_identical_to_declared_upstream_commit(self) -> None:
        actual_files = {
            path.relative_to(SKILL_ROOT).as_posix()
            for path in SKILL_ROOT.rglob("*")
            if path.is_file() and "__pycache__" not in path.parts
        }
        self.assertEqual(
            actual_files,
            set(UPSTREAM_BLOBS),
            f"unexpected Graphify skill surface for upstream {UPSTREAM_COMMIT}",
        )
        for relative, expected_blob in UPSTREAM_BLOBS.items():
            with self.subTest(relative=relative):
                self.assertEqual(
                    _git_blob_id((SKILL_ROOT / relative).read_bytes()),
                    expected_blob,
                    f"{relative} differs from Graphify {UPSTREAM_COMMIT}",
                )

    def test_aria_companion_owns_upstream_marker_compatibility(self) -> None:
        context = CONTEXT_SKILL.read_text(encoding="utf-8")
        boundary = ARIA_BOUNDARY.read_text(encoding="utf-8")
        self.assertIn("references/graphify-aria-boundary.md", context)
        self.assertIn("Graphify 0.9.48 writes `graphify-out/needs_update`", boundary)
        self.assertRegex(boundary, r"Remove\s+`graphify-out/needs_update` only after")
        self.assertIn("leave it after partial, failed, or unverified work", boundary)

    def test_hook_boundary_preserves_upstream_bytes_and_runtime_caveat(self) -> None:
        hooks = (SKILL_ROOT / "references/hooks.md").read_text(encoding="utf-8")
        boundary = ARIA_BOUNDARY.read_text(encoding="utf-8")
        self.assertIn("Doc/image changes are ignored by the hook", hooks)
        self.assertIn("AST-quick-scan changed Markdown headings", boundary)
        self.assertIn("refresh those semantic inputs explicitly", boundary)
        self.assertNotIn("marks changed documents", boundary)

    def test_mandatory_worktree_route_stays_outside_upstream_bundle(self) -> None:
        root_guidance = ROOT_GUIDANCE.read_text(encoding="utf-8")
        context = CONTEXT_SKILL.read_text(encoding="utf-8")
        boundary = ARIA_BOUNDARY.read_text(encoding="utf-8")
        upstream_skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        target_state = TARGET_STATE.read_text(encoding="utf-8")

        self.assertIn("## Graphify And Context7 Plugin", root_guidance)
        self.assertIn("scripts/setup_worktree_env.sh", boundary)
        self.assertIn("CODEX_SOURCE_WORKSPACE_PATH", boundary)
        self.assertIn("upstream incremental maintenance", boundary)
        self.assertIn("Models query the admitted graph", boundary)
        self.assertIn("## Branch Index", context)
        self.assertNotIn("## Graphify Branch", context)
        self.assertIn(
            "[`references/graphify-aria-boundary.md`](references/graphify-aria-boundary.md)",
            context,
        )
        self.assertNotIn("scripts/check_graphify_freshness.py", boundary)
        self.assertNotIn("graphify . --update", boundary)
        self.assertIn(
            "Accepted 2026-08-19 Graphify Lifecycle And Routing Supersession",
            target_state,
        )
        for state in ("fresh", "usable-stale", "unusable"):
            with self.subTest(state=state):
                self.assertIn(f"`{state}`", boundary)
        self.assertIn("graphify query", upstream_skill)
        self.assertIn("/graphify path", upstream_skill)
        self.assertIn("/graphify explain", upstream_skill)
        self.assertIn("use direct sources only", boundary)
        self.assertIn("Graphify never owns the located fact", boundary)


if __name__ == "__main__":
    unittest.main()
