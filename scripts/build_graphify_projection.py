#!/usr/bin/env python3
"""Build the deterministic Markdown evidence projection required by Graphify."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import posixpath
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Callable, Iterable, Mapping, Sequence

from glossary_build import (
    GlossaryError,
    normalize_and_validate_metadata,
)
from literature_catalog import (
    BibliographyEntry,
    LiteratureCatalog,
    LiteratureCatalogConfig,
    LiteratureCatalogError,
    ManifestEntry,
    load_literature_catalog,
)


SCHEMA_VERSION = "1"
Runner = Callable[..., subprocess.CompletedProcess[str]]


class ProjectionError(RuntimeError):
    """Report an invalid owner, ambiguous identity, or unsafe output operation."""


@dataclass(frozen=True)
class ProjectionConfig:
    """Canonical inputs and the one explicit Typst code-reference input."""

    repo_root: Path
    thesis_root: Path = Path("docs/typst/thesis/main.typ")
    style_path: Path = Path("docs/typst/shared/style.typ")
    glossary_path: Path = Path("docs/typst/shared/glossary.typ")
    symbols_path: Path = Path("docs/typst/shared/symbols.typ")
    equations_path: Path = Path("docs/typst/shared/equations.typ")
    bibliography_paths: tuple[Path, ...] = LiteratureCatalogConfig.bibliography_paths
    manifest_path: Path = LiteratureCatalogConfig.manifest_path
    tex_root: Path = LiteratureCatalogConfig.tex_root
    pdf_root: Path = LiteratureCatalogConfig.pdf_root
    output_path: Path = Path("graphify-input")
    aria_code_ref: str = "main"
    aria_code_ref_source: str = "default"


@dataclass(frozen=True)
class ProjectionResult:
    """Rendered relative Markdown files and non-fatal validation warnings."""

    files: Mapping[str, str]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class _Macro:
    kind: str
    source: Path
    line: int
    column: int
    target: str
    ref: str | None = None
    start: int | None = None
    end: int | None = None
    language: str | None = None


@dataclass
class _Page:
    identity: str
    family: str
    lines: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class _Heading:
    text: str
    level: int
    label: str | None = None


@dataclass(frozen=True)
class _RenderData:
    revision: str
    source_tree: str
    aria_code_oid: str
    aria_code_pin_kind: str
    closure: Sequence[Path]
    citations_by_source: Mapping[Path, Counter[str]]
    bib: Mapping[str, BibliographyEntry]
    joined: Mapping[str, ManifestEntry]
    manifest: Sequence[ManifestEntry]
    targets: Mapping[str, Mapping[str, str]]
    relations: Sequence[Mapping[str, object]]
    headings: Sequence[_Heading]
    warnings: Sequence[str]
    terms: Mapping[str, Mapping[str, object]]
    notation: Mapping[str, Mapping[str, Mapping[str, object]]]
    notation_owners: Mapping[tuple[str, str], Path]
    usage_by_source: Mapping[Path, Mapping[str, Counter[str]]]


@dataclass
class _Pages:
    thesis: dict[Path, _Page]
    citations: dict[str, _Page]
    literature: dict[str, _Page]
    code: dict[str, _Page]
    assets: dict[str, _Page]
    asset_owners: dict[str, tuple[str, str, str]]
    terms: dict[str, _Page]
    symbols: dict[str, _Page]
    equations: dict[str, _Page]

    def all(self) -> list[_Page]:
        return [
            *self.thesis.values(),
            *self.citations.values(),
            *self.literature.values(),
            *self.code.values(),
            *self.assets.values(),
            *self.terms.values(),
            *self.symbols.values(),
            *self.equations.values(),
        ]


def _default_runner(
    argv: Sequence[str], *, cwd: Path
) -> subprocess.CompletedProcess[str]:
    if not argv or argv[0] not in {"git", "typst"}:
        raise ProjectionError("only git and typst subprocesses are permitted")
    return subprocess.run(
        list(argv), cwd=cwd, check=False, capture_output=True, text=True
    )


def _run(runner: Runner, argv: Sequence[str], root: Path) -> str:
    if not argv or argv[0] not in {"git", "typst"}:
        raise ProjectionError("only git and typst subprocesses are permitted")
    try:
        result = runner(list(argv), cwd=root)
    except OSError as error:
        raise ProjectionError(f"{argv[0]} unavailable: {error}") from error
    if result.returncode:
        detail = (result.stderr or result.stdout or "command failed").strip()
        raise ProjectionError(f"{argv[0]} failed: {detail}")
    return result.stdout


def _relative_path(path: Path, *, label: str) -> Path:
    if path.is_absolute() or ".." in path.parts:
        raise ProjectionError(f"{label} must be a repository-relative path: {path}")
    return Path(PurePosixPath(path.as_posix()))


def _owner_path(config: ProjectionConfig, relative: Path) -> Path:
    relative = _relative_path(relative, label="owner")
    repository = config.repo_root.resolve()
    candidate = repository / relative
    try:
        resolved = candidate.resolve(strict=False)
    except (OSError, RuntimeError) as error:
        raise ProjectionError(
            f"owner path cannot be resolved safely: {relative.as_posix()}: {error}"
        ) from error
    if not resolved.is_relative_to(repository):
        raise ProjectionError(
            f"owner path physically escapes repository: {relative.as_posix()}"
        )
    return resolved


def _lexists(path: Path) -> bool:
    """Return whether a path or dangling symlink exists without resolving it."""

    return os.path.lexists(path)


def _strip_typst_noncode(text: str, *, blank_strings: bool = False) -> str:
    """Blank comments and raw blocks, optionally strings, preserving line positions."""

    def blank(match: re.Match[str]) -> str:
        return "".join("\n" if char == "\n" else " " for char in match.group(0))

    text = re.sub(r"(?s)```.*?```", blank, text)
    text = re.sub(r"(?s)`[^`]*`", blank, text)
    if blank_strings:
        text = re.sub(r'"(?:\\.|[^"\\])*"', blank, text, flags=re.S)
    text = re.sub(r"/\*.*?\*/", blank, text, flags=re.S)
    text = re.sub(r"//[^\n]*", blank, text)
    return text


def _literal_include(relative: Path, value: str, clean: str, position: int) -> Path:
    if value.startswith("@"):
        return relative
    include = PurePosixPath(value)
    line = clean.count("\n", 0, position) + 1
    if include.is_absolute():
        raise ProjectionError(
            f"{relative.as_posix()}:{line}: include escapes repository"
        )
    normalized = posixpath.normpath(
        posixpath.join(relative.parent.as_posix(), include.as_posix())
    )
    if normalized == ".." or normalized.startswith("../"):
        raise ProjectionError(
            f"{relative.as_posix()}:{line}: include escapes repository"
        )
    return Path(PurePosixPath(normalized))


def _included_sources(relative: Path, clean: str) -> list[Path]:
    literal_spans: list[tuple[int, int]] = []
    targets: list[Path] = []
    for match in re.finditer(r'#(?:include|import)\s+"([^"]+)"', clean):
        literal_spans.append(match.span())
        target = _literal_include(relative, match.group(1), clean, match.start())
        if target != relative:
            targets.append(target)
    for match in re.finditer(r"#(?:include|import)\s+([^\s\n,;)]+)", clean):
        if any(start <= match.start() < end for start, end in literal_spans):
            continue
        token = match.group(1)
        if token.startswith('"') or token.startswith("@"):
            continue
        line = clean.count("\n", 0, match.start()) + 1
        raise ProjectionError(
            f"{relative.as_posix()}:{line}: dynamic include/import is unsupported"
        )
    return targets


def _source_closure(config: ProjectionConfig) -> tuple[Path, ...]:
    root = _relative_path(config.thesis_root, label="thesis root")
    pending = [root]
    seen: set[Path] = set()
    while pending:
        relative = pending.pop()
        if relative in seen:
            continue
        source = _owner_path(config, relative)
        if not source.is_file():
            raise ProjectionError(f"missing active Typst owner: {relative.as_posix()}")
        seen.add(relative)
        clean = _strip_typst_noncode(source.read_text(encoding="utf-8"))
        pending.extend(_included_sources(relative, clean))
    return tuple(sorted(seen, key=lambda item: item.as_posix()))


def _lexical_sources(
    config: ProjectionConfig,
    closure: Iterable[Path],
    catalog: LiteratureCatalog,
) -> tuple[dict[Path, Counter[str]], list[_Macro]]:
    citations_by_source: dict[Path, Counter[str]] = {}
    macros: list[_Macro] = []
    macro_re = re.compile(r"#(gh-symbol|gh-wip|gh)\s*\(([^\n)]*)\)")
    for relative in closure:
        clean = _strip_typst_noncode(
            _owner_path(config, relative).read_text(encoding="utf-8")
        )
        citation_text = re.sub(r'#(?:include|import)\s+"[^"]+"[^\n]*', "", clean)
        citations_by_source[relative] = catalog.citations(citation_text)
        for match in macro_re.finditer(clean):
            kind, body = match.groups()
            first = re.match(r'\s*"([^"]+)"', body)
            if first is None:
                line = clean.count("\n", 0, match.start()) + 1
                raise ProjectionError(
                    f"{relative.as_posix()}:{line}: {kind} target must be literal"
                )
            named = {
                key: quoted or numeric
                for key, quoted, numeric in re.findall(
                    r'\b(ref|line|end|language)\s*:\s*(?:"([^"]+)"|(\d+))', body
                )
            }
            line = clean.count("\n", 0, match.start()) + 1
            last_newline = clean.rfind("\n", 0, match.start())
            macros.append(
                _Macro(
                    kind=kind,
                    source=relative,
                    line=line,
                    column=match.start() - last_newline,
                    target=first.group(1),
                    ref=named.get("ref"),
                    start=int(named["line"]) if "line" in named else None,
                    end=int(named["end"]) if "end" in named else None,
                    language=named.get("language"),
                )
            )
    return citations_by_source, macros


def _notation_metadata(
    config: ProjectionConfig, runner: Runner
) -> dict[str, dict[str, dict[str, object]]]:
    """Query the canonical Typst facades used by Graphify notation pages."""

    notation: dict[str, dict[str, dict[str, object]]] = {}
    for group, path, label, facade in (
        ("symbols", config.symbols_path, "aria-notation-symbol", "symb"),
        ("equations", config.equations_path, "aria-notation-equation", "eqs"),
    ):
        output = _run(
            runner,
            [
                "typst",
                "query",
                path.as_posix(),
                f"<{label}>",
                "--field",
                "value",
                "--format",
                "json",
            ],
            config.repo_root,
        )
        try:
            queried = json.loads(output or "[]")
        except json.JSONDecodeError as error:
            raise ProjectionError(
                f"{group} metadata query returned invalid JSON"
            ) from error
        if not isinstance(queried, list) or not all(
            isinstance(row, dict) for row in queried
        ):
            raise ProjectionError(f"{group} metadata query must return a JSON list")
        entries: dict[str, dict[str, object]] = {}
        for index, row in enumerate(queried, start=1):
            entry = dict(row.get("value", row))
            key = entry.get("key")
            tex = entry.get("tex")
            description = entry.get("description")
            thesis_list = entry.get("thesis_list")
            order = entry.get("order")
            if not isinstance(key, str) or not key.strip():
                raise ProjectionError(f"{group} metadata #{index} has an invalid key")
            if not isinstance(tex, str) or not tex.strip():
                raise ProjectionError(f"{group}.{key}: tex must be a non-empty string")
            if not isinstance(description, str):
                raise ProjectionError(f"{group}.{key}: description must be a string")
            if not isinstance(thesis_list, bool):
                raise ProjectionError(f"{group}.{key}: thesis_list must be a boolean")
            if isinstance(order, bool) or not isinstance(order, int):
                raise ProjectionError(f"{group}.{key}: order must be an integer")
            if key in entries:
                raise ProjectionError(f"{group}: duplicate notation key {key!r}")
            entries[key] = {
                "tex": tex.strip(),
                "typst": f"#{facade}.{key}",
                "description": description.strip(),
                "thesis_list": thesis_list,
                "order": order,
            }
        notation[group] = entries
    return notation


def _glossary_terms(
    config: ProjectionConfig, runner: Runner, bib: Mapping[str, BibliographyEntry]
) -> dict[str, Mapping[str, object]]:
    """Query the canonical Glossarium rows through the injected Typst runner."""

    output = _run(
        runner,
        [
            "typst",
            "query",
            config.glossary_path.as_posix(),
            "<aria-glossary-term>",
            "--field",
            "value",
            "--format",
            "json",
        ],
        config.repo_root,
    )
    try:
        queried = json.loads(output or "[]")
    except json.JSONDecodeError as error:
        raise ProjectionError("glossary query returned invalid JSON") from error
    if not isinstance(queried, list) or not all(
        isinstance(row, dict) for row in queried
    ):
        raise ProjectionError("glossary query must return a JSON list of metadata")
    raw = [dict(row.get("value", row)) for row in queried]
    try:
        notation = _notation_metadata(config, runner)
        terms = normalize_and_validate_metadata(raw, notation)
    except GlossaryError as error:
        raise ProjectionError(f"glossary metadata invalid: {error}") from error
    term_map: dict[str, Mapping[str, object]] = {
        str(term["id"]): term for term in terms
    }
    if len(term_map) != len(terms):  # Defensive: validation normally catches this.
        raise ProjectionError("duplicate glossary term identity")
    for term_id, term in term_map.items():
        citations = term.get("citations", [])
        if not isinstance(citations, list):
            raise ProjectionError(f"{term_id}: citations must be a list")
        for key in citations:
            if not isinstance(key, str):
                raise ProjectionError(f"{term_id}: citations must contain strings")
            if key not in bib:
                raise ProjectionError(f"{term_id}: unknown citation {key!r}")
    return term_map


def _notation_owners(
    config: ProjectionConfig, notation: Mapping[str, Mapping[str, Mapping[str, object]]]
) -> dict[tuple[str, str], Path]:
    owners: dict[tuple[str, str], Path] = {}
    for group, prefix, directory in (
        ("symbols", "symb", "symbols"),
        ("equations", "eqs", "equations"),
    ):
        for key, entry in notation[group].items():
            expression = str(entry["typst"])
            match = re.fullmatch(
                rf"#{prefix}\.([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)",
                expression,
            )
            if match is None:
                raise ProjectionError(
                    f"{group}.{key}: malformed Typst expression {expression!r}"
                )
            namespace, member = match.groups()
            owner = Path(f"docs/typst/shared/{directory}/{namespace}.typ")
            try:
                text = _owner_path(config, owner).read_text(encoding="utf-8")
            except (OSError, ProjectionError) as error:
                raise ProjectionError(
                    f"{group}.{key}: missing implementation module {owner.as_posix()}"
                ) from error
            declarations = re.findall(rf"(?m)^\s*{re.escape(member)}\s*:", text)
            if len(declarations) != 1:
                raise ProjectionError(
                    f"{group}.{key}: expected one declaration of {member!r} in {owner.as_posix()}, found {len(declarations)}"
                )
            owners[(group, key)] = owner
    return owners


def _section_usage(
    config: ProjectionConfig,
    closure: Iterable[Path],
    terms: Mapping[str, Mapping[str, object]],
    notation: Mapping[str, Mapping[str, Mapping[str, object]]],
    bib: Mapping[str, BibliographyEntry],
) -> dict[Path, dict[str, Counter[str]]]:
    """Return delimiter-safe lexical references from active thesis sections only."""

    result: dict[Path, dict[str, Counter[str]]] = {}
    known_terms = set(terms)
    for source in closure:
        if not source.is_relative_to(Path("docs/typst/thesis/sections")):
            continue
        clean = _strip_typst_noncode(
            _owner_path(config, source).read_text(encoding="utf-8"),
            blank_strings=True,
        )
        clean = re.sub(r'#(?:include|import)\s+"[^"]+"[^\n]*', "", clean)
        usages: dict[str, Counter[str]] = {
            "term": Counter(),
            "symbol": Counter(),
            "equation": Counter(),
        }
        for match in re.finditer(
            r"(?<![\w])@([A-Za-z0-9_+-]+)(:[A-Za-z0-9_+-]+)?(?![A-Za-z0-9_+-])",
            clean,
        ):
            key, suffix = match.groups()
            line = clean.count("\n", 0, match.start()) + 1
            if key in known_terms:
                if key in bib:
                    raise ProjectionError(
                        f"{source.as_posix()}:{line}: ambiguous glossary/bibliography ID {key}"
                    )
                if suffix not in (None, ":short"):
                    raise ProjectionError(
                        f"{source.as_posix()}:{line}: invalid glossary suffix {suffix}"
                    )
                usages["term"][key] += 1
            elif suffix == ":short":
                raise ProjectionError(
                    f"{source.as_posix()}:{line}: unknown glossary term {key}:short"
                )
        for family, prefix, group in (
            ("symbol", "symb", "symbols"),
            ("equation", "eqs", "equations"),
        ):
            for match in re.finditer(
                rf"#{prefix}\.([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)",
                clean,
            ):
                key = match.group(1)
                line = clean.count("\n", 0, match.start()) + 1
                if key not in notation[group]:
                    raise ProjectionError(
                        f"{source.as_posix()}:{line}: unknown #{prefix}.{key}"
                    )
                usages[family][key] += 1
        result[source] = usages
    return result


def _query_typst(
    config: ProjectionConfig, runner: Runner, selector: str
) -> list[Mapping[str, object]]:
    project_root, thesis_input = _typst_context(config)
    output = _run(
        runner,
        [
            "typst",
            "query",
            thesis_input,
            selector,
            "--root",
            ".",
            "--input",
            f"aria-code-ref={config.aria_code_ref}",
            "--format",
            "json",
        ],
        project_root,
    )
    try:
        value = json.loads(output or "[]")
    except json.JSONDecodeError as error:
        raise ProjectionError(
            f"typst {selector} query returned invalid JSON"
        ) from error
    if not isinstance(value, list) or not all(isinstance(row, dict) for row in value):
        raise ProjectionError(f"typst {selector} query must return a JSON list")
    return value


def _compiled_value(row: Mapping[str, object], *names: str) -> str | None:
    for name in names:
        value = row.get(name)
        if isinstance(value, str):
            return value
    nested = row.get("value")
    if isinstance(nested, dict):
        return _compiled_value(nested, *names)
    return None


def _compiled_text(value: object) -> str:
    """Flatten Typst's compiled content tree without inferring source structure."""

    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "".join(_compiled_text(item) for item in value)
    if not isinstance(value, dict):
        return ""
    if isinstance(value.get("text"), str):
        return str(value["text"])
    return _compiled_text(value.get("child")) + _compiled_text(value.get("children"))


