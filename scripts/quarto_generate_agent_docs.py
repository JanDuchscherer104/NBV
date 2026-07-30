#!/usr/bin/env python3
"""Generate internal Quarto pages for maintained agent guidance."""

from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS_ROOT = REPO_ROOT / "docs"
OUTPUT_ROOT = REPO_ROOT / ".agents" / "generated" / "agent_scaffold"
GITHUB_BLOB_BASE = "https://github.com/JanDuchscherer104/ARIA-NBV/blob/main"
GENERATED_NOTE = (
    "This internal page is generated from canonical repo markdown. "
    "It is an operator aid under `.agents/generated/`, not public Quarto content. "
    "Refresh it with `./scripts/quarto_generate_agent_docs.py`."
)


@dataclass(frozen=True)
class DocSpec:
    source: str
    output: str
    title: str
    section: str
    nav_label: str
    summary: str


DOC_SPECS: tuple[DocSpec, ...] = (
    DocSpec(
        source="AGENTS.md",
        output="instructions/repo_guidance.qmd",
        title="Repo Guidance",
        section="Instructions",
        nav_label="Repo Guidance",
        summary="Root Codex guidance, bootstrap order, commands, and repo-wide constraints.",
    ),
    DocSpec(
        source="docs/AGENTS.md",
        output="instructions/docs_guidance.qmd",
        title="Docs Guidance",
        section="Instructions",
        nav_label="Docs Guidance",
        summary="Quarto and Typst editing rules for the docs workspace.",
    ),
    DocSpec(
        source="aria_nbv/AGENTS.md",
        output="instructions/package_guidance.qmd",
        title="Package Guidance",
        section="Instructions",
        nav_label="Package Guidance",
        summary="Package-level implementation, verification, and config-factory rules.",
    ),
    DocSpec(
        source="aria_nbv/aria_nbv/data_handling/AGENTS.md",
        output="instructions/data_handling_boundary.qmd",
        title="Data Handling Boundary",
        section="Instructions",
        nav_label="Data Handling Boundary",
        summary="Contracts and verification rules for the typed data-handling surface.",
    ),
    DocSpec(
        source="aria_nbv/aria_nbv/rri_metrics/AGENTS.md",
        output="instructions/rri_metrics_boundary.qmd",
        title="RRI Metrics Boundary",
        section="Instructions",
        nav_label="RRI Metrics Boundary",
        summary="Boundary rules for oracle RRI semantics, binning, and related metrics.",
    ),
    DocSpec(
        source="aria_nbv/aria_nbv/vin/AGENTS.md",
        output="instructions/vin_boundary.qmd",
        title="VIN Boundary",
        section="Instructions",
        nav_label="VIN Boundary",
        summary="Guidance for scorer inputs, batch contracts, and VIN-facing frame semantics.",
    ),
    DocSpec(
        source=".agents/memory/README.md",
        output="state/memory_readme.qmd",
        title="Agent Memory README",
        section="Canonical State",
        nav_label="Memory README",
        summary="Overview of the canonical memory layout and how history is organized.",
    ),
    DocSpec(
        source=".agents/memory/state/PROJECT_STATE.md",
        output="state/project_state.qmd",
        title="Project State",
        section="Canonical State",
        nav_label="Project State",
        summary="Current project truth for goals, architecture, and active working assumptions.",
    ),
    DocSpec(
        source=".agents/memory/state/DECISIONS.md",
        output="state/decisions.qmd",
        title="Decisions",
        section="Canonical State",
        nav_label="Decisions",
        summary="Durable repo and technical decisions that shape the active scaffold.",
    ),
    DocSpec(
        source=".agents/memory/state/OPEN_QUESTIONS.md",
        output="state/open_questions.qmd",
        title="Open Questions",
        section="Canonical State",
        nav_label="Open Questions",
        summary="Tracked unknowns, pending experiments, and unresolved design questions.",
    ),
    DocSpec(
        source=".agents/memory/state/GOTCHAS.md",
        output="state/gotchas.qmd",
        title="Gotchas",
        section="Canonical State",
        nav_label="Gotchas",
        summary="Maintained pitfalls, validation traps, and environment caveats.",
    ),
    DocSpec(
        source=".agents/references/operator_quick_reference.md",
        output="references/operator_quick_reference.qmd",
        title="Operator Quick Reference",
        section="References",
        nav_label="Operator Quick Reference",
        summary="Compact operator aid for environment recovery, repo hygiene, and key commands.",
    ),
    DocSpec(
        source=".agents/references/python_conventions.md",
        output="references/python_conventions.qmd",
        title="Python Conventions",
        section="References",
        nav_label="Python Conventions",
        summary="Long-form Python style, typing, docstring, and config examples.",
    ),
    DocSpec(
        source=".agents/skills/aria-nbv-context/SKILL.md",
        output="skills/aria_nbv_context_skill.qmd",
        title="aria-nbv-context Skill",
        section="Skills & Routing",
        nav_label="aria-nbv-context Skill",
        summary="Discovery-and-routing skill for localizing tasks across paper, docs, memory, and code.",
    ),
    DocSpec(
        source=".agents/skills/aria-nbv-context/references/context_map.md",
        output="skills/context_map.qmd",
        title="Context Map",
        section="Skills & Routing",
        nav_label="Context Map",
        summary="Concept-to-source routing map for the maintained scaffold surfaces.",
    ),
)

