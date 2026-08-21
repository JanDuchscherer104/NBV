#!/usr/bin/env python3
"""Audit ARIA-NBV agent skill frontmatter, references, and routing fixtures."""

from __future__ import annotations

import argparse
import json
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
ROOT_RESOLVED = ROOT.resolve()
SKILLS_DIR = ROOT / ".agents" / "skills"
ROUTING_FIXTURES = ROOT / "scripts" / "scaffold" / "fixtures" / "routing.json"
UPSTREAM_SKILL_PATHS = {SKILLS_DIR / "graphify" / "SKILL.md"}
APPROVED_CUSTOM_SKILL_PATHS = {
    SKILLS_DIR / name / "SKILL.md"
    for name in (
        "agent-behavior",
        "agents-db",
        "aria-grill",
        "aria-nbv-context",
        "aria-nbv-mermaid",
        "lrz-ai-systems",
        "measured-autoresearch",
        "python-standards",
        "rerun-nbv-inspector",
        "simplification",
        "typst-authoring",
    )
}

FRONTMATTER_KEYS = {"name", "description"}
HOT_PATH_LINE_BUDGET = 150
CONTEXT7_REGISTRY = (
    ROOT
    / ".agents"
    / "skills"
    / "aria-nbv-context"
    / "references"
    / "context7_library_ids.md"
)
CONTEXT7_ID_RE = re.compile(r"^/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)?$")
BACKTICK_TOKEN_RE = re.compile(r"`([^`\n]+)`")
TOOL_REF_RE = re.compile(r"^mcp__[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+|__[A-Za-z0-9_]+)$")
DEPRECATED_CONTEXT7_TOOL_IDS = {
    "mcp__MCP_DOCKER.resolve_library_id",
    "mcp__MCP_DOCKER.get_library_docs",
}
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
        "roadmap or thesis claims should point to canonical thesis/current-state sources",
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
    "aria-nbv-mermaid": {"formula-detail"},
}


def context7_tokens(text: str) -> set[str]:
    """Extract exact backticked Context7 IDs, excluding URL path substrings."""

    return {
        match.group(1).strip()
        for match in BACKTICK_TOKEN_RE.finditer(text)
        if CONTEXT7_ID_RE.fullmatch(match.group(1).strip())
    }


def explicit_tool_ids(text: str) -> set[str]:
    """Return canonical tool identifiers declared as exact backtick tokens."""
    return {
        token.strip()
        for token in BACKTICK_TOKEN_RE.findall(text)
        if TOOL_REF_RE.fullmatch(token.strip())
    }


def custom_skill_paths(skills_dir: Path = SKILLS_DIR) -> set[Path]:
    """Return discovered custom skill entrypoints, excluding upstream Graphify."""
    return {
        path.resolve()
        for path in skills_dir.glob("*/SKILL.md")
        if path.parent.name != "graphify"
    }


def active_custom_reference_files(skills_dir: Path = SKILLS_DIR) -> tuple[Path, ...]:
    """Return every file in custom skill references trees, excluding Graphify."""
    return tuple(
        sorted(
            path.resolve()
            for skill_path in custom_skill_paths(skills_dir)
            for path in skill_path.parent.glob("references/**/*")
            if path.is_file()
        )
    )


def deprecated_context7_calls(paths: tuple[Path, ...]) -> dict[Path, set[str]]:
    """Find deprecated Context7 identifiers in active reference files."""
    findings: dict[Path, set[str]] = {}
    for path in paths:
        content = path.read_bytes()
        identifiers = {
            identifier
            for identifier in DEPRECATED_CONTEXT7_TOOL_IDS
            if identifier.encode() in content
        }
        if identifiers:
            findings[path] = identifiers
    return findings


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


def load_context7_registry(
    path: Path = CONTEXT7_REGISTRY,
) -> tuple[set[str], list[str]]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return set(), [f"{rel(path)}: cannot read Context7 registry: {exc}"]
    ids = context7_tokens(text)
    if not ids:
        return ids, [f"{rel(path)}: no exact Context7 IDs found"]
    return ids, []


@dataclass(frozen=True)
class Skill:
    path: Path
    dirname: str
    name: str
    description: str
    line_count: int
    text: str


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def is_upstream_skill(path: Path) -> bool:
    """Return whether a live skill is governed by an exact upstream bundle."""

    return path in UPSTREAM_SKILL_PATHS


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
        raise TypeError("frontmatter must be a mapping")
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
        if not isinstance(name, str) or not name.strip():
            errors.append(f"{rel(skill_md)}: missing non-empty name")
            continue
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
                line_count=line_count,
                text=text,
            )
        )

    if not skills:
        errors.append(f"{rel(skills_dir)}: no skills found")
    return skills, errors


