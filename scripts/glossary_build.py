#!/usr/bin/env python3
"""Build ARIA-NBV glossary artifacts from the canonical Typst source."""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TERMS = ROOT / "docs/typst/shared/glossary.typ"
DEFAULT_COMPAT_YAML = ROOT / "docs/glossary" / "terms.yml"
DEFAULT_QMD = ROOT / "docs/contents/glossary.qmd"
DEFAULT_TYPST = ROOT / "docs/typst/shared/glossary.generated.typ"
DEFAULT_JSONL = ROOT / "docs/_generated/context/glossary.jsonl"
DEFAULT_SHORTCODE_LUA = (
    ROOT / "docs/_extensions/aria-glossary/glossary_terms.generated.lua"
)
DEFAULT_SYMBOLS = ROOT / "docs/typst/shared/symbols.typ"
DEFAULT_EQUATIONS = ROOT / "docs/typst/shared/equations.typ"
DEFAULT_NOTATION_YAML = ROOT / "docs/notation.yml"
DEFAULT_NOTATION_LUA = ROOT / "docs/_extensions/aria-glossary/notation.generated.lua"
DEFAULT_NOTATION_TYPST = ROOT / "docs/typst/shared/notation.generated.typ"

REQUIRED_FIELDS = {
    "id",
    "anchor",
    "label",
    "category",
    "definition_short",
    "internal_links",
    "citations",
    "related",
    "kg_tags",
}


class GlossaryError(ValueError):
    """Raised when the glossary source is invalid."""


