"""Resolve stored-rollout theory references from canonical documentation."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml

from ....configs import PathConfig

_GITHUB_SOURCE_ROOT = "https://github.com/JanDuchscherer104/ARIA-NBV/blob/main"


class TheoryResolutionError(ValueError):
    """Report unavailable or inconsistent canonical theory metadata."""


@dataclass(frozen=True, slots=True)
class TheoryReferences:
    """Stable documentation identifiers requested by one explanation."""

    equation_ids: tuple[str, ...] = ()
    symbol_ids: tuple[str, ...] = ()
    term_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for identifiers in (self.equation_ids, self.symbol_ids, self.term_ids):
            if any(not identifier.strip() for identifier in identifiers):
                raise ValueError("Theory reference identifiers must be non-empty.")
            if len(set(identifiers)) != len(identifiers):
                raise ValueError("Theory reference identifiers must be unique within each category.")


@dataclass(frozen=True, slots=True)
class ResolvedNotation:
    """One equation or symbol resolved from the notation registry."""

    identifier: str
    kind: Literal["equation", "symbol"]
    tex: str
    typst: str
    description: str | None
    source_url: str


@dataclass(frozen=True, slots=True)
class ResolvedTerm:
    """One generated glossary term used by a scientific explanation."""

    identifier: str
    label: str
    short: str | None
    definition: str
    source_url: str


@dataclass(frozen=True, slots=True)
class ResolvedTheory:
    """Canonical theory material ready for presentation."""

    equations: tuple[ResolvedNotation, ...]
    symbols: tuple[ResolvedNotation, ...]
    terms: tuple[ResolvedTerm, ...]


def resolve_theory(references: TheoryReferences, *, root: Path | None = None) -> ResolvedTheory:
    """Resolve stable theory identifiers without parsing Typst at runtime."""

    repository_root = (root or PathConfig().root).expanduser().resolve()
    notation_path = repository_root / "docs" / "notation.yml"
    terms_path = repository_root / "docs" / "glossary" / "terms.yml"
    notation_identity = _file_identity(notation_path)
    terms_identity = _file_identity(terms_path)
    notation, terms = _load_registry(
        notation_path.as_posix(),
        *notation_identity,
        terms_path.as_posix(),
        *terms_identity,
    )
    return ResolvedTheory(
        equations=tuple(
            _resolve_notation(notation, "equations", identifier, kind="equation")
            for identifier in references.equation_ids
        ),
        symbols=tuple(
            _resolve_notation(notation, "symbols", identifier, kind="symbol") for identifier in references.symbol_ids
        ),
        terms=tuple(_resolve_term(terms, identifier) for identifier in references.term_ids),
    )


def validate_theory_registry(references: TheoryReferences, *, root: Path | None = None) -> None:
    """Fail closed when any requested canonical theory identifier is unavailable."""

    resolve_theory(references, root=root)


def _file_identity(path: Path) -> tuple[int, int, str]:
    try:
        stat = path.stat()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise TheoryResolutionError(f"canonical theory file is unavailable: {path}") from exc
    return stat.st_mtime_ns, stat.st_size, digest


@lru_cache(maxsize=8)
def _load_registry(
    notation_path_raw: str,
    _notation_mtime_ns: int,
    _notation_size: int,
    _notation_sha256: str,
    terms_path_raw: str,
    _terms_mtime_ns: int,
    _terms_size: int,
    _terms_sha256: str,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    notation_path = Path(notation_path_raw)
    terms_path = Path(terms_path_raw)
    notation = _load_yaml(notation_path)
    raw_terms = _load_yaml(terms_path)
    if not isinstance(notation, dict):
        raise TheoryResolutionError(f"canonical theory registry must be a mapping: {notation_path}")
    if not isinstance(raw_terms, list):
        raise TheoryResolutionError(f"canonical theory glossary must be a list: {terms_path}")
    terms: dict[str, dict[str, Any]] = {}
    for row in raw_terms:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            raise TheoryResolutionError(f"canonical theory glossary contains an invalid term row: {terms_path}")
        identifier = row["id"]
        if identifier in terms:
            raise TheoryResolutionError(f"canonical theory glossary repeats term {identifier!r}")
        terms[identifier] = row
    return notation, terms


def _load_yaml(path: Path) -> object:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise TheoryResolutionError(f"cannot load canonical theory metadata from {path}: {exc}") from exc


def _resolve_notation(
    notation: dict[str, Any],
    group_name: Literal["equations", "symbols"],
    identifier: str,
    *,
    kind: Literal["equation", "symbol"],
) -> ResolvedNotation:
    group = notation.get(group_name)
    if not isinstance(group, dict):
        raise TheoryResolutionError(f"canonical theory registry has no {group_name!r} mapping")
    entry = group.get(identifier)
    if not isinstance(entry, dict):
        raise TheoryResolutionError(f"canonical theory {kind} {identifier!r} is unavailable")
    tex = entry.get("tex")
    typst = entry.get("typst")
    description = entry.get("description")
    if not isinstance(tex, str) or not tex.strip() or not isinstance(typst, str) or not typst.strip():
        raise TheoryResolutionError(f"canonical theory {kind} {identifier!r} is malformed")
    if description is not None and (not isinstance(description, str) or not description.strip()):
        raise TheoryResolutionError(f"canonical theory {kind} {identifier!r} has an invalid description")
    return ResolvedNotation(
        identifier=identifier,
        kind=kind,
        tex=tex.strip(),
        typst=typst.strip(),
        description=None if description is None else description.strip(),
        source_url=_notation_source_url(identifier, typst.strip(), kind=kind),
    )


def _resolve_term(terms: dict[str, dict[str, Any]], identifier: str) -> ResolvedTerm:
    entry = terms.get(identifier)
    if entry is None:
        raise TheoryResolutionError(f"canonical theory glossary term {identifier!r} is unavailable")
    label = entry.get("label")
    short = entry.get("short")
    definition = entry.get("definition_short")
    if not isinstance(label, str) or not label.strip() or not isinstance(definition, str) or not definition.strip():
        raise TheoryResolutionError(f"canonical theory glossary term {identifier!r} is malformed")
    if short is not None and (not isinstance(short, str) or not short.strip()):
        raise TheoryResolutionError(f"canonical theory glossary term {identifier!r} has an invalid short label")
    return ResolvedTerm(
        identifier=identifier,
        label=label.strip(),
        short=None if short is None else short.strip(),
        definition=definition.strip(),
        source_url=f"{_GITHUB_SOURCE_ROOT}/docs/typst/shared/glossary.typ",
    )


def _notation_source_url(
    identifier: str,
    typst: str,
    *,
    kind: Literal["equation", "symbol"],
) -> str:
    expected_prefix = "#eqs." if kind == "equation" else "#symb."
    if not typst.startswith(expected_prefix):
        raise TheoryResolutionError(f"canonical theory {kind} {identifier!r} has an unsupported Typst reference")
    module = typst.removeprefix(expected_prefix).split(".", maxsplit=1)[0]
    if not module:
        raise TheoryResolutionError(f"canonical theory {kind} {identifier!r} has no Typst module")
    directory = "equations" if kind == "equation" else "symbols"
    return f"{_GITHUB_SOURCE_ROOT}/docs/typst/shared/{directory}/{module}.typ"