def _compiled_headings(rows: Sequence[Mapping[str, object]]) -> tuple[_Heading, ...]:
    """Retain compiled heading facts while leaving source attribution unresolved."""

    headings: list[_Heading] = []
    for row in rows:
        level = row.get("level")
        if not isinstance(level, int) or isinstance(level, bool) or level < 1:
            raise ProjectionError("typst heading query returned an invalid level")
        text = _compiled_text(row.get("body"))
        label = row.get("label")
        if label is not None and not isinstance(label, str):
            raise ProjectionError("typst heading query returned an invalid label")
        headings.append(_Heading(text=text, level=level, label=label))
    return tuple(headings)


def _citation_key(value: str) -> str:
    """Normalize Typst's serialized label wrapper to its BibTeX key."""

    if value.startswith("<") and value.endswith(">"):
        return value[1:-1]
    return value


def _compile_typst(config: ProjectionConfig, runner: Runner, output: Path) -> None:
    project_root, thesis_input = _typst_context(config)
    _run(
        runner,
        [
            "typst",
            "compile",
            thesis_input,
            str(output),
            "--root",
            ".",
            "--input",
            f"aria-code-ref={config.aria_code_ref}",
        ],
        project_root,
    )


def _typst_context(config: ProjectionConfig) -> tuple[Path, str]:
    """Return the owner root and thesis path used by the Typst subprocess."""

    thesis_root = _relative_path(config.thesis_root, label="thesis root")
    if len(thesis_root.parts) == 1:
        return config.repo_root, thesis_root.as_posix()
    owner_root = config.repo_root / thesis_root.parts[0]
    return owner_root, PurePosixPath(*thesis_root.parts[1:]).as_posix()


