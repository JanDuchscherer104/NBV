"""Small typed bridge from Streamlit labels to the canonical documentation registries."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml

from ..configs import PathConfig

LabelDisplayMode = Literal["Symbols", "Text", "Both"]
LABEL_DISPLAY_MODES: tuple[LabelDisplayMode, ...] = ("Symbols", "Text", "Both")
LabelSurface = Literal["markdown", "plain"]


class TheoryResolutionError(ValueError):
    """Raised when a requested canonical equation, symbol, or term is unavailable."""


@dataclass(frozen=True, slots=True)
class ScientificLabel:
    """Presentation metadata for one persisted scientific field."""

    identifier: str
    text: str | None = None
    symbol_key: str | None = None
    units: str | None = None


SCIENTIFIC_LABELS: dict[str, ScientificLabel] = {
    "rri": ScientificLabel("rri", "Reconstruction improvement", "oracle.rri", "fraction"),
    "oracle_rri": ScientificLabel("oracle_rri", "Oracle RRI", "oracle.rri", "fraction"),
    "target_rri": ScientificLabel("target_rri", "Target RRI", "entity.rri_e", "fraction"),
    "selected_target_rri": ScientificLabel("selected_target_rri", "Selected target RRI", "entity.rri_e", "fraction"),
    "cumulative_target_rri": ScientificLabel(
        "cumulative_target_rri", "Cumulative target RRI", "entity.rri_e", "fraction"
    ),
    "selected_target_root_gain": ScientificLabel(
        "selected_target_root_gain", "Selected one-step target root gain", "entity.target_reward", "fraction"
    ),
    "target_root_gain": ScientificLabel(
        "target_root_gain", "One-step target root gain", "entity.target_reward", "fraction"
    ),
    "cumulative_target_root_gain": ScientificLabel(
        "cumulative_target_root_gain", "Cumulative target root gain", "rl.observed_cumulative_root_gain", "fraction"
    ),
    "endpoint_gain": ScientificLabel("endpoint_gain", "Endpoint gain", "entity.endpoint_gain", "fraction"),
    "log_gain": ScientificLabel("log_gain", "Log endpoint gain", "entity.log_gain"),
    "q_h": ScientificLabel("q_h", "Finite-horizon action value", "rl.qh"),
    "qh": ScientificLabel("qh", "Finite-horizon action value", "rl.qh"),
    "return_h": ScientificLabel("return_h", "Finite-horizon return", "entity.return_h"),
    "discount_gamma": ScientificLabel("discount_gamma", "Discount factor", "rl.gamma"),
    "horizon": ScientificLabel("horizon", "Rollout horizon", "rl.H", "steps"),
    "candidate_table": ScientificLabel("candidate_table", "Candidate set", "rl.candidate_table"),
    "validity_mask": ScientificLabel("validity_mask", "Candidate validity mask", "rl.validity_mask"),
    "target_error": ScientificLabel("target_error", "Target error", "entity.target_error"),
    "target_error_next": ScientificLabel("target_error_next", "Next target error", "entity.target_error_next"),
    "target_error_0": ScientificLabel("target_error_0", "Root target error", "entity.target_error_0"),
    "point_to_mesh_error": ScientificLabel("point_to_mesh_error", "Point-to-mesh error", "oracle.dist_pm"),
    "mesh_to_point_error": ScientificLabel("mesh_to_point_error", "Mesh-to-point error", "oracle.dist_mp"),
    "pm_acc_after": ScientificLabel("pm_acc_after", "Point-to-mesh error", "oracle.dist_pm"),
    "pm_comp_after": ScientificLabel("pm_comp_after", "Mesh-to-point error", "oracle.dist_mp"),
}


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


def format_identifier(identifier: str) -> str:
    """Format a persisted identifier for a readable non-mathematical surface."""

    return identifier.replace("_", " ").title()


def scientific_label(identifier: str) -> ScientificLabel:
    """Return curated presentation metadata without changing the source key."""

    return SCIENTIFIC_LABELS.get(identifier, ScientificLabel(identifier=identifier))


def format_scientific_label(
    label: ScientificLabel | str,
    *,
    mode: LabelDisplayMode = "Both",
    surface: LabelSurface = "plain",
    root: Path | None = None,
) -> str:
    configured = scientific_label(label) if isinstance(label, str) else label
    readable = configured.text or format_identifier(configured.identifier)
    units = f" ({configured.units})" if configured.units else ""
    if configured.symbol_key is None or surface == "plain" or mode == "Text":
        return f"{readable}{units}"
    resolved = resolve_theory(TheoryReferences(symbol_ids=(configured.symbol_key,)), root=root).symbols[0]
    symbol = f"${resolved.tex}$"
    return f"{symbol}{units}" if mode == "Symbols" else f"{symbol} — {readable}{units}"


def symbol_label(
    identifier: str,
    *,
    mode: LabelDisplayMode = "Both",
    math_capable: bool = True,
    root: Path | None = None,
) -> str:
    """Resolve one canonical symbol for a plot or readable UI label."""

    resolved = resolve_theory(TheoryReferences(symbol_ids=(identifier,)), root=root).symbols[0]
    description = resolved.description or format_identifier(identifier)
    if not math_capable or mode == "Text":
        return description
    if mode == "Symbols":
        return f"${resolved.tex}$"
    return f"${resolved.tex}$ — {description}"


def equation_label(
    identifier: str,
    *,
    mode: LabelDisplayMode = "Both",
    math_capable: bool = True,
    root: Path | None = None,
) -> str:
    """Resolve one canonical equation for a plot or readable UI label."""

    resolved = resolve_theory(TheoryReferences(equation_ids=(identifier,)), root=root).equations[0]
    description = resolved.description or format_identifier(identifier)
    if not math_capable or mode == "Text":
        return description
    if mode == "Symbols":
        return f"${resolved.tex}$"
    return f"${resolved.tex}$ — {description}"


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
