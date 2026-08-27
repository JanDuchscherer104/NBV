"""Validated TOML recipe for immutable scientific reports.

Recipes select code-owned report sections and presentation settings. They do
not contain Python import paths, callables, equations, Plotly traces, or Typst
markup. Runtime sources and clients are injected when the builder is created.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Literal

from pydantic import Field, field_validator, model_validator

from ..utils import TargetConfig

if TYPE_CHECKING:
    from .builder import ScientificReportBuilder


class RolloutSourceConfig(TargetConfig[object]):
    """Select immutable rollout stores for report sections."""

    store_paths: tuple[Path, ...] = ()
    """Rollout Zarr store paths, resolved by the rollout reader at build time."""

    sidecar_paths: tuple[Path, ...] = ()
    """Optional immutable JSON/JSONL sidecars admitted by rollout reporting."""


class WandbSourceConfig(TargetConfig[object]):
    """Select exact W&B runs and history fields for report sections."""

    entity: str = ""
    """W&B entity that owns every selected run."""

    project: str = ""
    """W&B project that owns every selected run."""

    run_ids: tuple[str, ...] = ()
    """Exact W&B run IDs; confirmatory reports prohibit dynamic filtering."""

    history_keys: tuple[str, ...] = ()
    """History columns fetched for code-owned report products."""

    history_mode: Literal["sampled", "complete"] = "sampled"
    """Whether acquisition uses sampled ``history`` or exhaustive ``scan_history``."""

    max_rows: int = Field(default=2000, ge=1)
    """Maximum sampled rows; ignored for complete history acquisition."""

    @field_validator("run_ids", "history_keys")
    @classmethod
    def _unique_nonempty_values(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(not value.strip() for value in values) or len(values) != len(set(values)):
            raise ValueError("W&B identifiers and history keys must be non-empty and unique.")
        return values


class ReportSourcesConfig(TargetConfig[object]):
    """Optional source families available to configured report sections."""

    rollout: RolloutSourceConfig | None = None
    """Rollout-store selection, when rollout sections are configured."""

    wandb: WandbSourceConfig | None = None
    """W&B run selection, when W&B sections are configured."""


class RolloutReportSectionConfig(TargetConfig[object]):
    """Wrap canonical rollout report-v1 frames without changing reductions."""

    kind: Literal["rollout"] = "rollout"
    """Closed discriminator for the rollout report producer."""

    id: str = "rollout"
    """Stable section identifier used as the result-ID prefix."""

    include_tables: tuple[str, ...] = ("stores", "facts")
    """Canonical rollout report-v1 tables to materialize in the snapshot."""

    quantity_fact_key: str = "candidate_validity.fraction"
    """Fact key promoted as the section's named quantity."""

    quantity_symbol_id: str | None = "rl.validity_mask"
    """Canonical symbol ID, or ``None`` only for an operational quantity."""

    figure_fact_keys: tuple[str, ...] = (
        "candidate_validity.valid",
        "candidate_validity.total",
    )
    """Fact keys shown by the section's deterministic Plotly bar figure."""


class WandbReportSectionConfig(TargetConfig[object]):
    """Materialize one exact W&B metric curve and dynamics summary."""

    kind: Literal["wandb"] = "wandb"
    """Closed discriminator for the W&B report producer."""

    id: str = "wandb"
    """Stable section identifier used as the result-ID prefix."""

    metric: str
    """Exact W&B history key plotted across selected runs."""

    symbol_id: str | None = None
    """Canonical symbol ID, or ``None`` when the metric is operational."""

    ema_alpha: float = Field(default=0.2, ge=0.0, le=1.0)
    """Exponential-moving-average factor; zero disables the smoothed trace."""

    show_raw: bool = True
    """Whether the canonical figure includes raw metric traces."""

    segment_fraction: float = Field(default=0.2, gt=0.0, le=0.5)
    """Fraction used by the existing W&B early/mid/late dynamics reducer."""


ReportSectionConfig = Annotated[
    RolloutReportSectionConfig | WandbReportSectionConfig,
    Field(discriminator="kind"),
]


class ReportThemeConfig(TargetConfig[object]):
    """Shared Plotly styling for interactive preview and static export."""

    template: str = "plotly_white"
    """Plotly template name applied by code-owned figure builders."""

    font_family: str = "Arial"
    """Font family recorded in figures and renderer provenance."""

    colorway: tuple[str, ...] = Field(
        default=(
            "#3B6FB6",
            "#B85450",
            "#6F4A8E",
            "#2E7D6E",
            "#A66A2C",
        ),
        min_length=1,
    )
    """Ordered, high-contrast categorical palette shared by report figures."""