def _repository(config: ProjectionConfig) -> str:
    text = _owner_path(config, config.style_path).read_text(encoding="utf-8")
    match = re.search(r'#let\s+aria-github-repo\s*=\s*"([^"]+)"', text)
    if match is None or match.group(1).count("/") != 1:
        raise ProjectionError(
            f"{config.style_path.as_posix()}: missing aria-github-repo"
        )
    return match.group(1)


def _resolve_ref(config: ProjectionConfig, runner: Runner, ref: str) -> tuple[str, str]:
    pin_kind = "full-sha" if re.fullmatch(r"[0-9a-fA-F]{40}", ref) else "mutable"
    tag = runner(
        ["git", "show-ref", "--verify", "--quiet", f"refs/tags/{ref}"],
        cwd=config.repo_root,
    )
    if tag.returncode == 0:
        pin_kind = "release-tag"
    result = runner(
        ["git", "rev-parse", "--verify", f"{ref}^{{commit}}"], cwd=config.repo_root
    )
    if result.returncode == 0:
        return result.stdout.strip(), pin_kind
    detail = (result.stderr or result.stdout or "unresolved ref").strip()
    raise ProjectionError(f"git failed to resolve ref {ref}: {detail}")


def _line_range(macro: _Macro) -> tuple[int, int]:
    start = macro.start or 1
    end = macro.end or start
    if start < 1 or end < start:
        raise ProjectionError(
            f"{macro.source.as_posix()}:{macro.line}: invalid line range"
        )
    return start, end