def markdown_reference_links(skill: Skill) -> list[str]:
    """Return Markdown reference links declared by a skill body."""

    body = body_without_frontmatter(skill.text)
    return re.findall(r"\]\((?:\./)?(references/[^)\s]+\.md(?:#[^)\s]+)?)\)", body)


def local_markdown_pointers(path: Path, text: str) -> list[str]:
    """Extract explicit local Markdown pointers, excluding URLs and prose."""
    pointers = [
        pointer
        for pointer in re.findall(r"\]\(([^)\s]+\.md(?:#[^)\s]+)?)\)", text)
        if not pointer.startswith(("http://", "https://", "mailto:"))
        and not any(char in pointer for char in "*?[")
    ]
    package_index = (
        path.name == "index.md"
        and path.parent.name == "packages"
        and path.parent.parent.name == "references"
    )
    for token in BACKTICK_TOKEN_RE.findall(text):
        if not token.endswith(".md") and ".md#" not in token:
            continue
        if token.startswith(("http://", "https://", "mailto:")):
            continue
        if any(char in token for char in "*?["):
            continue
        explicit = "/" in token or token.startswith(".")
        candidate = resolve_markdown_pointer(path, token)
        if (
            candidate is not None
            and candidate.is_file()
            and (explicit or (package_index and "/" not in token))
        ):
            pointers.append(token)
    return pointers


def resolve_markdown_pointer(source: Path, pointer: str) -> Path | None:
    """Resolve a repository-relative pointer using the skill's conventions."""
    relative, _, _ = pointer.partition("#")
    if relative.startswith(("http://", "https://", "mailto:", "/")):
        return None
    skill_root = next(
        (parent for parent in source.parents if (parent / "SKILL.md").is_file()),
        None,
    )
    if relative.startswith("references/") and skill_root is not None:
        return (skill_root / relative).resolve()
    if relative.startswith(("./", "../")):
        return (source.parent / relative).resolve()
    if relative.startswith((".agents/", "aria_nbv/", "docs/", "scripts/")):
        return (ROOT / relative).resolve()
    if relative.startswith("assets/"):
        return (ROOT / relative).resolve()
    if source.name == "graphify-aria-boundary.md" and relative == "references/hooks.md":
        return (SKILLS_DIR / "graphify" / relative).resolve()
    return (source.parent / relative).resolve()


def audit_reference_graph(skills: list[Skill]) -> list[str]:
    """Validate local pointers and bound custom reference reachability."""
    errors: list[str] = []
    for skill in skills:
        if is_upstream_skill(skill.path):
            continue
        skill_root = skill.path.parent
        reference_files = tuple(sorted(skill_root.glob("references/**/*.md")))
        nodes = {path.resolve() for path in reference_files}
        edges: dict[Path, set[Path]] = {skill.path.resolve(): set()}
        edges.update({node: set() for node in nodes})
        sources = (skill.path, *reference_files)
        for source in sources:
            for pointer in local_markdown_pointers(
                source, source.read_text(encoding="utf-8")
            ):
                target = resolve_markdown_pointer(source, pointer)
                if target is None:
                    continue
                _, _, anchor = pointer.partition("#")
                if not target.is_file():
                    errors.append(
                        f"{rel(source)}: reference pointer {pointer!r} does not exist"
                    )
                    continue
                if anchor and anchor not in markdown_anchors(target):
                    errors.append(
                        f"{rel(source)}: reference pointer anchor {pointer!r} was not found"
                    )
                if target in edges and target in nodes:
                    edges[source.resolve()].add(target)

        reachable: dict[Path, int] = {}
        active: list[Path] = []
        active_set: set[Path] = set()

        def visit(
            node: Path,
            depth: int,
        ) -> None:
            reachable[node] = min(depth, reachable.get(node, depth))
            if node in nodes and depth > 2:
                errors.append(
                    f"{rel(node)}: progressive-disclosure reference depth exceeds 2 "
                    f"on path: {' -> '.join(rel(path) for path in (*active, node))}"
                )
            active.append(node)
            active_set.add(node)
            for child in edges.get(node, ()):
                if child in active_set:
                    cycle = " -> ".join(rel(path) for path in (*active, child))
                    errors.append(
                        f"{rel(node)}: progressive-disclosure cycle/backedge: {cycle}"
                    )
                    continue
                visit(child, depth + 1)
            active.pop()
            active_set.remove(node)

        visit(skill.path.resolve(), 0)
        for node in nodes:
            if node not in reachable:
                errors.append(f"{rel(node)}: orphan progressive-disclosure reference")
    return sorted(set(errors))


