#!/usr/bin/env python3
"""Inspect and maintain the ARIA-NBV internal agents DB.

The DB is intentionally small and human-editable. This helper validates the
TOML files, prints ranked active work, and moves completed items to
``.agents/resolved.toml`` without deleting history.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tomllib
from datetime import date
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
AGENTS_ROOT = REPO_ROOT / ".agents"

ACTIVE_FILES = {
    "issue": AGENTS_ROOT / "issues.toml",
    "todo": AGENTS_ROOT / "todos.toml",
    "refactor": AGENTS_ROOT / "refactors.toml",
}
RESOLVED_FILE = AGENTS_ROOT / "resolved.toml"
PROPOSALS_FILE = AGENTS_ROOT / "proposals.toml"
RESOLVED_PROPOSALS_FILE = AGENTS_ROOT / "proposals_resolved.toml"

TITLES = {
    "issue": "# ARIA-NBV Issues",
    "todo": "# ARIA-NBV TODOs",
    "refactor": "# ARIA-NBV Refactors",
    "resolved": "# ARIA-NBV Resolved Items",
}

PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}
STATUS_RANK = {"open": 0, "todo": 0, "in_progress": 1, "blocked": 2}

REQUIRED_FIELDS = {
    "issue": {
        "id",
        "title",
        "description",
        "type",
        "priority",
        "status",
        "labels",
        "context",
        "references",
    },
    "todo": {
        "id",
        "title",
        "description",
        "priority",
        "status",
        "labels",
        "loc_min",
        "loc_expected",
        "loc_max",
        "issue_ids",
        "context",
        "references",
        "implementation_notes",
        "acceptance",
        "verification",
    },
    "refactor": {
        "id",
        "title",
        "description",
        "priority",
        "status",
        "labels",
        "loc_min",
        "loc_expected",
        "loc_max",
        "issue_ids",
        "context",
        "implementation_notes",
        "acceptance",
        "verification",
    },
}

INT_FIELDS = {"loc_min", "loc_expected", "loc_max"}
LIST_FIELDS = {
    "labels",
    "issue_ids",
    "context",
    "references",
    "implementation_notes",
    "acceptance",
    "verification",
}
NON_EMPTY_LIST_FIELDS = {"context", "references"}
REFERENCE_PREFIXES = (
    "repo:",
    "bib:",
    "doi:",
    "arxiv:",
    "s2:",
    "url:",
    "context7:",
)
RESOLUTION_FIELDS = ["resolved_at", "resolution_note", "resolved_from"]
PROPOSAL_REQUIRED_FIELDS = {
    "id",
    "source_debrief",
    "target_owner",
    "proposed_statement",
    "evidence",
    "current_conflict",
    "scope",
    "status",
    "opened_at",
}
PROPOSAL_ACTIVE_STATUSES = {"proposed", "deferred", "reviewed"}
PROPOSAL_DISPOSITIONS = {"accept", "reject", "narrow", "defer"}


def _load_toml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ValueError(f"missing DB file: {path.relative_to(REPO_ROOT)}")
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _load_active() -> dict[str, list[dict[str, Any]]]:
    return {kind: list(_load_toml(path).get(kind, [])) for kind, path in ACTIVE_FILES.items()}


def _load_resolved() -> dict[str, list[dict[str, Any]]]:
    if not RESOLVED_FILE.exists():
        return {"issue": [], "todo": [], "refactor": []}
    data = _load_toml(RESOLVED_FILE)
    return {
        "issue": list(data.get("issue", [])),
        "todo": list(data.get("todo", [])),
        "refactor": list(data.get("refactor", [])),
    }


def _load_proposals(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return list(_load_toml(path).get("proposal", []))


def _write_proposals(path: Path, records: list[dict[str, Any]]) -> None:
    lines = ["# ARIA-NBV Human Intent Proposals", ""]
    for record in records:
        lines.append("[[proposal]]")
        for key in (
            "id",
            "source_debrief",
            "target_owner",
            "proposed_statement",
            "evidence",
            "current_conflict",
            "scope",
            "status",
            "opened_at",
            "disposition",
            "reviewed_by",
            "review_receipt",
            "reviewed_at",
            "owner_edit_commit",
            "proof",
            "resolution_reason",
            "resolved_at",
        ):
            if key in record:
                lines.append(f"{key} = {_format_value(record[key])}")
        lines.append("")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _validate_proposal(record: dict[str, Any], seen_ids: set[str]) -> list[str]:
    errors: list[str] = []
    proposal_id = str(record.get("id", "<missing-id>"))
    if not proposal_id.startswith("proposal-"):
        errors.append(f"{proposal_id}: proposal id must start with `proposal-`")
    if proposal_id in seen_ids:
        errors.append(f"{proposal_id}: duplicate proposal id")
    seen_ids.add(proposal_id)
    missing = sorted(PROPOSAL_REQUIRED_FIELDS - record.keys())
    if missing:
        errors.append(f"{proposal_id}: missing proposal fields: {', '.join(missing)}")
    if record.get("status") not in PROPOSAL_ACTIVE_STATUSES:
        errors.append(
            f"{proposal_id}: active proposal status must be proposed, deferred, or reviewed"
        )
    for field in PROPOSAL_REQUIRED_FIELDS - {"status"}:
        value = record.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{proposal_id}: `{field}` must be a non-empty string")
    for field in ("source_debrief", "target_owner"):
        value = record.get(field)
        if isinstance(value, str) and value and not (REPO_ROOT / value).is_file():
            errors.append(f"{proposal_id}: `{field}` does not exist: {value}")
    if record.get("status") == "deferred":
        if record.get("disposition") != "defer":
            errors.append(f"{proposal_id}: deferred proposal requires disposition=defer")
        for field in ("reviewed_by", "review_receipt", "reviewed_at"):
            if not str(record.get(field, "")).strip():
                errors.append(f"{proposal_id}: deferred proposal requires `{field}`")
    if record.get("status") == "reviewed":
        if record.get("disposition") not in {"accept", "reject", "narrow"}:
            errors.append(f"{proposal_id}: reviewed proposal has invalid disposition")
        for field in ("reviewed_by", "review_receipt", "reviewed_at"):
            if not str(record.get(field, "")).strip():
                errors.append(f"{proposal_id}: reviewed proposal requires `{field}`")
    return errors


def _quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _format_value(value: Any) -> str:
    if isinstance(value, int):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(_quote(str(item)) for item in value) + "]"
    return _quote(str(value))


def _field_order(kind: str, record: dict[str, Any]) -> list[str]:
    common = ["id", "title", "description"]
    if kind == "issue":
        ordered = [*common, "type", "priority", "status", "labels", "context", "references"]
    else:
        ordered = [
            *common,
            "priority",
            "status",
            "labels",
            "issue_ids",
            "loc_min",
            "loc_expected",
            "loc_max",
            "context",
            "references",
            "implementation_notes",
            "acceptance",
            "verification",
        ]
    ordered.extend(key for key in RESOLUTION_FIELDS if key in record)
    ordered.extend(key for key in sorted(record) if key not in ordered)
    return ordered


def _dump_records(title: str, kind: str, records: list[dict[str, Any]]) -> str:
    lines = [title, ""]
    for record in records:
        lines.append(f"[[{kind}]]")
        for key in _field_order(kind, record):
            if key in record:
                lines.append(f"{key} = {_format_value(record[key])}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _write_active(kind: str, records: list[dict[str, Any]]) -> None:
    ACTIVE_FILES[kind].write_text(
        _dump_records(TITLES[kind], kind, records),
        encoding="utf-8",
    )


def _write_resolved(records_by_kind: dict[str, list[dict[str, Any]]]) -> None:
    lines = [TITLES["resolved"], ""]
    for kind in ("issue", "todo", "refactor"):
        for record in records_by_kind.get(kind, []):
            lines.append(f"[[{kind}]]")
            for key in _field_order(kind, record):
                if key in record:
                    lines.append(f"{key} = {_format_value(record[key])}")
            lines.append("")
    RESOLVED_FILE.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _rank_key(kind: str, record: dict[str, Any]) -> tuple[int, int, int, str]:
    return (
        PRIORITY_RANK.get(str(record.get("priority")), 99),
        STATUS_RANK.get(str(record.get("status")), 99),
        int(record.get("loc_expected", 1_000_000)) if kind != "issue" else 0,
        str(record.get("id", "")),
    )


def _validate_record(
    kind: str,
    record: dict[str, Any],
    active_issue_ids: set[str],
    seen_ids: set[str],
) -> list[str]:
    errors: list[str] = []
    record_id = str(record.get("id", "<missing-id>"))
    expected_prefix = f"{kind}-"
    if not record_id.startswith(expected_prefix):
        errors.append(f"{record_id}: id must start with `{expected_prefix}`")
    if record_id in seen_ids:
        errors.append(f"{record_id}: duplicate id")
    seen_ids.add(record_id)

    missing = sorted(REQUIRED_FIELDS[kind] - record.keys())
    if missing:
        errors.append(f"{record_id}: missing fields: {', '.join(missing)}")

    priority = record.get("priority")
    if priority not in PRIORITY_RANK:
        errors.append(f"{record_id}: invalid priority: {priority!r}")

    for field in INT_FIELDS & record.keys():
        value = record[field]
        if not isinstance(value, int):
            errors.append(f"{record_id}: `{field}` must be an integer")
    if all(field in record for field in INT_FIELDS):
        loc_min = int(record["loc_min"])
        loc_expected = int(record["loc_expected"])
        loc_max = int(record["loc_max"])
        if not loc_min <= loc_expected <= loc_max:
            errors.append(f"{record_id}: expected loc_min <= loc_expected <= loc_max")

    for field in LIST_FIELDS & record.keys():
        value = record[field]
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            errors.append(f"{record_id}: `{field}` must be a string list")
            continue
        if field in NON_EMPTY_LIST_FIELDS and not value:
            errors.append(f"{record_id}: `{field}` must not be empty")
        if field == "references":
            for item in value:
                if not item.strip():
                    errors.append(f"{record_id}: `references` contains an empty item")
                if not item.startswith(REFERENCE_PREFIXES):
                    errors.append(
                        f"{record_id}: reference `{item}` must start with one of {', '.join(REFERENCE_PREFIXES)}"
                    )

    if kind in {"todo", "refactor"}:
        for issue_id in record.get("issue_ids", []):
            if issue_id not in active_issue_ids:
                errors.append(f"{record_id}: unknown active issue id `{issue_id}`")

    return errors


def validate(*, quiet: bool = False) -> int:
    errors: list[str] = []
    try:
        active = _load_active()
        resolved = _load_resolved()
    except ValueError as exc:
        errors.append(str(exc))
        active = {"issue": [], "todo": [], "refactor": []}
        resolved = {"issue": [], "todo": [], "refactor": []}

    active_issue_ids = {str(record.get("id")) for record in active["issue"]}
    seen_ids: set[str] = set()
    for kind in ("issue", "todo", "refactor"):
        for record in active[kind]:
            errors.extend(_validate_record(kind, record, active_issue_ids, seen_ids))
    active_ids = {str(record.get("id")) for records in active.values() for record in records}
    resolved_ids = {str(record.get("id")) for records in resolved.values() for record in records}
    for record_id in sorted(active_ids & resolved_ids):
        errors.append(f"{record_id}: active id reuses a resolved record id")

    proposal_ids: set[str] = set()
    active_proposals = _load_proposals(PROPOSALS_FILE)
    resolved_proposals = _load_proposals(RESOLVED_PROPOSALS_FILE)
    for proposal in active_proposals:
        errors.extend(_validate_proposal(proposal, proposal_ids))
    for proposal in resolved_proposals:
        proposal_id = str(proposal.get("id", "<missing-id>"))
        if proposal_id in proposal_ids:
            errors.append(f"{proposal_id}: active proposal reuses a resolved id")
        proposal_ids.add(proposal_id)
        if proposal.get("status") != "resolved":
            errors.append(f"{proposal_id}: resolved proposal status must be resolved")
        if proposal.get("disposition") not in {"accept", "reject", "narrow"}:
            errors.append(f"{proposal_id}: invalid resolved disposition")
        for field in ("reviewed_by", "review_receipt", "reviewed_at", "resolved_at"):
            if not str(proposal.get(field, "")).strip():
                errors.append(f"{proposal_id}: resolved proposal requires `{field}`")
        if proposal.get("disposition") in {"accept", "narrow"}:
            for field in ("owner_edit_commit", "proof"):
                if not str(proposal.get(field, "")).strip():
                    errors.append(f"{proposal_id}: installed proposal requires `{field}`")
        if proposal.get("disposition") == "reject" and not str(
            proposal.get("resolution_reason", "")
        ).strip():
            errors.append(f"{proposal_id}: rejected proposal requires a reason")

    if errors:
        print("agents DB validation failed", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    if not quiet:
        print("agents DB validation passed")
    return 0


def list_ranked() -> int:
    if validate(quiet=True) != 0:
        return 1

    active = _load_active()
    for kind, label in (
        ("issue", "Active Issues"),
        ("todo", "Active TODOs"),
        ("refactor", "Active Refactors"),
    ):
        print(f"\n## {label}")
        records = sorted(active[kind], key=lambda record: _rank_key(kind, record))
        if not records:
            print("(none)")
            continue
        for record in records:
            loc = ""
            if kind != "issue":
                loc = f" loc≈{record['loc_expected']}"
            print(f"- {record['id']} [{record['priority']}/{record['status']}]{loc}: {record['title']}")
            print(f"  {record['description']}")
    return 0


def resolve(kind: str, record_id: str, note: str) -> int:
    if kind not in ACTIVE_FILES:
        print(f"unknown record kind: {kind}", file=sys.stderr)
        return 2
    if validate(quiet=True) != 0:
        return 1

    active = _load_active()
    records = active[kind]
    match = next((record for record in records if record.get("id") == record_id), None)
    if match is None:
        print(f"{kind} not found: {record_id}", file=sys.stderr)
        return 1

    active[kind] = [record for record in records if record.get("id") != record_id]
    resolved = _load_resolved()
    moved = dict(match)
    moved["status"] = "resolved"
    moved["resolved_at"] = date.today().isoformat()
    moved["resolution_note"] = note
    moved["resolved_from"] = ACTIVE_FILES[kind].relative_to(REPO_ROOT).as_posix()
    resolved.setdefault(kind, []).append(moved)

    _write_active(kind, active[kind])
    _write_resolved(resolved)
    print(f"resolved {kind} {record_id}")
    return 0


def search(query: str, *, scope: str = "all") -> int:
    """Case-insensitive search across active and resolved records.

    Use this before planning new work or diagnosing a symptom: prior decisions
    in `.agents/resolved.toml` are gold for "has this been tried?".
    """
    needle = query.casefold()
    if not needle:
        print("agents-db search: empty query", file=sys.stderr)
        return 2

    def _matches(record: dict[str, Any]) -> bool:
        for key in ("id", "title", "description"):
            if needle in str(record.get(key, "")).casefold():
                return True
        for key in ("labels", "context", "implementation_notes", "acceptance"):
            for item in record.get(key, []) or []:
                if needle in str(item).casefold():
                    return True
        return False

    active = _load_active() if scope in {"all", "active"} else {"issue": [], "todo": [], "refactor": []}
    resolved = _load_resolved() if scope in {"all", "resolved"} else {"issue": [], "todo": [], "refactor": []}

    hits = 0
    for label, store in (("Active", active), ("Resolved", resolved)):
        for kind in ("issue", "todo", "refactor"):
            matches = [record for record in store.get(kind, []) if _matches(record)]
            if not matches:
                continue
            print(f"\n## {label} {kind}s")
            for record in matches:
                hits += 1
                priority = record.get("priority", "?")
                status = record.get("status", "?")
                print(f"- {record['id']} [{priority}/{status}]: {record.get('title', '')}")
                if label == "Resolved" and record.get("resolution_note"):
                    print(f"  resolved {record.get('resolved_at', '?')}: {record['resolution_note']}")
    if hits == 0:
        print(f"agents-db search: no matches for {query!r}")
    return 0


def proposal_open(
    proposal_id: str,
    *,
    source_debrief: str,
    target_owner: str,
    statement: str,
    evidence: str,
    conflict: str,
    scope: str,
) -> int:
    if validate(quiet=True) != 0:
        return 1
    records = _load_proposals(PROPOSALS_FILE)
    if any(record.get("id") == proposal_id for record in records) or any(
        record.get("id") == proposal_id
        for record in _load_proposals(RESOLVED_PROPOSALS_FILE)
    ):
        print(f"proposal id already exists: {proposal_id}", file=sys.stderr)
        return 1
    record = {
        "id": proposal_id,
        "source_debrief": source_debrief,
        "target_owner": target_owner,
        "proposed_statement": statement,
        "evidence": evidence,
        "current_conflict": conflict,
        "scope": scope,
        "status": "proposed",
        "opened_at": date.today().isoformat(),
    }
    errors = _validate_proposal(record, set())
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    records.append(record)
    _write_proposals(PROPOSALS_FILE, records)
    print(f"opened proposal {proposal_id}")
    return 0


def _commit_touches_target(commit: str, target_owner: str) -> bool:
    result = subprocess.run(
        ["git", "diff-tree", "--root", "--no-commit-id", "--name-only", "-r", commit],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and target_owner in result.stdout.splitlines()


def proposal_review(
    proposal_id: str,
    *,
    disposition: str,
    reviewer: str,
    receipt: str,
    owner_edit_commit: str | None,
    proof: str | None,
    reason: str | None,
) -> int:
    if reviewer != "current-user":
        print("proposal review requires reviewer=current-user", file=sys.stderr)
        return 1
    records = _load_proposals(PROPOSALS_FILE)
    record = next((item for item in records if item.get("id") == proposal_id), None)
    if record is None:
        print(f"active proposal not found: {proposal_id}", file=sys.stderr)
        return 1
    reviewed = dict(record)
    reviewed.update(
        disposition=disposition,
        reviewed_by=reviewer,
        review_receipt=receipt,
        reviewed_at=date.today().isoformat(),
    )
    if disposition == "defer":
        reviewed["status"] = "deferred"
        records[records.index(record)] = reviewed
        _write_proposals(PROPOSALS_FILE, records)
        print(f"deferred proposal {proposal_id}")
        return 0
    if disposition in {"accept", "narrow"}:
        if not owner_edit_commit or not proof:
            print("accept/narrow requires --owner-edit-commit and --proof", file=sys.stderr)
            return 1
        if not _commit_touches_target(owner_edit_commit, str(record["target_owner"])):
            print("owner edit commit does not touch target owner", file=sys.stderr)
            return 1
        reviewed["owner_edit_commit"] = owner_edit_commit
        reviewed["proof"] = proof
    elif disposition == "reject":
        if not reason:
            print("reject requires --reason", file=sys.stderr)
            return 1
        reviewed["resolution_reason"] = reason
    else:
        print(f"unsupported disposition: {disposition}", file=sys.stderr)
        return 2
    reviewed["status"] = "reviewed"
    records[records.index(record)] = reviewed
    _write_proposals(PROPOSALS_FILE, records)
    print(f"reviewed proposal {proposal_id}: {disposition}")
    return 0


def proposal_resolve(proposal_id: str) -> int:
    records = _load_proposals(PROPOSALS_FILE)
    record = next((item for item in records if item.get("id") == proposal_id), None)
    if record is None or record.get("status") != "reviewed":
        print("proposal must have a completed non-defer review before resolution", file=sys.stderr)
        return 1
    resolved = dict(record)
    resolved["status"] = "resolved"
    resolved["resolved_at"] = date.today().isoformat()
    _write_proposals(
        PROPOSALS_FILE, [item for item in records if item.get("id") != proposal_id]
    )
    history = _load_proposals(RESOLVED_PROPOSALS_FILE)
    history.append(resolved)
    _write_proposals(RESOLVED_PROPOSALS_FILE, history)
    print(f"resolved proposal {proposal_id}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("list", help="Print ranked active records.")
    subparsers.add_parser("validate", help="Validate DB schema and references.")

    search_parser = subparsers.add_parser(
        "search",
        help="Case-insensitive search across active and resolved records.",
    )
    search_parser.add_argument("query")
    search_parser.add_argument(
        "--scope",
        choices=["all", "active", "resolved"],
        default="all",
        help="Restrict search to active, resolved, or both (default: all).",
    )

    resolve_parser = subparsers.add_parser("resolve", help="Move a record to resolved.toml.")
    resolve_parser.add_argument("kind", choices=sorted(ACTIVE_FILES))
    resolve_parser.add_argument("record_id")
    resolve_parser.add_argument("--note", required=True)
    open_parser = subparsers.add_parser("proposal-open", help="Open a typed proposal record.")
    open_parser.add_argument("proposal_id")
    open_parser.add_argument("--source-debrief", required=True)
    open_parser.add_argument("--target-owner", required=True)
    open_parser.add_argument("--statement", required=True)
    open_parser.add_argument("--evidence", required=True)
    open_parser.add_argument("--conflict", required=True)
    open_parser.add_argument("--scope", required=True)
    review_parser = subparsers.add_parser("proposal-review", help="Record current-user review.")
    review_parser.add_argument("proposal_id")
    review_parser.add_argument("--disposition", choices=sorted(PROPOSAL_DISPOSITIONS), required=True)
    review_parser.add_argument("--reviewer", choices=["current-user"], required=True)
    review_parser.add_argument("--receipt", required=True)
    review_parser.add_argument("--owner-edit-commit")
    review_parser.add_argument("--proof")
    review_parser.add_argument("--reason")
    resolve_proposal = subparsers.add_parser("proposal-resolve", help="Archive a reviewed proposal.")
    resolve_proposal.add_argument("proposal_id")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    command = args.command or "list"
    if command == "list":
        return list_ranked()
    if command == "validate":
        return validate()
    if command == "search":
        return search(args.query, scope=args.scope)
    if command == "resolve":
        return resolve(args.kind, args.record_id, args.note)
    if command == "proposal-open":
        return proposal_open(
            args.proposal_id,
            source_debrief=args.source_debrief,
            target_owner=args.target_owner,
            statement=args.statement,
            evidence=args.evidence,
            conflict=args.conflict,
            scope=args.scope,
        )
    if command == "proposal-review":
        return proposal_review(
            args.proposal_id,
            disposition=args.disposition,
            reviewer=args.reviewer,
            receipt=args.receipt,
            owner_edit_commit=args.owner_edit_commit,
            proof=args.proof,
            reason=args.reason,
        )
    if command == "proposal-resolve":
        return proposal_resolve(args.proposal_id)
    raise AssertionError(f"unhandled command: {command}")


if __name__ == "__main__":
    raise SystemExit(main())