def _code_url(repository: str, ref: str, path: str, start: int, end: int) -> str:
    fragment = f"#L{start}" + (f"-L{end}" if end != start else "")
    return f"https://github.com/{repository}/blob/{ref}/{path}{fragment}"


def _symbol_url(repository: str, symbol: str, language: str) -> str:
    return (
        f"https://github.com/search?q=repo%3A{repository}"
        f"+language%3A{language}+symbol%3A{symbol}&type=code"
    )


def _code_targets(
    config: ProjectionConfig,
    runner: Runner,
    repository: str,
    macros: Sequence[_Macro],
    compiled_links: Sequence[str],
) -> tuple[dict[str, dict[str, str]], list[dict[str, object]]]:
    expected_urls: list[str] = []
    expected_symbol_urls = {
        _symbol_url(repository, macro.target, macro.language or "python")
        for macro in macros
        if macro.kind == "gh-symbol"
    }
    admitted = [
        link
        for link in compiled_links
        if link.startswith(f"https://github.com/{repository}/blob/")
        or link in expected_symbol_urls
    ]
    relations: list[dict[str, object]] = []
    targets: dict[str, dict[str, str]] = {}
    head = _run(runner, ["git", "rev-parse", "HEAD"], config.repo_root).strip()
    dirty_output = _run(
        runner, ["git", "status", "--porcelain", "--"], config.repo_root
    )
    dirty_paths = {line[3:] for line in dirty_output.splitlines() if len(line) > 3}
    for macro in macros:
        if macro.kind == "gh-symbol":
            url = _symbol_url(repository, macro.target, macro.language or "python")
            expected_urls.append(url)
            relations.append(
                {
                    "kind": macro.kind,
                    "status": "unresolved-dynamic",
                    "target": macro.target,
                    "compiled_url": url,
                    "source": macro.source.as_posix(),
                    "line": macro.line,
                    "column": macro.column,
                }
            )
            continue
        path = _relative_path(Path(macro.target), label="code target").as_posix()
        ref = macro.ref or config.aria_code_ref
        if macro.kind == "gh" and ref == "main":
            raise ProjectionError(
                f"{macro.source.as_posix()}:{macro.line}: main is mutable and invalid for final gh"
            )
        oid, pin_kind = _resolve_ref(config, runner, ref)
        if macro.kind == "gh" and pin_kind == "mutable":
            raise ProjectionError(
                f"{macro.source.as_posix()}:{macro.line}: mutable ref {ref} is invalid for final gh"
            )
        start, end = _line_range(macro)
        _run(runner, ["git", "cat-file", "-e", f"{oid}:{path}"], config.repo_root)
        content = _run(runner, ["git", "show", f"{oid}:{path}"], config.repo_root)
        if end > max(1, len(content.splitlines())):
            raise ProjectionError(
                f"{macro.source.as_posix()}:{macro.line}: line range exceeds {path}"
            )
        url = _code_url(repository, ref, path, start, end)
        expected_urls.append(url)
        identity = f"code-target:{repository}@{ref}[{oid}]:{path}:{start}-{end}"
        current = config.repo_root / path
        if oid == head:
            status = "same-ref-owner-dirty" if path in dirty_paths else "same-ref-clean"
        else:
            status = (
                "different-ref-path-present"
                if _lexists(current)
                else "different-ref-path-absent"
            )
        targets.setdefault(
            identity,
            {
                "repository": repository,
                "source_ref": ref,
                "resolved_oid": oid,
                "path": path,
                "line_range": f"{start}-{end}",
                "validation": status,
                "owner_url": url,
            },
        )
        relations.append(
            {
                "kind": macro.kind,
                "target": identity,
                "compiled_url": url,
                "pin_kind": pin_kind,
                "source": macro.source.as_posix(),
                "line": macro.line,
                "column": macro.column,
            }
        )
    if Counter(expected_urls) != Counter(admitted):
        raise ProjectionError(
            "compiled/lexical code-link destination multiplicity mismatch"
        )
    totals = Counter(str(relation.get("target")) for relation in relations)
    ordinals: Counter[str] = Counter()
    for relation in relations:
        target = str(relation.get("target"))
        ordinals[target] += 1
        relation["ordinal"] = ordinals[target]
        relation["multiplicity"] = totals[target]
    return targets, relations


