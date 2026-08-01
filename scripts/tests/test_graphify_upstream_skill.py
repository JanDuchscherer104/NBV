#!/usr/bin/env python3
"""Verify that the project Graphify skill is the exact upstream bundle."""

from __future__ import annotations

import hashlib
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
SKILL_ROOT = ROOT / ".agents/skills/graphify"
CONTEXT_SKILL = ROOT / ".agents/skills/aria-nbv-context/SKILL.md"
UPSTREAM_COMMIT = "4fe11092ccbe9f543608f140c790f68d5d83cae4"
UPSTREAM_BLOBS = {
    ".graphify_version": "425d81acf4c7433074588660fbe9bfc32b79d1b0",
    "SKILL.md": "afb4ecc12169e247fcf65d4e5e64df5283064ef5",
    "references/add-watch.md": "77844343e140553b7f1bf419e32640568c2014ff",
    "references/exports.md": "242ff868e015b158504dda3ea1992e4cd9686843",
    "references/extraction-spec.md": "388df7674f2d25e83f87041864bbe7635aa15e75",
    "references/github-and-merge.md": "a41ea06e17c1676483356a2a06504a1bfb0870e4",
    "references/hooks.md": "3fb74d1545394154c30ee052f24da8dd07dd9e9f",
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
        self.assertIn("Graphify 0.9.31 writes the semantic-refresh marker", context)
        self.assertRegex(context, r"remove\s+`graphify-out/needs_update` only after")
        self.assertRegex(context, r"Leave the marker\s+in\s+place after any partial, failed")


if __name__ == "__main__":
    unittest.main()
