"""Thin Streamlit adapter for rollout-owned target-frame S2 reports."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import Path

import streamlit as st

from ....reporting import ReportRequest, ReportSnapshot, ReportTable, ScientificReportConfig, ScientificReportError
from ..report_results import render_report_snapshot


def render_s2_report_preview(
    *,
    store_path: Path,
    store_identity: str,
    recipe: ScientificReportConfig,
    section_id: str,
    recipe_label: str,
    key_prefix: str,
) -> None:
    r"""Build and render the configured S2 report only after explicit dispatch.

    The adapter owns widget and session state only. ``ScientificReportConfig``
    owns source binding and immutable snapshot construction;
    :mod:`aria_nbv.rollouts.s2_analysis` owns store reads and reduction; and
    :mod:`aria_nbv.rollouts.s2_plotting` owns Plotly construction. Consequently
    this module cannot silently diverge from the figures exported to Typst.

    Args:
        store_path: Active immutable rollout Zarr directory.
        store_identity: Replacement-sensitive identity used to invalidate page
            state when the selected directory changes in place.
        recipe: Shared TOML-backed scientific report recipe.
        section_id: Configured ``rollout_s2`` section selected for this view.
        recipe_label: Human-readable recipe path or provenance label.
        key_prefix: Store-scoped Streamlit widget namespace.
    """

    section = recipe.rollout_s2_section(section_id)
    analysis = section.analysis
    st.markdown("#### Target-frame S² movement, view-direction, and frustum evidence")
    st.caption(
        "The active store is evaluated through the same immutable report transaction used by thesis export. "
        f"Recipe `{recipe_label}` · section `{section_id}` · "
        f"{analysis.azimuth_bins}×{analysis.elevation_bins} equal-solid-angle cells · "
        f"at most {analysis.projection_limit:,} provenance points per channel."
    )
    st.caption(
        "Movement uses the target-frame geometric-mean OBB semi-axis scale before unit projection; camera +Z "
        "defines view direction; calibrated frusta measure geometric proxy-surface support, not observed mesh visibility."
    )

    request_digest = _preview_digest(
        store_path=store_path,
        store_identity=store_identity,
        recipe=recipe,
        section_id=section_id,
    )
    state_key = f"{key_prefix}:s2-report-snapshot"
    if st.button(
        "Build complete target-frame S² report",
        type="primary",
        key=f"{key_prefix}:build-s2-report",
        help="Reads every factual selected path in the active store and freezes one immutable report snapshot.",
    ):
        try:
            bound_recipe = recipe.bind_rollout_stores((store_path,))
            with st.status("Building immutable S² report snapshot", expanded=True):
                snapshot = bound_recipe.setup_target().build(ReportRequest(section_ids=(section_id,)))
            st.session_state[state_key] = (request_digest, snapshot)
        except (ScientificReportError, OSError, ValueError) as exc:
            st.session_state.pop(state_key, None)
            st.error(f"S² report unavailable: {exc}")
            return

    state = st.session_state.get(state_key)
    if state is not None and state[0] != request_digest:
        st.session_state.pop(state_key, None)
        state = None
    if state is None:
        st.info("Build the S² report to acquire complete-store evidence. Ordinary reruns remain metadata-only.")
        return

    snapshot = state[1]
    if not isinstance(snapshot, ReportSnapshot):
        st.session_state.pop(state_key, None)
        st.error("Stored S² preview state is invalid; build the report again.")
        return
    _render_support_summary(snapshot, section_id=section_id)
    render_report_snapshot(
        snapshot,
        key_prefix=f"{key_prefix}:s2-report",
        show_quantities=False,
    )


def _preview_digest(
    *,
    store_path: Path,
    store_identity: str,
    recipe: ScientificReportConfig,
    section_id: str,
) -> str:
    """Bind page state to content, selected section, and the validated recipe."""

    payload = "\n".join((store_path.resolve().as_posix(), store_identity, section_id, recipe.to_toml()))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _render_support_summary(snapshot: ReportSnapshot, *, section_id: str) -> None:
    """Lead with the support denominator retained in the immutable table."""

    result = snapshot.result(f"{section_id}.table.support")
    if not isinstance(result, ReportTable) or not result.rows:
        st.warning("The S² report contains no support row for the active store.")
        return
    row = dict(zip((column.id for column in result.columns), result.rows[0], strict=True))
    st.caption(
        f"Evidence support: {_integer_cell(row, 'source_sample_count'):,} source samples · "
        f"{_integer_cell(row, 'source_snippet_count'):,} unique scene/snippet windows · "
        f"{_integer_cell(row, 'source_scene_count'):,} scenes · "
        f"{_integer_cell(row, 'target_count'):,} targets · "
        f"{_integer_cell(row, 'rollout_count'):,}/{_integer_cell(row, 'store_rollout_count'):,} "
        f"admissible rollout chains · {_integer_cell(row, 'selected_step_count'):,} selected steps."
    )
    if _integer_cell(row, "movement_count") == 0 and _integer_cell(row, "view_direction_count") == 0:
        st.warning("No finite factual selected-action directions survived the rollout-owned reducer.")
    issue_count = _integer_cell(row, "issue_count")
    if issue_count > 0:
        st.warning(
            f"The reducer retained {issue_count:,} addressed exclusions; inspect `{section_id}.table.issues` below."
        )


def _integer_cell(row: Mapping[str, object], field: str) -> int:
    """Read one required integral support cell from a sealed report table."""

    value = row[field]
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"S2 support field {field!r} must contain an integer, got {value!r}.")
    return value


__all__ = ["render_s2_report_preview"]
