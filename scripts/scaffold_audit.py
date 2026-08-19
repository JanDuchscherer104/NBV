#!/usr/bin/env python3
"""Audit ARIA-NBV agent scaffold skill metadata and routing fixtures."""

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
BIBLIOGRAPHY = ROOT / "docs" / "references.bib"
CONTEXT_MAP = (
    ROOT / ".agents" / "skills" / "aria-nbv-context" / "references" / "context_map.md"
)
CONTEXT7_REGISTRY = (
    ROOT
    / ".agents"
    / "skills"
    / "aria-nbv-context"
    / "references"
    / "context7_library_ids.md"
)
CONTEXT7_ID_RE = re.compile(r"^/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)?$")
TOOL_REF_RE = re.compile(r"^mcp__[A-Za-z0-9_]+\.[A-Za-z0-9_]+$")
AUDIT_OWNED_TOOL_REFS = {
    "mcp__MCP_DOCKER.analyze_python_file",
    "mcp__MCP_DOCKER.analyze_python_package",
    "mcp__MCP_DOCKER.analyze_security_and_patterns",
    "mcp__MCP_DOCKER.analyze_test_coverage",
    "mcp__MCP_DOCKER.browser_click",
    "mcp__MCP_DOCKER.browser_close",
    "mcp__MCP_DOCKER.browser_console_messages",
    "mcp__MCP_DOCKER.browser_drag",
    "mcp__MCP_DOCKER.browser_evaluate",
    "mcp__MCP_DOCKER.browser_file_upload",
    "mcp__MCP_DOCKER.browser_fill_form",
    "mcp__MCP_DOCKER.browser_handle_dialog",
    "mcp__MCP_DOCKER.browser_hover",
    "mcp__MCP_DOCKER.browser_navigate",
    "mcp__MCP_DOCKER.browser_navigate_back",
    "mcp__MCP_DOCKER.browser_network_requests",
    "mcp__MCP_DOCKER.browser_press_key",
    "mcp__MCP_DOCKER.browser_resize",
    "mcp__MCP_DOCKER.browser_run_code",
    "mcp__MCP_DOCKER.browser_select_option",
    "mcp__MCP_DOCKER.browser_snapshot",
    "mcp__MCP_DOCKER.browser_tabs",
    "mcp__MCP_DOCKER.browser_take_screenshot",
    "mcp__MCP_DOCKER.browser_type",
    "mcp__MCP_DOCKER.browser_wait_for",
    "mcp__MCP_DOCKER.download_paper",
    "mcp__MCP_DOCKER.find_long_functions",
    "mcp__MCP_DOCKER.find_package_issues",
    "mcp__MCP_DOCKER.get_extraction_guidance",
    "mcp__MCP_DOCKER.get_library_docs",
    "mcp__MCP_DOCKER.get_package_metrics",
    "mcp__MCP_DOCKER.list_papers",
    "mcp__MCP_DOCKER.read_paper",
    "mcp__MCP_DOCKER.resolve_library_id",
    "mcp__MCP_DOCKER.search_papers",
    "mcp__MCP_DOCKER.tdd_refactoring_guidance",
    "mcp__code_index.get_file_summary",
    "mcp__code_index.get_file_watcher_status",
    "mcp__code_index.get_settings_info",
    "mcp__code_index.get_symbol_body",
    "mcp__code_index.search_code_advanced",
    "mcp__openaiDeveloperDocs.get_openapi_spec",
    "mcp__openaiDeveloperDocs.list_openai_docs",
}
OPTIONAL_TOOL_REF_PREFIXES = {"mcp__codex_apps__"}
CONTEXT7_TRIGGER_RE = re.compile(
    r"\b(Context7|official docs?|external librar(?:y|ies)|API|SDK|"
    r"PyTorch3D|PyTorch|Rerun|Streamlit|Gymnasium|SB3|Stable Baselines3|"
    r"Pydantic|msgspec|Zarr|Typst|Quarto)\b",
    re.IGNORECASE,
)
LITERATURE_TRIGGER_RE = re.compile(
    r"\b(literature|BibTeX|citation|advisor-facing|thesis|paper|claim-check|"
    r"VIN-NBV|Project Aria|EFM3D|Double-Q|RRI)\b",
    re.IGNORECASE,
)

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


def metadata_strings(metadata: dict[str, Any], fields: set[str]) -> list[str]:
    values: list[str] = []
    for field in fields:
        value = metadata.get(field)
        if isinstance(value, list):
            values.extend(item for item in value if isinstance(item, str))
        elif isinstance(value, str):
            values.append(value)
    return values


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


