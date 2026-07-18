"""Stable public entry point for the stored-rollout inspector."""

from __future__ import annotations

from ._stored_rollouts_page import (
    render_stored_rollouts_page,
)


def render_stored_rollouts_panel() -> None:
    """Render the science-first stored-dataset inspection workflow."""

    render_stored_rollouts_page()


__all__ = ["render_stored_rollouts_panel"]