def description_sentence_count(description: str) -> int:
    return len(re.findall(r"(?<=[.!?])(?:['\")\]]*)?(?=\s|$)", description))


def audit_skills(skills: list[Skill]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    context7_registry, context7_registry_errors = load_context7_registry()
    errors.extend(context7_registry_errors)

    for skill in skills:
        prefix = rel(skill.path)
        if skill.dirname != skill.name:
            errors.append(
                f"{prefix}: directory/frontmatter mismatch (directory={skill.dirname!r}, name={skill.name!r})"
            )

        if is_upstream_skill(skill.path):
            continue

        frontmatter = load_frontmatter(skill.path)
        unexpected = sorted(set(frontmatter) - FRONTMATTER_KEYS)
        if unexpected:
            errors.append(
                f"{prefix}: unexpected frontmatter keys: {', '.join(unexpected)}"
            )
        if description_sentence_count(skill.description) != 1:
            errors.append(f"{prefix}: description must be exactly one sentence")
        if len(skill.description.split()) > 45:
            warnings.append(
                f"{prefix}: description is {len(skill.description.split())} words "
                "(soft budget 45)"
            )

        if skill.line_count > HOT_PATH_LINE_BUDGET:
            warnings.append(
                f"{prefix}: hot path is {skill.line_count} lines "
                f"(budget {HOT_PATH_LINE_BUDGET}); prune or move detail to references"
            )

        for link in markdown_reference_links(skill):
            relative, _, anchor = link.partition("#")
            reference = skill.path.parent / relative
            if not reference.is_file():
                errors.append(f"{prefix}: reference link {link!r} does not exist")
            elif anchor and anchor not in markdown_anchors(reference):
                errors.append(f"{prefix}: reference link anchor {link!r} was not found")

    discovered_custom = custom_skill_paths(SKILLS_DIR)
    approved_custom = {path.resolve() for path in APPROVED_CUSTOM_SKILL_PATHS}
    if discovered_custom != approved_custom:
        errors.append(
            "custom skill entrypoints must equal approved set: "
            f"found {sorted(rel(path) for path in discovered_custom)}, expected "
            f"{sorted(rel(path) for path in approved_custom)}"
        )

    reference_files = tuple(
        path for path in SKILLS_DIR.rglob("*.md") if "graphify" not in path.parts
    )
    observed_context7: dict[str, list[Path]] = {}
    for path in reference_files:
        for library_id in context7_tokens(path.read_text(encoding="utf-8")):
            observed_context7.setdefault(library_id, []).append(path)
    for library_id, owners in observed_context7.items():
        if library_id not in context7_registry:
            errors.append(
                f"{rel(CONTEXT7_REGISTRY)}: Context7 ID {library_id!r} is absent from the registry; "
                f"found {[rel(path) for path in owners]}"
            )
    for library_id in context7_registry:
        owners = [
            path
            for path in reference_files
            if library_id in context7_tokens(path.read_text(encoding="utf-8"))
        ]
        if owners != [CONTEXT7_REGISTRY]:
            errors.append(
                f"{rel(CONTEXT7_REGISTRY)}: Context7 ID {library_id!r} must have one registry owner; "
                f"found {[rel(path) for path in owners]}"
            )

    for call in (
        "mcp__codex_apps__context7_query_docs",
        "mcp__codex_apps__context7_resolve_library_id",
    ):
        owners = [
            path
            for path in reference_files
            if call in explicit_tool_ids(path.read_text(encoding="utf-8"))
        ]
        if owners != [CONTEXT7_REGISTRY]:
            errors.append(
                f"{rel(CONTEXT7_REGISTRY)}: Context7 tool {call!r} must have one registry owner; "
                f"found {[rel(path) for path in owners]}"
            )

    for path, identifiers in deprecated_context7_calls(
        active_custom_reference_files()
    ).items():
        errors.append(
            f"{rel(path)}: deprecated Docker-MCP Context7 tool identifiers: "
            f"{', '.join(sorted(identifiers))}"
        )

    errors.extend(audit_reference_graph(skills))

    return errors, warnings


def audit_semantic_drift(skills: list[Skill]) -> list[str]:
    """Warn when hot-path skills look like durable project-truth owners."""
    warnings: list[str] = []
    for skill in skills:
        if is_upstream_skill(skill.path):
            continue
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

    if not isinstance(data, dict):
        return [f"{rel(path)}: top level must be an object"], []
    if set(data) != {"version", "purpose", "fixtures"}:
        unknown = sorted(set(data) - {"version", "purpose", "fixtures"})
        missing = sorted({"version", "purpose", "fixtures"} - set(data))
        return [
            f"{rel(path)}: top-level keys must be version, purpose, fixtures"
            + (f"; unknown: {', '.join(unknown)}" if unknown else "")
            + (f"; missing: {', '.join(missing)}" if missing else "")
        ], []
    if not isinstance(data["version"], int):
        errors.append(f"{rel(path)}: version must be an integer")
    if not isinstance(data["purpose"], str) or not data["purpose"].strip():
        errors.append(f"{rel(path)}: purpose must be a non-empty string")

    fixtures = data["fixtures"]
    if not isinstance(fixtures, list) or not fixtures:
        return [f"{rel(path)}: fixtures must be a non-empty list"], []

    seen_ids: set[str] = set()
    allowed_fixture_keys = {
        "id",
        "task",
        "expected_owner_paths",
        "stable_skill_ids",
        "expected_tool_refs",
        "forbidden_tool_refs",
        "required_outcomes",
        "forbidden_outcomes",
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
        owner_paths = fixture.get("expected_owner_paths")
        resolved_owner_paths: list[Path] = []
        if not isinstance(owner_paths, list) or not owner_paths:
            errors.append(
                f"{rel(path)} fixture {fixture_id or index}: expected_owner_paths must be a non-empty list"
            )
        elif not all(isinstance(owner, str) and owner.strip() for owner in owner_paths):
            errors.append(
                f"{rel(path)} fixture {fixture_id or index}: expected_owner_paths entries must be non-empty strings"
            )
        else:
            for owner in owner_paths:
                owner_path = (ROOT / owner).resolve()
                if not owner_path.is_relative_to(ROOT_RESOLVED):
                    errors.append(
                        f"{rel(path)} fixture {fixture_id or index}: owner path escapes repo root: {owner!r}"
                    )
                elif not owner_path.exists():
                    errors.append(
                        f"{rel(path)} fixture {fixture_id or index}: owner path does not exist: {owner!r}"
                    )
                else:
                    resolved_owner_paths.append(owner_path)

        stable_skill_ids = fixture.get("stable_skill_ids", [])
        if not isinstance(stable_skill_ids, list):
            errors.append(
                f"{rel(path)} fixture {fixture_id or index}: stable_skill_ids must be a list"
            )
        elif not all(
            isinstance(skill_id, str) and skill_id.strip()
            for skill_id in stable_skill_ids
        ):
            errors.append(
                f"{rel(path)} fixture {fixture_id or index}: stable_skill_ids entries must be non-empty strings"
            )
        else:
            for skill_id in stable_skill_ids:
                if skill_id != "python-standards":
                    errors.append(
                        f"{rel(path)} fixture {fixture_id or index}: unapproved stable skill id: {skill_id!r}"
                    )
                elif (
                    skills_by_name[skill_id].path.resolve() not in resolved_owner_paths
                ):
                    errors.append(
                        f"{rel(path)} fixture {fixture_id or index}: stable skill id {skill_id!r} lacks its owner path"
                    )

        expected_tool_refs = fixture.get("expected_tool_refs", [])
        forbidden_tool_refs = fixture.get("forbidden_tool_refs", [])

        if not isinstance(expected_tool_refs, list) or not all(
            isinstance(item, str) and item.strip() for item in expected_tool_refs
        ):
            errors.append(
                f"{rel(path)} fixture {fixture_id or index}: expected_tool_refs must be a list of strings"
            )
        else:
            for tool_ref in expected_tool_refs:
                if not TOOL_REF_RE.match(tool_ref):
                    errors.append(
                        f"{rel(path)} fixture {fixture_id or index}: malformed expected_tool_ref {tool_ref!r}"
                    )
                elif not any(
                    tool_ref
                    in explicit_tool_ids(owner_path.read_text(encoding="utf-8"))
                    for owner_path in resolved_owner_paths
                    if owner_path.is_file()
                ):
                    errors.append(
                        f"{rel(path)} fixture {fixture_id or index}: expected_tool_ref {tool_ref!r} is not declared by an expected owner path"
                    )
        if not isinstance(forbidden_tool_refs, list) or not all(
            isinstance(item, str) and item.strip() for item in forbidden_tool_refs
        ):
            errors.append(
                f"{rel(path)} fixture {fixture_id or index}: forbidden_tool_refs must be a list of strings"
            )
        else:
            for tool_ref in forbidden_tool_refs:
                if not TOOL_REF_RE.match(tool_ref):
                    errors.append(
                        f"{rel(path)} fixture {fixture_id or index}: malformed forbidden_tool_ref {tool_ref!r}"
                    )
        if (
            isinstance(expected_tool_refs, list)
            and expected_tool_refs
            and isinstance(forbidden_tool_refs, list)
        ):
            owner_forbidden = {
                tool_ref
                for owner_path in resolved_owner_paths
                if owner_path.is_file()
                for tool_ref in forbidden_tool_refs
                if re.search(
                    rf"(?<![A-Za-z0-9_]){re.escape(tool_ref)}(?![A-Za-z0-9_])",
                    owner_path.read_text(encoding="utf-8"),
                )
            }
            if owner_forbidden:
                errors.append(
                    f"{rel(path)} fixture {fixture_id or index}: forbidden tool refs occur in expected owner paths: {', '.join(sorted(owner_forbidden))}"
                )
        if isinstance(expected_tool_refs, list) and isinstance(
            forbidden_tool_refs, list
        ):
            overlap = sorted(set(expected_tool_refs) & set(forbidden_tool_refs))
            if overlap:
                errors.append(
                    f"{rel(path)} fixture {fixture_id or index}: expected and forbidden tool refs overlap: {', '.join(overlap)}"
                )

        for field in ("required_outcomes", "forbidden_outcomes"):
            value = fixture.get(field)
            if not isinstance(value, list) or not value:
                errors.append(
                    f"{rel(path)} fixture {fixture_id or index}: {field} must be a non-empty list"
                )
            elif not all(isinstance(item, str) and item.strip() for item in value):
                errors.append(
                    f"{rel(path)} fixture {fixture_id or index}: {field} entries must be non-empty strings"
                )

    return errors, warnings


def self_test_skill_text(
    name: str, body: str, description: str = "Test-only skill fixture."
) -> str:
    return f"""---
name: {name}
description: {description}
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


# Negative probes cover native frontmatter, reference reachability, and the
# fixture contract without relying on a metadata registry.
def run_self_tests() -> tuple[list[str], list[str]]:
    failures: list[str] = []
    passes: list[str] = []

    def expect(name: str, condition: bool, detail: str) -> None:
        (passes if condition else failures).append(
            name if condition else f"{name}: {detail}"
        )

    tmp_parent = ROOT / ".tmp"
    tmp_parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="scaffold-audit-", dir=tmp_parent) as tmp:
        tmp_root = Path(tmp)

        def probe(text: str, dirname: str) -> tuple[list[str], list[str]]:
            write_self_test_skill(tmp_root, dirname, text)
            loaded, load_errors = load_skills(tmp_root / "skills")
            errors, warnings = audit_skills(loaded)
            return load_errors + errors, warnings

        errors, _ = probe(
            "---\nname: probe\ndescription: Test fixture.\nmetadata: {}\n---\n",
            "probe",
        )
        expect(
            "unexpected-frontmatter",
            any("unexpected frontmatter keys" in e for e in errors),
            "legacy metadata key was accepted",
        )

        errors, _ = probe("Body without frontmatter.\n", "missing-frontmatter")
        expect(
            "missing-frontmatter",
            any("unreadable frontmatter" in e for e in errors),
            "missing frontmatter was accepted",
        )

        errors, _ = probe(
            self_test_skill_text(
                "description-probe", "Body.", "Two sentences. Still one description."
            ),
            "description-probe",
        )
        expect(
            "description-one-sentence",
            any("exactly one sentence" in e for e in errors),
            "multi-sentence description was accepted",
        )

        errors, _ = probe(
            self_test_skill_text(
                "reference-probe", "See [the branch](references/missing.md)."
            ),
            "reference-probe",
        )
        expect(
            "reference-integrity",
            any("reference link" in e for e in errors),
            "missing conditional reference was accepted",
        )

        errors, _ = probe(
            self_test_skill_text(
                "anchor-probe", "See [the branch](references/ok.md#missing)."
            ),
            "anchor-probe",
        )
        (tmp_root / "skills" / "anchor-probe" / "references").mkdir(
            parents=True, exist_ok=True
        )
        (tmp_root / "skills" / "anchor-probe" / "references" / "ok.md").write_text(
            "# Present\n", encoding="utf-8"
        )
        loaded, _ = load_skills(tmp_root / "skills")
        errors = audit_reference_graph(loaded)
        expect(
            "bad-reference-anchor",
            any("anchor" in e for e in errors),
            "bad reference anchor was accepted",
        )

        cross_root = tmp_root / "skills" / "cross-probe"
        cross_root.mkdir(parents=True, exist_ok=True)
        (cross_root / "SKILL.md").write_text(
            self_test_skill_text(
                "cross-probe",
                "See [`other`](../other-probe/references/target.md#missing).",
            ),
            encoding="utf-8",
        )
        other = tmp_root / "skills" / "other-probe" / "references"
        other.mkdir(parents=True)
        (other / "target.md").write_text("# Target\n", encoding="utf-8")
        loaded, _ = load_skills(tmp_root / "skills")
        errors = audit_reference_graph(loaded)
        expect(
            "cross-skill-anchor",
            any("cross-probe/SKILL.md" in e and "anchor" in e for e in errors),
            "cross-skill anchor was not checked",
        )

        errors, _ = probe(
            self_test_skill_text("other-name", "Body."), "mismatched-name"
        )
        expect(
            "directory-frontmatter-mismatch",
            any("directory/frontmatter mismatch" in e for e in errors),
            "directory/name mismatch was accepted",
        )

        expect(
            "context7-exact-token",
            context7_tokens(
                "https://github.com/facebookresearch/efm3d `/not-a/token` `/valid/id`"
            )
            == {"/not-a/token", "/valid/id"},
            "URL path was treated as a Context7 ID",
        )
        expect(
            "context7-tool-collision",
            not explicit_tool_ids(
                "`mcp__codex_apps__context7_query_docs_suffix`"
            ).intersection({"mcp__codex_apps__context7_query_docs"}),
            "tool-name suffix was treated as the canonical tool",
        )

        deprecated_root = tmp_root / "skills" / "deprecated-probe"
        deprecated_reference = deprecated_root / "references" / "active.md"
        deprecated_reference.parent.mkdir(parents=True)
        deprecated_reference.write_text(
            "Call mcp__MCP_DOCKER.get_library_docs here.\n", encoding="utf-8"
        )
        write_self_test_skill(
            tmp_root,
            "deprecated-probe",
            self_test_skill_text("deprecated-probe", "See `references/active.md`."),
        )
        expect(
            "deprecated-active-reference",
            bool(
                deprecated_context7_calls(
                    active_custom_reference_files(tmp_root / "skills")
                )
            ),
            "deprecated call in an active reference was accepted",
        )

        skills, load_errors = load_skills(SKILLS_DIR)
        skills_by_name = {skill.name: skill for skill in skills}
        expect("live-skills-load", not load_errors, "; ".join(load_errors))
        explicit_owner = tmp_root / "context7-owner.md"
        explicit_owner.write_text(
            "`mcp__codex_apps__context7_query_docs`\n", encoding="utf-8"
        )
        fixture = {
            "version": 1,
            "purpose": "explicit owner probe",
            "fixtures": [
                {
                    "id": "owner-tool",
                    "task": "Validate explicit owner tool declarations.",
                    "expected_owner_paths": [str(explicit_owner.relative_to(ROOT))],
                    "expected_tool_refs": ["mcp__codex_apps__context7_query_docs"],
                    "required_outcomes": ["owner path is available"],
                    "forbidden_outcomes": ["metadata registry is consulted"],
                }
            ],
        }
        errors, _ = audit_routing_fixtures(
            self_test_fixture_path(tmp_root, fixture), skills_by_name
        )
        expect("explicit-owner-tool-ref", not errors, "; ".join(errors))

        prose_owner = tmp_root / "prose-owner.md"
        prose_owner.write_text(
            "The tool mcp__codex_apps__context7_query_docs is useful.\n",
            encoding="utf-8",
        )
        prose_only = json.loads(json.dumps(fixture))
        prose_only["fixtures"][0]["expected_owner_paths"] = [
            str(prose_owner.relative_to(ROOT))
        ]
        errors, _ = audit_routing_fixtures(
            self_test_fixture_path(tmp_root, prose_only), skills_by_name
        )
        expect(
            "prose-only-tool-ref",
            any("not declared by an expected owner path" in e for e in errors),
            "prose-only tool declaration was accepted",
        )

        missing_owner = json.loads(json.dumps(fixture))
        missing_owner["fixtures"][0]["expected_owner_paths"] = [
            ".agents/skills/agent-behavior/SKILL.md"
        ]
        errors, _ = audit_routing_fixtures(
            self_test_fixture_path(tmp_root, missing_owner), skills_by_name
        )
        expect(
            "missing-owner-tool-ref",
            any("not declared by an expected owner path" in e for e in errors),
            "tool ref without explicit owner was accepted",
        )

        contradiction = json.loads(json.dumps(fixture))
        contradiction["fixtures"][0]["forbidden_tool_refs"] = [
            "mcp__codex_apps__context7_query_docs"
        ]
        errors, _ = audit_routing_fixtures(
            self_test_fixture_path(tmp_root, contradiction), skills_by_name
        )
        expect(
            "forbidden-tool-contradiction",
            any("overlap" in e for e in errors),
            "expected/forbidden contradiction was accepted",
        )

        for name, mutation, needle in (
            (
                "fixture-unknown-key",
                lambda value: value["fixtures"][0].update(extra=True),
                "unknown keys",
            ),
            (
                "fixture-duplicate-id",
                lambda value: value["fixtures"].append(value["fixtures"][0]),
                "duplicate id",
            ),
            (
                "fixture-path-escape",
                lambda value: value["fixtures"][0].update(
                    expected_owner_paths=["../escape.md"]
                ),
                "escapes repo root",
            ),
            (
                "fixture-missing-path",
                lambda value: value["fixtures"][0].update(
                    expected_owner_paths=["missing.md"]
                ),
                "does not exist",
            ),
            (
                "fixture-bad-tool-id",
                lambda value: value["fixtures"][0].update(
                    expected_tool_refs=["not-a-tool"]
                ),
                "malformed expected_tool_ref",
            ),
            (
                "fixture-empty-outcomes",
                lambda value: value["fixtures"][0].update(required_outcomes=[]),
                "required_outcomes",
            ),
        ):
            mutated = json.loads(json.dumps(fixture))
            mutation(mutated)
            errors, _ = audit_routing_fixtures(
                self_test_fixture_path(tmp_root, mutated), skills_by_name
            )
            expect(name, any(needle in e for e in errors), f"{name} was accepted")

        escaped = json.loads(json.dumps(fixture))
        escaped["fixtures"][0]["expected_owner_paths"] = [
            ".agents/skills/agent-behavior/SKILL.md"
        ]
        errors, _ = audit_routing_fixtures(
            self_test_fixture_path(tmp_root, escaped), skills_by_name
        )
        expect(
            "fixture-missing-explicit-tool",
            any("not declared by an expected owner path" in e for e in errors),
            "missing explicit tool declaration was accepted",
        )

        graph_skill = Skill(
            tmp_root / "graph" / "SKILL.md", "graph", "graph", "Test fixture.", 1, ""
        )
        graph_dir = graph_skill.path.parent
        (graph_dir / "references").mkdir(parents=True)
        graph_skill.path.write_text(
            self_test_skill_text(
                "graph", "See `references/a.md` and `references/shortcut.md`."
            ),
            encoding="utf-8",
        )
        (graph_dir / "references" / "a.md").write_text(
            "See `./b.md`.\n", encoding="utf-8"
        )
        (graph_dir / "references" / "b.md").write_text(
            "See `./c.md`.\n", encoding="utf-8"
        )
        (graph_dir / "references" / "c.md").write_text("# C\n", encoding="utf-8")
        (graph_dir / "references" / "shortcut.md").write_text(
            "See `./c.md`.\n", encoding="utf-8"
        )
        errors = audit_reference_graph([graph_skill])
        expect(
            "progressive-non-shortest-depth",
            any("depth exceeds 2" in e and "on path" in e for e in errors),
            "over-depth path was accepted because a shorter path existed",
        )

        (graph_dir / "references" / "orphan.md").write_text(
            "# Orphan\n", encoding="utf-8"
        )
        errors = audit_reference_graph([graph_skill])
        expect(
            "progressive-orphan",
            any("orphan" in e for e in errors),
            "orphan reference was accepted",
        )

        bare_dir = tmp_root / "bare"
        (bare_dir / "references").mkdir(parents=True)
        bare_path = bare_dir / "SKILL.md"
        bare_path.write_text(
            self_test_skill_text("bare", "See `references/guide.md`."),
            encoding="utf-8",
        )
        (bare_dir / "references" / "guide.md").write_text(
            "See `orphan.md`.\n", encoding="utf-8"
        )
        (bare_dir / "references" / "orphan.md").write_text(
            "# Orphan\n", encoding="utf-8"
        )
        bare_skill = Skill(
            bare_path,
            "bare",
            "bare",
            "Test fixture.",
            1,
            bare_path.read_text(encoding="utf-8"),
        )
        errors = audit_reference_graph([bare_skill])
        expect(
            "bare-sibling-orphan",
            any("orphan progressive-disclosure reference" in e for e in errors),
            "bare sibling token outside the package index made an orphan reachable",
        )

        package_dir = tmp_root / "package-index"
        package_references = package_dir / "references" / "packages"
        package_references.mkdir(parents=True)
        package_path = package_dir / "SKILL.md"
        package_path.write_text(
            self_test_skill_text(
                "package-index", "See `references/packages/index.md`."
            ),
            encoding="utf-8",
        )
        package_index = package_references / "index.md"
        package_index.write_text("See `booktabs.md`.\n", encoding="utf-8")
        (package_references / "booktabs.md").write_text(
            "# Booktabs\n", encoding="utf-8"
        )
        package_skill = Skill(
            package_path,
            "package-index",
            "package-index",
            "Test fixture.",
            1,
            package_path.read_text(encoding="utf-8"),
        )
        expect(
            "package-index-sibling",
            not audit_reference_graph([package_skill]),
            "package index sibling pointer was rejected",
        )

        cycle_dir = tmp_root / "cycle"
        (cycle_dir / "references").mkdir(parents=True)
        cycle_path = cycle_dir / "SKILL.md"
        cycle_path.write_text(
            self_test_skill_text("cycle", "See `references/a.md`."), encoding="utf-8"
        )
        (cycle_dir / "references" / "a.md").write_text(
            "See `./b.md`.\n", encoding="utf-8"
        )
        (cycle_dir / "references" / "b.md").write_text(
            "See `./a.md`.\n", encoding="utf-8"
        )
        cycle_skill = Skill(
            cycle_path,
            "cycle",
            "cycle",
            "Test fixture.",
            4,
            cycle_path.read_text(encoding="utf-8"),
        )
        errors = audit_reference_graph([cycle_skill])
        expect(
            "progressive-peer-cycle",
            any("cycle/backedge" in e for e in errors),
            "peer cycle was accepted despite violating progressive disclosure",
        )

        leaf_dir = tmp_root / "leaf"
        (leaf_dir / "references").mkdir(parents=True)
        leaf_path = leaf_dir / "SKILL.md"
        leaf_path.write_text(
            self_test_skill_text("leaf", "See `references/leaf.md`."),
            encoding="utf-8",
        )
        (leaf_dir / "references" / "leaf.md").write_text("# Leaf\n", encoding="utf-8")
        leaf_skill = Skill(
            leaf_path,
            "leaf",
            "leaf",
            "Test fixture.",
            4,
            leaf_path.read_text(encoding="utf-8"),
        )
        expect(
            "progressive-leaf-reference",
            not audit_reference_graph([leaf_skill]),
            "legitimate leaf reference was rejected",
        )

        drift = Skill(
            tmp_root / "drift" / "SKILL.md",
            "drift",
            "drift",
            "Test fixture.",
            4,
            self_test_skill_text("drift", "## Implementation Contract\n"),
        )
        expect(
            "semantic-drift-warning",
            bool(audit_semantic_drift([drift])),
            "semantic drift warning was absent",
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
        payload = {"passed": passes, "failures": failures}
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(
                f"scaffold-audit self-test: passed={len(passes)} failures={len(failures)}"
            )
            for failure in failures:
                print(f"- {failure}")
        return 1 if failures else 0

    skills, load_errors = load_skills(SKILLS_DIR)
    skill_errors, skill_warnings = audit_skills(skills)
    drift_warnings = audit_semantic_drift(skills)
    fixture_errors, fixture_warnings = audit_routing_fixtures(
        ROUTING_FIXTURES,
        {skill.name: skill for skill in skills},
    )

    errors = load_errors + skill_errors + fixture_errors
    warnings = skill_warnings + drift_warnings + fixture_warnings
    audit_payload: dict[str, object] = {
        "skills": len(skills),
        "errors": errors,
        "warnings": warnings,
    }

    if args.json:
        print(json.dumps(audit_payload, indent=2, sort_keys=True))
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
