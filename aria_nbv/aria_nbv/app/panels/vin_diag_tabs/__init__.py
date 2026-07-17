"""Typed facade for the VIN diagnostics tab renderers.

The package exports the shared context plus focused views of summaries,
geometry, transforms, evidence, encodings, tokens, ordinal outputs, and bin
values.
"""

from __future__ import annotations

from .bin_values import render_bin_values_tab
from .context import VinDiagContext
from .coral import render_coral_tab
from .encodings import render_encodings_tab
from .evidence import render_evidence_tab
from .field import render_field_tab
from .geometry import render_geometry_tab
from .pose import render_pose_tab
from .summary import render_summary_tab
from .tokens import render_tokens_tab
from .transforms import render_transforms_tab

__all__ = [
    "VinDiagContext",
    "render_bin_values_tab",
    "render_coral_tab",
    "render_encodings_tab",
    "render_evidence_tab",
    "render_field_tab",
    "render_geometry_tab",
    "render_pose_tab",
    "render_summary_tab",
    "render_tokens_tab",
    "render_transforms_tab",
]
