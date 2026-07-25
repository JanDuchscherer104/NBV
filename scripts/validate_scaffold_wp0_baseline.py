#!/usr/bin/env python3
"""Validate the immutable WP0 scaffold baseline against its Git tree."""

from __future__ import annotations

import argparse
from collections import Counter
import csv
import fnmatch
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Literal, TypedDict, cast, overload


ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = ROOT / ".agents/baselines/scaffold_wp0_baseline.json"
INVENTORY_PATH = ROOT / ".agents/baselines/scaffold_wp0_inventory.csv"
REQUIRED_INVENTORY_COLUMNS = {
    "id",
    "category",
    "surface",
    "paths",
    "owner",
    "status",
    "disposition",
    "verification",
    "rollback_commit",
}
CLOSED_STATUSES = {"exclude", "historical", "migrate", "promote", "retain", "retire"}
REQUIRED_CATEGORIES = {
    "context-consumer",
    "context-producer",
    "graphify",
    "guidance",
    "hook",
    "litkg-capability",
    "omx-candidate",
    "reference",
    "skill",
    "state-consumer",
    "state-journal",
}
FRONTMATTER_VALUE = re.compile(r"^(name|description):\s*(.*)$", re.MULTILINE)
LINE_ANCHOR = re.compile(
    r"^(?P<path>.+):(?P<start>[1-9][0-9]*)(?:-(?P<end>[1-9][0-9]*))?$"
)
PLACEHOLDER_VALUE = re.compile(
    r"(?:^|\b)(?:n/?a|none|placeholder|tbd|todo|unknown|unassigned)(?:\b|$)",
    re.IGNORECASE,
)
IMPORTANT_LOC_OWNERS = {
    "Makefile",
    ".gemini/settings.json",
    "scripts/agents_db.py",
    "scripts/debrief_nudge.sh",
    "scripts/sync_claude_skills.sh",
}
REQUIRED_LOC_INCLUDE_GLOBS = {
    ".agents/baselines/**",
    "aria_nbv/AGENTS.md",
    "scripts/validate_scaffold_wp0_baseline.py",
}
CONTEXT_CONSUMER_PATTERNS = (
    re.compile(rb"docs/_generated/context(?:/|\b)"),
    re.compile(
        rb"(?<![A-Za-z0-9_])(?:source_index|literature_index|data_contracts)"
        rb"\.(?:md|jsonl)"
    ),
    re.compile(rb"\bmake context(?:-[a-z0-9-]+)?\b"),
)
FAILURE_DIGEST = re.compile(r"^[0-9a-f]{64}$")


class SourceRecord(TypedDict):
    path: str
    physical_lines: int
    sha256: str


@overload
def _git(*args: str, text: Literal[False] = False) -> bytes: ...


@overload
def _git(*args: str, text: Literal[True]) -> str: ...


def _git(*args: str, text: bool = False) -> bytes | str:
    return cast(
        bytes | str,
        subprocess.check_output(["git", *args], cwd=ROOT, text=text),
    )


def _tree(commit: str) -> dict[str, tuple[str, str]]:
    raw = _git("ls-tree", "-rz", "--full-tree", commit)
    assert isinstance(raw, bytes)
    entries: dict[str, tuple[str, str]] = {}
    for record in raw.split(b"\0"):
        if not record:
            continue
        metadata, encoded_path = record.split(b"\t", 1)
        mode, object_type, object_id = metadata.decode().split()
        path = encoded_path.decode("utf-8", errors="surrogateescape")
        entries[path] = (mode, object_id if object_type in {"blob", "commit"} else "")
    return entries


def _blob(object_id: str) -> bytes:
    value = _git("cat-file", "blob", object_id)
    assert isinstance(value, bytes)
    return value


def _matches(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)


def _regular_paths(tree: dict[str, tuple[str, str]]) -> set[str]:
    return {path for path, (mode, _) in tree.items() if mode in {"100644", "100755"}}


def _inventory_tokens(rows: list[dict[str, str]], categories: set[str]) -> list[str]:
    return [
        token.strip()
        for row in rows
        if row["category"] in categories
        for token in row["paths"].split(";")
        if token.strip()
    ]


