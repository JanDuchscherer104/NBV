"""Typed factory configuration for the Streamlit NBV explorer.

This module provides dataset-input and oracle-label pipeline settings and
resolves the app target lazily so importing configuration does not import
Streamlit.
"""

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
    """Compose the actor input source and oracle diagnostics pipeline."""

    @property
    def target_type(self) -> type["NbvStreamlitApp"]:
        """Return the lazily imported Streamlit application type."""

        return _target_cls()

    dataset: AseEfmDatasetConfig = Field(default_factory=AseEfmDatasetConfig)
    """Configuration for observed EFM snippets and attached evaluation assets."""

    labeler: OracleRriLabelerConfig = Field(default_factory=OracleRriLabelerConfig)
    """Actor-action candidate settings plus oracle depth/RRI label stages."""


__all__ = ["NbvStreamlitAppConfig"]
