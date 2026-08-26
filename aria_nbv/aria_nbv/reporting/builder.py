"""Build immutable report snapshots from explicit existing-store adapters."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from ..configs import PathConfig
from ._rollouts import _acquire_rollout_evidence, _build_rollout_section
from ._wandb import _acquire_wandb_evidence, _build_wandb_section
from .config import ScientificReportConfig
from .errors import ScientificReportError
from .notation import TheoryReferences, TheoryResolutionError, notation_sha256, validate_theory_registry
from .results import NamedQuantity, ReportFigure, ReportSnapshot, ReportTable, SourceIdentity


@dataclass(frozen=True, slots=True)
class ReportRequest:
    """Optional section/result selection for one explicit build dispatch."""

    section_ids: tuple[str, ...] = ()
    """Selected section IDs; empty means every configured section."""

    result_ids: tuple[str, ...] = ()
    """Selected exact result IDs; empty means every result in selected sections."""

    def __post_init__(self) -> None:
        for identifiers in (self.section_ids, self.result_ids):
            if any(not identifier.strip() for identifier in identifiers) or len(identifiers) != len(set(identifiers)):
                raise ValueError("Report request identifiers must be non-empty and unique.")


class ScientificReportBuilder:
    """Materialize one validated recipe into a sealed report snapshot.

    Construction stores configuration and injected clients only. Expensive W&B
    and rollout reads occur exclusively in :meth:`build`, which Streamlit and
    CLI callers invoke explicitly. Each configured source family is acquired at
    most once per build and reused by all selected sections.
    """

    def __init__(
        self,
        config: ScientificReportConfig,
        *,
        wandb_api: object | None = None,
        root: Path | None = None,
    ) -> None:
        self.config = config
        self._wandb_api = wandb_api
        self._root = (root or PathConfig().root).expanduser().resolve()

    def build(self, request: ReportRequest | None = None) -> ReportSnapshot:
        """Acquire selected evidence once and return a provenance-closed snapshot."""

        request = request or ReportRequest()
        self.config.validate_build_readiness(section_ids=request.section_ids)
        requested_sections = frozenset(request.section_ids) or None
        requested_results = frozenset(request.result_ids) or None
        configured_ids = {section.id for section in self.config.sections}
        if requested_sections is not None and not requested_sections.issubset(configured_ids):
            missing = sorted(requested_sections - configured_ids)
            raise ScientificReportError("result_missing", f"Unknown report sections: {missing}")

        quantities: list[NamedQuantity] = []
        tables: list[ReportTable] = []
        figures: list[ReportFigure] = []
        sources: list[SourceIdentity] = []
        rollout_evidence = None
        wandb_evidence = None
        rollout_tables = frozenset(
            {
                "stores",
                "facts",
                *(
                    table_name
                    for section in self.config.sections
                    if section.kind == "rollout" and (requested_sections is None or section.id in requested_sections)
                    for table_name in section.include_tables
                ),
            }
        )
        try:
            for section in self.config.sections:
                if requested_sections is not None and section.id not in requested_sections:
                    continue
                if section.kind == "rollout":
                    rollout_source = self.config.sources.rollout
                    assert rollout_source is not None
                    if rollout_evidence is None:
                        rollout_evidence = _acquire_rollout_evidence(
                            rollout_source,
                            evidence_status=self.config.evidence_status,
                            required_tables=rollout_tables,
                        )
                        sources.append(rollout_evidence.identity)
                    rollout_results = _build_rollout_section(
                        rollout_evidence,
                        section,
                        self.config.theme,
                        requested_result_ids=requested_results,
                    )
                    quantities.extend(rollout_results.quantities)
                    tables.extend(rollout_results.tables)
                    figures.extend(rollout_results.figures)
                else:
                    wandb_source = self.config.sources.wandb
                    assert wandb_source is not None
                    if self._wandb_api is None:
                        raise ScientificReportError("source_unavailable", "W&B report requested without an API client.")
                    if wandb_evidence is None:
                        wandb_evidence = _acquire_wandb_evidence(
                            wandb_source,
                            evidence_status=self.config.evidence_status,
                            api=self._wandb_api,  # type: ignore[arg-type]
                        )
                        sources.append(wandb_evidence.identity)
                    wandb_results = _build_wandb_section(
                        wandb_evidence,
                        section,
                        self.config.theme,
                        requested_result_ids=requested_results,
                    )
                    quantities.extend(wandb_results.quantities)
                    tables.extend(wandb_results.tables)
                    figures.extend(wandb_results.figures)
        except ScientificReportError:
            raise
        except Exception as exc:
            raise ScientificReportError("source_unavailable", str(exc)) from exc

        actual_results = (
            {quantity.id for quantity in quantities}
            | {table.id for table in tables}
            | {figure.id for figure in figures}
        )
        if requested_results is not None and not requested_results.issubset(actual_results):
            missing = sorted(requested_results - actual_results)
            raise ScientificReportError("result_missing", f"Requested report results were not produced: {missing}")
        symbol_ids = tuple(
            sorted(
                {
                    *(quantity.symbol_id for quantity in quantities if quantity.symbol_id is not None),
                    *(column.symbol_id for table in tables for column in table.columns if column.symbol_id is not None),
                    *(symbol_id for figure in figures for symbol_id in figure.symbol_ids),
                }
            )
        )
        try:
            validate_theory_registry(TheoryReferences(symbol_ids=symbol_ids), root=self._root)
        except TheoryResolutionError as exc:
            raise ScientificReportError("notation_unknown", str(exc)) from exc

        config_bytes = json.dumps(
            self.config.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        return ReportSnapshot.create(
            evidence_status=self.config.evidence_status,
            config_sha256=hashlib.sha256(config_bytes).hexdigest(),
            notation_sha256=notation_sha256(root=self._root),
            source_identities=tuple(sources),
            quantities=tuple(quantities),
            tables=tuple(tables),
            figures=tuple(figures),
            resolved_recipe=self.config.to_toml().encode("utf-8"),
        )


__all__ = ["ReportRequest", "ScientificReportBuilder"]
