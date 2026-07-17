"""Config-as-factory wrapper for the refactored Streamlit app."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import Field

from ..data_handling import AseEfmDatasetConfig
from ..oracle.pipelines.scene_labels import OracleRriLabelerConfig
from ..utils import TargetConfig

if TYPE_CHECKING:
    from .app import NbvStreamlitApp


class NbvStreamlitAppConfig(TargetConfig["NbvStreamlitApp"]):
    """Top-level config for the refactored Streamlit app."""

    @property
    def target_type(self) -> type["NbvStreamlitApp"]:
        from .app import NbvStreamlitApp

        return NbvStreamlitApp

    dataset: AseEfmDatasetConfig = Field(default_factory=AseEfmDatasetConfig)
    """Dataset configuration used by the app."""

    labeler: OracleRriLabelerConfig = Field(default_factory=OracleRriLabelerConfig)
    """Oracle label pipeline configuration (candidates → depth → RRI)."""


__all__ = ["NbvStreamlitAppConfig"]
