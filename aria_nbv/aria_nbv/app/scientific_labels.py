"""Small typed bridge from Streamlit labels to the canonical documentation registries."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from ..reporting.notation import (
    ResolvedNotation,
    ResolvedTerm,
    ResolvedTheory,
    TheoryReferences,
    TheoryResolutionError,
    resolve_theory,
    validate_theory_registry,
)

LabelDisplayMode = Literal["Symbols", "Text", "Both"]
LABEL_DISPLAY_MODES: tuple[LabelDisplayMode, ...] = ("Symbols", "Text", "Both")
LabelSurface = Literal["markdown", "plain"]


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
    "selected_target_rri": ScientificLabel(
        "selected_target_rri", "Selected target RRI", "entity.target_rri_marginal", "fraction"
    ),
    "cumulative_target_rri": ScientificLabel(
        "cumulative_target_rri", "Cumulative target RRI", "entity.target_rri_cumulative", "fraction"
    ),
    "selected_target_root_gain": ScientificLabel(
        "selected_target_root_gain", "Selected one-step target root gain", "entity.target_reward", "fraction"
    ),
    "target_root_gain": ScientificLabel(
        "target_root_gain", "One-step target root gain", "entity.target_reward", "fraction"
    ),
    "cumulative_target_root_gain": ScientificLabel(
        "cumulative_target_root_gain", "Cumulative target root gain", "entity.target_root_gain_cumulative", "fraction"
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
    "target_error": ScientificLabel("target_error", "Target error"),
    "target_error_next": ScientificLabel("target_error_next", "Next target error"),
    "target_error_0": ScientificLabel("target_error_0", "Root target error"),
    "point_to_mesh_error": ScientificLabel("point_to_mesh_error", "Point-to-mesh error"),
    "mesh_to_point_error": ScientificLabel("mesh_to_point_error", "Mesh-to-point error"),
    "pm_acc_after": ScientificLabel("pm_acc_after", "Point-to-mesh error"),
    "pm_comp_after": ScientificLabel("pm_comp_after", "Mesh-to-point error"),
}


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


__all__ = [
    "LABEL_DISPLAY_MODES",
    "SCIENTIFIC_LABELS",
    "LabelDisplayMode",
    "LabelSurface",
    "ResolvedNotation",
    "ResolvedTerm",
    "ResolvedTheory",
    "ScientificLabel",
    "TheoryReferences",
    "TheoryResolutionError",
    "equation_label",
    "format_identifier",
    "format_scientific_label",
    "resolve_theory",
    "scientific_label",
    "symbol_label",
    "validate_theory_registry",
]
