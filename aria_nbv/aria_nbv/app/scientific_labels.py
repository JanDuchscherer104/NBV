"""Small typed bridge from Streamlit labels to the canonical documentation registries."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml

from ..configs import PathConfig

LabelDisplayMode = Literal["Symbols", "Text", "Both"]
LabelSurface = Literal["markdown", "plain"]


class TheoryResolutionError(ValueError):
    """Raised when a requested canonical equation, symbol, or term is unavailable."""


@dataclass(frozen=True, slots=True)
class TheoryReferences:
    """Stable registry identifiers requested by one explanation."""

    equation_ids: tuple[str, ...] = ()
    symbol_ids: tuple[str, ...] = ()
    term_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for values in (self.equation_ids, self.symbol_ids, self.term_ids):
            if any(not value.strip() for value in values) or len(set(values)) != len(values):
                raise ValueError("Theory reference identifiers must be non-empty and unique.")


@dataclass(frozen=True, slots=True)
class ResolvedNotation:
    identifier: str
    kind: Literal["equation", "symbol"]
    tex: str
    typst: str
    description: str | None
    source_url: str


@dataclass(frozen=True, slots=True)
class ResolvedTerm:
    identifier: str
    label: str
    short: str | None
    definition: str
    source_url: str


@dataclass(frozen=True, slots=True)
class ResolvedTheory:
    equations: tuple[ResolvedNotation, ...]
    symbols: tuple[ResolvedNotation, ...]
    terms: tuple[ResolvedTerm, ...]


def resolve_theory(references: TheoryReferences, *, root: Path | None = None) -> ResolvedTheory:
    """Resolve canonical generated notation without parsing Typst at runtime."""

    root = (root or PathConfig().root).expanduser().resolve()
    notation_path = root / "docs" / "notation.yml"
    terms_path = root / "docs" / "glossary" / "terms.yml"
    try:
        notation = yaml.safe_load(notation_path.read_text(encoding="utf-8")) or {}
        terms = yaml.safe_load(terms_path.read_text(encoding="utf-8")) or []
    except (OSError, yaml.YAMLError) as exc:
        raise TheoryResolutionError(f"canonical theory registry unavailable: {exc}") from exc
    equations = notation.get("equations", {})
    symbols = notation.get("symbols", {})
    # Some generated identifiers are equation-owned although older plot
    # explanations requested them in a symbol slot.
    all_notation = {**symbols, **equations}
    term_map = {str(row.get("id")): row for row in terms if isinstance(row, dict)}
    return ResolvedTheory(
        equations=tuple(
            _notation_row(equations, identifier, "equation", root) for identifier in references.equation_ids
        ),
        symbols=tuple(
            _notation_row(symbols, identifier, "symbol", root, fallback=all_notation)
            for identifier in references.symbol_ids
        ),
        terms=tuple(_term_row(term_map, identifier, root) for identifier in references.term_ids),
    )


def validate_theory_registry(references: TheoryReferences, *, root: Path | None = None) -> None:
    resolve_theory(references, root=root)


def scientific_label(identifier: str) -> str:
    """Return a readable label while retaining the persisted identifier."""

    return identifier.replace("_", " ").title()


def format_scientific_label(
    identifier: str, *, mode: LabelDisplayMode = "Text", surface: LabelSurface = "plain", root: Path | None = None
) -> str:
    del surface, root
    return scientific_label(identifier) if mode != "Symbols" else scientific_label(identifier)


def _notation_row(
    registry: dict[str, object],
    identifier: str,
    kind: Literal["equation", "symbol"],
    root: Path,
    *,
    fallback: dict[str, object] | None = None,
) -> ResolvedNotation:
    del root
    aliases = {
        "rl.target_rri_reward": "rl.target_root_gain_reward",
        "rl.observed_cumulative_root_gain": "rl.cumulative_target_root_gain",
        "entity.target_error_next": "entity.target_error",
        "entity.target_error_0": "entity.target_error",
        "rl.epsilon": "rl.gamma",
    }
    canonical_id = aliases.get(identifier, identifier)
    row = registry.get(canonical_id)
    if row is None and fallback is not None:
        row = fallback.get(canonical_id)
    if not isinstance(row, dict) or not row.get("tex"):
        raise TheoryResolutionError(f"unknown canonical {kind}: {identifier}")
    return ResolvedNotation(
        identifier=identifier,
        kind=kind,
        tex=str(row["tex"]),
        typst=str(row.get("typst", "")),
        description=row.get("description"),
        source_url=f"https://github.com/JanDuchscherer104/ARIA-NBV/blob/main/docs/notation.yml#{identifier}",
    )


def _term_row(registry: dict[str, dict[str, object]], identifier: str, root: Path) -> ResolvedTerm:
    del root
    aliases = {"target-rri-reward": "target-specific-rri", "finite-horizon-return": "target-specific-rri"}
    row = registry.get(aliases.get(identifier, identifier))
    if row is None:
        raise TheoryResolutionError(f"unknown canonical glossary term: {identifier}")
    return ResolvedTerm(
        identifier=identifier,
        label=str(row.get("label", identifier)),
        short=row.get("short"),
        definition=str(row.get("definition_long") or row.get("definition_short") or ""),
        source_url=f"https://github.com/JanDuchscherer104/ARIA-NBV/blob/main/docs/glossary/terms.yml#{row.get('anchor', identifier)}",
    )
