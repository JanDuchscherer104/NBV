#!/usr/bin/env python3
"""Audit ARIA-NBV agent scaffold skill metadata and routing fixtures."""

from __future__ import annotations

import argparse
import csv
import importlib
import json
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, cast


class YamlModule(Protocol):
    YAMLError: type[Exception]

    def safe_load(self, stream: str) -> object: ...


yaml = cast(YamlModule, importlib.import_module("yaml"))

ROOT = Path(__file__).resolve().parents[1]
ROOT_RESOLVED = ROOT.resolve()
SKILLS_DIR = ROOT / ".agents" / "skills"
ROUTING_FIXTURES = ROOT / ".agents" / "references" / "scaffold_routing_fixtures.json"
WP5_INVENTORY = ROOT / ".agents" / "baselines" / "scaffold_wp5_skill_inventory.json"
WP6_INVENTORY = ROOT / ".agents" / "baselines" / "scaffold_wp6_skill_inventory.json"
WP5_DISPOSITIONS = (
    ROOT / ".agents" / "baselines" / "scaffold_wp5_skill_dispositions.csv"
)
WP6_CAPABILITIES = (
    ROOT / ".agents" / "baselines" / "scaffold_wp6_capability_dispositions.csv"
)

ALLOWED_MODES = {"implementation", "router", "diagnostic", "review", "maintenance"}
REQUIRED_METADATA = {
    "mode",
    "not_when",
    "handoff_to",
    "evidence_required",
    "applies_to",
    "triggers",
    "must_read",
    "canonical_sources",
    "verification",
}
OPTIONAL_METADATA = {
    "context7_refs",
    "literature_refs",
    "tool_refs",
}
METADATA_KEYS = REQUIRED_METADATA | OPTIONAL_METADATA
BLOCKED_HANDOFF_PREFIXES = {"omx", "github", "oh-my-codex"}
DECLARED_CAPABILITY_TOKENS = {"external", "GitHub", "owning", "nearest", "specialized"}
HOT_PATH_LINE_BUDGET = 150
PREFERRED_HOT_PATH_LINE_BUDGET = 120
CLOSED_DISPOSITIONS = {"migrated", "already_owned", "duplicate", "obsolete"}
CONTEXT7_IDS = ROOT / ".agents" / "references" / "context7_library_ids.md"
BIBLIOGRAPHY = ROOT / "docs" / "references.bib"
TOOL_REF_RE = re.compile(r"^mcp__[A-Za-z0-9_]+\.[A-Za-z0-9_]+$")
SEMANTIC_DRIFT_RULES: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "formula-detail",
        re.compile(r"(?m)^\s*\$\$|\\begin\{|\\frac\{|\\mathcal\{|\\operatorname\{"),
        "formula or equation detail belongs in thesis/theory/package owners",
    ),
    (
        "roadmap-claim",
        re.compile(
            r"\b(RQ[1-6]|M[1-6]|thesis (?:core|deliverable|claim|roadmap)|"
            r"advisor-facing|roadmap evidence gate)\b",
            re.IGNORECASE,
        ),
        "roadmap or thesis claims should point to exact owning thesis sources",
    ),
    (
        "future-plan",
        re.compile(
            r"\b(planned but unimplemented|future work|not yet implemented|"
            r"when time permits|will be implemented)\b",
            re.IGNORECASE,
        ),
        "future or unimplemented plans belong in backlog, roadmap, or theory docs",
    ),
    (
        "implementation-contract",
        re.compile(
            r"(?m)^## .*?(Schema|Data Model|Implementation Detail|Contract)\b|"
            r"\b(record|store|payload|DTO|API) fields?\b",
            re.IGNORECASE,
        ),
        "implementation contracts belong in source, package AGENTS, or generated docs",
    ),
)
SEMANTIC_DRIFT_EXEMPTIONS = {
    "aria-docs": {"roadmap-claim"},
}
BROAD_APPLIES_EXEMPTIONS = {"agent-behavior", "aria-nbv-context", "plan-grill"}


def slugify_heading(text: str) -> str:
    text = re.sub(r"\{#[^}]+}", "", text)
    text = text.strip().lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"\s+", "-", text)
    return text.strip("-")


def markdown_anchors(path: Path) -> set[str]:
    anchors: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        heading = re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*$", line)
        if not heading:
            continue
        text = heading.group(1).strip()
        explicit = re.search(r"\{#([^}]+)}", text)
        if explicit:
            anchors.add(explicit.group(1).strip())
        slug = slugify_heading(text)
        if slug:
            anchors.add(slug)
    return anchors


