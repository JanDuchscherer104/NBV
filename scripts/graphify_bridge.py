from __future__ import annotations

import hashlib
import keyword
import os
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

_SUPPORTED = {".typ", ".tex", ".bib"}
_MARKERS = """archive_note conflict_todo decision_todo impl_todo prune_todo
question_todo research_todo thesis_status validation_todo""".split()
_TYP_IMPORT = re.compile(r'^\s*#(?:include|import)\s+"([^"]+)"')
_HEADING = re.compile(r"^\s*(=+)\s+(.+?)\s*$")
_LET = re.compile(r"^\s*#let\s+([\w-]+)")
_LET_DICT = re.compile(r"^\s*#let\s+([\w-]+)\s*=\s*\(\s*$")
_DICT_KEY = re.compile(r"^\s*([\w-]+)\s*:")
_REF = re.compile(r"\b(symb|eqs)\.([\w-]+)\.([\w-]+)\b")
_CITE = re.compile(r"(?<![\w\\])@([A-Za-z0-9][\w:.-]*)")
_MARKER = re.compile(r"#(" + "|".join(sorted(_MARKERS)) + r")\s*\(")
_CODE_PATH = re.compile(r"(?<![\w/])(aria_nbv/aria_nbv/[\w./-]+\.py)\b")
_CODE_DOTTED = re.compile(r"(?<![\w/])(aria_nbv(?:\.[A-Za-z_]\w*)+)\b")
_TEX_IMPORT = re.compile(r"\\(?:input|include)\s*\{([^}]+)\}")
_TEX_SECTION = re.compile(r"\\(subsubsection|subsection|section)\*?\s*\{([^}]*)\}")
_TEX_LABEL = re.compile(r"\\label\s*\{([^}]+)\}")
_BIB_ENTRY = re.compile(r"@([A-Za-z]+)\s*\{\s*([^,\s]+)\s*,", re.IGNORECASE)
_BIB_EPRINT = re.compile(r"\beprint\s*=\s*[{\"]([^}\"]+)[}\"]", re.IGNORECASE)
_TERM_KEY = re.compile(r'^\s*key\s*:\s*"([^"]+)"', re.MULTILINE)
Events = list[tuple[int, str]]
PaperNodes = Mapping[PurePosixPath, Iterable[str]]


@dataclass(frozen=True)
class BridgeResult:
    output_paths: tuple[Path, ...]
    line_map: dict[Path, dict[int, tuple[str, int]]]


@dataclass(frozen=True)
class _Source:
    path: PurePosixPath
    text: str