SECTION_ORDER = (
    "Instructions",
    "Canonical State",
    "References",
    "Skills & Routing",
)

SITE_ASSET_SUFFIXES = {".qmd", ".pdf", ".png", ".jpg", ".jpeg", ".svg", ".gif"}
LINK_RE = re.compile(r"(?<!!)\[([^\]]+)\]\(([^)]+)\)")


def yaml_quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        return {}, text
    match = re.match(r"^---\n(.*?)\n---\n?", text, flags=re.DOTALL)
    if not match:
        return {}, text
    metadata: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip('"')
    return metadata, text[match.end() :]


def split_heading(text: str) -> tuple[str | None, str]:
    lines = text.splitlines()
    while lines and not lines[0].strip():
        lines.pop(0)
    if lines and lines[0].startswith("# "):
        title = lines[0][2:].strip()
        return title, "\n".join(lines[1:]).lstrip("\n")
    return None, text.lstrip("\n")


def relative_path(source: Path, target: Path) -> str:
    return Path(os.path.relpath(target, source.parent)).as_posix()


def to_repo_relative(path: Path) -> str | None:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return None


def translate_target(
    target: str,
    *,
    source_file: Path,
    output_file: Path,
    source_map: dict[str, DocSpec],
) -> str:
    if target.startswith(("http://", "https://", "mailto:", "#")):
        return target

    target_path, fragment = target, ""
    if "#" in target:
        target_path, fragment = target.split("#", 1)
        fragment = f"#{fragment}"

    resolved = (source_file.parent / target_path).resolve()
    repo_relative = to_repo_relative(resolved)
    if repo_relative is None or not resolved.exists():
        return target

    if repo_relative in source_map:
        mapped = OUTPUT_ROOT / source_map[repo_relative].output
        return f"{relative_path(output_file, mapped)}{fragment}"

    if repo_relative.startswith("docs/"):
        docs_relative = Path(repo_relative).relative_to("docs")
        if docs_relative.suffix.lower() in SITE_ASSET_SUFFIXES:
            mapped = DOCS_ROOT / docs_relative
            return f"{relative_path(output_file, mapped)}{fragment}"

    return f"{GITHUB_BLOB_BASE}/{repo_relative}{fragment}"