def _slug(identity: str) -> str:
    readable = re.sub(r"[^a-z0-9]+", "-", identity.casefold()).strip("-")[:42]
    digest = hashlib.sha256(identity.encode()).hexdigest()[:12]
    return f"{readable or 'identity'}-{digest}.md"


def _page_path(page: _Page) -> str:
    return f"{page.family}/{_slug(page.identity)}"


def _link(source_path: str, target_path: str, label: str) -> str:
    return (
        f"[{label}]({posixpath.relpath(target_path, posixpath.dirname(source_path))})"
    )


def _human_link(source_path: str, owner: str, label: str) -> str:
    target = posixpath.join("..", owner)
    return f"[{label}]({posixpath.relpath(target, posixpath.dirname(source_path))}) (human provenance)"


def _make_pages(config: ProjectionConfig, data: _RenderData) -> _Pages:
    thesis = {
        source: _Page(f"thesis-source:{source.as_posix()}", "thesis")
        for source in data.closure
    }
    citations = {key: _Page(f"citation:{key}", "citations") for key in data.bib}
    literature = {
        row.identity: _Page(row.identity, "literature") for row in data.manifest
    }
    code = {identity: _Page(identity, "code") for identity in data.targets}
    assets: dict[str, _Page] = {}
    asset_owners: dict[str, tuple[str, str, str]] = {}
    terms = {key: _Page(f"glossary-term:{key}", "glossary") for key in data.terms}
    symbols = {
        key: _Page(f"symbol:{key}", "symbols") for key in data.notation["symbols"]
    }
    equations = {
        key: _Page(f"equation:{key}", "equations") for key in data.notation["equations"]
    }
    for row in data.manifest:
        for kind, relative in (
            ("tex-root", row.tex_path),
            ("pdf", row.pdf_path),
        ):
            if relative is None:
                continue
            identity = f"{kind}:{relative.as_posix()}"
            assets.setdefault(identity, _Page(identity, "assets"))
            status = (
                "present" if _lexists(config.repo_root / relative) else "missing-local"
            )
            asset_owners[identity] = (relative.as_posix(), status, kind)
    return _Pages(
        thesis=thesis,
        citations=citations,
        literature=literature,
        code=code,
        assets=assets,
        asset_owners=asset_owners,
        terms=terms,
        symbols=symbols,
        equations=equations,
    )


def _page_paths(pages: _Pages) -> dict[str, str]:
    paths: dict[str, str] = {}
    for page in pages.all():
        path = _page_path(page)
        if page.identity in paths or path in paths.values():
            raise ProjectionError(
                f"duplicate generated identity or filename: {page.identity}"
            )
        paths[page.identity] = path
    return paths


def _populate_thesis_pages(
    data: _RenderData, pages: _Pages, paths: Mapping[str, str]
) -> None:
    for source, page in pages.thesis.items():
        source_path = paths[page.identity]
        page.lines.append(
            f"owner: {_human_link(source_path, source.as_posix(), source.as_posix())}"
        )
        for key in sorted(data.citations_by_source[source]):
            page.lines.append(
                f"citation: {_link(source_path, paths[f'citation:{key}'], f'citation:{key}')}"
            )
        for kind, label, identity_prefix in (
            ("term", "uses_term", "glossary-term"),
            ("symbol", "uses_symbol", "symbol"),
            ("equation", "uses_equation", "equation"),
        ):
            for key, count in sorted(
                data.usage_by_source.get(source, {}).get(kind, {}).items()
            ):
                identity = f"{identity_prefix}:{key}"
                page.lines.append(
                    f"{label}: {_link(source_path, paths[identity], identity)}"
                )
                page.lines.append(f"  multiplicity: {count}")
        for relation in data.relations:
            if relation.get("source") != source.as_posix():
                continue
            target = str(relation["target"])
            linked_target = (
                _link(source_path, paths[target], target) if target in paths else target
            )
            page.lines.append(f"relation: {linked_target}")
            for key in (
                "kind",
                "compiled_url",
                "pin_kind",
                "status",
                "line",
                "column",
                "ordinal",
                "multiplicity",
            ):
                if key in relation:
                    page.lines.append(f"  {key}: {relation[key]}")


def _populate_citation_pages(
    data: _RenderData, pages: _Pages, paths: Mapping[str, str]
) -> None:
    for key, page in pages.citations.items():
        source_path = paths[page.identity]
        entry = data.bib[key]
        page.lines.append(
            f"owner: {_human_link(source_path, entry.owner.as_posix(), entry.locator)}"
        )
        if key in data.joined:
            target = data.joined[key].identity
            page.lines.append(
                f"literature: {_link(source_path, paths[target], target)}"
            )
        else:
            page.lines.append("join_status: unmatched")