def _token_path(token: str) -> str:
    match = LINE_ANCHOR.fullmatch(token)
    return match.group("path") if match else token


def _expanded_inventory_paths(
    rows: list[dict[str, str]],
    categories: set[str],
    tree: dict[str, tuple[str, str]],
) -> set[str]:
    paths: set[str] = set()
    for token in _inventory_tokens(rows, categories):
        path = _token_path(token)
        if any(character in path for character in "*?["):
            paths.update(
                candidate for candidate in tree if fnmatch.fnmatchcase(candidate, path)
            )
        else:
            paths.add(path)
    return paths


def derive_required_inventory_surfaces(
    tree: dict[str, tuple[str, str]], active_scaffold_paths: set[str]
) -> dict[str, set[str]]:
    """Derive closed-ledger source families from the pinned baseline tree."""
    regular = _regular_paths(tree)
    guidance = {
        path
        for path in regular
        if path in {"AGENTS.md", "CLAUDE.md", "docs/AGENTS.md"}
        or (path.startswith("aria_nbv/") and path.endswith("/AGENTS.md"))
    }
    references = {path for path in regular if path.startswith(".agents/references/")}
    skills = {
        path
        for path in regular
        if fnmatch.fnmatchcase(path, ".agents/skills/*/SKILL.md")
    }
    journals = {
        path
        for path in regular
        if fnmatch.fnmatchcase(path, ".agents/memory/state/*.md")
    }
    hooks = {
        path
        for path in regular
        if path
        in {
            "Makefile",
            ".claude/settings.json",
            ".codex/hooks.example.json",
            ".codex-plugin/hooks.json",
            ".gemini/settings.json",
            "scripts/debrief_nudge.sh",
            "scripts/kg/auto_refresh.sh",
        }
        or path.startswith(".codex-plugin/hooks/")
        or path.startswith("scripts/git_hooks/")
    }
    context = {
        path
        for path in regular
        if path == "Makefile"
        or path == "aria_nbv/scripts/get_context.py"
        or path.startswith("scripts/nbv_")
        or path.startswith(".agents/skills/aria-nbv-context/scripts/")
        or path == ".claude/commands/context-refresh.md"
    }
    context_producer_only = {
        path
        for path in context
        if path != "Makefile"
        and (
            path == "aria_nbv/scripts/get_context.py"
            or path.startswith("scripts/nbv_")
            or path.startswith(".agents/skills/aria-nbv-context/scripts/")
        )
    }
    context_consumers = {
        path
        for path in active_scaffold_paths - context_producer_only
        if any(
            pattern.search(_blob(tree[path][1]))
            for pattern in CONTEXT_CONSUMER_PATTERNS
        )
    }
    litkg = {
        path
        for path in tree
        if path
        in {
            "Makefile",
            ".agents/external/litkg-rs",
            ".agents/kg/README.md",
            ".agents/references/litkg_quick_reference.md",
            ".claude/commands/kg-claim-check.md",
            ".configs/litkg.toml",
        }
        or path.startswith("scripts/kg/")
        or path.startswith(".agents/skills/aria-litkg-memory/")
        or path.startswith(".agents/skills/semantic-scholar-litkg/")
    }
    graphify = {
        path
        for path in regular
        if path in active_scaffold_paths or path.startswith("scripts/tests/")
        if path in {"Makefile", ".gitignore", ".graphifyignore"}
        or path.startswith(".codex/skills/graphify/")
        or "graphify" in Path(path).name
        or path == "scripts/tests/test_post_commit_graph_dispatch.sh"
        or path == "scripts/git_hooks/post-commit"
    }
    return {
        "guidance": guidance,
        "reference": references,
        "skill": skills,
        "state-journal": journals,
        "hook": hooks,
        "omx-candidate": {path for path in tree if path.startswith(".omx/")},
        "context-consumer": context_consumers,
        "context-family": context,
        "litkg-family": litkg,
        "graphify-family": graphify,
    }