STOPWORDS = {
    "and",
    "are",
    "aria",
    "but",
    "for",
    "from",
    "into",
    "lookup",
    "nbv",
    "not",
    "only",
    "route",
    "routing",
    "skill",
    "task",
    "the",
    "this",
    "through",
    "use",
    "when",
    "with",
    "without",
}


def tokens(text: str) -> set[str]:
    raw = re.findall(r"[a-z0-9_]+", text.lower())
    return {token for token in raw if token not in STOPWORDS and len(token) >= 3}


def metadata_strings(metadata: dict[str, Any], fields: set[str]) -> list[str]:
    values: list[str] = []
    for field in fields:
        value = metadata.get(field)
        if isinstance(value, list):
            values.extend(item for item in value if isinstance(item, str))
        elif isinstance(value, str):
            values.append(value)
    return values


def load_context7_ids(path: Path = CONTEXT7_IDS) -> tuple[set[str], list[str]]:
    errors: list[str] = []
    ids: set[str] = set()
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return ids, [f"{rel(path)}: cannot read Context7 registry: {exc}"]
    for match in re.finditer(r"`(/[^`\s]+)`", text):
        ids.add(match.group(1))
    if not ids:
        errors.append(f"{rel(path)}: no Context7 library IDs found")
    return ids, errors


def load_bibtex_keys(path: Path = BIBLIOGRAPHY) -> tuple[set[str], list[str]]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return set(), [f"{rel(path)}: cannot read bibliography: {exc}"]
    keys = {
        match.group(1).strip() for match in re.finditer(r"@\w+\s*\{\s*([^,\s]+)", text)
    }
    if not keys:
        return keys, [f"{rel(path)}: no BibTeX keys found"]
    return keys, []


def repo_path_exists(ref: str) -> bool:
    path_text, _, anchor = ref.partition("#")
    if (
        not path_text
        or path_text.startswith("/")
        or path_text.startswith("docs/_generated/")
    ):
        return False
    path = ROOT / path_text
    resolved = path.resolve()
    if not is_relative_to(resolved, ROOT_RESOLVED) or not resolved.exists():
        return False
    if anchor and resolved.suffix in {".md", ".qmd"}:
        return anchor in markdown_anchors(resolved)
    return True


@dataclass(frozen=True)
class Skill:
    path: Path
    dirname: str
    name: str
    description: str
    metadata: dict[str, Any]
    line_count: int
    text: str


def skill_route_tokens(skill: Skill) -> set[str]:
    text = " ".join(
        [skill.name, skill.description]
        + metadata_strings(skill.metadata, {"triggers", "applies_to"})
    )
    return tokens(text)


def skill_boundary_tokens(skill: Skill) -> set[str]:
    text = " ".join(
        [skill.name, skill.description, skill.text]
        + metadata_strings(
            skill.metadata,
            {"not_when", "handoff_to", "evidence_required", "must_read"},
        )
    )
    return tokens(text)


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def load_frontmatter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError("missing YAML frontmatter")
    try:
        _, frontmatter, _ = text.split("---", 2)
    except ValueError as exc:
        raise ValueError("unterminated YAML frontmatter") from exc
    data = yaml.safe_load(frontmatter) or {}
    if not isinstance(data, dict):
        raise ValueError("frontmatter must be a mapping")
    return data


def body_without_frontmatter(text: str) -> str:
    if not text.startswith("---\n"):
        return text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return text
    return parts[2]


def first_match_line(text: str, pattern: re.Pattern[str]) -> int | None:
    match = pattern.search(text)
    if match is None:
        return None
    return text[: match.start()].count("\n") + 1


def load_skills(skills_dir: Path) -> tuple[list[Skill], list[str]]:
    errors: list[str] = []
    skills: list[Skill] = []

    if not skills_dir.is_dir():
        return [], [f"missing skills directory: {rel(skills_dir)}"]

    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        try:
            data = load_frontmatter(skill_md)
        except (OSError, ValueError, yaml.YAMLError) as exc:
            errors.append(f"{rel(skill_md)}: unreadable frontmatter: {exc}")
            continue

        name = data.get("name")
        metadata = data.get("metadata")
        if not isinstance(name, str) or not name.strip():
            errors.append(f"{rel(skill_md)}: missing non-empty name")
            continue
        if not isinstance(metadata, dict):
            errors.append(f"{rel(skill_md)}: missing metadata mapping")
            metadata = {}
        description = data.get("description")
        if not isinstance(description, str) or not description.strip():
            errors.append(f"{rel(skill_md)}: missing non-empty description")
            description = ""

        text = skill_md.read_text(encoding="utf-8")
        line_count = len(text.splitlines())
        skills.append(
            Skill(
                path=skill_md,
                dirname=skill_md.parent.name,
                name=name.strip(),
                description=description.strip(),
                metadata=metadata,
                line_count=line_count,
                text=text,
            )
        )

    if not skills:
        errors.append(f"{rel(skills_dir)}: no skills found")
    return skills, errors


