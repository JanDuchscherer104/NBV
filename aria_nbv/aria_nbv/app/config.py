"""Typed factory configuration for the Streamlit NBV explorer.

This module provides dataset-input and oracle-label pipeline settings and
resolves the app target lazily so importing configuration does not import
Streamlit.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import Field, field_validator

from ..data_handling import AseEfmDatasetConfig
from ..oracle.pipelines.scene_labels import OracleRriLabelerConfig
from ..utils import TargetConfig

if TYPE_CHECKING:
    from ..reporting import ScientificReportConfig
    from .app import NbvStreamlitApp


class NbvStreamlitAppConfig(TargetConfig["NbvStreamlitApp"]):
    """Compose the actor input source and oracle diagnostics pipeline."""

    @property
    def target_type(self) -> type["NbvStreamlitApp"]:
        """Return the lazily imported Streamlit application type."""

        from .app import NbvStreamlitApp

        return NbvStreamlitApp

    dataset: AseEfmDatasetConfig = Field(default_factory=AseEfmDatasetConfig)
    """Configuration for observed EFM snippets and attached evaluation assets."""

    labeler: OracleRriLabelerConfig = Field(default_factory=OracleRriLabelerConfig)  # type: ignore[arg-type]
    """Actor-action candidate settings plus oracle depth/RRI label stages."""

    s2_report_recipe_path: Path = Path(".configs/reports/s2-thesis-pilot.toml")
    """Shared TOML recipe supplying S2 analysis, channels, theme, and evidence status."""

    s2_report_section_id: str = "s2"
    """Configured ``rollout_s2`` section used by active-store previews."""

    @field_validator("s2_report_section_id")
    @classmethod
    def _nonempty_s2_section_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("s2_report_section_id must be non-empty.")
        return value

    def load_s2_report_recipe(self, *, root: Path | None = None) -> tuple["ScientificReportConfig", Path]:
        """Load and validate the shared S2 recipe without acquiring evidence.

        Relative paths resolve against the repository root. The configured
        section is validated as ``rollout_s2`` immediately, while its persisted
        rollout source is replaced by the active immutable store only after an
        explicit preview dispatch.
        """

        from ..configs import PathConfig
        from ..reporting import ScientificReportConfig

        repository_root = (root or PathConfig().root).expanduser().resolve()
        configured_path = self.s2_report_recipe_path.expanduser()
        recipe_path = (
            configured_path.resolve()
            if configured_path.is_absolute()
            else (repository_root / configured_path).resolve()
        )
        recipe = ScientificReportConfig.from_toml(recipe_path)
        recipe.rollout_s2_section(self.s2_report_section_id)
        return recipe, recipe_path


__all__ = ["NbvStreamlitAppConfig"]
