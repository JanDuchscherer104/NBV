#!/usr/bin/env python3
"""Validate the canonical thesis-development roadmap and its Typst projection."""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import tomllib
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[2]
ROADMAP_DATA = ROOT / "docs/typst/thesis/development/roadmap.toml"
ROADMAP_TYP = ROOT / "docs/typst/thesis/development/roadmap.typ"
MAIN_TYP = ROOT / "docs/typst/thesis/main.typ"
METADATA_TYP = ROOT / "docs/typst/thesis/metadata.typ"
ALLOWED_MILESTONE_STATES = {"done", "in-progress", "planned", "buffer"}
EXPECTED_SNAPSHOT_KINDS = {"done", "now", "blocked", "next"}
OBSOLETE_REPORT = "m1-" + "contract-report"


def _require_keys(record: dict[str, object], keys: set[str], owner: str) -> None:
    missing = keys - record.keys()
    assert not missing, f"{owner} is missing keys: {sorted(missing)}"


def _local_pointer_exists(pointer: str) -> bool:
    parsed = urlparse(pointer)
    if parsed.scheme in {"http", "https"}:
        return True
    return (ROOT / pointer).exists()


def _query_metadata(selector: str) -> list[object]:
    command = [
        os.environ.get("TYPST", "typst"),
        "query",
        "--root",
        "docs",
        str(ROADMAP_TYP),
        selector,
        "--field",
        "value",
    ]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        output = "\n".join(part for part in (result.stdout, result.stderr) if part)
        raise AssertionError(f"roadmap Typst query failed:\n{output}")
    values = json.loads(result.stdout)
    return values if isinstance(values, list) else [values]