def validate_counting_rules(
    baseline: dict[str, Any],
    tree: dict[str, tuple[str, str]],
    resolved_paths: set[str],
) -> list[str]:
    errors: list[str] = []
    include_globs = set(
        baseline["counting_rules"]["active_scaffold_source_loc"]["include_globs"]
    )
    missing_globs = REQUIRED_LOC_INCLUDE_GLOBS - include_globs
    if missing_globs:
        errors.append(
            f"active scaffold LOC include globs are missing: {sorted(missing_globs)}"
        )
    required = set(IMPORTANT_LOC_OWNERS)
    required.update(
        path
        for path, (mode, _) in tree.items()
        if mode in {"100644", "100755"} and path.startswith(".codex-plugin/")
    )
    required.update(
        path
        for path, (mode, _) in tree.items()
        if mode in {"100644", "100755"} and path.startswith("scripts/nbv_")
    )
    missing = required - resolved_paths
    if missing:
        errors.append(f"active scaffold LOC owners are missing: {sorted(missing)}")
    return errors


def validate_failure_allowlist(baseline: dict[str, Any]) -> list[str]:
    """Validate exact, expiring failure records without rerunning baseline commands."""
    errors: list[str] = []
    failures = baseline.get("verification_snapshot", [])
    commands = [failure.get("command", "") for failure in failures]
    if len(commands) != len(set(commands)):
        errors.append("baseline failure commands are not unique")
    required = {
        "command",
        "exit_code",
        "normalized_failure_signature",
        "output_sha256",
        "owning_workpackage",
        "expiry_point",
    }
    for index, failure in enumerate(failures, start=1):
        missing = required - set(failure)
        if missing:
            errors.append(
                f"baseline failure {index} is missing fields: {sorted(missing)}"
            )
            continue
        if failure["exit_code"] <= 0:
            errors.append(
                f"baseline failure {index} does not record a failing exit code"
            )
        if not FAILURE_DIGEST.fullmatch(failure["output_sha256"]):
            errors.append(f"baseline failure {index} has an invalid output digest")
        if not str(failure["command"]).strip():
            errors.append(f"baseline failure {index} has an incomplete command")
        for field in ("normalized_failure_signature", "expiry_point"):
            if len(str(failure[field]).strip()) < 8:
                errors.append(f"baseline failure {index} has an incomplete {field}")
        if not re.fullmatch(r"WP[1-7]", failure["owning_workpackage"]):
            errors.append(f"baseline failure {index} has an invalid owning workpackage")
    return errors


def validate_graphify_snapshot(baseline: dict[str, Any]) -> list[str]:
    """Require deterministic unavailable values when no baseline graph exists."""
    errors: list[str] = []
    graphify = baseline.get("graphify", {})
    required = {"corpus", "graph_size", "node_count", "edge_count"}
    missing = required - set(graphify)
    if missing:
        return [f"Graphify snapshot is missing fields: {sorted(missing)}"]
    if graphify.get("graph_json") == "absent":
        expected = {
            "corpus": {
                "policy_path": ".graphifyignore",
                "manifest_state": "absent",
            },
            "graph_size": {"state": "unavailable", "bytes": None},
            "node_count": {"state": "unavailable", "value": None},
            "edge_count": {"state": "unavailable", "value": None},
        }
        for field, value in expected.items():
            if graphify[field] != value:
                errors.append(
                    f"Graphify {field} must use the deterministic absent-graph value"
                )
    return errors


def validate_inventory_paths(
    rows: list[dict[str, str]], tree: dict[str, tuple[str, str]]
) -> list[str]:
    errors: list[str] = []
    for line_number, row in enumerate(rows, start=2):
        for token in (value.strip() for value in row["paths"].split(";")):
            match = LINE_ANCHOR.fullmatch(token)
            path = match.group("path") if match else token
            if any(character in path for character in "*?["):
                matches = [
                    candidate
                    for candidate in tree
                    if fnmatch.fnmatchcase(candidate, path)
                ]
                if not matches:
                    errors.append(
                        f"inventory line {line_number} path glob has no baseline matches: {token}"
                    )
                if match:
                    errors.append(
                        f"inventory line {line_number} cannot anchor a path glob: {token}"
                    )
                continue
            entry = tree.get(path)
            if entry is None:
                errors.append(
                    f"inventory line {line_number} path is absent from baseline tree: {path}"
                )
                continue
            if match:
                if entry[0] not in {"100644", "100755"}:
                    errors.append(
                        f"inventory line {line_number} anchors non-file path: {path}"
                    )
                    continue
                line_count = len(_blob(entry[1]).splitlines())
                start = int(match.group("start"))
                end = int(match.group("end") or start)
                if start > end or end > line_count:
                    errors.append(
                        f"inventory line {line_number} has invalid line anchor {token} "
                        f"for {line_count}-line file"
                    )
    return errors


