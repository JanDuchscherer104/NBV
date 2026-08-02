#!/usr/bin/env python3
"""Regression tests for native debrief path portability."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_agent_memory import artifact_locator_errors  # noqa: E402


class ArtifactLocatorTests(unittest.TestCase):
    def test_current_debriefs_reject_machine_local_artifacts(self) -> None:
        for locator in (
            "/home/jd/.mempalace/palaces/aria",
            "/tmp/aria-report.pdf",
            r"C:\Users\jd\aria-report.pdf",
        ):
            with self.subTest(locator=locator):
                errors = artifact_locator_errors(
                    "history.md",
                    {"date": "2026-08-01", "artifacts": [locator]},
                )
                self.assertEqual(len(errors), 1)
                self.assertIn("portable artifact locator", errors[0])

    def test_current_debriefs_accept_portable_artifacts(self) -> None:
        errors = artifact_locator_errors(
            "history.md",
            {
                "date": "2026-08-01",
                "artifacts": [
                    "~/.mempalace/palaces/aria",
                    ".artifacts/reports/aria.pdf",
                    "palace:aria-nbv-compositional-v1",
                ],
            },
        )
        self.assertEqual(errors, [])

    def test_pre_ratchet_records_are_grandfathered(self) -> None:
        errors = artifact_locator_errors(
            "history.md",
            {"date": "2026-07-31", "artifacts": ["/home/jd/legacy"]},
        )
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
