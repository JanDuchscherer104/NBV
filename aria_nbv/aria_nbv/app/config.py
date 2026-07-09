"""Config-as-factory wrapper for the refactored Streamlit app."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import Field

from ..data_handling import AseEfmDatasetConfig
from ..pipelines import OracleRriLabelerConfig
from ..utils import TargetConfig

if TYPE_CHECKING:
    from .app import NbvStreamlitApp


def _target_cls():
    from .app import NbvStreamlitApp

    return NbvStreamlitApp


class NbvStreamlitAppConfig(TargetConfig["NbvStreamlitApp"]):
    """Top-level config for the refactored Streamlit app."""

    @property
    def target_type(self) -> type["NbvStreamlitApp"]:
        return _target_cls()

    dataset: AseEfmDatasetConfig = Field(default_factory=AseEfmDatasetConfig)
    """Dataset configuration used by the app."""

    labeler: OracleRriLabelerConfig = Field(default_factory=OracleRriLabelerConfig)
    """Oracle label pipeline configuration (candidates → depth → RRI)."""


__all__ = ["NbvStreamlitAppConfig"]