def _manifest_text_field(
    row: ManifestEntry, field_name: str, *, required: bool = False
) -> str | None:
    value = row.data.get(field_name)
    if value is None and not required:
        return None
    if not isinstance(value, str) or (required and not value.strip()):
        raise ProjectionError(f"manifest line {row.line}: {field_name} must be text")
    if "\n" in value or "\r" in value:
        raise ProjectionError(
            f"manifest line {row.line}: {field_name} must be single-line text"
        )
    return value


def _literature_metadata_lines(row: ManifestEntry) -> list[str]:
    """Render only the factual catalogue fields admitted by the projection."""

    lines = [f"title: {_manifest_text_field(row, 'title', required=True)}"]
    for field_name, output_name in (
        ("short_title", "short_title"),
        ("relevance_category", "relevance_category"),
        ("url", "landing_url"),
    ):
        value = _manifest_text_field(row, field_name)
        if value is not None:
            lines.append(f"{output_name}: {value}")
    rank = row.data.get("relevance_rank")
    if rank is not None:
        if not isinstance(rank, int) or isinstance(rank, bool):
            raise ProjectionError(
                f"manifest line {row.line}: relevance_rank must be an integer"
            )
        lines.append(f"relevance_rank: {rank}")
    ideas = row.data.get("adoptable_ideas")
    if ideas is not None:
        if not isinstance(ideas, list):
            raise ProjectionError(
                f"manifest line {row.line}: adoptable_ideas must be a list of text"
            )
        for idea in ideas:
            if (
                not isinstance(idea, str)
                or not idea.strip()
                or "\n" in idea
                or "\r" in idea
            ):
                raise ProjectionError(
                    f"manifest line {row.line}: adoptable_ideas must contain single-line text"
                )
            lines.append(f"adoptable_idea: {idea}")
    return lines


def _populate_literature_pages(
    config: ProjectionConfig,
    data: _RenderData,
    pages: _Pages,
    paths: Mapping[str, str],
) -> None:
    matched_by_row: dict[str, list[str]] = defaultdict(list)
    for key, row in data.joined.items():
        matched_by_row[row.identity].append(key)
    for row in data.manifest:
        page = pages.literature[row.identity]
        source_path = paths[page.identity]
        page.lines.extend(
            [
                *_literature_metadata_lines(row),
                f"owner: {_human_link(source_path, config.manifest_path.as_posix(), f'{config.manifest_path.as_posix()}:{row.line}')}",
                f"source_locator: {config.manifest_path.as_posix()}:{row.line}",
                f"join_status: {'matched' if matched_by_row[row.identity] else 'unmatched'}",
            ]
        )
        for key in sorted(matched_by_row[row.identity]):
            page.lines.append(
                f"citation: {_link(source_path, paths[f'citation:{key}'], f'citation:{key}')}"
            )
        for kind, relative in (
            ("tex-root", row.tex_path),
            ("pdf", row.pdf_path),
        ):
            if relative:
                identity = f"{kind}:{relative.as_posix()}"
                page.lines.append(
                    f"asset: {_link(source_path, paths[identity], identity)}"
                )


def _populate_fact_pages(
    data: _RenderData, pages: _Pages, paths: Mapping[str, str]
) -> None:
    for identity, facts in data.targets.items():
        owner_label = f"{facts['path']}:{facts['line_range']}"
        pages.code[identity].lines.append(
            f"owner: [{owner_label}]({facts['owner_url']}) (human provenance)"
        )
        pages.code[identity].lines.extend(
            f"{key}: {value}" for key, value in facts.items() if key != "owner_url"
        )
    for identity, page in pages.assets.items():
        source_path = paths[identity]
        owner, status, kind = pages.asset_owners[identity]
        page.lines.extend(
            [
                f"owner: {_human_link(source_path, owner, owner)}",
                f"status: {status}",
                "status_provenance: environment-local-path-presence",
                "page_locator: unavailable"
                if kind == "pdf"
                else "content_parsed: false",
            ]
        )


def _populate_entity_pages(
    config: ProjectionConfig, data: _RenderData, pages: _Pages, paths: Mapping[str, str]
) -> None:
    for key, page in pages.terms.items():
        term = data.terms[key]
        source_path = paths[page.identity]
        page.lines.extend(
            [
                f"label: {term['label']}",
                f"definition: {term['definition_short']}",
                f"owner: {_human_link(source_path, config.glossary_path.as_posix(), config.glossary_path.as_posix())}",
            ]
        )
        if term.get("parent"):
            page.lines.append(f"parent_label: {term['parent']}")
        related = term.get("related", [])
        if not isinstance(related, list):
            raise ProjectionError(f"{key}: related must be a list")
        for target in related:
            if not isinstance(target, str):
                raise ProjectionError(f"{key}: related must contain strings")
            identity = f"glossary-term:{target}"
            page.lines.append(
                f"related: {_link(source_path, paths[identity], identity)}"
            )
        for ref_field, prefix in (
            ("symbol_refs", "symbol"),
            ("equation_refs", "equation"),
            ("citations", "citation"),
        ):
            refs = term.get(ref_field, [])
            if not isinstance(refs, list):
                raise ProjectionError(f"{key}: {ref_field} must be a list")
            for target in refs:
                if not isinstance(target, str):
                    raise ProjectionError(f"{key}: {ref_field} must contain strings")
                identity = f"{prefix}:{target}"
                page.lines.append(
                    f"{ref_field.removesuffix('_refs')}: {_link(source_path, paths[identity], identity)}"
                )
    for group, collection, prefix in (
        ("symbols", pages.symbols, "symbol"),
        ("equations", pages.equations, "equation"),
    ):
        for key, page in collection.items():
            source_path = paths[page.identity]
            entry = data.notation[group][key]
            owner = data.notation_owners[(group, key)]
            page.lines.extend(
                [
                    f"tex: {entry['tex']}",
                    f"typst: {entry['typst']}",
                    f"metadata_owner: {_human_link(source_path, (config.symbols_path if group == 'symbols' else config.equations_path).as_posix(), (config.symbols_path if group == 'symbols' else config.equations_path).as_posix())}",
                    f"implementation_owner: {_human_link(source_path, owner.as_posix(), owner.as_posix())}",
                ]
            )
            if entry.get("description"):
                page.lines.append(f"description: {entry['description']}")