def _compile_roadmap() -> None:
    with tempfile.TemporaryDirectory(prefix="aria-nbv-roadmap-") as temp:
        output = Path(temp) / "roadmap.pdf"
        result = subprocess.run(
            [
                os.environ.get("TYPST", "typst"),
                "compile",
                "--root",
                "docs",
                str(ROADMAP_TYP),
                str(output),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            details = "\n".join(part for part in (result.stdout, result.stderr) if part)
            raise AssertionError(f"roadmap Typst compile failed:\n{details}")


def _submission_date_from_metadata() -> date:
    text = METADATA_TYP.read_text(encoding="utf-8")
    match = re.search(
        r"#let submissionDate = datetime\(day:\s*(\d+),\s*month:\s*(\d+),\s*year:\s*(\d+)\)",
        text,
    )
    assert match is not None, "could not resolve submissionDate from metadata.typ"
    day, month, year = (int(value) for value in match.groups())
    return date(year, month, day)


def main() -> None:
    with ROADMAP_DATA.open("rb") as stream:
        roadmap = tomllib.load(stream)

    _require_keys(
        roadmap,
        {"meta", "snapshot", "milestones", "blockers", "promotions"},
        "roadmap",
    )
    meta = roadmap["meta"]
    assert isinstance(meta, dict)
    _require_keys(
        meta,
        {
            "reviewed_at",
            "review_due",
            "review_cadence_days",
            "current_milestone",
            "complete_by",
            "submission_date",
        },
        "roadmap.meta",
    )
    reviewed_at = meta["reviewed_at"]
    review_due = meta["review_due"]
    complete_by = meta["complete_by"]
    submission_date = meta["submission_date"]
    assert all(
        isinstance(value, date)
        for value in (reviewed_at, review_due, complete_by, submission_date)
    )
    cadence = int(meta["review_cadence_days"])
    assert cadence > 0
    assert review_due == reviewed_at + timedelta(days=cadence)
    as_of = date.fromisoformat(
        os.environ.get("ROADMAP_AS_OF", date.today().isoformat())
    )
    assert reviewed_at <= as_of, f"roadmap review date {reviewed_at} is in the future"
    assert as_of <= review_due, (
        f"roadmap is stale: reviewed {reviewed_at}, due {review_due}, today {as_of}"
    )
    assert complete_by < submission_date
    assert submission_date == _submission_date_from_metadata()

    snapshot = roadmap["snapshot"]
    assert isinstance(snapshot, list)
    assert len(snapshot) == len(EXPECTED_SNAPSHOT_KINDS)
    snapshot_kinds = [entry["kind"] for entry in snapshot]
    assert len(snapshot_kinds) == len(set(snapshot_kinds)), "duplicate snapshot kinds"
    assert set(snapshot_kinds) == EXPECTED_SNAPSHOT_KINDS
    for entry in snapshot:
        _require_keys(entry, {"kind", "title", "body", "evidence"}, "snapshot")

    milestones = roadmap["milestones"]
    assert isinstance(milestones, list) and milestones
    milestone_ids = [milestone["id"] for milestone in milestones]
    assert len(milestone_ids) == len(set(milestone_ids)), "duplicate milestone IDs"
    by_id = {milestone["id"]: milestone for milestone in milestones}
    assert meta["current_milestone"] in by_id
    current_milestone = by_id[meta["current_milestone"]]
    assert current_milestone["status"] == "in-progress"
    assert current_milestone["start"] <= reviewed_at <= current_milestone["end"], (
        "current milestone must contain the roadmap review date"
    )
    assert sum(milestone["status"] == "in-progress" for milestone in milestones) == 1
    assert milestones[0]["status"] == "done"
    assert milestones[-1]["status"] == "buffer"
    assert milestones[-1]["end"] == submission_date
    assert milestones[-2]["end"] == complete_by

    for index, milestone in enumerate(milestones):
        _require_keys(
            milestone,
            {"id", "title", "start", "end", "status", "depends_on", "gate", "evidence"},
            f"milestone {milestone.get('id', index)}",
        )
        assert milestone["status"] in ALLOWED_MILESTONE_STATES
        assert milestone["start"] <= milestone["end"]
        if index:
            assert milestones[index - 1]["end"] < milestone["start"], (
                f"milestones overlap or are unordered at {milestone['id']}"
            )
        for dependency in milestone["depends_on"]:
            assert dependency in by_id, f"unknown dependency {dependency}"
            assert by_id[dependency]["end"] < milestone["start"], (
                f"dependency {dependency} does not precede {milestone['id']}"
            )

    blockers = roadmap["blockers"]
    assert isinstance(blockers, list)
    blocker_ids = [blocker["id"] for blocker in blockers]
    assert len(blocker_ids) == len(set(blocker_ids)), "duplicate blocker IDs"
    for blocker in blockers:
        _require_keys(
            blocker,
            {"id", "title", "affects", "body", "evidence"},
            blocker["id"],
        )
        assert set(blocker["affects"]) <= set(milestone_ids)

    evidence_records = [*snapshot, *milestones, *blockers]
    for record in evidence_records:
        owner = record.get("id", record.get("kind"))
        assert record["evidence"], f"missing evidence pointers for {owner}"
        for pointer in record["evidence"]:
            assert _local_pointer_exists(pointer), (
                f"missing roadmap evidence pointer: {pointer}"
            )

    main_text = MAIN_TYP.read_text(encoding="utf-8")
    roadmap_text = ROADMAP_TYP.read_text(encoding="utf-8")
    assert main_text.count('#include "development/roadmap.typ"') == 1
    assert 'toml("roadmap.toml")' in roadmap_text
    obsolete_report_path = ROADMAP_DATA.parent / f"{OBSOLETE_REPORT}.typ"
    obsolete_report_text = obsolete_report_path.read_text(encoding="utf-8")
    assert "DEPRECATED_ROADMAP_SHIM" in obsolete_report_text
    assert f"development/{OBSOLETE_REPORT}.typ" not in main_text
    for retired_construct in ("thesis_status", "development-table", "promotion_entry"):
        assert retired_construct not in obsolete_report_text
    for path in (ROOT / "docs").rglob("*"):
        if (
            path.is_file()
            and path != obsolete_report_path
            and path.suffix in {".md", ".qmd", ".typ", ".toml", ".yml"}
        ):
            assert OBSOLETE_REPORT not in path.read_text(encoding="utf-8"), (
                f"obsolete M1 report reference remains in {path.relative_to(ROOT)}"
            )

    _compile_roadmap()
    assert _query_metadata("<roadmap-review-date>") == [reviewed_at.isoformat()]
    assert _query_metadata("<roadmap-current-milestone>") == [meta["current_milestone"]]
    print("thesis roadmap contract passed")


if __name__ == "__main__":
    main()
