"""Shared configuration, diagnostics, geometry, and visualization utilities.

The package exports low-level helpers used across data handling, VIN training,
and interactive diagnostics. Domain-specific ownership remains in the calling
package; this namespace contains only cross-cutting contracts.
"""

from .base_config import BaseConfig, SingletonConfig, TargetConfig
from .console import Console, Verbosity
from .frames import rotate_yaw_cw90
from .optuna_optimizable import Optimizable, optimizable_field
from .rich_summary import (
    SummaryRow,
    build_nested,
    rich_summary,
    summarize,
    summarize_shape,
    summary_markdown,
    summary_rows,
)
from .schemas import Stage, ValueStrEnum
from .viz_utils import extract_scene_id_from_sequence_name, validate_scene_data

__all__ = [
    "BaseConfig",
    "Console",
    "Optimizable",
    "Stage",
    "ValueStrEnum",
    "Verbosity",
    "SingletonConfig",
    "TargetConfig",
    "optimizable_field",
    "rich_summary",
    "build_nested",
    "summarize",
    "summarize_shape",
    "SummaryRow",
    "summary_rows",
    "summary_markdown",
    "extract_scene_id_from_sequence_name",
    "validate_scene_data",
    "rotate_yaw_cw90",
]
