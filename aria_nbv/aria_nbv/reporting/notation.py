"""Presentation-free resolution of canonical Typst notation and glossary IDs.

The canonical definitions remain in ``docs/typst/shared``. This module reads
their generated YAML projections so Python report builders and Streamlit can
validate identifiers and display descriptions without parsing or copying Typst
bodies into report recipes.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml

from ..configs import PathConfig

_GITHUB_SOURCE_ROOT = "https://github.com/JanDuchscherer104/ARIA-NBV/blob/main"


class TheoryResolutionError(ValueError):
    """Raised when a requested canonical equation, symbol, or term is unavailable."""


@dataclass(frozen=True, slots=True)
class TheoryReferences:
    """Stable registry identifiers requested by one explanation or result."""

    equation_ids: tuple[str, ...] = ()
    """Canonical equation identifiers from generated ``docs/notation.yml``."""

    symbol_ids: tuple[str, ...] = ()
    """Canonical symbol identifiers from generated ``docs/notation.yml``."""

    term_ids: tuple[str, ...] = ()
    """Canonical glossary identifiers from generated ``docs/glossary/terms.yml``."""

    def __post_init__(self) -> None:
        for values in (self.equation_ids, self.symbol_ids, self.term_ids):
            if any(not value.strip() for value in values) or len(set(values)) != len(values):
                raise ValueError("Theory reference identifiers must be non-empty and unique.")


@dataclass(frozen=True, slots=True)
class ResolvedNotation:
    """Display projection and canonical owner link for one symbol or equation."""

    identifier: str
    """Canonical registry identifier."""

    kind: Literal["equation", "symbol"]
    """Notation registry family."""

    tex: str
    """Generated TeX projection for math-capable Python surfaces."""

    typst: str
    """Reference to the canonical Typst facade."""

    description: str | None
    """Generated human-readable description."""

    source_url: str
    """Browser-valid link to the canonical Typst owner."""


@dataclass(frozen=True, slots=True)
class ResolvedTerm:
    """Display projection and canonical owner link for one glossary term."""

    identifier: str
    """Requested canonical or supported alias identifier."""

    label: str
    """Human-readable canonical label."""

    short: str | None
    """Optional abbreviation."""

    definition: str
    """Generated long or short definition."""

    source_url: str
    """Browser-valid link to the canonical glossary owner."""


@dataclass(frozen=True, slots=True)
class ResolvedTheory:
    """Resolved equation, symbol, and glossary projections for one request."""

    equations: tuple[ResolvedNotation, ...]
    """Equations in requested order."""

    symbols: tuple[ResolvedNotation, ...]
    """Symbols in requested order."""

    terms: tuple[ResolvedTerm, ...]
    """Glossary terms in requested order."""


def resolve_theory(references: TheoryReferences, *, root: Path | None = None) -> ResolvedTheory:
    """Resolve canonical generated notation without parsing Typst at runtime."""

    resolved_root = (root or PathConfig().root).expanduser().resolve()
    notation_path = resolved_root / "docs" / "notation.yml"
    terms_path = resolved_root / "docs" / "glossary" / "terms.yml"
    notation, term_map = _load_registry(
        notation_path.as_posix(),
        *_file_identity(notation_path),
        terms_path.as_posix(),
        *_file_identity(terms_path),
    )
    equations = notation.get("equations", {})
    symbols = notation.get("symbols", {})
    return ResolvedTheory(
        equations=tuple(_notation_row(equations, identifier, "equation") for identifier in references.equation_ids),
        symbols=tuple(_notation_row(symbols, identifier, "symbol") for identifier in references.symbol_ids),
        terms=tuple(_term_row(term_map, identifier) for identifier in references.term_ids),
    )


def validate_theory_registry(references: TheoryReferences, *, root: Path | None = None) -> None:
    """Fail unless every requested identifier resolves through generated owners."""

    resolve_theory(references, root=root)


def notation_sha256(*, root: Path | None = None) -> str:
    """Return the content digest of the generated canonical notation projection."""

    resolved_root = (root or PathConfig().root).expanduser().resolve()
    return hashlib.sha256((resolved_root / "docs" / "notation.yml").read_bytes()).hexdigest()


def _notation_row(
    registry: dict[str, Any],
    identifier: str,
    kind: Literal["equation", "symbol"],
) -> ResolvedNotation:
    row = registry.get(identifier)
    if not isinstance(row, dict) or not row.get("tex"):
        raise TheoryResolutionError(f"unknown canonical {kind}: {identifier}")
    typst = str(row.get("typst", ""))
    return ResolvedNotation(
        identifier=identifier,
        kind=kind,
        tex=str(row["tex"]),
        typst=typst,
        description=row.get("description"),
        source_url=_notation_source_url(identifier, typst, kind=kind),
    )


def _notation_source_url(identifier: str, typst: str, *, kind: Literal["equation", "symbol"]) -> str:
    prefix = "#eqs." if kind == "equation" else "#symb."
    expected = f"{prefix}{identifier}"
    if typst != expected:
        raise TheoryResolutionError(f"canonical {kind} {identifier!r} has unsupported Typst reference {typst!r}")
    module = identifier.split(".", 1)[0]
    directory = "equations" if kind == "equation" else "symbols"
    return f"{_GITHUB_SOURCE_ROOT}/docs/typst/shared/{directory}/{module}.typ"


def _term_row(registry: dict[str, dict[str, Any]], identifier: str) -> ResolvedTerm:
    aliases = {"target-rri-reward": "target-specific-rri", "finite-horizon-return": "target-specific-rri"}
    row = registry.get(aliases.get(identifier, identifier))
    if row is None:
        raise TheoryResolutionError(f"unknown canonical glossary term: {identifier}")
    return ResolvedTerm(
        identifier=identifier,
        label=str(row.get("label", identifier)),
        short=row.get("short"),
        definition=str(row.get("definition_long") or row.get("definition_short") or ""),
        source_url=f"{_GITHUB_SOURCE_ROOT}/docs/typst/shared/glossary.typ",
    )


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
    notation = _load_yaml(Path(notation_path_raw))
    raw_terms = _load_yaml(Path(terms_path_raw))
    if not isinstance(notation, dict):
        raise TheoryResolutionError(f"canonical theory registry must be a mapping: {notation_path_raw}")
    if not isinstance(raw_terms, list):
        raise TheoryResolutionError(f"canonical theory glossary must be a list: {terms_path_raw}")
    terms: dict[str, dict[str, Any]] = {}
    for row in raw_terms:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            raise TheoryResolutionError(f"canonical theory glossary contains an invalid term row: {terms_path_raw}")
        identifier = row["id"]
        if identifier in terms:
            raise TheoryResolutionError(f"canonical theory glossary repeats term {identifier!r}")
        terms[identifier] = row
    return notation, terms


def _load_yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise TheoryResolutionError(f"cannot load canonical theory metadata from {path}: {exc}") from exc


__all__ = [
    "ResolvedNotation",
    "ResolvedTerm",
    "ResolvedTheory",
    "TheoryReferences",
    "TheoryResolutionError",
    "notation_sha256",
    "resolve_theory",
    "validate_theory_registry",
]