class _Parser:
    def __init__(self, source: _Source) -> None:
        self.source = source
        anchor = f"source_{_identifier(source.path.stem)}"
        self.lines: list[tuple[int, str]] = [(1, f"def {anchor}(): pass")]
        self.definitions: set[str] = {anchor}
        self.occurrences: dict[tuple[str, int], int] = {}

    def add(self, line: int, *text: str) -> None:
        self.lines.extend((line, item) for item in text)

    def _reserve(self, name: str) -> None:
        if name in self.definitions:
            raise ValueError(f"duplicate generated node in {self.source.path}: {name}")
        self.definitions.add(name)

    def define(self, line: int, name: str) -> str:
        self._reserve(name)
        self.add(line, f"def {name}(): pass")
        return name

    def function(self, line: int, name: str, calls: Iterable[str]) -> str:
        self._reserve(name)
        body = tuple(f"    {call}()" for call in calls) or ("    pass",)
        self.add(line, f"def {name}():", *body)
        return name

    def occurrence(self, kind: str, line: int, value: str = "") -> str:
        key = (kind, line)
        ordinal = self.occurrences.get(key, 0) + 1
        self.occurrences[key] = ordinal
        digest = hashlib.sha1(value.encode()).hexdigest()[:8] if value else ""
        tail = f"_{_identifier(value)[:32]}_{digest}" if value else ""
        return f"{_identifier(kind)}_L{line}_{ordinal}{tail}"

    def code_refs(self, line: str, number: int) -> None:
        seen: set[str] = set()
        for path in _CODE_PATH.findall(line):
            reference = path[len("aria_nbv/") : -3].replace("/", ".")
            seen.add(reference)
            node = self.occurrence("code_reference", number, reference)
            alias = node + "_module"
            self.add(number, f"import {reference} as {alias}")
            self.function(number, node, (alias,))
        for reference in _CODE_DOTTED.findall(line):
            if reference in seen:
                continue
            parts = reference.split(".")
            symbol = next(
                (
                    index
                    for index, part in enumerate(parts[1:], 1)
                    if part[:1].isupper()
                ),
                None,
            )
            node = self.occurrence("code_reference", number, reference)
            alias = node + "_object"
            import_line = f"import {reference} as {alias}"
            if symbol is not None:
                module = ".".join(parts[:symbol])
                import_line = f"from {module} import {parts[symbol]} as {alias}"
            self.add(number, import_line)
            self.function(number, node, (alias,))

    def typ_events(
        self,
        paths: set[PurePosixPath],
        citations: Mapping[str, PurePosixPath],
        terms: Mapping[str, PurePosixPath],
        paper_nodes: PaperNodes,
    ) -> Events:
        lines, dictionary = self.source.text.splitlines(), None
        for node in paper_nodes.get(self.source.path, ()):
            self.define(1, node)
        for number, line in enumerate(lines, 1):
            imported = _TYP_IMPORT.match(line)
            if imported and not imported.group(1).startswith("@"):
                target = _resolve(self.source.path, imported.group(1), paths)
                self.add(number, _import(self.source.path, target))
            if heading := _HEADING.match(line):
                title = re.sub(r"<[^>]+>\s*$", "", heading.group(2)).strip()
                kind = f"heading_{len(heading.group(1))}"
                self.define(number, self.occurrence(kind, number, title))
            if let := _LET.match(line):
                self.define(number, self.occurrence("let", number, let.group(1)))
            if started := _LET_DICT.match(line):
                dictionary = _identifier(started.group(1))
            elif dictionary and re.match(r"^\s*\)\s*$", line):
                dictionary = None
            elif dictionary and (key := _DICT_KEY.match(line)):
                prefixes = {"symbols": "symb", "equations": "eqs"}
                prefix = prefixes.get(self.source.path.parent.name)
                owner = f"{prefix}_{self.source.path.stem}" if prefix else dictionary
                self.define(number, f"{owner}_{_identifier(key.group(1))}")
            if self.source.path.stem.startswith("glossary") and (
                term := _TERM_KEY.match(line)
            ):
                self.define(number, f"term_{_identifier(term.group(1))}")
            for root, group, key in _REF.findall(line):
                name = f"{_identifier(root)}_{_identifier(group)}_{_identifier(key)}"
                use = self.occurrence(f"{root}_use", number, f"{group}.{key}")
                self.function(number, use, (name,))
            for match in _MARKER.finditer(line):
                arguments = _call_text(lines, number - 1, match.start())
                called = [
                    self.define(
                        number, self.occurrence(f"marker_{field}", number, value)
                    )
                    for field in ("implementation", "evidence", "source", "gate")
                    if (value := _literal(arguments, field)) is not None
                ]
                name = self.occurrence(f"marker_{match.group(1)}", number)
                self.function(number, name, called)
            if not (imported and imported.group(1).startswith("@")):
                for key in _CITE.findall(line):
                    term_key = key.partition(":")[0]
                    if term_key in terms:
                        target = terms[term_key]
                        name, kind = f"term_{_identifier(term_key)}", "term_use"
                    elif key in citations:
                        target = citations[key]
                        name, kind = f"citation_{_identifier(key)}", "citation_use"
                    else:
                        continue
                    self.add(number, _import(self.source.path, target, name))
                    self.function(number, self.occurrence(kind, number, key), (name,))
            self.code_refs(line, number)
        return self.lines

    def non_typ_events(
        self,
        paths: set[PurePosixPath],
        paper_nodes: PaperNodes,
        bib_entries: list[tuple[int, str, str | None]],
        papers: Mapping[str, tuple[PurePosixPath, str]],
    ) -> Events:
        for node in paper_nodes.get(self.source.path, ()):
            self.define(1, node)
        if self.source.path.suffix.lower() == ".tex":
            for number, line in enumerate(self.source.text.splitlines(), 1):
                for value in _TEX_IMPORT.findall(line):
                    target = _resolve(self.source.path, value.strip(), paths)
                    self.add(number, _import(self.source.path, target))
                for level, title in _TEX_SECTION.findall(line):
                    self.define(number, self.occurrence(level, number, title))
                for label in _TEX_LABEL.findall(line):
                    self.define(number, self.occurrence("label", number, label))
                self.code_refs(line, number)
            return self.lines
        for number, key, arxiv in bib_entries:
            self.define(number, f"citation_{_identifier(key)}")
            if arxiv and arxiv in papers:
                target, paper_node = papers[arxiv]
                self.add(number, _import(self.source.path, target, paper_node))
                name = self.occurrence("arxiv_match", number, arxiv)
                self.function(number, name, (paper_node,))
        return self.lines


