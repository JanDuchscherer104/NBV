#!/usr/bin/env python3
"""Verify that WP6 preserves the tracked literature source owners byte-for-byte."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "docs/literature/sources.jsonl"
BIBLIOGRAPHY = ROOT / "docs/references.bib"
EXPECTED_MANIFEST_SHA256 = (
    "48b37df12e76090ca2653647438c6339f8a60343a87f82a6f3cae0248807fddc"
)
EXPECTED_BIBLIOGRAPHY_SHA256 = (
    "813490008843162a5961b397ba5e4586e7e8796cb7fb7cc5a968e70ebb0751ca"
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    assert digest(MANIFEST) == EXPECTED_MANIFEST_SHA256
    assert digest(BIBLIOGRAPHY) == EXPECTED_BIBLIOGRAPHY_SHA256
    rows = [
        json.loads(line)
        for line in MANIFEST.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == 44
    for row in rows:
        tex_dir = ROOT / "docs/literature/tex-src" / row["tex_dir"]
        assert tex_dir.is_dir(), f"missing TeX mirror: {tex_dir}"
        assert any(path.is_file() for path in tex_dir.rglob("*")), (
            f"empty TeX mirror: {tex_dir}"
        )
    public_pages = list((ROOT / "docs/contents/literature").glob("*.qmd"))
    assert len(public_pages) >= 10
    print(
        f"WP6 literature owners: PASS ({len(rows)} manifest rows, {len(public_pages)} public pages)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