def load_context_map_routes(path: Path = CONTEXT_MAP) -> tuple[set[str], list[str]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return set(), [f"{rel(path)}: cannot read context map: {exc}"]
    routes: set[str] = set()
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|") or "---" in stripped:
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) < 2:
            continue
        label = cells[0].strip("` ")
        if not label or label.lower() in {"topic", "concept route"}:
            continue
        routes.add(label)
    return routes, []


def load_context7_registry(
    path: Path = CONTEXT7_REGISTRY,
) -> tuple[set[str], list[str]]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return set(), [f"{rel(path)}: cannot read Context7 registry: {exc}"]
    ids = {
        match.group(1)
        for match in re.finditer(r"`(/[^`\s]+/[^`\s]+)`", text)
        if CONTEXT7_ID_RE.fullmatch(match.group(1))
    }
    if not ids:
        return ids, [f"{rel(path)}: no exact Context7 IDs found"]
    return ids, []


def repo_path_exists(ref: str, *, base: Path = ROOT) -> bool:
    path_text, _, anchor = ref.partition("#")
    if not path_text or path_text.startswith("/"):
        return False
    path = base / path_text
    resolved = path.resolve()
    if not is_relative_to(resolved, ROOT_RESOLVED) or not resolved.exists():
        return False
    generated_docs = (ROOT / "docs" / "_generated").resolve()
    if is_relative_to(resolved, generated_docs):
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
    has_metadata: bool
    line_count: int
    text: str


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


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
        if not isinstance(name, str) or not name.strip():
            errors.append(f"{rel(skill_md)}: missing non-empty name")
            continue
        has_metadata = "metadata" in data
        metadata = data.get("metadata")
        if not isinstance(metadata, dict):
            if not is_upstream_skill(skill_md):
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
                has_metadata=has_metadata,
                line_count=line_count,
                text=text,
            )
        )

    if not skills:
        errors.append(f"{rel(skills_dir)}: no skills found")
    return skills, errors


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
    bibtex_keys, bibtex_errors = load_bibtex_keys()
    context_routes, context_route_errors = load_context_map_routes()
    context7_registry, context7_registry_errors = load_context7_registry()
    errors.extend(bibtex_errors)
    errors.extend(context_route_errors)
    errors.extend(context7_registry_errors)

    for skill in skills:
        prefix = rel(skill.path)
        if skill.dirname != skill.name:
            errors.append(
                f"{prefix}: directory/frontmatter mismatch (directory={skill.dirname!r}, name={skill.name!r})"
            )

        if is_upstream_skill(skill.path):
            continue

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
        if isinstance(applies_to, list) and "**" in applies_to:
            warnings.append(f"{prefix}: broad applies_to '**' should stay intentional")

        if skill.line_count > HOT_PATH_LINE_BUDGET:
            warnings.append(
                f"{prefix}: hot path is {skill.line_count} lines "
                f"(budget {HOT_PATH_LINE_BUDGET}); prune or move detail to references"
            )

        context7_refs = skill.metadata.get("context7_refs") or []
        if isinstance(context7_refs, list):
            for ref in context7_refs:
                if not isinstance(ref, str) or not ref.strip():
                    continue
                if not CONTEXT7_ID_RE.fullmatch(ref):
                    errors.append(
                        f"{prefix}: metadata.context7_refs entry {ref!r} must be an exact Context7 ID"
                    )
                elif ref not in context7_registry:
                    errors.append(
                        f"{prefix}: metadata.context7_refs entry {ref!r} is absent from "
                        f"{rel(CONTEXT7_REGISTRY)}"
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
                elif (
                    ref in bibtex_keys or ref in context_routes or repo_path_exists(ref)
                ):
                    continue
                else:
                    errors.append(
                        f"{prefix}: metadata.literature_refs entry {ref!r} is not a BibTeX key, "
                        "context-map route label, or existing repo path"
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
                elif ref not in AUDIT_OWNED_TOOL_REFS and not any(
                    ref.startswith(prefix) for prefix in OPTIONAL_TOOL_REF_PREFIXES
                ):
                    warnings.append(
                        f"{prefix}: metadata.tool_refs entry {ref!r} is not in the audit-owned tool registry"
                    )

        trigger_text = " ".join(
            [skill.description]
            + metadata_strings(
                skill.metadata,
                {"triggers", "evidence_required", "handoff_to", "must_read"},
            )
        )
        routes_to_context7_registry = rel(CONTEXT7_REGISTRY) in canonical_sources
        if (
            CONTEXT7_TRIGGER_RE.search(trigger_text)
            and not context7_refs
            and not routes_to_context7_registry
        ):
            warnings.append(
                f"{prefix}: external-library/API trigger language has no metadata.context7_refs"
            )
        if LITERATURE_TRIGGER_RE.search(trigger_text) and not literature_refs:
            warnings.append(
                f"{prefix}: literature/thesis/advisor trigger language has no metadata.literature_refs"
            )

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
    skills_by_path = {skill.path.resolve(): skill for skill in skills_by_name.values()}
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
        expected_owner_tool_refs: set[str] = set()
        for owner_path in resolved_owner_paths:
            owner_skill = skills_by_path.get(owner_path)
            if owner_skill:
                expected_owner_tool_refs.update(
                    owner_skill.metadata.get("tool_refs") or []
                )

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
                elif tool_ref not in expected_owner_tool_refs:
                    errors.append(
                        f"{rel(path)} fixture {fixture_id or index}: expected_tool_ref {tool_ref!r} is not declared by an expected owner"
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

        malformed_path = tmp_root / "skills" / "malformed-yaml" / "SKILL.md"
        malformed_path.parent.mkdir(parents=True, exist_ok=True)
        malformed_path.write_text("---\nname: [\n---\n", encoding="utf-8")
        _, load_errors = load_skills(tmp_root / "skills")
        expect(
            "malformed-yaml",
            any("unreadable frontmatter" in error for error in load_errors),
            "malformed YAML was not rejected",
        )
        malformed_path.unlink()
        malformed_path.parent.rmdir()

        mismatch_text = self_test_skill_text(
            "other-name",
            [".agents/references/source_order.md#compositional-owner-tree"],
            "Use this test body for directory-name validation.",
        )
        write_self_test_skill(tmp_root, "mismatched-name", mismatch_text)
        skills, load_errors = load_skills(tmp_root / "skills")
        errors, _ = audit_skills(skills)
        expect(
            "directory-frontmatter-mismatch",
            not load_errors
            and any("directory/frontmatter mismatch" in error for error in errors),
            "directory/frontmatter mismatch was not rejected",
        )

        missing_description = "---\nname: missing-description\nmetadata: {}\n---\n"
        write_self_test_skill(tmp_root, "missing-description", missing_description)
        _, load_errors = load_skills(tmp_root / "skills")
        expect(
            "missing-description",
            any("missing non-empty description" in error for error in load_errors),
            "missing description was not rejected",
        )
        (tmp_root / "skills" / "missing-description" / "SKILL.md").unlink()
        (tmp_root / "skills" / "missing-description").rmdir()

        unconverted_text = (
            "---\nname: unconverted-no-metadata\ndescription: Test fixture.\n---\n"
        )
        write_self_test_skill(tmp_root, "unconverted-no-metadata", unconverted_text)
        _, load_errors = load_skills(tmp_root / "skills")
        expect(
            "unconverted-metadata-absent",
            any(
                "unconverted-no-metadata/SKILL.md: missing metadata mapping" in error
                for error in load_errors
            ),
            "unconverted skill without legacy metadata was not rejected",
        )
        (tmp_root / "skills" / "unconverted-no-metadata" / "SKILL.md").unlink()
        (tmp_root / "skills" / "unconverted-no-metadata").rmdir()

        partial_legacy_text = "---\nname: unconverted-partial-metadata\ndescription: Test fixture.\nmetadata:\n  mode: router\n---\n"
        write_self_test_skill(
            tmp_root, "unconverted-partial-metadata", partial_legacy_text
        )
        skills, load_errors = load_skills(tmp_root / "skills")
        errors, _ = audit_skills(skills)
        expect(
            "unconverted-partial-legacy-metadata",
            not load_errors
            and any("missing metadata fields" in error for error in errors),
            "unconverted skill with partial legacy metadata was not rejected",
        )

        missing_fixture = {
            "version": 1,
            "purpose": "fixture schema probe",
            "fixtures": [{"id": "missing-required-fields"}],
        }
        errors, _ = audit_routing_fixtures(
            self_test_fixture_path(tmp_root, missing_fixture), skills_by_name
        )
        expect(
            "fixture-required-fields",
            any("missing task" in error for error in errors)
            and any("expected_owner_paths must be" in error for error in errors)
            and any("required_outcomes must be" in error for error in errors)
            and any("forbidden_outcomes must be" in error for error in errors),
            "fixture schema omissions were not rejected",
        )

        owner_path_probe = {
            "version": 1,
            "purpose": "owner path probe",
            "fixtures": [
                {
                    "id": "owner-path-probe",
                    "task": "Validate owner paths.",
                    "expected_owner_paths": ["../outside.md", "missing-owner.md"],
                    "required_outcomes": ["owner path validation"],
                    "forbidden_outcomes": ["missing owner accepted"],
                }
            ],
        }
        errors, _ = audit_routing_fixtures(
            self_test_fixture_path(tmp_root, owner_path_probe), skills_by_name
        )
        expect(
            "fixture-owner-path-containment-and-existence",
            any("escapes repo root" in error for error in errors)
            and any("does not exist" in error for error in errors),
            "escaping or missing owner paths were not rejected",
        )

        stable_id_probe = {
            "version": 1,
            "purpose": "stable id probe",
            "fixtures": [
                {
                    "id": "stable-id-probe",
                    "task": "Validate stable identifiers.",
                    "expected_owner_paths": [".agents/skills/agent-behavior/SKILL.md"],
                    "stable_skill_ids": ["agent-behavior"],
                    "required_outcomes": ["stable id validation"],
                    "forbidden_outcomes": ["unapproved stable id accepted"],
                }
            ],
        }
        errors, _ = audit_routing_fixtures(
            self_test_fixture_path(tmp_root, stable_id_probe), skills_by_name
        )
        expect(
            "fixture-stable-skill-id",
            any("unapproved stable skill id" in error for error in errors),
            "unapproved stable skill id was not rejected",
        )

        duplicate_and_unknown_probe = {
            "version": 1,
            "purpose": "fixture identity probe",
            "fixtures": [
                {
                    "id": "duplicate-fixture",
                    "task": "Validate fixture identity.",
                    "expected_owner_paths": ["AGENTS.md"],
                    "required_outcomes": ["owner path is available"],
                    "forbidden_outcomes": ["duplicate id is accepted"],
                },
                {
                    "id": "duplicate-fixture",
                    "task": "Validate unknown keys.",
                    "expected_owner_paths": ["AGENTS.md"],
                    "required_outcomes": ["owner path is available"],
                    "forbidden_outcomes": ["unknown key is accepted"],
                    "unexpected": True,
                },
            ],
        }
        errors, _ = audit_routing_fixtures(
            self_test_fixture_path(tmp_root, duplicate_and_unknown_probe),
            skills_by_name,
        )
        expect(
            "fixture-duplicate-id-and-unknown-key",
            any("duplicate id" in error for error in errors)
            and any("unknown keys" in error for error in errors),
            "duplicate fixture ID or unknown fixture key was not rejected",
        )

        empty_outcomes_probe = {
            "version": 1,
            "purpose": "outcome probe",
            "fixtures": [
                {
                    "id": "empty-outcomes",
                    "task": "Validate outcome fields.",
                    "expected_owner_paths": ["AGENTS.md"],
                    "required_outcomes": [],
                    "forbidden_outcomes": [],
                }
            ],
        }
        errors, _ = audit_routing_fixtures(
            self_test_fixture_path(tmp_root, empty_outcomes_probe), skills_by_name
        )
        expect(
            "fixture-empty-outcomes",
            any("required_outcomes must be" in error for error in errors)
            and any("forbidden_outcomes must be" in error for error in errors),
            "empty outcome fields were not rejected",
        )

        malformed_and_undeclared_tool_probe = {
            "version": 1,
            "purpose": "tool declaration probe",
            "fixtures": [
                {
                    "id": "malformed-and-undeclared-tools",
                    "task": "Validate expected owner tool declarations.",
                    "expected_owner_paths": [".agents/skills/agent-behavior/SKILL.md"],
                    "expected_tool_refs": [
                        "malformed tool",
                        "mcp__code_index.search_code_advanced",
                    ],
                    "forbidden_tool_refs": ["also malformed"],
                    "required_outcomes": ["tool declaration validation"],
                    "forbidden_outcomes": ["malformed tool declaration accepted"],
                }
            ],
        }
        errors, _ = audit_routing_fixtures(
            self_test_fixture_path(tmp_root, malformed_and_undeclared_tool_probe),
            skills_by_name,
        )
        expect(
            "fixture-malformed-and-undeclared-tool-refs",
            sum("malformed" in error for error in errors) >= 2
            and any("not declared by an expected owner" in error for error in errors),
            "malformed or undeclared tool refs were not rejected",
        )

        drift_text = self_test_skill_text(
            "truth-leak-skill",
            [".agents/references/source_order.md#compositional-owner-tree"],
            "This planned but unimplemented Q_H roadmap detail will be implemented later.",
        )
        drift_path = write_self_test_skill(tmp_root, "truth-leak-skill", drift_text)
        drift_skill = Skill(
            path=drift_path,
            dirname="truth-leak-skill",
            name="truth-leak-skill",
            description="Test-only skill fixture.",
            metadata={},
            has_metadata=False,
            line_count=len(drift_text.splitlines()),
            text=drift_text,
        )
        warnings = audit_semantic_drift([drift_skill])
        expect(
            "planned-detail-semantic-drift",
            any("possible semantic drift" in warning for warning in warnings),
            "planned thesis detail in skill body was not warned",
        )

        missing_literature_text = self_test_skill_text(
            "missing-literature-skill",
            [".agents/references/source_order.md#compositional-owner-tree"],
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

        unregistered_context7_text = self_test_skill_text(
            "unregistered-context7-skill",
            [".agents/references/source_order.md#compositional-owner-tree"],
            "Use this test body for Context7 registry validation.",
            '  context7_refs:\n    - "/example/not-in-registry"',
        )
        write_self_test_skill(
            tmp_root, "unregistered-context7-skill", unregistered_context7_text
        )
        skills, load_errors = load_skills(tmp_root / "skills")
        errors, _ = audit_skills(skills)
        expect(
            "unregistered-context7-ref",
            not load_errors and any("absent from" in error for error in errors),
            "unregistered Context7 ref was not rejected",
        )

        malformed_tool_text = self_test_skill_text(
            "malformed-tool-skill",
            [".agents/references/source_order.md#compositional-owner-tree"],
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

        unknown_tool_text = self_test_skill_text(
            "unknown-tool-skill",
            [".agents/references/source_order.md#compositional-owner-tree"],
            "Use this test body for tool ref inventory validation.",
            '  tool_refs:\n    - "mcp__Bogus.fake"',
        )
        write_self_test_skill(tmp_root, "unknown-tool-skill", unknown_tool_text)
        skills, load_errors = load_skills(tmp_root / "skills")
        _, warnings = audit_skills(skills)
        expect(
            "unknown-tool-ref-warned",
            not load_errors
            and any("audit-owned tool registry" in warning for warning in warnings),
            "unknown canonical-looking tool ref was not warned",
        )

        browser_overtrigger_fixture = {
            "version": 1,
            "purpose": "tool-ref probe",
            "fixtures": [
                {
                    "id": "browser-overtrigger-probe",
                    "task": "Diagnose a concrete Streamlit browser symptom with live UI evidence.",
                    "expected_owner_paths": [".agents/skills/agent-behavior/SKILL.md"],
                    "forbidden_tool_refs": ["mcp__MCP_DOCKER.browser_run_code"],
                    "required_outcomes": ["owner path is available"],
                    "forbidden_outcomes": ["browser use is required"],
                }
            ],
        }
        errors, _ = audit_routing_fixtures(
            self_test_fixture_path(tmp_root, browser_overtrigger_fixture),
            skills_by_name,
        )
        expect(
            "forbidden-tool-without-owner-declaration",
            not errors,
            "; ".join(errors),
        )

        python_analyzer_overtrigger_fixture = {
            "version": 1,
            "purpose": "tool contradiction probe",
            "fixtures": [
                {
                    "id": "python-analyzer-overtrigger-probe",
                    "task": "Simplify Python code with analyzer guidance after code-index localization.",
                    "expected_owner_paths": [".agents/skills/simplification/SKILL.md"],
                    "expected_tool_refs": ["mcp__MCP_DOCKER.analyze_python_file"],
                    "forbidden_tool_refs": ["mcp__MCP_DOCKER.analyze_python_file"],
                    "required_outcomes": ["owner path is available"],
                    "forbidden_outcomes": ["tool contradiction is accepted"],
                }
            ],
        }
        errors, _ = audit_routing_fixtures(
            self_test_fixture_path(tmp_root, python_analyzer_overtrigger_fixture),
            skills_by_name,
        )
        expect(
            "expected-forbidden-tool-contradiction",
            any(
                "expected and forbidden tool refs overlap" in error for error in errors
            ),
            "expected/forbidden tool contradiction was not rejected",
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