def audit_wp6_inventory(path: Path, skills: list[Skill]) -> list[str]:
    """Require the exact ten-skill retained boundary."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"{rel(path)}: unreadable WP5 inventory: {exc}"]

    declared = data.get("active_skills")
    removed = data.get("removed_wp6_skills")
    errors: list[str] = []
    if not isinstance(declared, list) or not all(
        isinstance(item, str) for item in declared
    ):
        return [f"{rel(path)}: active_skills must be a string list"]
    if len(declared) != 10 or len(set(declared)) != 10:
        errors.append(
            f"{rel(path)}: active_skills must contain exactly ten unique names"
        )
    actual = {skill.name for skill in skills}
    expected = set(declared)
    if actual != expected:
        errors.append(
            f"{rel(path)}: active skill mismatch; missing={sorted(expected - actual)} "
            f"extra={sorted(actual - expected)}"
        )
    if set(removed or []) != {"aria-litkg-memory", "semantic-scholar-litkg"}:
        errors.append(
            f"{rel(path)}: removed_wp6_skills must contain exactly the two retired skills"
        )
    elif actual & set(removed):
        errors.append(
            f"{rel(path)}: removed skill remains active: {sorted(actual & set(removed))}"
        )
    return errors


def audit_wp6_capabilities(path: Path) -> list[str]:
    """Require all approved WP6 capability families to have closed dispositions."""
    required_families = {
        "authority-aware-search-and-task-routing",
        "claim-checking",
        "provenance-and-consolidation",
        "paper-ingestion-and-materialization",
        "semantic-scholar-enrichment",
        "neo4j-export-and-runtime",
        "mcp-integration",
        "auto-refresh-hooks-and-generated-documentation",
    }
    required_fields = {
        "capability_family",
        "status",
        "destination_owner",
        "evidence",
        "verification",
        "rollback_commit",
        "rationale",
    }
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
    except (OSError, csv.Error) as exc:
        return [f"{rel(path)}: unreadable WP6 capability ledger: {exc}"]
    errors: list[str] = []
    seen: set[str] = set()
    for index, row in enumerate(rows, start=2):
        missing = sorted(
            field for field in required_fields if not (row.get(field) or "").strip()
        )
        if missing:
            errors.append(
                f"{rel(path)}:{index}: empty required fields: {', '.join(missing)}"
            )
            continue
        family = row["capability_family"].strip()
        if family in seen:
            errors.append(
                f"{rel(path)}:{index}: duplicate capability family {family!r}"
            )
        seen.add(family)
        if row["status"].strip() not in {"replaced", "preserved", "retired"}:
            errors.append(f"{rel(path)}:{index}: unresolved status {row['status']!r}")
        if not re.fullmatch(r"[0-9a-f]{40}", row["rollback_commit"].strip()):
            errors.append(
                f"{rel(path)}:{index}: rollback_commit must be a full Git hash"
            )
    if seen != required_families:
        errors.append(
            f"{rel(path)}: capability coverage mismatch; missing={sorted(required_families - seen)} "
            f"extra={sorted(seen - required_families)}"
        )
    return errors


def audit_wp5_dispositions(
    path: Path, inventory_path: Path = WP5_INVENTORY
) -> list[str]:
    """Reject unresolved or incomplete source-owner disposition rows."""
    errors: list[str] = []
    try:
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
        removed = set(inventory["removed_or_merged_skills"])
        with path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
    except (OSError, json.JSONDecodeError, KeyError, csv.Error) as exc:
        return [f"{rel(path)}: unreadable WP5 disposition ledger: {exc}"]

    required = {
        "skill",
        "rule_family",
        "status",
        "destination_owners",
        "evidence",
        "verification",
        "rationale",
    }
    if not rows:
        return [f"{rel(path)}: disposition ledger must not be empty"]
    seen: set[str] = set()
    for index, row in enumerate(rows, start=2):
        missing = sorted(key for key in required if not (row.get(key) or "").strip())
        if missing:
            errors.append(
                f"{rel(path)}:{index}: empty required fields: {', '.join(missing)}"
            )
            continue
        skill = row["skill"].strip()
        seen.add(skill)
        if skill not in removed:
            errors.append(
                f"{rel(path)}:{index}: disposition names non-removed skill {skill!r}"
            )
        if row["status"].strip() not in CLOSED_DISPOSITIONS:
            errors.append(
                f"{rel(path)}:{index}: unresolved disposition status {row['status']!r}"
            )
        for owner in row["destination_owners"].split(";"):
            owner_path = ROOT / owner.strip()
            if not owner.strip() or not owner_path.exists():
                errors.append(
                    f"{rel(path)}:{index}: destination owner does not exist: {owner.strip()!r}"
                )
    if seen != removed:
        errors.append(
            f"{rel(path)}: disposition coverage mismatch; missing={sorted(removed - seen)} "
            f"extra={sorted(seen - removed)}"
        )
    return errors


def first_handoff_token(entry: Any) -> str | None:
    if not isinstance(entry, str):
        return None
    text = entry.strip()
    if not text:
        return None
    return re.split(r"\s+", text, maxsplit=1)[0]


def audit_skills(skills: list[Skill]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    known_names = {skill.name for skill in skills}
    context7_ids, context7_errors = load_context7_ids()
    bibtex_keys, bibtex_errors = load_bibtex_keys()
    errors.extend(context7_errors)
    errors.extend(bibtex_errors)

    for skill in skills:
        prefix = rel(skill.path)
        if skill.dirname != skill.name:
            errors.append(
                f"{prefix}: directory/frontmatter mismatch (directory={skill.dirname!r}, name={skill.name!r})"
            )

        missing = sorted(REQUIRED_METADATA - skill.metadata.keys())
        if missing:
            errors.append(f"{prefix}: missing metadata fields: {', '.join(missing)}")

        unknown_metadata = sorted(set(skill.metadata) - METADATA_KEYS)
        if unknown_metadata:
            errors.append(
                f"{prefix}: unknown metadata fields: {', '.join(unknown_metadata)}"
            )

        mode = skill.metadata.get("mode")
        if mode not in ALLOWED_MODES:
            errors.append(
                f"{prefix}: unsupported metadata.mode {mode!r}; expected one of {', '.join(sorted(ALLOWED_MODES))}"
            )

        for field in METADATA_KEYS - {"mode"}:
            value = skill.metadata.get(field)
            if value is not None and not isinstance(value, list):
                errors.append(f"{prefix}: metadata.{field} must be a list")
            elif isinstance(value, list):
                for item in value:
                    if not isinstance(item, str) or not item.strip():
                        errors.append(
                            f"{prefix}: metadata.{field} entries must be non-empty strings"
                        )

        canonical_sources = skill.metadata.get("canonical_sources") or []
        if isinstance(canonical_sources, list):
            if not canonical_sources:
                errors.append(f"{prefix}: metadata.canonical_sources must not be empty")
            for source in canonical_sources:
                if not isinstance(source, str) or not source.strip():
                    errors.append(
                        f"{prefix}: metadata.canonical_sources entries must be non-empty strings"
                    )
                    continue
                source_path, _, anchor = source.partition("#")
                path = ROOT / source_path
                if not source_path or source_path.startswith("/"):
                    errors.append(
                        f"{prefix}: canonical source {source!r} must be a relative repo path"
                    )
                    continue
                resolved_path = path.resolve()
                if not is_relative_to(resolved_path, ROOT_RESOLVED):
                    errors.append(
                        f"{prefix}: canonical source {source_path!r} escapes the repo root"
                    )
                    continue
                if not resolved_path.exists():
                    errors.append(
                        f"{prefix}: canonical source {source_path!r} does not exist"
                    )
                    continue
                if anchor and resolved_path.suffix in {".md", ".qmd"}:
                    anchors = markdown_anchors(resolved_path)
                    if anchor not in anchors:
                        errors.append(
                            f"{prefix}: canonical source anchor {source!r} was not found"
                        )

        handoffs = skill.metadata.get("handoff_to") or []
        if isinstance(handoffs, list):
            for handoff in handoffs:
                token = first_handoff_token(handoff)
                if token is None:
                    errors.append(f"{prefix}: empty or non-string handoff entry")
                    continue
                if ":" in token:
                    namespace = token.split(":", 1)[0]
                    if namespace in BLOCKED_HANDOFF_PREFIXES:
                        errors.append(
                            f"{prefix}: unresolved handoff namespace in {handoff!r}; "
                            "use a local skill name or declared capability wording"
                        )
                elif (
                    token not in known_names and token not in DECLARED_CAPABILITY_TOKENS
                ):
                    warnings.append(
                        f"{prefix}: handoff target {token!r} is not a known skill name"
                    )

        applies_to = skill.metadata.get("applies_to") or []
        if (
            isinstance(applies_to, list)
            and "**" in applies_to
            and skill.name not in BROAD_APPLIES_EXEMPTIONS
        ):
            warnings.append(f"{prefix}: broad applies_to '**' should stay intentional")

        if skill.line_count > HOT_PATH_LINE_BUDGET:
            warnings.append(
                f"{prefix}: hot path is {skill.line_count} lines "
                f"(budget {HOT_PATH_LINE_BUDGET}); prune or move detail to references"
            )
        elif skill.line_count > PREFERRED_HOT_PATH_LINE_BUDGET:
            warnings.append(
                f"{prefix}: hot path is {skill.line_count} lines "
                f"(preferred {PREFERRED_HOT_PATH_LINE_BUDGET}); keep progressive disclosure tight"
            )

        context7_refs = skill.metadata.get("context7_refs") or []
        if isinstance(context7_refs, list):
            for ref in context7_refs:
                if not isinstance(ref, str) or not ref.strip():
                    continue
                if not ref.startswith("/"):
                    errors.append(
                        f"{prefix}: metadata.context7_refs entry {ref!r} must be an exact Context7 ID"
                    )
                elif ref not in context7_ids:
                    errors.append(
                        f"{prefix}: metadata.context7_refs entry {ref!r} is not listed in {rel(CONTEXT7_IDS)}"
                    )

        literature_refs = skill.metadata.get("literature_refs") or []
        if isinstance(literature_refs, list):
            for ref in literature_refs:
                if not isinstance(ref, str) or not ref.strip():
                    continue
                if ref.startswith("docs/_generated/"):
                    errors.append(
                        f"{prefix}: metadata.literature_refs entry {ref!r} points to generated evidence, "
                        "not an owning literature source"
                    )
                elif ref in bibtex_keys or repo_path_exists(ref):
                    continue
                else:
                    errors.append(
                        f"{prefix}: metadata.literature_refs entry {ref!r} is not a BibTeX key, "
                        "or existing repo path"
                    )

        tool_refs = skill.metadata.get("tool_refs") or []
        if isinstance(tool_refs, list):
            for ref in tool_refs:
                if not isinstance(ref, str) or not ref.strip():
                    continue
                if not TOOL_REF_RE.match(ref):
                    errors.append(
                        f"{prefix}: metadata.tool_refs entry {ref!r} must use canonical "
                        "mcp__<server>.<tool_name> form"
                    )

    return errors, warnings


def audit_semantic_drift(skills: list[Skill]) -> list[str]:
    """Warn when hot-path skills look like durable project-truth owners."""
    warnings: list[str] = []
    for skill in skills:
        body = body_without_frontmatter(skill.text)
        if not body.strip():
            continue
        body_offset = skill.text[: skill.text.find(body)].count("\n")
        for rule_id, pattern, message in SEMANTIC_DRIFT_RULES:
            if rule_id in SEMANTIC_DRIFT_EXEMPTIONS.get(skill.name, set()):
                continue
            line = first_match_line(body, pattern)
            if line is None:
                continue
            warnings.append(
                f"{rel(skill.path)}:{body_offset + line}: possible semantic drift "
                f"({rule_id}); {message}; keep only routing/evidence text in skills"
            )
    return warnings


def audit_routing_fixtures(
    path: Path, skills_by_name: dict[str, Skill]
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if not path.is_file():
        return [f"missing routing fixture file: {rel(path)}"], []

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"{rel(path)}: unreadable JSON: {exc}"], []

    fixtures = data.get("fixtures") if isinstance(data, dict) else None
    if not isinstance(fixtures, list) or not fixtures:
        return [f"{rel(path)}: fixtures must be a non-empty list"], []

    seen_ids: set[str] = set()
    allowed_fixture_keys = {
        "id",
        "task",
        "expected_skills",
        "forbidden_tool_refs",
        "non_goals",
    }
    known_names = set(skills_by_name)
    route_tokens_by_skill = {
        name: skill_route_tokens(skill) for name, skill in skills_by_name.items()
    }
    boundary_tokens_by_skill = {
        name: skill_boundary_tokens(skill) for name, skill in skills_by_name.items()
    }
    for index, fixture in enumerate(fixtures, start=1):
        if not isinstance(fixture, dict):
            errors.append(f"{rel(path)} fixture #{index}: must be an object")
            continue
        extra_keys = sorted(set(fixture) - allowed_fixture_keys)
        if extra_keys:
            errors.append(
                f"{rel(path)} fixture #{index}: unknown keys: {', '.join(extra_keys)}"
            )
        fixture_id = fixture.get("id")
        if not isinstance(fixture_id, str) or not fixture_id:
            errors.append(f"{rel(path)} fixture #{index}: missing id")
        elif fixture_id in seen_ids:
            errors.append(f"{rel(path)} fixture {fixture_id}: duplicate id")
        else:
            seen_ids.add(fixture_id)

        task = fixture.get("task")
        if not isinstance(task, str) or not task.strip():
            errors.append(f"{rel(path)} fixture {fixture_id or index}: missing task")
            fixture_tokens = tokens(str(fixture_id or ""))
        else:
            fixture_tokens = tokens(f"{fixture_id or ''} {task}")

        expected = fixture.get("expected_skills")
        forbidden_tool_refs = fixture.get("forbidden_tool_refs", [])
        if not isinstance(expected, list) or not expected:
            errors.append(
                f"{rel(path)} fixture {fixture_id or index}: expected_skills must be a non-empty list"
            )
        elif not all(isinstance(skill, str) and skill.strip() for skill in expected):
            errors.append(
                f"{rel(path)} fixture {fixture_id or index}: expected_skills entries must be non-empty strings"
            )
        else:
            missing = sorted(skill for skill in expected if skill not in known_names)
            if missing:
                errors.append(
                    f"{rel(path)} fixture {fixture_id or index}: unknown expected skill(s): {', '.join(missing)}"
                )

            if len(expected) > 2:
                warnings.append(
                    f"{rel(path)} fixture {fixture_id or index}: more than two expected skills; "
                    "keep routing fixtures focused"
                )

            for skill_name in expected:
                overlap = fixture_tokens & route_tokens_by_skill.get(skill_name, set())
                if not overlap:
                    errors.append(
                        f"{rel(path)} fixture {fixture_id or index}: expected skill "
                        f"{skill_name!r} has no routing-cue overlap with fixture id/task"
                    )

            expected_skill_tool_refs: set[str] = set()
            for skill_name in expected:
                expected_skill_tool_refs.update(
                    skills_by_name[skill_name].metadata.get("tool_refs") or []
                )

            if not isinstance(forbidden_tool_refs, list):
                errors.append(
                    f"{rel(path)} fixture {fixture_id or index}: forbidden_tool_refs must be a list"
                )
            elif not all(
                isinstance(item, str) and item.strip() for item in forbidden_tool_refs
            ):
                errors.append(
                    f"{rel(path)} fixture {fixture_id or index}: forbidden_tool_refs entries must be non-empty strings"
                )
            else:
                for tool_ref in forbidden_tool_refs:
                    if not TOOL_REF_RE.match(tool_ref):
                        errors.append(
                            f"{rel(path)} fixture {fixture_id or index}: forbidden_tool_ref "
                            f"{tool_ref!r} must use canonical mcp__<server>.<tool_name> form"
                        )
                    elif tool_ref in expected_skill_tool_refs:
                        errors.append(
                            f"{rel(path)} fixture {fixture_id or index}: forbidden_tool_ref "
                            f"{tool_ref!r} is declared by expected skills"
                        )

        non_goals = fixture.get("non_goals")
        if not isinstance(non_goals, list) or not non_goals:
            errors.append(
                f"{rel(path)} fixture {fixture_id or index}: non_goals must be a non-empty list"
            )
        elif not all(isinstance(item, str) and item.strip() for item in non_goals):
            errors.append(
                f"{rel(path)} fixture {fixture_id or index}: non_goals entries must be non-empty strings"
            )
        else:
            expected_set = set(expected) if isinstance(expected, list) else set()
            boundary_tokens = set()
            for skill_name in expected_set:
                boundary_tokens |= boundary_tokens_by_skill.get(skill_name, set())
            for skill_name, route_tokens in route_tokens_by_skill.items():
                if skill_name not in expected_set:
                    boundary_tokens |= route_tokens

            for item in non_goals:
                item_tokens = tokens(item)
                if item_tokens and not item_tokens & boundary_tokens:
                    errors.append(
                        f"{rel(path)} fixture {fixture_id or index}: non_goal "
                        f"{item!r} does not match expected-skill boundaries or adjacent skill cues"
                    )

    return errors, warnings


def self_test_skill_text(
    name: str,
    canonical_sources: list[str],
    body: str,
    extra_metadata: str = "",
) -> str:
    canonical_yaml = "\n".join(f'    - "{source}"' for source in canonical_sources)
    extra = f"{extra_metadata.rstrip()}\n" if extra_metadata.strip() else ""
    return f"""---