def _identifier(value: Any) -> str:
    name = re.sub(r"\W+", "_", str(value), flags=re.UNICODE).strip("_") or "item"
    if name[0].isdigit():
        name = "_" + name
    return name + "_" if keyword.iskeyword(name) else name


def _source(item: Any) -> _Source:
    if isinstance(item, Mapping):
        raw_path, text = item["path"], item["text"]
    else:
        raw_path, text = item.path, item.text
    path = PurePosixPath(str(raw_path).replace("\\", "/"))
    if path.is_absolute() or not path.name or ".." in path.parts:
        raise ValueError(f"source path must be repo-relative: {raw_path!r}")
    if path.suffix.lower() not in _SUPPORTED:
        raise ValueError(f"unsupported source suffix: {path.suffix or '<none>'}")
    if not isinstance(text, str):
        raise TypeError(f"source text must be str: {path}")
    return _Source(path, text)


def _resolve(
    owner: PurePosixPath, value: str, paths: set[PurePosixPath]
) -> PurePosixPath:
    raw = PurePosixPath(value)
    if raw.is_absolute() or value.startswith("@"):
        raise ValueError(f"unsupported relative include in {owner}: {value}")
    joined = PurePosixPath(os.path.normpath(str(owner.parent / raw)))
    candidates = (
        joined,
        joined.with_suffix(owner.suffix) if not joined.suffix else joined,
    )
    if target := next(
        (candidate for candidate in candidates if candidate in paths), None
    ):
        return target
    raise ValueError(f"unresolved relative include in {owner}: {value}")


def _import(owner: PurePosixPath, target: PurePosixPath, name: str = "*") -> str:
    relative = PurePosixPath(
        os.path.relpath(str(target.with_suffix("")), str(owner.parent))
    )
    parts = list(relative.parts)
    parents = 0
    while parts and parts[0] == "..":
        parents += 1
        parts.pop(0)
    module = ".".join(_identifier(part) for part in parts)
    return f"from {'.' * (parents + 1)}{module} import {name}"


def _call_text(lines: list[str], start: int, column: int) -> str:
    text = "\n".join(lines[start:])
    begin = text.find("(", column)
    depth, quote, escaped = 0, None, False
    for index in range(begin, len(text)):
        char = text[index]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
        elif char in "\"'":
            quote = char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return text[begin + 1 : index]
    raise ValueError(f"unterminated marker call at line {start + 1}")


def _literal(text: str, name: str) -> str | None:
    match = re.search(
        rf"\b{re.escape(name)}\s*:\s*(\"(?:\\.|[^\"])*\"|\[(?:[^\[\]]|\[[^\]]*\])*\])",
        text,
        re.DOTALL,
    )
    if match is None:
        return None
    value = match.group(1)
    return (
        bytes(value[1:-1], "utf-8").decode("unicode_escape")
        if value.startswith('"')
        else re.sub(r"\s+", " ", value[1:-1]).strip()
    )