def _frontmatter(data: bytes, path: str) -> dict[str, str]:
    text = data.decode("utf-8")
    if not text.startswith("---\n") or "\n---\n" not in text[4:]:
        raise ValueError(f"{path}: missing YAML frontmatter")
    body = text[4 : text.index("\n---\n", 4)]
    values = {
        key: value.strip().strip("\"'")
        for key, value in FRONTMATTER_VALUE.findall(body)
    }
    if not values.get("name") or not values.get("description"):
        raise ValueError(
            f"{path}: frontmatter must contain scalar name and description"
        )
    return values


def _active_scaffold_paths(
    baseline: dict[str, Any], tree: dict[str, tuple[str, str]]
) -> set[str]:
    rules = baseline["counting_rules"]["active_scaffold_source_loc"]
    return {
        path
        for path, (mode, _) in tree.items()
        if mode in {"100644", "100755"}
        and _matches(path, rules["include_globs"])
        and not _matches(path, rules["exclude_globs"])
    }


def compute_repository_baseline(baseline: dict[str, Any]) -> dict[str, Any]:
    commit = baseline["source_state"]["commit"]
    tree = _tree(commit)
    paths = sorted(_active_scaffold_paths(baseline, tree))
    source_records: list[SourceRecord] = []
    for path in paths:
        data = _blob(tree[path][1])
        source_records.append(
            {
                "path": path,
                "physical_lines": len(data.splitlines()),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
    path_digest = hashlib.sha256(
        b"".join(record["path"].encode() + b"\0" for record in source_records)
    ).hexdigest()
    content_digest = hashlib.sha256(
        b"".join(
            record["path"].encode() + b"\0" + record["sha256"].encode() + b"\0"
            for record in source_records
        )
    ).hexdigest()

    skills = []
    for path in sorted(
        path
        for path, (mode, _) in tree.items()
        if mode in {"100644", "100755"}
        and fnmatch.fnmatchcase(path, ".agents/skills/*/SKILL.md")
    ):
        data = _blob(tree[path][1])
        frontmatter = _frontmatter(data, path)
        description = frontmatter["description"]
        skills.append(
            {
                "name": frontmatter["name"],
                "path": path,
                "physical_lines": len(data.splitlines()),
                "description": description,
                "description_bytes": len(description.encode("utf-8")),
            }
        )

    return {
        "active_scaffold_source": {
            "file_count": len(source_records),
            "physical_lines": sum(
                record["physical_lines"] for record in source_records
            ),
            "resolved_paths_sha256": path_digest,
            "content_sha256": content_digest,
        },
        "aria_skills": skills,
        "aria_skill_count": len(skills),
        "aria_skill_description_bytes": sum(
            skill["description_bytes"] for skill in skills
        ),
    }


def _load_inventory() -> list[dict[str, str]]:
    with INVENTORY_PATH.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if set(reader.fieldnames or ()) != REQUIRED_INVENTORY_COLUMNS:
            raise ValueError(
                "inventory columns differ from the closed-ledger schema: "
                f"{reader.fieldnames}"
            )
        return list(reader)


def validate_inventory(
    rows: list[dict[str, str]],
    baseline_commit: str,
    expected_skills: set[str],
    tree: dict[str, tuple[str, str]],
    active_scaffold_paths: set[str],
) -> list[str]:
    errors: list[str] = []
    identifiers = [row["id"] for row in rows]
    if len(identifiers) != len(set(identifiers)):
        errors.append("inventory ids are not unique")
    surfaces = [(row["category"], row["surface"]) for row in rows]
    if len(surfaces) != len(set(surfaces)):
        errors.append("inventory category/surface pairs are not unique")
    missing_categories = REQUIRED_CATEGORIES - {row["category"] for row in rows}
    if missing_categories:
        errors.append(f"inventory categories are missing: {sorted(missing_categories)}")
    for line_number, row in enumerate(rows, start=2):
        missing = [column for column, value in row.items() if not value.strip()]
        if missing:
            errors.append(f"inventory line {line_number} has empty fields: {missing}")
        if row["status"] not in CLOSED_STATUSES:
            errors.append(
                f"inventory line {line_number} has open/unknown status {row['status']!r}"
            )
        if row["rollback_commit"] != baseline_commit:
            errors.append(
                f"inventory line {line_number} rollback commit differs from baseline"
            )
        for field in ("owner", "disposition", "verification"):
            value = row[field].strip()
            if len(value) < 8 or PLACEHOLDER_VALUE.search(value):
                errors.append(
                    f"inventory line {line_number} has placeholder {field}: {value!r}"
                )

    errors.extend(validate_inventory_paths(rows, tree))

    inventoried_skills = {row["surface"] for row in rows if row["category"] == "skill"}
    if inventoried_skills != expected_skills:
        errors.append(
            "skill inventory mismatch: "
            f"missing={sorted(expected_skills - inventoried_skills)}, "
            f"extra={sorted(inventoried_skills - expected_skills)}"
        )

    expected_journals = {
        "DECISIONS.md",
        "GOTCHAS.md",
        "OPEN_QUESTIONS.md",
        "PROJECT_STATE.md",
    }
    inventoried_journals = {
        Path(row["paths"]).name for row in rows if row["category"] == "state-journal"
    }
    if inventoried_journals != expected_journals:
        errors.append("state-journal inventory is not exact")

    required = derive_required_inventory_surfaces(tree, active_scaffold_paths)
    observed_context_consumers = _expanded_inventory_paths(
        rows, {"context-consumer"}, tree
    )
    expected_context_consumers = required["context-consumer"]
    if observed_context_consumers != expected_context_consumers:
        errors.append(
            "context-consumer inventory mismatch: "
            f"missing={sorted(expected_context_consumers - observed_context_consumers)}, "
            f"extra={sorted(observed_context_consumers - expected_context_consumers)}"
        )
    for category in (
        "guidance",
        "reference",
        "skill",
        "state-journal",
        "hook",
        "omx-candidate",
    ):
        observed = _expanded_inventory_paths(rows, {category}, tree)
        expected = required[category]
        if observed != expected:
            errors.append(
                f"{category} inventory mismatch: "
                f"missing={sorted(expected - observed)}, "
                f"extra={sorted(observed - expected)}"
            )
    family_categories = {
        "context-family": {"context-consumer", "context-producer", "state-consumer"},
        "litkg-family": {
            "litkg-capability",
            "hook",
            "reference",
            "skill",
            "state-consumer",
        },
        "graphify-family": {"graphify", "hook", "state-consumer"},
    }
    for family, categories in family_categories.items():
        observed = _expanded_inventory_paths(rows, categories, tree)
        missing_paths = required[family] - observed
        if missing_paths:
            errors.append(f"{family} inventory is missing: {sorted(missing_paths)}")

    overlap_requirements = {
        ".agents/skills/aria-nbv-context/scripts/nbv_context_index.sh": {
            "context-producer",
            "state-consumer",
        },
        "scripts/kg/auto_refresh.sh": {
            "hook",
            "litkg-capability",
            "state-consumer",
        },
        "Makefile": {"context-producer", "hook", "litkg-capability"},
    }
    for path, categories in overlap_requirements.items():
        for category in categories:
            observed = _expanded_inventory_paths(rows, {category}, tree)
            if path not in observed:
                errors.append(
                    f"cross-category inventory is missing {path} from {category}"
                )
    return errors


def _environment_skill_measurement() -> tuple[int, int]:
    raw = subprocess.check_output(["codex", "debug", "prompt-input"], cwd=ROOT)
    payload = json.loads(raw)
    text = "\n".join(
        content.get("text", "")
        for message in payload
        for content in message.get("content", [])
        if content.get("type") == "input_text"
    )
    roots = {
        root
        for root, path in re.findall(r"^- `(r\d+)` = `([^`]+)`$", text, re.MULTILINE)
        if Path(path) == ROOT / ".agents/skills"
    }
    if len(roots) != 1:
        raise ValueError(f"expected one project ARIA skill root; found {sorted(roots)}")
    root = next(iter(roots))
    pattern = re.compile(
        rf"^- mempalace-aria-nbv:[^:]+: (.*?) "
        rf"\(file: {re.escape(root)}/[^/]+/SKILL\.md\)$",
        re.MULTILINE,
    )
    descriptions = pattern.findall(text)
    return len(descriptions), sum(len(value.encode("utf-8")) for value in descriptions)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--print-computed", action="store_true")
    parser.add_argument("--check-environment", action="store_true")
    args = parser.parse_args()

    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    tree = _tree(baseline["source_state"]["commit"])
    active_scaffold_paths = _active_scaffold_paths(baseline, tree)
    computed = compute_repository_baseline(baseline)
    if args.print_computed:
        print(json.dumps(computed, indent=2, sort_keys=True))
        return 0

    errors: list[str] = []
    if computed != baseline["measurements"]:
        errors.append(
            "repository measurements differ from the recorded baseline; "
            f"observed={json.dumps(computed, sort_keys=True)}"
        )
    errors.extend(validate_counting_rules(baseline, tree, active_scaffold_paths))
    errors.extend(validate_failure_allowlist(baseline))
    errors.extend(validate_graphify_snapshot(baseline))
    inventory: list[dict[str, str]] = []
    try:
        inventory = _load_inventory()
        inventory_bytes = INVENTORY_PATH.read_bytes()
        inventory_summary = baseline["inventory"]
        observed_categories = dict(
            sorted(Counter(row["category"] for row in inventory).items())
        )
        observed_ids = sorted(row["id"] for row in inventory)
        if len(inventory) != inventory_summary["row_count"]:
            errors.append("inventory row count differs from the immutable baseline")
        if observed_ids != inventory_summary["required_ids"]:
            errors.append(
                "inventory required ids differ: "
                f"missing={sorted(set(inventory_summary['required_ids']) - set(observed_ids))}, "
                f"extra={sorted(set(observed_ids) - set(inventory_summary['required_ids']))}"
            )
        observed_inventory_sha256 = hashlib.sha256(inventory_bytes).hexdigest()
        if observed_inventory_sha256 != inventory_summary["sha256"]:
            errors.append(
                "inventory content hash differs from the immutable baseline; "
                f"observed={observed_inventory_sha256}"
            )
        if observed_categories != inventory_summary["category_counts"]:
            errors.append(
                "inventory category counts differ from the immutable baseline"
            )
        errors.extend(
            validate_inventory(
                inventory,
                baseline["source_state"]["commit"],
                {skill["name"] for skill in computed["aria_skills"]},
                tree,
                active_scaffold_paths,
            )
        )
    except (OSError, ValueError) as exc:
        errors.append(str(exc))

    if args.check_environment:
        observed = _environment_skill_measurement()
        expected = baseline["codex_environment"]
        if observed != (
            expected["model_visible_aria_skill_count"],
            expected["model_visible_aria_description_bytes"],
        ):
            errors.append(
                "Codex model-visible ARIA skill measurement differs from the snapshot: "
                f"observed={observed}"
            )

    if errors:
        print("WP0 scaffold baseline validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(
        "WP0 scaffold baseline valid: "
        f"{computed['active_scaffold_source']['file_count']} files, "
        f"{computed['active_scaffold_source']['physical_lines']} lines, "
        f"{computed['aria_skill_count']} ARIA skills, "
        f"{computed['aria_skill_description_bytes']} description bytes, "
        f"{len(inventory)} closed inventory rows"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