def rewrite_links(
    markdown: str,
    *,
    source_file: Path,
    output_file: Path,
    source_map: dict[str, DocSpec],
) -> str:
    rewritten_lines: list[str] = []
    in_fence = False

    for line in markdown.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            rewritten_lines.append(line)
            continue
        if in_fence:
            rewritten_lines.append(line)
            continue

        def replace(match: re.Match[str]) -> str:
            label = match.group(1)
            target = match.group(2).strip()
            translated = translate_target(
                target,
                source_file=source_file,
                output_file=output_file,
                source_map=source_map,
            )
            return f"[{label}]({translated})"

        rewritten_lines.append(LINK_RE.sub(replace, line))

    return "\n".join(rewritten_lines).rstrip() + "\n"


def render_page(spec: DocSpec, source_map: dict[str, DocSpec]) -> None:
    source_file = REPO_ROOT / spec.source
    output_file = OUTPUT_ROOT / spec.output
    metadata, text = split_frontmatter(source_file.read_text(encoding="utf-8"))
    source_heading, body = split_heading(text)
    body = rewrite_links(
        body,
        source_file=source_file,
        output_file=output_file,
        source_map=source_map,
    )

    callout_lines = [
        '::: {.callout-note collapse="true"}',
        "## Canonical Source",
        f"- Source file: [`{spec.source}`]({GITHUB_BLOB_BASE}/{spec.source})",
        f"- Generated page: `.agents/generated/agent_scaffold/{spec.output}`",
        "- Refresh: `./scripts/quarto_generate_agent_docs.py`",
    ]
    if "scope" in metadata:
        callout_lines.append(f"- Scope: `{metadata['scope']}`")
    if "applies_to" in metadata:
        callout_lines.append(f"- Applies to: `{metadata['applies_to']}`")
    summary = metadata.get("summary", spec.summary)
    if summary:
        callout_lines.append(f"- Summary: {summary}")
    callout_lines.append(":::")

    page_title = source_heading or spec.title
    output_text = [
        "---",
        f"title: {yaml_quote(page_title)}",
        "format: html",
        "---",
        "",
        f"<!-- Generated by scripts/quarto_generate_agent_docs.py from {spec.source}. -->",
        "",
        GENERATED_NOTE,
        "",
        *callout_lines,
        "",
        body.strip(),
        "",
    ]

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text("\n".join(output_text), encoding="utf-8")


def render_index() -> None:
    grouped: dict[str, list[DocSpec]] = {section: [] for section in SECTION_ORDER}
    for spec in DOC_SPECS:
        grouped[spec.section].append(spec)

    lines = [
        "---",
        'title: "Agent Scaffolding"',
        "format: html",
        "---",
        "",
        "<!-- Generated by scripts/quarto_generate_agent_docs.py. -->",
        "",
        "This internal index mirrors maintained Codex guidance and scaffold",
        "markdown for operator use.",
        "",
        "It includes the active `AGENTS.md` files, canonical memory state, agent",
        "references, and the `aria-nbv-context` routing skill. It intentionally",
        "excludes episodic history, `.agents/archive/`, and temporary workpads.",
        "",
        "Refresh these pages with `./scripts/quarto_generate_agent_docs.py`.",
        "GitHub Pages must not publish this generated tree.",
        "",
    ]

    for section in SECTION_ORDER:
        lines.extend(
            [
                f"## {section}",
                "",
            ]
        )
        for spec in grouped[section]:
            lines.append(f"- [{spec.nav_label}]({spec.output}): {spec.summary}")
        lines.append("")

    index_file = OUTPUT_ROOT / "index.qmd"
    index_file.parent.mkdir(parents=True, exist_ok=True)
    index_file.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    for child in OUTPUT_ROOT.iterdir():
        if child.name == ".gitignore":
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()

    source_map = {spec.source: spec for spec in DOC_SPECS}
    for spec in DOC_SPECS:
        render_page(spec, source_map)
    render_index()


if __name__ == "__main__":
    main()