def _owner_paths(config: ProjectionConfig, closure: Sequence[Path]) -> list[Path]:
    return [
        *closure,
        config.style_path,
        *config.bibliography_paths,
        config.manifest_path,
        config.glossary_path,
        config.symbols_path,
        config.equations_path,
    ]


def _asset_inventory_digest(pages: _Pages) -> str:
    inventory = [
        {
            "identity": identity,
            "owner": owner,
            "status": status,
            "kind": kind,
        }
        for identity, (owner, status, kind) in sorted(pages.asset_owners.items())
    ]
    encoded = json.dumps(
        inventory, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _render_index(
    config: ProjectionConfig,
    runner: Runner,
    data: _RenderData,
    pages: _Pages,
    paths: Mapping[str, str],
) -> str:
    owner_paths = [*_owner_paths(config, data.closure), *data.notation_owners.values()]
    owner_rows = []
    for owner in sorted(set(owner_paths), key=lambda path: path.as_posix()):
        digest = hashlib.sha256(_owner_path(config, owner).read_bytes()).hexdigest()
        owner_rows.append(f"- {owner.as_posix()}: sha256:{digest}")
    index = [
        "# graphify-projection:index",
        "",
        "Derived navigation only; exact repository sources remain authoritative.",
        "",
        f"schema_version: {SCHEMA_VERSION}",
        f"source_revision: {data.revision}",
        f"source_tree: {data.source_tree}",
        f"aria_code_ref: {config.aria_code_ref}",
        f"aria_code_ref_source: {config.aria_code_ref_source}",
        f"aria_code_ref_pin_kind: {data.aria_code_pin_kind}",
        f"aria_code_ref_resolved_oid: {data.aria_code_oid}",
        f"owner_worktree_state: {'dirty' if _owners_dirty(config, runner, owner_paths) else 'clean'}",
        "asset_presence_scope: environment-local",
        f"asset_inventory_sha256: {_asset_inventory_digest(pages)}",
        "heading_source_attribution: unavailable",
        f"heading_count: {len(data.headings)}",
        f"entity_count: {len(pages.all())}",
        "errors: 0",
        f"warnings: {len(data.warnings)}",
        "",
        "## Owner digests",
        "",
        *owner_rows,
        "",
        "## Families",
        "",
    ]
    families = Counter(page.family for page in pages.all())
    for family in (
        "thesis",
        "code",
        "citations",
        "literature",
        "assets",
        "glossary",
        "symbols",
        "equations",
    ):
        if families[family]:
            candidates = sorted(
                path for path in paths.values() if path.startswith(f"{family}/")
            )
            index.append(
                f"- {_link('index.md', candidates[0], family)}: {families[family]}"
            )
    index.extend(["", "## Compiled headings", ""])
    for heading in data.headings:
        label = heading.label if heading.label is not None else "unavailable"
        index.append(
            f"- level={heading.level}; text={json.dumps(heading.text, ensure_ascii=False)}; label={label}"
        )
    return "\n".join(index) + "\n"


def _render_pages(
    config: ProjectionConfig,
    runner: Runner,
    data: _RenderData,
) -> dict[str, str]:
    pages = _make_pages(config, data)
    paths = _page_paths(pages)
    _populate_thesis_pages(data, pages, paths)
    _populate_citation_pages(data, pages, paths)
    _populate_literature_pages(config, data, pages, paths)
    _populate_fact_pages(data, pages, paths)
    _populate_entity_pages(config, data, pages, paths)
    files: dict[str, str] = {}
    for page in sorted(pages.all(), key=lambda item: item.identity):
        path = paths[page.identity]
        files[path] = "\n".join([f"# {page.identity}", "", *page.lines, ""]) + "\n"
    files["index.md"] = _render_index(config, runner, data, pages, paths)
    _validate_markdown_links(files)
    return dict(sorted(files.items()))


def _owners_dirty(
    config: ProjectionConfig, runner: Runner, owners: Iterable[Path]
) -> bool:
    paths = [path.as_posix() for path in owners]
    output = _run(
        runner,
        ["git", "status", "--porcelain", "--", *paths],
        config.repo_root,
    )
    return bool(output.strip())


def _validate_markdown_links(files: Mapping[str, str]) -> None:
    for source, body in files.items():
        for target in re.findall(r"\]\(([^)]+\.md)\)", body):
            resolved = posixpath.normpath(
                posixpath.join(posixpath.dirname(source), target)
            )
            if resolved not in files:
                raise ProjectionError(
                    f"generated link from {source} does not resolve: {target}"
                )


def _validate_output(
    config: ProjectionConfig, owners: Iterable[Path]
) -> tuple[Path, Path, Path]:
    relative = _relative_path(config.output_path, label="output")
    if not relative.parts:
        raise ProjectionError("output cannot be the repository root")
    for owner in owners:
        if relative == owner or relative in owner.parents or owner in relative.parents:
            raise ProjectionError(f"output overlaps owner path: {owner.as_posix()}")
    output = config.repo_root / relative
    repository = config.repo_root.resolve()
    if not output.resolve(strict=False).is_relative_to(repository):
        raise ProjectionError("output physically escapes repository")
    cursor = config.repo_root
    for part in relative.parts:
        cursor /= part
        if _lexists(cursor) and cursor.is_symlink():
            raise ProjectionError(f"output path has symlink component: {cursor}")
    temporary = output.parent / f".{output.name}.tmp"
    backup = output.parent / f".{output.name}.backup"
    return output, temporary, backup


def _replace_path(source: Path, destination: Path) -> None:
    """Rename one sibling path; kept injectable for swap-failure tests."""

    source.replace(destination)


def _write_tree(root: Path, files: Mapping[str, str]) -> None:
    root.mkdir(parents=True)
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
    actual = {
        path.relative_to(root).as_posix(): path.read_text(encoding="utf-8")
        for path in root.rglob("*.md")
    }
    if actual != dict(files):
        raise ProjectionError(
            "temporary projection validation did not reproduce rendered bytes"
        )


def _install(
    output: Path, temporary: Path, backup: Path, files: Mapping[str, str]
) -> None:
    for debris in (temporary, backup):
        if debris.is_dir() and not debris.is_symlink():
            shutil.rmtree(debris)
        elif _lexists(debris):
            debris.unlink()
    _write_tree(temporary, files)
    moved_old = False
    try:
        if _lexists(output):
            _replace_path(output, backup)
            moved_old = True
        _replace_path(temporary, output)
    except OSError as error:
        if moved_old and _lexists(backup) and not _lexists(output):
            _replace_path(backup, output)
        if temporary.is_dir():
            shutil.rmtree(temporary)
        raise ProjectionError(
            f"projection swap failed; previous output restored: {error}"
        ) from error
    if backup.is_dir() and not backup.is_symlink():
        shutil.rmtree(backup)
    elif _lexists(backup):
        backup.unlink()


def build_projection(
    config: ProjectionConfig,
    *,
    runner: Runner = _default_runner,
    check: bool = False,
) -> ProjectionResult:
    """Validate canonical owners and optionally replace the generated projection."""

    config = ProjectionConfig(
        **{**config.__dict__, "repo_root": config.repo_root.absolute()}
    )
    closure = _source_closure(config)
    owner_paths = (
        *closure,
        config.style_path,
        *config.bibliography_paths,
        config.manifest_path,
        config.glossary_path,
        config.symbols_path,
        config.equations_path,
    )
    try:
        catalog = load_literature_catalog(
            LiteratureCatalogConfig(
                repo_root=config.repo_root,
                bibliography_paths=config.bibliography_paths,
                manifest_path=config.manifest_path,
                tex_root=config.tex_root,
                pdf_root=config.pdf_root,
            )
        )
    except LiteratureCatalogError as error:
        raise ProjectionError(str(error)) from error
    bib = catalog.bibliography
    terms = _glossary_terms(config, runner, bib)
    try:
        notation = _notation_metadata(config, runner)
    except GlossaryError as error:
        raise ProjectionError(f"notation metadata invalid: {error}") from error
    notation_owners = _notation_owners(config, notation)
    output, temporary, backup = _validate_output(
        config, (*owner_paths, *notation_owners.values())
    )
    warnings = tuple(
        f"stale projection debris: {path.relative_to(config.repo_root).as_posix()}"
        for path in (temporary, backup)
        if _lexists(path)
    )
    usage_by_source = _section_usage(config, closure, terms, notation, bib)
    citations_by_source, macros = _lexical_sources(config, closure, catalog)
    lexical_citations: Counter[str] = Counter()
    for citations in citations_by_source.values():
        lexical_citations.update(citations)
    compiled_cites = _query_typst(config, runner, "cite")
    compiled_links = _query_typst(config, runner, "link")
    compiled_headings = _compiled_headings(_query_typst(config, runner, "heading"))
    with tempfile.TemporaryDirectory(prefix="aria-graphify-verify-") as scratch:
        _compile_typst(config, runner, Path(scratch) / "thesis.pdf")
    compiled_keys = Counter(
        _citation_key(value)
        for row in compiled_cites
        if (value := _compiled_value(row, "key", "citation")) is not None
    )
    missing = sorted(set(compiled_keys) - set(bib))
    if missing:
        raise ProjectionError(
            f"compiled citation absent from bibliographies: {', '.join(missing)}"
        )
    if compiled_keys != lexical_citations:
        differences = ", ".join(
            f"{key}:lexical={lexical_citations[key]},compiled={compiled_keys[key]}"
            for key in sorted(lexical_citations.keys() | compiled_keys.keys())
            if lexical_citations[key] != compiled_keys[key]
        )
        raise ProjectionError(
            f"compiled/lexical citation multiplicity mismatch: {differences}"
        )
    manifest = catalog.manifest
    joined = catalog.joined
    repository = _repository(config)
    link_values = [
        value
        for row in compiled_links
        if (value := _compiled_value(row, "dest", "destination", "url")) is not None
    ]
    targets, relations = _code_targets(config, runner, repository, macros, link_values)
    revision = _run(
        runner,
        ["git", "rev-parse", "--verify", "--end-of-options", "HEAD^{commit}"],
        config.repo_root,
    ).strip()
    source_tree = _run(
        runner,
        [
            "git",
            "rev-parse",
            "--verify",
            "--end-of-options",
            f"{revision}^{{tree}}",
        ],
        config.repo_root,
    ).strip()
    aria_code_oid, aria_code_pin_kind = _resolve_ref(
        config, runner, config.aria_code_ref
    )
    files = _render_pages(
        config,
        runner,
        _RenderData(
            revision=revision,
            source_tree=source_tree,
            aria_code_oid=aria_code_oid,
            aria_code_pin_kind=aria_code_pin_kind,
            closure=closure,
            citations_by_source=citations_by_source,
            bib=bib,
            joined=joined,
            manifest=manifest,
            targets=targets,
            relations=relations,
            headings=compiled_headings,
            warnings=warnings if check else (),
            terms=terms,
            notation=notation,
            notation_owners=notation_owners,
            usage_by_source=usage_by_source,
        ),
    )
    if not check:
        _install(output, temporary, backup, files)
    return ProjectionResult(files=files, warnings=warnings if check else ())


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=Path("graphify-input"))
    parser.add_argument("--aria-code-ref", default="main")
    parser.add_argument("--check", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    args = _parser().parse_args(raw_argv)
    source = (
        "cli"
        if any(
            argument == "--aria-code-ref" or argument.startswith("--aria-code-ref=")
            for argument in raw_argv
        )
        else "default"
    )
    config = ProjectionConfig(
        repo_root=args.repo_root,
        output_path=args.output,
        aria_code_ref=args.aria_code_ref,
        aria_code_ref_source=source,
    )
    try:
        result = build_projection(config, check=args.check)
    except ProjectionError as error:
        print(f"graphify projection: {error}", file=sys.stderr)
        return 1
    action = "validated" if args.check else "built"
    print(f"graphify projection {action}: {len(result.files)} Markdown files")
    for warning in result.warnings:
        print(f"warning: {warning}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