class ReportExportConfig(TargetConfig[object]):
    """Static-asset and bundle publication settings."""

    width: int = Field(default=1400, ge=320)
    """Static figure width in pixels."""

    height: int = Field(default=900, ge=240)
    """Static figure height in pixels."""

    scale: float = Field(default=2.0, gt=0.0)
    """Static raster/vector renderer scale factor."""

    two_dimensional_format: Literal["svg", "png"] = "svg"
    """Default static format for non-WebGL Plotly figures."""

    webgl_format: Literal["png"] = "png"
    """Static format for WebGL or 3D figures."""


class ScientificReportConfig(TargetConfig["ScientificReportBuilder"]):
    """Build one immutable, provenance-closed scientific report snapshot.

    The config is the durable recipe shared by CLI and Streamlit. Calling
    :meth:`setup_target` injects external clients and canonical-notation root;
    parsing or describing the config performs no W&B or rollout payload reads.
    """

    schema_version: Literal["aria-nbv-report-config-v1"] = "aria-nbv-report-config-v1"
    """Closed recipe schema version."""

    evidence_status: Literal["pilot", "confirmatory"] = "pilot"
    """Scientific evidence class enforced by source and export gates."""

    sources: ReportSourcesConfig = Field(default_factory=ReportSourcesConfig)
    """Existing evidence-store selections; credentials and clients are excluded."""

    sections: tuple[ReportSectionConfig, ...] = ()
    """Closed, code-owned report products in author-selected order."""

    theme: ReportThemeConfig = Field(default_factory=ReportThemeConfig)
    """Shared interactive/static Plotly presentation settings."""

    export: ReportExportConfig = Field(default_factory=ReportExportConfig)
    """Static renderer settings recorded in the exported manifest."""

    @field_validator("sections")
    @classmethod
    def _unique_section_ids(cls, sections: tuple[ReportSectionConfig, ...]) -> tuple[ReportSectionConfig, ...]:
        ids = [section.id for section in sections]
        if any(not identifier.strip() for identifier in ids) or len(ids) != len(set(ids)):
            raise ValueError("Report section IDs must be non-empty and unique.")
        return sections

    @model_validator(mode="after")
    def _validate_source_requirements(self) -> "ScientificReportConfig":
        kinds = {section.kind for section in self.sections}
        if "rollout" in kinds and self.sources.rollout is None:
            raise ValueError("Rollout report sections require sources.rollout.")
        if "wandb" in kinds and self.sources.wandb is None:
            raise ValueError("W&B report sections require sources.wandb.")
        if self.evidence_status == "confirmatory" and self.sources.wandb is not None:
            source = self.sources.wandb
            if not source.run_ids or source.history_mode != "complete":
                raise ValueError("Confirmatory W&B evidence requires exact run_ids and complete history.")
        return self

    def setup_target(
        self,
        *,
        wandb_api: object | None = None,
        root: Path | None = None,
    ) -> "ScientificReportBuilder":
        """Construct a builder with late-bound external adapters."""

        from .builder import ScientificReportBuilder

        return ScientificReportBuilder(self, wandb_api=wandb_api, root=root)

    def validate_build_readiness(self, *, section_ids: tuple[str, ...] = ()) -> None:
        """Fail before client construction when selected source selectors are incomplete."""

        from .errors import ScientificReportError

        selected = frozenset(section_ids)
        kinds = {section.kind for section in self.sections if not selected or section.id in selected}
        rollout = self.sources.rollout
        if "rollout" in kinds and (rollout is None or not rollout.store_paths):
            raise ScientificReportError("config_invalid", "Rollout report sections require at least one store path.")
        wandb = self.sources.wandb
        if "wandb" in kinds and (
            wandb is None or not wandb.entity.strip() or not wandb.project.strip() or not wandb.run_ids
        ):
            raise ScientificReportError(
                "config_invalid",
                "W&B report sections require an entity, project, and exact run IDs.",
            )


__all__ = [
    "ReportExportConfig",
    "ReportSectionConfig",
    "ReportSourcesConfig",
    "ReportThemeConfig",
    "RolloutReportSectionConfig",
    "RolloutSourceConfig",
    "ScientificReportConfig",
    "WandbReportSectionConfig",
    "WandbSourceConfig",
]