def _bib_entries(source: _Source) -> list[tuple[int, str, str | None]]:
    lines, entries, index = source.text.splitlines(), [], 0
    while index < len(lines):
        match = _BIB_ENTRY.search(lines[index])
        if not match or match.group(1).lower() in {"string", "comment", "preamble"}:
            index += 1
            continue
        depth, end = lines[index].count("{") - lines[index].count("}"), index
        while depth > 0 and end + 1 < len(lines):
            end += 1
            depth += lines[end].count("{") - lines[end].count("}")
        eprint = _BIB_EPRINT.search("\n".join(lines[index : end + 1]))
        entries.append(
            (index + 1, match.group(2), eprint.group(1).strip() if eprint else None)
        )
        index = end + 1
    return entries


def _unique_index(
    values: Iterable[tuple[str, PurePosixPath]], kind: str
) -> dict[str, PurePosixPath]:
    result: dict[str, PurePosixPath] = {}
    normalized: set[str] = set()
    for key, path in values:
        identifier = _identifier(key)
        if key in result or identifier in normalized:
            raise ValueError(f"duplicate {kind} key: {key}")
        result[key] = path
        normalized.add(identifier)
    return result


def materialize(
    sources: Iterable[Any],
    destination: str | os.PathLike[str],
    *,
    paper_by_arxiv: Mapping[str, Any] | None = None,
) -> BridgeResult:
    parsed = [_source(item) for item in sources]
    if not parsed:
        raise ValueError("empty conversion")
    for source in parsed:
        if not source.text.strip():
            raise ValueError(f"empty conversion: {source.path}")
    paths = {source.path for source in parsed}
    if len(paths) != len(parsed):
        raise ValueError("duplicate source path")
    outputs = {source.path.with_suffix(".py") for source in parsed}
    if len(outputs) != len(parsed):
        raise ValueError("duplicate output path")
    papers: dict[str, tuple[PurePosixPath, str]] = {}
    paper_nodes: dict[PurePosixPath, list[str]] = {}
    for arxiv, value in sorted(
        (paper_by_arxiv or {}).items(), key=lambda item: str(item[0])
    ):
        target = PurePosixPath(str(value).replace("\\", "/"))
        if target not in paths:
            raise ValueError(f"unresolved paper module for arXiv {arxiv}: {target}")
        node = f"paper_arxiv_{_identifier(arxiv)}"
        papers[str(arxiv)] = (target, node)
        paper_nodes.setdefault(target, []).append(node)
    bib_data = {
        source.path: _bib_entries(source)
        for source in parsed
        if source.path.suffix.lower() == ".bib"
    }
    citations = _unique_index(
        ((key, path) for path, entries in bib_data.items() for _, key, _ in entries),
        "BibTeX",
    )
    terms = _unique_index(
        (
            (key, source.path)
            for source in parsed
            if source.path.suffix.lower() == ".typ"
            and source.path.stem.startswith("glossary")
            for key in _TERM_KEY.findall(source.text)
        ),
        "glossary",
    )
    root, result_paths, line_map = Path(destination), [], {}
    for source in sorted(parsed, key=lambda item: str(item.path)):
        suffix = source.path.suffix.lower()
        parser = _Parser(source)
        if suffix == ".typ":
            events = parser.typ_events(paths, citations, terms, paper_nodes)
        else:
            events = parser.non_typ_events(
                paths, paper_nodes, bib_data.get(source.path, []), papers
            )
        relative = source.path.with_suffix(".py")
        output = root.joinpath(*relative.parts)
        output.parent.mkdir(parents=True, exist_ok=True)
        rendered: list[str] = []
        mapped: dict[int, tuple[str, int]] = {}
        for original, block in events:
            for line in block.splitlines():
                rendered.append(line)
                mapped[len(rendered)] = (str(source.path), original)
        output.write_text("\n".join(rendered) + "\n", encoding="utf-8")
        result_paths.append(output)
        line_map[output] = mapped
    return BridgeResult(tuple(result_paths), line_map)
