"""Stable public entry point for the stored-rollout inspector."""

from __future__ import annotations

from ...reporting import ScientificReportConfig
from ._stored_rollouts_page import (
    render_stored_rollouts_page,
)


def render_stored_rollouts_panel(
    *,
    s2_recipe: ScientificReportConfig | None = None,
    s2_section_id: str = "s2",
    s2_recipe_label: str = "default",
) -> None:
    """Render the science-first stored-dataset inspection workflow."""

    render_stored_rollouts_page(
        s2_recipe=s2_recipe or ScientificReportConfig(),
        s2_section_id=s2_section_id,
        s2_recipe_label=s2_recipe_label,
    )


__all__ = ["render_stored_rollouts_panel"]
