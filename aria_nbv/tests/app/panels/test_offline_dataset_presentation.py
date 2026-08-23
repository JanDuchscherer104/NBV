"""Regression coverage for the root-store diagnostics presentation boundary."""

from __future__ import annotations

import inspect

from aria_nbv.app.panels import offline_dataset


def test_root_store_diagnostics_use_four_progressive_workspaces() -> None:
    """The page keeps the primary workspaces stable and groups detail tools."""

    assert offline_dataset._SECTIONS == ("Overview", "Content", "Runtime", "Details")
    source = inspect.getsource(offline_dataset._render_stats)
    assert 'st.expander("Core distributions", expanded=True)' in source
    assert 'st.expander("Persisted blocks"' in source
    assert 'st.expander("Manifest and shapes"' in source
    assert 'st.expander("Coverage"' not in source


def test_root_store_rri_views_use_global_scientific_label_mode() -> None:
    """Plot-facing RRI labels go through the shared presentation helper."""

    source = inspect.getsource(offline_dataset._render_rri_components)
    binner_source = inspect.getsource(offline_dataset._render_binner)
    assert "render_scientific_notation" in source
    assert 'current_scientific_label("rri")' in source
    assert 'current_scientific_label("oracle_rri")' in binner_source
