#!/usr/bin/env python3
"""Inspect and maintain the ARIA-NBV internal agents DB.

The DB is intentionally small and human-editable. This helper validates the
TOML files, prints ranked active work, and moves completed items to
``.agents/resolved.toml`` without deleting history.
"""

from __future__ import annotations

import argparse
import json
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
    raise AssertionError(f"unhandled command: {command}")


if __name__ == "__main__":
    raise SystemExit(main())
