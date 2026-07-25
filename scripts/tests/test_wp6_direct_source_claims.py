#!/usr/bin/env python3
"""Exercise the fixed WP6 direct-source claim-checklist fixtures."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = ROOT / "scripts/tests/fixtures/wp6_direct_source"
MANIFEST = FIXTURE_ROOT / "claims.json"
REQUIRED_EVIDENCE = {
    "claim_id",
    "claim_text",
    "citation_key",
    "source_path",
    "source_digest",
    "locator_type",
    "locator_value",
    "extracted_support",
    "wording_verdict",
    "expected_reason",
    "actual_reason",
    "touched_output_paths",
    "render_command",
    "render_digest",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    fixtures = manifest["fixtures"]
    assert [row["id"] for row in fixtures] == [
        "supported_exact",
        "overstated_generalization",
        "missing_citation",
        "missing_locator",
    ]

    bib_text = (FIXTURE_ROOT / "refs.bib").read_text(encoding="utf-8")
    bib_keys = set(re.findall(r"@\w+\s*\{\s*([^,\s]+)", bib_text))
    source_text = (FIXTURE_ROOT / "source.tex").read_text(encoding="utf-8")
    support = "The planner evaluates a finite candidate set for each observed scene."
    assert support in source_text

    typst = shutil.which("typst")
    assert typst, "typst is required to verify touched-surface render evidence"
    with tempfile.TemporaryDirectory(prefix="wp6-claim-") as tmp:
        rendered = Path(tmp) / "touched.pdf"
        render_command = [
            typst,
            "compile",
            str(FIXTURE_ROOT / "touched.typ"),
            str(rendered),
        ]
        subprocess.run(
            render_command, cwd=ROOT, check=True, capture_output=True, text=True
        )
        render_digest = digest(rendered)

        evidence = []
        for row in fixtures:
            if row["citation_key"] not in bib_keys:
                reason = "citation_unresolved"
            elif not row["locator_type"] or not row["locator_value"]:
                reason = "locator_required"
            elif "optimal for all scenes" in row["claim_text"].lower():
                reason = "wording_exceeds_source"
            else:
                reason = "pass"
            record = {
                "claim_id": row["id"],
                "claim_text": row["claim_text"],
                "citation_key": row["citation_key"],
                "source_path": row["source_path"],
                "source_digest": digest(ROOT / row["source_path"]),
                "locator_type": row["locator_type"],
                "locator_value": row["locator_value"],
                "extracted_support": support,
                "wording_verdict": "calibrated" if reason == "pass" else "rejected",
                "expected_reason": row["expected_reason"],
                "actual_reason": reason,
                "touched_output_paths": [
                    "scripts/tests/fixtures/wp6_direct_source/touched.typ"
                ],
                "render_command": " ".join(render_command),
                "render_digest": render_digest,
            }
            assert set(record) == REQUIRED_EVIDENCE
            assert record["actual_reason"] == record["expected_reason"]
            evidence.append(record)

        evidence_path = Path(tmp) / "evidence.json"
        evidence_path.write_text(
            json.dumps(evidence, indent=2, sort_keys=True), encoding="utf-8"
        )
        assert len(json.loads(evidence_path.read_text(encoding="utf-8"))) == 4

    print("WP6 direct-source claim fixtures: PASS (4 cases)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