name: {name}
description: Test-only skill fixture.
metadata:
  mode: router
  not_when:
    - "test-only adjacent owner"
  handoff_to:
    - "external test capability"
  evidence_required:
    - "test evidence"
  applies_to:
    - ".tmp/**"
  triggers:
    - "test"
  must_read:
    - "AGENTS.md"
  canonical_sources:
{canonical_yaml}
{extra}\
  verification:
    - "test verification"
---

# Test Skill

{body}
"""


def write_self_test_skill(root: Path, name: str, text: str) -> Path:
    skill_dir = root / "skills" / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    path = skill_dir / "SKILL.md"
    path.write_text(text, encoding="utf-8")
    return path


def self_test_fixture_path(root: Path, data: dict[str, Any]) -> Path:
    path = root / "fixtures.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def routing_fixture_with_expected(
    fixture_id: str, expected: list[str]
) -> dict[str, Any]:
    data = cast(
        dict[str, Any],
        json.loads(ROUTING_FIXTURES.read_text(encoding="utf-8")),
    )
    for fixture in data["fixtures"]:
        if fixture["id"] == fixture_id:
            fixture["expected_skills"] = expected
            return data
    raise AssertionError(f"missing fixture {fixture_id}")


def run_self_tests() -> tuple[list[str], list[str]]:
    failures: list[str] = []
    passes: list[str] = []

    def expect(test_name: str, condition: bool, detail: str) -> None:
        if condition:
            passes.append(test_name)
        else:
            failures.append(f"{test_name}: {detail}")

    tmp_parent = ROOT / ".tmp"
    tmp_parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="scaffold-audit-", dir=tmp_parent) as tmp:
        tmp_root = Path(tmp)

        escape_text = self_test_skill_text(
            "escape-skill",
            ["../outside.md"],
            "Use this test body for canonical source escape validation.",
        )
        write_self_test_skill(tmp_root, "escape-skill", escape_text)
        skills, load_errors = load_skills(tmp_root / "skills")
        errors, _ = audit_skills(skills)
        expect(
            "canonical-source-escape",
            not load_errors
            and any("escapes the repo root" in error for error in errors),
            "escaped canonical source was not rejected",
        )

        anchor_text = self_test_skill_text(
            "missing-anchor-skill",
            [".agents/references/source_order.md#definitely-missing-anchor"],
            "Use this test body for missing anchor validation.",
        )
        write_self_test_skill(tmp_root, "missing-anchor-skill", anchor_text)
        skills, load_errors = load_skills(tmp_root / "skills")
        errors, _ = audit_skills(skills)
        expect(
            "missing-canonical-anchor",
            not load_errors
            and any("canonical source anchor" in error for error in errors),
            "missing markdown anchor was not rejected",
        )

        skills, load_errors = load_skills(SKILLS_DIR)
        skills_by_name = {skill.name: skill for skill in skills}
        expect("live-skills-load", not load_errors, "; ".join(load_errors))

        missing_fixture = {
            "fixtures": [
                {
                    "id": "missing-task-and-non-goals",
                    "expected_skills": ["aria-nbv-context"],
                }
            ]
        }
        errors, _ = audit_routing_fixtures(
            self_test_fixture_path(tmp_root, missing_fixture), skills_by_name
        )
        expect(
            "fixture-missing-task-non-goals",
            any("missing task" in error for error in errors)
            and any("non_goals must be" in error for error in errors),
            "fixture schema omissions were not rejected",
        )

        local_as_docs = routing_fixture_with_expected(
            "local-file-lookup", ["aria-docs"]
        )
        errors, _ = audit_routing_fixtures(
            self_test_fixture_path(tmp_root, local_as_docs), skills_by_name
        )
        expect(
            "local-lookup-not-docs",
            any(
                "aria-docs" in error and "no routing-cue overlap" in error
                for error in errors
            ),
            "local lookup incorrectly passed as docs routing",
        )

        docs_as_measurement = routing_fixture_with_expected(
            "quarto-typst-mermaid-docs", ["measured-autoresearch"]
        )
        errors, _ = audit_routing_fixtures(
            self_test_fixture_path(tmp_root, docs_as_measurement), skills_by_name
        )
        expect(
            "docs-not-measured-autoresearch",
            any(
                "measured-autoresearch" in error and "no routing-cue overlap" in error
                for error in errors
            ),
            "Quarto/Typst/Mermaid work incorrectly passed as measurement routing",
        )

        drift_text = self_test_skill_text(
            "truth-leak-skill",
            [".agents/references/source_order.md#role-split"],
            "This planned but unimplemented Q_H roadmap detail will be implemented later.",
        )
        drift_path = write_self_test_skill(tmp_root, "truth-leak-skill", drift_text)
        drift_skill = Skill(
            path=drift_path,
            dirname="truth-leak-skill",
            name="truth-leak-skill",
            description="Test-only skill fixture.",
            metadata={},
            line_count=len(drift_text.splitlines()),
            text=drift_text,
        )
        warnings = audit_semantic_drift([drift_skill])
        expect(
            "planned-detail-semantic-drift",
            any("possible semantic drift" in warning for warning in warnings),
            "planned thesis detail in skill body was not warned",
        )

        unknown_context7_text = self_test_skill_text(
            "unknown-context7-skill",
            [".agents/references/context7_library_ids.md"],
            "Use this test body for Context7 validation.",
            '  context7_refs:\n    - "/missing/context7-id"',
        )
        write_self_test_skill(tmp_root, "unknown-context7-skill", unknown_context7_text)
        skills, load_errors = load_skills(tmp_root / "skills")
        errors, _ = audit_skills(skills)
        expect(
            "unknown-context7-ref",
            not load_errors
            and any("metadata.context7_refs" in error for error in errors),
            "unknown Context7 ID was not rejected",
        )

        missing_literature_text = self_test_skill_text(
            "missing-literature-skill",
            [".agents/references/source_order.md#role-split"],
            "Use this test body for literature ref validation.",
            '  literature_refs:\n    - "DefinitelyMissingBibKey2026"',
        )
        write_self_test_skill(
            tmp_root, "missing-literature-skill", missing_literature_text
        )
        skills, load_errors = load_skills(tmp_root / "skills")
        errors, _ = audit_skills(skills)
        expect(
            "missing-literature-ref",
            not load_errors
            and any("metadata.literature_refs" in error for error in errors),
            "missing literature ref was not rejected",
        )

        malformed_tool_text = self_test_skill_text(
            "malformed-tool-skill",
            [".agents/references/source_order.md#role-split"],
            "Use this test body for tool ref validation.",
            '  tool_refs:\n    - "Context7 get-library-docs"',
        )
        write_self_test_skill(tmp_root, "malformed-tool-skill", malformed_tool_text)
        skills, load_errors = load_skills(tmp_root / "skills")
        errors, _ = audit_skills(skills)
        expect(
            "malformed-tool-ref",
            not load_errors and any("metadata.tool_refs" in error for error in errors),
            "malformed tool ref was not rejected",
        )

        live_skills, live_load_errors = load_skills(SKILLS_DIR)
        inventory_errors = live_load_errors + audit_wp6_inventory(
            WP6_INVENTORY, live_skills
        )
        expect("wp6-live-inventory", not inventory_errors, "; ".join(inventory_errors))
        disposition_errors = audit_wp5_dispositions(WP5_DISPOSITIONS)
        expect(
            "wp5-closed-dispositions",
            not disposition_errors,
            "; ".join(disposition_errors),
        )
        capability_errors = audit_wp6_capabilities(WP6_CAPABILITIES)
        expect(
            "wp6-closed-capabilities",
            not capability_errors,
            "; ".join(capability_errors),
        )

    return passes, failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json", action="store_true", help="emit machine-readable audit output"
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="run negative probes for scaffold-audit invariants",
    )
    args = parser.parse_args()

    if args.self_test:
        passes, failures = run_self_tests()
        self_test_payload = {"passed": passes, "failures": failures}
        if args.json:
            print(json.dumps(self_test_payload, indent=2, sort_keys=True))
        else:
            print(
                f"scaffold-audit self-test: passed={len(passes)} failures={len(failures)}"
            )
            for failure in failures:
                print(f"- {failure}")
        return 1 if failures else 0

    skills, load_errors = load_skills(SKILLS_DIR)
    inventory_errors = audit_wp6_inventory(WP6_INVENTORY, skills)
    disposition_errors = audit_wp5_dispositions(WP5_DISPOSITIONS)
    capability_errors = audit_wp6_capabilities(WP6_CAPABILITIES)
    skill_errors, skill_warnings = audit_skills(skills)
    drift_warnings = audit_semantic_drift(skills)
    fixture_errors, fixture_warnings = audit_routing_fixtures(
        ROUTING_FIXTURES,
        {skill.name: skill for skill in skills},
    )

    errors = (
        load_errors
        + inventory_errors
        + disposition_errors
        + capability_errors
        + skill_errors
        + fixture_errors
    )
    warnings = skill_warnings + drift_warnings + fixture_warnings
    payload = {
        "skills": len(skills),
        "errors": errors,
        "warnings": warnings,
    }

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(
            f"scaffold-audit: skills={len(skills)} errors={len(errors)} warnings={len(warnings)}"
        )
        if errors:
            print("\nErrors:")
            for error in errors:
                print(f"- {error}")
        if warnings:
            print("\nWarnings:")
            for warning in warnings:
                print(f"- {warning}")

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
