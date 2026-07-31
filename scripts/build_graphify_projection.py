#!/usr/bin/env python3
"""Build the optional, deterministic Markdown evidence projection for Graphify."""

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
from typing import Callable, Iterable, Mapping, Sequence
from urllib.parse import urlsplit, urlunsplit


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
    bibliography_paths: tuple[Path, ...] = (
        Path("docs/references.bib"),
        Path("docs/references-qh.bib"),
    )
    manifest_path: Path = Path("docs/literature/sources.jsonl")
    tex_root: Path = Path("docs/literature/tex-src")
    pdf_root: Path = Path("docs/literature/pdf")
    output_path: Path = Path("graphify-input")
    aria_code_ref: str = "main"
    aria_code_ref_source: str = "default"


@dataclass(frozen=True)
class ProjectionResult:
    """Rendered relative Markdown files and non-fatal validation warnings."""

    files: Mapping[str, str]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class _BibEntry:
    key: str
    owner: Path
    locator: str
    arxiv: str | None = None
    doi: str | None = None
    url: str | None = None


@dataclass(frozen=True)
class _ManifestEntry:
    line: int
    data: Mapping[str, object]
    identity: str
    arxiv: str | None
    doi: str | None
    url: str | None


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
    return config.repo_root / _relative_path(relative, label="owner")


def _lexists(path: Path) -> bool:
    """Return whether a path or dangling symlink exists without resolving it."""

    return os.path.lexists(path)


def _strip_typst_noncode(text: str) -> str:
    """Blank comments and raw blocks while retaining source line positions."""

    def blank(match: re.Match[str]) -> str:
        return "".join("\n" if char == "\n" else " " for char in match.group(0))

    text = re.sub(r"(?s)```.*?```", blank, text)
    text = re.sub(r"(?s)`[^`]*`", blank, text)
    text = re.sub(r"/\*.*?\*/", blank, text, flags=re.S)
    text = re.sub(r"//[^\n]*", blank, text)
    return text


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
        literal_spans: list[tuple[int, int]] = []
        for match in re.finditer(r'#(?:include|import)\s+"([^"]+)"', clean):
            literal_spans.append(match.span())
            value = match.group(1)
            if value.startswith("@"):
                continue
            include = PurePosixPath(value)
            if include.is_absolute():
                line = clean.count("\n", 0, match.start()) + 1
                raise ProjectionError(
                    f"{relative.as_posix()}:{line}: include escapes repository"
                )
            normalized = posixpath.normpath(
                posixpath.join(relative.parent.as_posix(), include.as_posix())
            )
            if normalized == ".." or normalized.startswith("../"):
                line = clean.count("\n", 0, match.start()) + 1
                raise ProjectionError(
                    f"{relative.as_posix()}:{line}: include escapes repository"
                )
            target = Path(PurePosixPath(normalized))
            pending.append(target)
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
    return tuple(sorted(seen, key=lambda item: item.as_posix()))


def _lexical_sources(
    config: ProjectionConfig,
    closure: Iterable[Path],
    citation_keys: Iterable[str],
) -> tuple[Counter[str], list[_Macro]]:
    citations: Counter[str] = Counter()
    macros: list[_Macro] = []
    macro_re = re.compile(r"#(gh-symbol|gh-wip|gh)\s*\(([^\n)]*)\)")
    citation_alternation = "|".join(
        re.escape(key)
        for key in sorted(citation_keys, key=lambda key: (-len(key), key))
    )
    citation_re = (
        re.compile(rf"(?<![\w])@({citation_alternation})(?![A-Za-z0-9_+-])")
        if citation_alternation
        else None
    )
    for relative in closure:
        clean = _strip_typst_noncode(
            _owner_path(config, relative).read_text(encoding="utf-8")
        )
        citation_text = re.sub(r'#(?:include|import)\s+"[^"]+"[^\n]*', "", clean)
        if citation_re is not None:
            for token in citation_re.findall(citation_text):
                citations[token] += 1
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
    return citations, macros


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