def _query_metadata(path: Path, label: str) -> list[dict[str, Any]]:
    command = [
        "typst",
        "query",
        str(path),
        f"<{label}>",
        "--field",
        "value",
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise GlossaryError(
            "typst executable not found; install Typst to build the glossary"
        ) from exc
    except subprocess.CalledProcessError as exc:
        details = (exc.stderr or exc.stdout or "").strip()
        raise GlossaryError(f"typst query failed for {path}: {details}") from exc

    data = json.loads(completed.stdout)
    if not isinstance(data, list):
        raise GlossaryError(f"{path} query must return a list of metadata records")
    records: list[dict[str, Any]] = []
    for index, raw in enumerate(data, start=1):
        if not isinstance(raw, dict):
            raise GlossaryError(f"{path}: metadata record #{index} must be a mapping")
        records.append(raw)
    return records


def _load_terms(path: Path) -> list[dict[str, Any]]:
    return [
        _normalize_queried_term(raw)
        for raw in _query_metadata(path, "aria-glossary-term")
    ]


def _normalize_queried_term(raw: dict[str, Any]) -> dict[str, Any]:
    term = dict(raw)
    for field in (
        "aliases",
        "internal_links",
        "citations",
        "related",
        "kg_tags",
        "formulae",
        "symbol_refs",
        "equation_refs",
    ):
        if term.get(field) is None:
            term[field] = []
    for field in ("notation", "formula"):
        if term.get(field) is None:
            term[field] = {}
    if term.get("tier") is None:
        term["tier"] = "support"
    if term.get("short") is None and term.get("label") is not None:
        term["short"] = term["label"]
    if term.get("parent") is None:
        term.pop("parent", None)
    if term.get("typst_macro") is None:
        term.pop("typst_macro", None)
    return term


def _load_notation(path: Path) -> dict[str, dict[str, dict[str, Any]]]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise GlossaryError(
            f"cannot load notation metadata from {path}: {exc}"
        ) from exc
    if not isinstance(data, dict):
        raise GlossaryError(f"{path} must contain a YAML mapping")
    notation: dict[str, dict[str, dict[str, Any]]] = {}
    for group in ("symbols", "equations"):
        raw_group = data.get(group) or {}
        if not isinstance(raw_group, dict):
            raise GlossaryError(f"{path}: {group} must be a mapping")
        notation[group] = {}
        for key, raw_entry in raw_group.items():
            if not isinstance(key, str) or not key.strip():
                raise GlossaryError(f"{path}: {group} contains an invalid key")
            if not isinstance(raw_entry, dict):
                raise GlossaryError(f"{path}: {group}.{key} must be a mapping")
            tex = raw_entry.get("tex")
            typst = raw_entry.get("typst")
            if not isinstance(tex, str) or not tex.strip():
                raise GlossaryError(
                    f"{path}: {group}.{key}.tex must be a non-empty string"
                )
            if not isinstance(typst, str) or not typst.strip():
                raise GlossaryError(
                    f"{path}: {group}.{key}.typst must be a non-empty string"
                )
            entry: dict[str, Any] = {"tex": tex.strip(), "typst": typst.strip()}
            description = raw_entry.get("description")
            if description is not None:
                if not isinstance(description, str):
                    raise GlossaryError(
                        f"{path}: {group}.{key}.description must be a string"
                    )
                entry["description"] = description.strip()
            thesis_list = raw_entry.get("thesis_list", False)
            if not isinstance(thesis_list, bool):
                raise GlossaryError(
                    f"{path}: {group}.{key}.thesis_list must be a boolean"
                )
            entry["thesis_list"] = thesis_list
            order = raw_entry.get("order")
            if order is not None:
                if isinstance(order, bool) or not isinstance(order, int):
                    raise GlossaryError(
                        f"{path}: {group}.{key}.order must be an integer"
                    )
                entry["order"] = order
            notation[group][key] = entry
    return notation


def load_notation(path: Path) -> dict[str, dict[str, dict[str, Any]]]:
    """Load a generated notation adapter for a read-only consumer."""

    return _load_notation(path)


def _load_typst_notation(
    symbols_path: Path, equations_path: Path
) -> dict[str, dict[str, dict[str, Any]]]:
    """Derive the canonical notation registry from the two shared Typst facades."""

    notation: dict[str, dict[str, dict[str, Any]]] = {}
    for group, path, label, facade in (
        ("symbols", symbols_path, "aria-notation-symbol", "symb"),
        ("equations", equations_path, "aria-notation-equation", "eqs"),
    ):
        notation[group] = {}
        for index, raw in enumerate(_query_metadata(path, label), start=1):
            key = raw.get("key")
            tex = raw.get("tex")
            description = raw.get("description")
            thesis_list = raw.get("thesis_list")
            order = raw.get("order")
            if not isinstance(key, str) or not key.strip():
                raise GlossaryError(f"{path}: {label} #{index} has an invalid key")
            if not isinstance(tex, str) or not tex.strip():
                raise GlossaryError(
                    f"{path}: {group}.{key}.tex must be a non-empty string"
                )
            if not isinstance(description, str):
                raise GlossaryError(
                    f"{path}: {group}.{key}.description must be a string"
                )
            if not isinstance(thesis_list, bool):
                raise GlossaryError(
                    f"{path}: {group}.{key}.thesis_list must be a boolean"
                )
            if isinstance(order, bool) or not isinstance(order, int):
                raise GlossaryError(f"{path}: {group}.{key}.order must be an integer")
            if key in notation[group]:
                raise GlossaryError(f"{path}: duplicate {group} key {key!r}")
            notation[group][key] = {
                "tex": tex.strip(),
                "typst": f"#{facade}.{key}",
                "description": description.strip(),
                "thesis_list": thesis_list,
                "order": order,
            }
    return notation


def _validate_terms(terms: list[dict[str, Any]]) -> None:
    ids: set[str] = set()
    anchors: set[str] = set()
    typst_macros: set[str] = set()
    for term in terms:
        missing = sorted(REQUIRED_FIELDS - set(term))
        if missing:
            raise GlossaryError(
                f"{term.get('id', '<missing id>')} missing fields: {missing}"
            )
        term_id = _expect_string(term, "id")
        anchor = _expect_string(term, "anchor")
        if term_id in ids:
            raise GlossaryError(f"duplicate term id: {term_id}")
        if anchor in anchors:
            raise GlossaryError(f"duplicate anchor: {anchor}")
        ids.add(term_id)
        anchors.add(anchor)
        if not anchor.startswith("term-"):
            raise GlossaryError(f"{term_id}: anchor must start with 'term-'")
        for field in ("aliases", "internal_links", "citations", "related", "kg_tags"):
            if field in term and not isinstance(term[field], list):
                raise GlossaryError(f"{term_id}: {field} must be a list")
        for field in ("symbol_refs", "equation_refs"):
            if field in term and not isinstance(term[field], list):
                raise GlossaryError(f"{term_id}: {field} must be a list")
        tier = term.get("tier")
        if tier not in {"core", "support", "background"}:
            raise GlossaryError(
                f"{term_id}: tier must be one of core, support, background"
            )
        lookup_rank = term.get("lookup_rank")
        if lookup_rank is not None and (
            isinstance(lookup_rank, bool) or not isinstance(lookup_rank, (int, float))
        ):
            raise GlossaryError(f"{term_id}: lookup_rank must be numeric when set")
        typst_macro = term.get("typst_macro")
        if typst_macro is not None:
            if not isinstance(typst_macro, str) or not re.match(
                r"^[A-Za-z_][A-Za-z0-9_]*$", typst_macro
            ):
                raise GlossaryError(
                    f"{term_id}: typst_macro must be a valid Typst identifier"
                )
            if typst_macro in typst_macros:
                raise GlossaryError(f"duplicate typst_macro: {typst_macro}")
            typst_macros.add(typst_macro)
        formulae = term.get("formulae")
        if formulae is not None and not isinstance(formulae, list):
            raise GlossaryError(f"{term_id}: formulae must be a list")
        formula = term.get("formula")
        if formula is not None and not isinstance(formula, dict):
            raise GlossaryError(f"{term_id}: formula must be a mapping")
        if isinstance(formula, dict) and formula:
            tex = formula.get("tex")
            if tex is not None and (not isinstance(tex, str) or not tex.strip()):
                raise GlossaryError(
                    f"{term_id}: formula.tex must be a non-empty string"
                )
        for idx, formula in enumerate(formulae or [], start=1):
            if not isinstance(formula, dict):
                raise GlossaryError(f"{term_id}: formulae[{idx}] must be a mapping")
            tex = formula.get("tex")
            if not isinstance(tex, str) or not tex.strip():
                raise GlossaryError(
                    f"{term_id}: formulae[{idx}].tex must be a non-empty string"
                )
    for term in terms:
        term_id = _expect_string(term, "id")
        parent = term.get("parent")
        if parent is not None and (
            not isinstance(parent, str)
            or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", parent)
        ):
            raise GlossaryError(f"{term_id}: parent must be a taxonomy slug")
        for related in _as_list(term, "related"):
            if related not in ids:
                raise GlossaryError(f"{term_id}: unknown related {related!r}")


def _validate_lookup_refs(
    terms: list[dict[str, Any]], notation: dict[str, dict[str, dict[str, Any]]]
) -> None:
    for term in terms:
        term_id = _expect_string(term, "id")
        for ref in _as_list(term, "symbol_refs"):
            if ref not in notation["symbols"]:
                raise GlossaryError(f"{term_id}: unknown symbol_ref {ref!r}")
        for ref in _as_list(term, "equation_refs"):
            if ref not in notation["equations"]:
                raise GlossaryError(f"{term_id}: unknown equation_ref {ref!r}")


def _validate_notation_metadata(
    notation: dict[str, dict[str, dict[str, Any]]],
) -> None:
    for group in ("symbols", "equations"):
        for key, entry in notation[group].items():
            if entry.get("thesis_list") and not entry.get("description"):
                raise GlossaryError(
                    f"canonical {group} metadata: {key} has thesis_list: true "
                    "but no description"
                )


def normalize_and_validate_metadata(
    terms: list[dict[str, Any]], notation: dict[str, dict[str, dict[str, Any]]]
) -> list[dict[str, Any]]:
    """Normalize queried glossary rows and validate their shared metadata."""

    normalized = [_normalize_queried_term(term) for term in terms]
    _validate_terms(normalized)
    _validate_lookup_refs(normalized, notation)
    _validate_notation_metadata(notation)
    return normalized


def _validate_typst_notation_expressions(
    notation: dict[str, dict[str, dict[str, Any]]],
) -> None:
    """Compile every notation Typst expression against the shared facades."""

    checks = [
        (group, key, entry["typst"])
        for group in ("symbols", "equations")
        for key, entry in notation[group].items()
    ]
    if not checks:
        return

    tmp_parent = ROOT / ".omx" / "tmp"
    tmp_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="notation-check-", dir=tmp_parent
    ) as tmp_dir:
        tmp_path = Path(tmp_dir)
        fixture = tmp_path / "notation-check.typ"
        output = tmp_path / "notation-check.pdf"
        rel_symbols = os.path.relpath(
            ROOT / "docs/typst/shared/symbols.typ", start=tmp_path
        )
        rel_equations = os.path.relpath(
            ROOT / "docs/typst/shared/equations.typ", start=tmp_path
        )
        lines = [
            f'#import "{rel_symbols}": symb',
            f'#import "{rel_equations}": eqs',
            "",
            "#let notation-checks = (",
        ]
        for group, key, typst_expr in sorted(checks):
            lines += [
                f"  // {group}.{key}",
                f"  [{typst_expr}],",
            ]
        lines += [
            ")",
            "",
            "#for item in notation-checks {",
            "  item",
            "  linebreak()",
            "}",
            "",
        ]
        fixture.write_text("\n".join(lines), encoding="utf-8")
        command = [
            "typst",
            "compile",
            "--root",
            str(ROOT),
            str(fixture),
            str(output),
        ]
        try:
            subprocess.run(
                command,
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as exc:
            raise GlossaryError(
                "typst executable not found; install Typst to validate notation"
            ) from exc
        except subprocess.CalledProcessError as exc:
            details = (exc.stderr or exc.stdout or "").strip()
            raise GlossaryError(
                "docs/notation.yml contains a Typst expression that does not "
                f"compile against shared symbols/equations:\n{details}"
            ) from exc


def _expect_string(term: dict[str, Any], field: str) -> str:
    value = term.get(field)
    if not isinstance(value, str) or not value.strip():
        raise GlossaryError(
            f"{term.get('id', '<missing id>')}: {field} must be a non-empty string"
        )
    return value.strip()


def _as_list(term: dict[str, Any], field: str) -> list[str]:
    values = term.get(field) or []
    return [str(value) for value in values]


def _term_formulae(term: dict[str, Any]) -> list[dict[str, Any]]:
    formulae: list[dict[str, Any]] = []
    formula = term.get("formula")
    if isinstance(formula, dict) and formula.get("tex"):
        formulae.append(formula)
    for item in term.get("formulae") or []:
        if isinstance(item, dict) and item.get("tex"):
            formulae.append(item)
    return formulae


def _html_attr(value: str) -> str:
    return html.escape(value, quote=True)


def _html_text(value: str) -> str:
    return html.escape(value, quote=False)


def _qmd_link(
    path: str, label: str | None = None, *, css_class: str = "glossary-chip"
) -> str:
    target = _qmd_target(path)
    text = label or _link_label(path)
    return f'<a class="{css_class}" href="{_html_attr(target)}" title="{_html_attr(path)}">{_html_text(text)}</a>'


def _qmd_target(path: str) -> str:
    anchor = ""
    if "#" in path:
        path, anchor_value = path.split("#", 1)
        anchor = "#" + anchor_value
    if path.startswith("docs/contents/"):
        return _rendered_doc_path(path.removeprefix("docs/contents/")) + anchor
    elif path.startswith("docs/reference/"):
        return (
            "../reference/"
            + _rendered_doc_path(path.removeprefix("docs/reference/"))
            + anchor
        )
    elif path.startswith("docs/"):
        return "../" + _rendered_doc_path(path.removeprefix("docs/")) + anchor
    return _rendered_doc_path(path) + anchor


def _rendered_doc_path(path: str) -> str:
    if path.endswith(".qmd"):
        return path.removesuffix(".qmd") + ".html"
    return path


def _link_label(path: str) -> str:
    path_without_anchor = path.split("#", 1)[0]
    if path_without_anchor.startswith("docs/reference/"):
        return Path(path_without_anchor).stem.split(".")[-1]
    target = ROOT / path_without_anchor
    if target.suffix == ".qmd" and target.is_file():
        title = _read_qmd_title(target)
        if title:
            return title
    if path_without_anchor.startswith("docs/typst/"):
        return (
            Path(path_without_anchor).stem.replace("-", " ").replace("_", " ").title()
        )
    stem = Path(path_without_anchor).stem
    return stem.replace("-", " ").replace("_", " ").title()


def _read_qmd_title(path: Path) -> str | None:
    text = path.read_text(encoding="utf-8")
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            front_matter = text[3:end]
            for line in front_matter.splitlines():
                if line.strip().startswith("title:"):
                    raw = line.split(":", 1)[1].strip().strip('"').strip("'")
                    raw = re.sub(r"\s*\{\s*#[^}]+\}\s*$", "", raw).strip()
                    if raw:
                        return raw
    for line in text.splitlines():
        match = re.match(r"^#\s+(.+?)(?:\s+\{#.+\})?$", line.strip())
        if match:
            return match.group(1).strip("`")
    return None


def _term_title(term: dict[str, Any]) -> str:
    short = term.get("short")
    label = _expect_string(term, "label")
    if isinstance(short, str) and short and short != label:
        return f"{short} - {label}"
    return label


def _lookup_rank(term: dict[str, Any]) -> tuple[float, str]:
    raw_rank = term.get("lookup_rank")
    rank = float(raw_rank) if isinstance(raw_rank, (int, float)) else 9999.0
    return (rank, str(term["label"]).lower())


def _render_qmd(
    terms: list[dict[str, Any]],
    path: Path,
    notation: dict[str, dict[str, dict[str, str]]],
) -> None:
    core_terms = sorted(
        [term for term in terms if term.get("tier") == "core"],
        key=_lookup_rank,
    )
    all_groups = {term["category"].split(".", 1)[0] for term in terms}
    grouped: dict[str, list[dict[str, Any]]] = {}
    for term in sorted(
        [term for term in terms if term.get("tier") != "core"],
        key=lambda item: (
            item["category"],
            0 if item.get("tier") == "support" else 1,
            item["label"].lower(),
        ),
    ):
        grouped.setdefault(term["category"].split(".", 1)[0], []).append(term)

    term_by_id = {term["id"]: term for term in terms}
    tier_counts = {
        tier: len([term for term in terms if term.get("tier") == tier])
        for tier in ("core", "support", "background")
    }
    category_links = [
        f'<a class="glossary-chip glossary-category-chip" href="#glossary-tier-core">'
        f"Core <span>{len(core_terms)}</span></a>",
        '<a class="glossary-chip glossary-category-chip" href="#glossary-core-math-lookup">'
        "Math lookup</a>",
        *[
            f'<a class="glossary-chip glossary-category-chip" href="#glossary-category-{_slug(group)}">'
            f"{_html_text(_category_label(group))} <span>{len(group_terms)}</span></a>"
            for group, group_terms in grouped.items()
        ],
    ]
    lines = [
        "---",
        'title: "Glossary"',
        "phase: generated",
        "audience: public",
        "status: current",
        "owner: generated",
        "page-layout: full",
        "format:",
        "  html:",
        "    code-tools: false",
        "    page-layout: full",
        "    toc: false",
        "bibliography: ../references.bib",
        "number-sections: false",
        "execute:",
        "  freeze: false",
        "---",
        "",
        "<!-- Generated by scripts/glossary_build.py; edit docs/typst/shared/glossary.typ. -->",
        "",
        "::: {.glossary-page}",
        "",
        "::: {.glossary-intro}",
        f"**{len(terms)} terms** across **{len(all_groups)} categories**. The canonical source is",
        "`docs/typst/shared/glossary.typ`; generated Quarto, Typst, YAML, KG, and shortcode artifacts",
        "share the same definitions.",
        "",
        f"Tier counts: **{tier_counts['core']} core**, **{tier_counts['support']} support**,",
        f"and **{tier_counts['background']} background** terms. Core terms are the thesis math lookup;",
        "background terms remain linkable but are visually demoted.",
        "",
        "Use `{{{< gls term-id >}}}` for the linked short label and",
        "`{{{< glsfull term-id >}}}` for the linked full label in QMD pages.",
        ":::",
        "",
        '<nav class="glossary-category-index" aria-label="Glossary categories">',
        *category_links,
        "</nav>",
        "",
    ]
    lines += _render_core_lookup(core_terms, notation)
    lines += [
        "## Core Concepts {#glossary-tier-core}",
        "",
        '<div class="glossary-card-grid glossary-card-grid-core">',
        "",
    ]
    for term in core_terms:
        lines += _render_term_card(term, term_by_id, notation)
    lines += ["</div>", ""]

    for group, group_terms in grouped.items():
        lines += [
            f"## {_category_label(group)} {{#glossary-category-{_slug(group)}}}",
            "",
            '<div class="glossary-card-grid">',
            "",
        ]
        for term in group_terms:
            lines += _render_term_card(term, term_by_id, notation)
        lines += ["</div>", ""]
    all_citations = sorted(
        {citation for term in terms for citation in _as_list(term, "citations")}
    )
    if all_citations:
        lines += [
            "::: {.glossary-citation-seed}",
            "; ".join(f"[@{citation}]" for citation in all_citations),
            ":::",
            "",
        ]
    lines += [":::", ""]
    _write_text(path, "\n".join(lines).rstrip() + "\n")


def _render_core_lookup(
    core_terms: list[dict[str, Any]],
    notation: dict[str, dict[str, dict[str, str]]],
) -> list[str]:
    if not core_terms:
        return []
    lines = [
        "## Core Math Lookup {#glossary-core-math-lookup}",
        "",
        '<div class="glossary-lookup-wrap">',
        '<table class="glossary-lookup-table">',
        "<thead>",
        "<tr>",
        "<th>Concept</th>",
        "<th>Meaning</th>",
        "<th>Symbols</th>",
        "<th>Equations</th>",
        "</tr>",
        "</thead>",
        "<tbody>",
    ]
    for term in core_terms:
        term_link = f'<a href="#{_html_attr(term["anchor"])}">{_html_text(_term_title(term))}</a>'
        symbols = _render_notation_refs(
            _as_list(term, "symbol_refs"), notation["symbols"], "symbol"
        )
        equations = _render_notation_refs(
            _as_list(term, "equation_refs"), notation["equations"], "equation"
        )
        empty = '<span class="glossary-muted">-</span>'
        lines += [
            "<tr>",
            f"<td>{term_link}</td>",
            f"<td>{_html_text(str(term['definition_short']).strip())}</td>",
            f"<td>{symbols or empty}</td>",
            f"<td>{equations or empty}</td>",
            "</tr>",
        ]
    lines += ["</tbody>", "</table>", "</div>", ""]
    return lines


def _render_notation_refs(
    refs: list[str], entries: dict[str, dict[str, str]], kind: str
) -> str:
    items = []
    for ref in refs:
        entry = entries.get(ref)
        if entry is None:
            continue
        tex = entry["tex"]
        items.append(
            '<span class="glossary-notation-item">'
            f'<span class="glossary-notation-math">${tex}$</span>'
            f"<code>{_html_text(ref)}</code>"
            "</span>"
        )
    if not items:
        return ""
    return f'<div class="glossary-notation-list glossary-notation-{kind}s">{" ".join(items)}</div>'


def _render_term_card(
    term: dict[str, Any],
    term_by_id: dict[str, dict[str, Any]],
    notation: dict[str, dict[str, dict[str, str]]],
) -> list[str]:
    tier = str(term.get("tier") or "support")
    lines = [
        f'<article class="glossary-card glossary-tier-{_html_attr(tier)}" id="{_html_attr(term["anchor"])}">',
        '<div class="glossary-card-header">',
        f'<div class="glossary-term-title">{_html_text(term["label"])}</div>',
        '<div class="glossary-term-badges">',
    ]
    short = term.get("short")
    if isinstance(short, str) and short and short != term["label"]:
        lines.append(
            f'<span class="glossary-badge glossary-badge-short">{_html_text(short)}</span>'
        )
    lines += [
        f'<span class="glossary-badge glossary-tier-badge glossary-tier-badge-{_html_attr(tier)}">{_html_text(tier)}</span>',
        f'<span class="glossary-badge">{_html_text(term["category"])}</span>',
        "</div>",
        "</div>",
        "",
    ]
    aliases = _as_list(term, "aliases")
    if aliases:
        lines += [
            '<div class="glossary-aliases">',
            "<span>Aliases</span>",
            " ".join(f"<code>{_html_text(alias)}</code>" for alias in aliases),
            "</div>",
            "",
        ]
    symbol_refs = _render_notation_refs(
        _as_list(term, "symbol_refs"), notation["symbols"], "symbol"
    )
    equation_refs = _render_notation_refs(
        _as_list(term, "equation_refs"), notation["equations"], "equation"
    )
    if symbol_refs or equation_refs:
        lines += ['<div class="glossary-card-notation">']
        if symbol_refs:
            lines += [f"<div><strong>Symbols</strong>{symbol_refs}</div>"]
        if equation_refs:
            lines += [f"<div><strong>Equations</strong>{equation_refs}</div>"]
        lines += ["</div>", ""]
    lines += [
        f'<p class="glossary-definition">{_html_text(term["definition_short"].strip())}</p>',
        "",
    ]
    if term.get("definition_long"):
        lines += [
            f'<p class="glossary-detail-text">{_html_text(str(term["definition_long"]).strip())}</p>',
            "",
        ]
    for formula in _term_formulae(term):
        label = str(formula.get("label") or "").strip()
        lines += [
            "::: {.glossary-formula}",
        ]
        if label:
            lines += [f"**{_html_text(label)}**", ""]
        lines += [
            "$$",
            str(formula["tex"]).strip(),
            "$$",
            ":::",
            "",
        ]
    lines += _render_metadata_details(term, term_by_id)
    lines += ["</article>", ""]
    return lines


def _render_metadata_details(
    term: dict[str, Any], term_by_id: dict[str, dict[str, Any]]
) -> list[str]:
    related = []
    for related_id in _as_list(term, "related"):
        related_term = term_by_id.get(related_id)
        if related_term:
            related.append(
                f'<a class="glossary-chip" href="#{_html_attr(related_term["anchor"])}">'
                f"{_html_text(str(related_term.get('short') or related_term['label']))}</a>"
            )
    docs = [
        _qmd_link(link, css_class="glossary-chip")
        for link in _as_list(term, "internal_links")
    ]
    citations = [
        f'<a class="glossary-chip glossary-citation" href="#ref-{_html_attr(citation)}">&#64;{_html_text(citation)}</a>'
        for citation in _as_list(term, "citations")
    ]
    if not (related or docs or citations):
        return []

    lines = [
        '<details class="glossary-details">',
        "<summary>Links and references</summary>",
        '<div class="glossary-metadata">',
    ]
    if related:
        lines.append(
            f'<div class="glossary-metadata-row"><span>Related</span><div>{" ".join(related)}</div></div>'
        )
    if docs:
        lines.append(
            f'<div class="glossary-metadata-row"><span>Docs</span><div>{" ".join(docs)}</div></div>'
        )
    if citations:
        lines.append(
            f'<div class="glossary-metadata-row"><span>References</span><div>{" ".join(citations)}</div></div>'
        )
    lines += ["</div>", "</details>", ""]
    return lines


def _category_label(group: str) -> str:
    return group.replace("-", " ").replace("_", " ").title()


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", value.lower()).strip("-")


def _typst_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _lua_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _typst_content(value: str) -> str:
    return "[" + value.replace("]", "\\]") + "]"


def _typst_term_macros(terms: list[dict[str, Any]]) -> list[tuple[str, str, str]]:
    macros = []
    for term in terms:
        typst_macro = term.get("typst_macro")
        if isinstance(typst_macro, str) and typst_macro:
            macros.append(
                (
                    typst_macro,
                    str(term.get("short") or term["label"]),
                    str(term["label"]),
                )
            )
    return sorted(macros, key=lambda item: item[0].lower())


def _render_typst(terms: list[dict[str, Any]], path: Path) -> None:
    lines = [
        "// Generated by scripts/glossary_build.py; edit docs/typst/shared/glossary.typ.",
        "",
        "#let glossary = (",
    ]
    for term in sorted(terms, key=lambda item: item["id"]):
        short = term.get("short") or term["label"]
        lines.append(
            "  (id: "
            + _typst_string(term["id"])
            + ", label: "
            + _typst_string(term["label"])
            + ", short: "
            + _typst_string(str(short))
            + ", anchor: "
            + _typst_string(term["anchor"])
            + "),"
        )
    lines += [
        ")",
        "",
        "// Backwards-compatible Typst term constants generated from glossary records",
        "// carrying `typst_macro` metadata.",
    ]
    for macro, short, full in _typst_term_macros(terms):
        lines += [
            f"#let {macro} = {_typst_string(short)}",
            f"#let {macro}_full = {_typst_string(full)}",
        ]
    lines += [
        "",
        "// Use Glossarium-native @term references in Typst prose.",
        "// This compatibility file intentionally does not generate gls wrappers.",
        "",
        "#let glossary-list() = [",
    ]
    for term in sorted(terms, key=lambda item: item["label"].lower()):
        definition = str(term["definition_short"]).strip()
        lines.append(f"  - *{_term_title(term)}*: {definition}")
    lines += ["]", ""]
    _write_text(path, "\n".join(lines))


def _render_jsonl(terms: list[dict[str, Any]], path: Path) -> None:
    rows = []
    for term in sorted(terms, key=lambda item: item["id"]):
        rows.append(
            {
                "node_type": "Concept",
                "id": term["id"],
                "anchor": term["anchor"],
                "label": term["label"],
                "short": term.get("short"),
                "aliases": _as_list(term, "aliases"),
                "category": term["category"],
                "parent": term.get("parent"),
                "tier": term.get("tier"),
                "lookup_rank": term.get("lookup_rank"),
                "definition_short": str(term["definition_short"]).strip(),
                "definition_long": str(term.get("definition_long") or "").strip(),
                "internal_links": _as_list(term, "internal_links"),
                "citations": _as_list(term, "citations"),
                "related": _as_list(term, "related"),
                "kg_tags": _as_list(term, "kg_tags"),
                "typst_macro": term.get("typst_macro"),
                "symbol_refs": _as_list(term, "symbol_refs"),
                "equation_refs": _as_list(term, "equation_refs"),
                "notation": term.get("notation") or {},
                "formula": term.get("formula") or {},
                "formulae": term.get("formulae") or [],
            }
        )
    _write_text(path, "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def _render_compat_yaml(terms: list[dict[str, Any]], path: Path) -> None:
    rows = []
    for term in terms:
        row = {
            "id": term["id"],
            "anchor": term["anchor"],
            "label": term["label"],
            "short": term.get("short"),
        }
        if term.get("typst_macro"):
            row["typst_macro"] = term["typst_macro"]
        row.update(
            {
                "aliases": _as_list(term, "aliases"),
                "category": term["category"],
                "parent": term.get("parent"),
                "tier": term.get("tier"),
                "lookup_rank": term.get("lookup_rank"),
                "definition_short": str(term["definition_short"]).strip(),
                "definition_long": str(term.get("definition_long") or "").strip(),
                "formula": term.get("formula") or {},
                "formulae": term.get("formulae") or [],
                "notation": term.get("notation") or {},
                "symbol_refs": _as_list(term, "symbol_refs"),
                "equation_refs": _as_list(term, "equation_refs"),
                "internal_links": _as_list(term, "internal_links"),
                "citations": _as_list(term, "citations"),
                "related": _as_list(term, "related"),
                "kg_tags": _as_list(term, "kg_tags"),
            }
        )
        rows.append(
            {key: value for key, value in row.items() if value not in (None, {}, [])}
        )
    header = (
        "# Generated compatibility glossary source.\n"
        "# Do not edit by hand; edit docs/typst/shared/glossary.typ and run `make glossary`.\n\n"
    )
    body = yaml.safe_dump(rows, sort_keys=False, allow_unicode=True, width=88)
    _write_text(path, header + body)


def _render_shortcode_lua(terms: list[dict[str, Any]], path: Path) -> None:
    lines = [
        "-- Generated by scripts/glossary_build.py; edit docs/typst/shared/glossary.typ.",
        "",
        "return {",
    ]
    for term in sorted(terms, key=lambda item: item["id"]):
        short = str(term.get("short") or term["label"])
        lines += [
            f"  [{_lua_string(term['id'])}] = {{",
            f"    label = {_lua_string(term['label'])},",
            f"    short = {_lua_string(short)},",
            f"    anchor = {_lua_string(term['anchor'])},",
            "  },",
        ]
    lines += ["}", ""]
    _write_text(path, "\n".join(lines))


def _render_notation_lua(
    notation: dict[str, dict[str, dict[str, Any]]], path: Path
) -> None:
    lines = [
        "-- Generated by scripts/glossary_build.py; edit docs/typst/shared/symbols.typ or equations.typ.",
        "",
        "return {",
    ]
    for group in ("symbols", "equations"):
        lines.append(f"  {group} = {{")
        for key, entry in sorted(notation[group].items()):
            lines += [
                f"    [{_lua_string(key)}] = {{",
                f"      tex = {_lua_string(entry['tex'])},",
                f"      typst = {_lua_string(entry['typst'])},",
                f"      description = {_lua_string(entry.get('description', ''))},",
                f"      thesis_list = {str(entry.get('thesis_list', False)).lower()},",
                "    },",
            ]
        lines.append("  },")
    lines += ["}", ""]
    _write_text(path, "\n".join(lines))


def _render_notation_typst(
    notation: dict[str, dict[str, dict[str, Any]]], path: Path
) -> None:
    lines = [
        "// Generated by scripts/glossary_build.py; edit docs/typst/shared/symbols.typ or equations.typ.",
        "",
        '#import "symbols.typ": symb',
        '#import "equations.typ": eqs',
        "",
    ]
    for group in ("symbols", "equations"):
        lines.append(f"#let notation-{group} = (")
        sorted_entries = sorted(
            notation[group].items(),
            key=lambda item: (item[1].get("order", 9999), item[0]),
        )
        for key, entry in sorted_entries:
            lines.append(
                "  "
                + _typst_string(key)
                + ": (tex: "
                + _typst_string(entry["tex"])
                + ", typst: "
                + _typst_string(entry["typst"])
                + ", body: ["
                + entry["typst"]
                + "]"
                + ", description: "
                + _typst_string(entry.get("description", ""))
                + ", thesis_list: "
                + ("true" if entry.get("thesis_list", False) else "false")
                + ", order: "
                + str(entry.get("order", 9999))
                + "),"
            )
        lines += [")", ""]
        lines.append(f"#let notation-{group}-list = (")
        for key, entry in sorted_entries:
            lines.append(
                "  (key: "
                + _typst_string(key)
                + ", tex: "
                + _typst_string(entry["tex"])
                + ", typst: "
                + _typst_string(entry["typst"])
                + ", body: ["
                + entry["typst"]
                + "]"
                + ", description: "
                + _typst_string(entry.get("description", ""))
                + ", thesis_list: "
                + ("true" if entry.get("thesis_list", False) else "false")
                + ", order: "
                + str(entry.get("order", 9999))
                + "),"
            )
        lines += [")", ""]
    _write_text(path, "\n".join(lines))


def _render_notation_yaml(
    notation: dict[str, dict[str, dict[str, Any]]], path: Path
) -> None:
    """Write the generated Quarto and Graphify notation adapter."""

    lines = [
        "# Generated by scripts/glossary_build.py; do not edit by hand.",
        "# Canonical owners: docs/typst/shared/symbols.typ and equations.typ.",
        "",
    ]
    for group in ("symbols", "equations"):
        lines.append(f"{group}:")
        for key, entry in notation[group].items():
            lines += [
                f"  {key}:",
                f"    tex: {_yaml_string(entry['tex'])}",
                f"    typst: {_yaml_string(entry['typst'])}",
                f"    description: {_yaml_string(entry['description'])}",
                f"    thesis_list: {str(entry['thesis_list']).lower()}",
                f"    order: {entry['order']}",
            ]
        lines.append("")
    _write_text(path, "\n".join(lines))


def _yaml_string(value: str) -> str:
    """Render a YAML scalar without reinterpreting TeX escapes."""

    return "'" + value.replace("'", "''") + "'"


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build(args: argparse.Namespace) -> None:
    terms = _load_terms(args.terms)
    _validate_terms(terms)
    notation = _load_typst_notation(args.symbols, args.equations)
    _validate_lookup_refs(terms, notation)
    _validate_notation_metadata(notation)
    _validate_typst_notation_expressions(notation)
    actions = set(args.actions)
    if "all" in actions:
        actions = {
            "validate",
            "render-quarto",
            "render-typst",
            "render-jsonl",
            "render-compat-yaml",
            "render-shortcode-lua",
            "render-notation-yaml",
            "render-notation-lua",
            "render-notation-typst",
        }
    if "render-quarto" in actions:
        _render_qmd(terms, args.qmd_out, notation)
    if "render-typst" in actions:
        _render_typst(terms, args.typst_out)
    if "render-jsonl" in actions:
        _render_jsonl(terms, args.jsonl_out)
    if "render-compat-yaml" in actions:
        _render_compat_yaml(terms, args.compat_yaml_out)
    if "render-shortcode-lua" in actions:
        _render_shortcode_lua(terms, args.shortcode_lua_out)
    if "render-notation-yaml" in actions:
        _render_notation_yaml(notation, args.notation_yaml_out)
    if "render-notation-lua" in actions:
        _render_notation_lua(notation, args.notation_lua_out)
    if "render-notation-typst" in actions:
        _render_notation_typst(notation, args.notation_typst_out)
    if "validate" in actions:
        print(f"Validated {len(terms)} glossary terms from {args.terms}")
        print(
            f"Validated {len(notation['symbols'])} symbols and "
            f"{len(notation['equations'])} equations from {args.symbols} and "
            f"{args.equations}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "actions",
        nargs="*",
        default=["all"],
        choices=[
            "all",
            "validate",
            "render-quarto",
            "render-typst",
            "render-jsonl",
            "render-compat-yaml",
            "render-shortcode-lua",
            "render-notation-yaml",
            "render-notation-lua",
            "render-notation-typst",
        ],
    )
    parser.add_argument("--terms", type=Path, default=DEFAULT_TERMS)
    parser.add_argument("--compat-yaml-out", type=Path, default=DEFAULT_COMPAT_YAML)
    parser.add_argument("--symbols", type=Path, default=DEFAULT_SYMBOLS)
    parser.add_argument("--equations", type=Path, default=DEFAULT_EQUATIONS)
    parser.add_argument("--qmd-out", type=Path, default=DEFAULT_QMD)
    parser.add_argument("--typst-out", type=Path, default=DEFAULT_TYPST)
    parser.add_argument("--jsonl-out", type=Path, default=DEFAULT_JSONL)
    parser.add_argument("--shortcode-lua-out", type=Path, default=DEFAULT_SHORTCODE_LUA)
    parser.add_argument("--notation-lua-out", type=Path, default=DEFAULT_NOTATION_LUA)
    parser.add_argument("--notation-yaml-out", type=Path, default=DEFAULT_NOTATION_YAML)
    parser.add_argument(
        "--notation-typst-out", type=Path, default=DEFAULT_NOTATION_TYPST
    )
    args = parser.parse_args()
    try:
        build(args)
    except GlossaryError as exc:
        raise SystemExit(f"glossary error: {exc}") from exc


if __name__ == "__main__":
    main()