def _normalize_arxiv(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    result = value.strip().casefold()
    result = re.sub(r"^(?:arxiv:|https?://arxiv\.org/(?:abs|pdf)/)", "", result)
    result = re.sub(r"\.pdf$", "", result)
    return re.sub(r"v\d+$", "", result)


def _normalize_doi(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return re.sub(
        r"^(?:doi:|https?://doi\.org/)", "", value.strip(), flags=re.I
    ).casefold()


def _normalize_url(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    parsed = urlsplit(value.strip())
    if not parsed.scheme or not parsed.netloc:
        return value.strip()
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/")
    return urlunsplit(
        (
            parsed.scheme.casefold(),
            parsed.netloc.casefold(),
            path,
            parsed.query,
            parsed.fragment,
        )
    )


def _bib_entries(config: ProjectionConfig) -> dict[str, _BibEntry]:
    entries: dict[str, _BibEntry] = {}
    for owner in config.bibliography_paths:
        text = _owner_path(config, owner).read_text(encoding="utf-8")
        index = 0
        while True:
            start = re.search(r"@[A-Za-z]+\s*[{(]\s*([^,\s]+)\s*,", text[index:])
            if start is None:
                break
            absolute = index + start.start()
            body_start = index + start.end()
            opener = "{" if "{" in start.group(0) else "("
            closer = "}" if opener == "{" else ")"
            depth = 1
            cursor = body_start
            while cursor < len(text) and depth:
                if text[cursor] == opener:
                    depth += 1
                elif text[cursor] == closer:
                    depth -= 1
                cursor += 1
            if depth:
                raise ProjectionError(f"{owner.as_posix()}: malformed BibTeX entry")
            key = start.group(1)
            if key in entries:
                raise ProjectionError(f"duplicate bibliography key {key}")
            body = text[body_start : cursor - 1]
            fields: dict[str, str] = {}
            for name in ("eprint", "arxiv", "doi", "url"):
                match = re.search(
                    rf"(?is)\b{name}\s*=\s*(?:{{([^{{}}]*)}}|\"([^\"]*)\")",
                    body,
                )
                if match:
                    fields[name] = (match.group(1) or match.group(2)).strip()
            line = text.count("\n", 0, absolute) + 1
            entries[key] = _BibEntry(
                key=key,
                owner=owner,
                locator=f"{owner.as_posix()}:{line}",
                arxiv=_normalize_arxiv(fields.get("eprint") or fields.get("arxiv")),
                doi=_normalize_doi(fields.get("doi")),
                url=_normalize_url(fields.get("url")),
            )
            index = cursor
    return entries


def _asset_relative(root: Path, value: object, *, line: int) -> Path | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ProjectionError(f"manifest line {line}: asset path must be a string")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ProjectionError(
            f"manifest line {line}: asset path escapes its root: {value}"
        )
    return Path(PurePosixPath((root / path).as_posix()))


def _manifest_entries(config: ProjectionConfig) -> list[_ManifestEntry]:
    result: list[_ManifestEntry] = []
    text = _owner_path(config, config.manifest_path).read_text(encoding="utf-8")
    for line, raw in enumerate(text.splitlines(), 1):
        if not raw.strip():
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as error:
            raise ProjectionError(
                f"{config.manifest_path.as_posix()}:{line}: invalid JSON"
            ) from error
        if not isinstance(data, dict):
            raise ProjectionError(
                f"{config.manifest_path.as_posix()}:{line}: expected object"
            )
        arxiv = _normalize_arxiv(data.get("arxiv_id") or data.get("arxiv"))
        doi = _normalize_doi(data.get("doi"))
        url = _normalize_url(data.get("url"))
        if arxiv:
            identity = f"literature:arxiv:{arxiv}"
        elif doi:
            identity = f"literature:doi:{doi}"
        elif url:
            identity = f"literature:url:{url}"
        else:
            identity = f"literature:manifest-line:{line}"
        _asset_relative(config.tex_root, data.get("tex_dir"), line=line)
        _asset_relative(config.pdf_root, data.get("pdf_file"), line=line)
        result.append(_ManifestEntry(line, data, identity, arxiv, doi, url))
    identities = [entry.identity for entry in result]
    if len(identities) != len(set(identities)):
        raise ProjectionError("duplicate manifest generated identity")
    return result


def _join_bibliography(
    bib: Mapping[str, _BibEntry], manifest: Sequence[_ManifestEntry]
) -> dict[str, _ManifestEntry]:
    indexes: dict[str, dict[str, list[_ManifestEntry]]] = {
        "arxiv": defaultdict(list),
        "doi": defaultdict(list),
        "url": defaultdict(list),
    }
    for row in manifest:
        for field_name in indexes:
            value = getattr(row, field_name)
            if value:
                indexes[field_name][value].append(row)
    joined: dict[str, _ManifestEntry] = {}
    for key, entry in bib.items():
        signal_matches: list[tuple[str, list[_ManifestEntry]]] = []
        for field_name in ("arxiv", "doi", "url"):
            value = getattr(entry, field_name)
            matches = indexes[field_name].get(value, []) if value else []
            if len(matches) > 1:
                raise ProjectionError(
                    f"ambiguous {field_name} join for bibliography key {key}"
                )
            if matches:
                signal_matches.append((field_name, matches))
        distinct = {
            match.identity for _, matches in signal_matches for match in matches
        }
        if len(distinct) > 1:
            raise ProjectionError(
                f"conflicting identity signals for bibliography key {key}"
            )
        if signal_matches:
            joined[key] = signal_matches[0][1][0]
    return joined


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
    if ref == "main" and pin_kind == "mutable":
        return _run(
            runner, ["git", "rev-parse", "HEAD"], config.repo_root
        ).strip(), pin_kind
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


def _code_targets(
    config: ProjectionConfig,
    runner: Runner,
    repository: str,
    macros: Sequence[_Macro],
    compiled_links: Sequence[str],
) -> tuple[dict[str, dict[str, str]], list[dict[str, object]]]:
    admitted = [
        link
        for link in compiled_links
        if link.startswith(f"https://github.com/{repository}/blob/")
        or link.startswith("https://github.com/search?")
        and f"repo%3A{repository}" in link
    ]
    expected_urls: list[str] = []
    relations: list[dict[str, object]] = []
    targets: dict[str, dict[str, str]] = {}
    head = _run(runner, ["git", "rev-parse", "HEAD"], config.repo_root).strip()
    dirty_output = _run(
        runner, ["git", "status", "--porcelain", "--"], config.repo_root
    )
    dirty_paths = {line[3:] for line in dirty_output.splitlines() if len(line) > 3}
    for macro in macros:
        if macro.kind == "gh-symbol":
            relations.append(
                {
                    "kind": macro.kind,
                    "status": "unresolved-dynamic",
                    "target": macro.target,
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


def _render_pages(
    config: ProjectionConfig,
    runner: Runner,
    revision: str,
    closure: Sequence[Path],
    citations: Counter[str],
    bib: Mapping[str, _BibEntry],
    joined: Mapping[str, _ManifestEntry],
    manifest: Sequence[_ManifestEntry],
    targets: Mapping[str, Mapping[str, str]],
    relations: Sequence[Mapping[str, object]],
    warnings: Sequence[str],
) -> dict[str, str]:
    pages: list[_Page] = []
    thesis_pages = {
        source: _Page(f"thesis-source:{source.as_posix()}", "thesis")
        for source in closure
    }
    pages.extend(thesis_pages.values())
    citation_pages = {key: _Page(f"citation:{key}", "citations") for key in bib}
    pages.extend(citation_pages.values())
    literature_pages = {
        row.identity: _Page(row.identity, "literature") for row in manifest
    }
    pages.extend(literature_pages.values())
    target_pages = {identity: _Page(identity, "code") for identity in targets}
    pages.extend(target_pages.values())
    asset_pages: dict[str, _Page] = {}
    asset_owners: dict[str, tuple[str, str, str]] = {}
    for row in manifest:
        for kind, root, field_name in (
            ("tex-root", config.tex_root, "tex_dir"),
            ("pdf", config.pdf_root, "pdf_file"),
        ):
            relative = _asset_relative(root, row.data.get(field_name), line=row.line)
            if relative is None:
                continue
            identity = f"{kind}:{relative.as_posix()}"
            asset_pages.setdefault(identity, _Page(identity, "assets"))
            status = (
                "present" if _lexists(config.repo_root / relative) else "missing-local"
            )
            asset_owners[identity] = (relative.as_posix(), status, kind)
    pages.extend(asset_pages.values())
    paths: dict[str, str] = {}
    for page in pages:
        path = _page_path(page)
        if page.identity in paths or path in paths.values():
            raise ProjectionError(
                f"duplicate generated identity or filename: {page.identity}"
            )
        paths[page.identity] = path

    for source, page in thesis_pages.items():
        source_path = paths[page.identity]
        page.lines.append(
            f"owner: {_human_link(source_path, source.as_posix(), source.as_posix())}"
        )
        for key in sorted(citations):
            page.lines.append(
                f"citation: {_link(source_path, paths[f'citation:{key}'], f'citation:{key}')}"
            )
        for relation in relations:
            if relation.get("source") != source.as_posix():
                continue
            target = str(relation["target"])
            page.lines.append(
                f"relation: {_link(source_path, paths[target], target) if target in paths else target}"
            )
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
    for key, page in citation_pages.items():
        source_path = paths[page.identity]
        entry = bib[key]
        page.lines.append(
            f"owner: {_human_link(source_path, entry.owner.as_posix(), entry.locator)}"
        )
        if key in joined:
            target = joined[key].identity
            page.lines.append(
                f"literature: {_link(source_path, paths[target], target)}"
            )
        else:
            page.lines.append("join_status: unmatched")
    matched_by_row: dict[str, list[str]] = defaultdict(list)
    for key, row in joined.items():
        matched_by_row[row.identity].append(key)
    for row in manifest:
        page = literature_pages[row.identity]
        source_path = paths[page.identity]
        page.lines.extend(
            [
                f"title: {row.data.get('title', '')}",
                f"owner: {_human_link(source_path, config.manifest_path.as_posix(), f'{config.manifest_path.as_posix()}:{row.line}')}",
                f"join_status: {'matched' if matched_by_row[row.identity] else 'unmatched'}",
            ]
        )
        for key in sorted(matched_by_row[row.identity]):
            page.lines.append(
                f"citation: {_link(source_path, paths[f'citation:{key}'], f'citation:{key}')}"
            )
        for kind, root, field_name in (
            ("tex-root", config.tex_root, "tex_dir"),
            ("pdf", config.pdf_root, "pdf_file"),
        ):
            relative = _asset_relative(root, row.data.get(field_name), line=row.line)
            if relative:
                identity = f"{kind}:{relative.as_posix()}"
                page.lines.append(
                    f"asset: {_link(source_path, paths[identity], identity)}"
                )
    for identity, facts in targets.items():
        target_pages[identity].lines.extend(
            f"{key}: {value}" for key, value in facts.items()
        )
    for identity, page in asset_pages.items():
        source_path = paths[identity]
        owner, status, kind = asset_owners[identity]
        page.lines.extend(
            [
                f"owner: {_human_link(source_path, owner, owner)}",
                f"status: {status}",
                "page_locator: unavailable"
                if kind == "pdf"
                else "content_parsed: false",
            ]
        )

    owner_paths = list(closure) + [
        config.style_path,
        *config.bibliography_paths,
        config.manifest_path,
    ]
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
        f"source_revision: {revision}",
        f"aria_code_ref: {config.aria_code_ref}",
        f"aria_code_ref_source: {config.aria_code_ref_source}",
        f"owner_worktree_state: {'dirty' if _owners_dirty(config, runner, owner_paths) else 'clean'}",
        f"warnings: {len(warnings)}",
        "",
        "## Owner digests",
        "",
        *owner_rows,
        "",
        "## Families",
        "",
    ]
    files: dict[str, str] = {}
    for page in sorted(pages, key=lambda item: item.identity):
        path = paths[page.identity]
        files[path] = "\n".join([f"# {page.identity}", "", *page.lines, ""]) + "\n"
    for family in ("thesis", "code", "citations", "literature", "assets"):
        candidates = sorted(path for path in files if path.startswith(f"{family}/"))
        if candidates:
            index.append(f"- {_link('index.md', candidates[0], family)}")
    files["index.md"] = "\n".join(index) + "\n"
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
    )
    output, temporary, backup = _validate_output(config, owner_paths)
    warnings = tuple(
        f"stale projection debris: {path.relative_to(config.repo_root).as_posix()}"
        for path in (temporary, backup)
        if _lexists(path)
    )
    bib = _bib_entries(config)
    lexical_citations, macros = _lexical_sources(config, closure, bib)
    compiled_cites = _query_typst(config, runner, "cite")
    compiled_links = _query_typst(config, runner, "link")
    _query_typst(config, runner, "heading")
    compile_output = temporary.parent / f".{output.name}.verify.pdf"
    try:
        _compile_typst(config, runner, compile_output)
    finally:
        if _lexists(compile_output):
            compile_output.unlink()
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
    manifest = _manifest_entries(config)
    joined = _join_bibliography(bib, manifest)
    repository = _repository(config)
    link_values = [
        value
        for row in compiled_links
        if (value := _compiled_value(row, "dest", "destination", "url")) is not None
    ]
    targets, relations = _code_targets(config, runner, repository, macros, link_values)
    revision = _run(runner, ["git", "rev-parse", "HEAD"], config.repo_root).strip()
    files = _render_pages(
        config,
        runner,
        revision,
        closure,
        lexical_citations,
        bib,
        joined,
        manifest,
        targets,
        relations,
        warnings,
    )
    if not check:
        _install(output, temporary, backup, files)
    return ProjectionResult(files=files, warnings=warnings)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=Path("graphify-input"))
    parser.add_argument("--aria-code-ref", default="main")
    parser.add_argument("--check", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    source = "cli" if argv and "--aria-code-ref" in argv else "default"
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
