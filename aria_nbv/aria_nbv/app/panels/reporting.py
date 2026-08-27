"""Streamlit preview and exact-snapshot export for scientific reports."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from ...configs import ConfigAuthoringError, ConfigDocument, PathConfig
from ...reporting import ScientificReportConfig, ScientificReportError, write_report_snapshot
from .report_results import render_report_snapshot

_SNAPSHOT_KEY = "reporting_workspace_snapshot"
_SOURCE_DIGEST_KEY = "reporting_workspace_source_digest"


@st.cache_resource
def _wandb_api() -> object:
    """Construct the shared thread-safe W&B API client only when requested."""

    import wandb

    return wandb.Api()


def render_reporting_workspace(*, configs_dir: Path | None = None) -> None:
    """Explicitly build, preview, and export one immutable report snapshot.

    Recipe selection and ordinary widget reruns perform TOML/schema inspection
    only. The ``Preview report`` action performs source acquisition exactly
    once; ``Export exact preview`` passes the stored snapshot directly to the
    static exporter and therefore causes no W&B or rollout-store reads.
    """

    st.header("Scientific Reporting")
    st.caption(
        "Preview and thesis export share the same immutable quantities, tables, and canonical Plotly specifications."
    )
    root = (configs_dir or PathConfig().configs_dir).expanduser().resolve()
    recipes = tuple(sorted((root / "reports").glob("*.toml"), key=lambda path: path.as_posix()))
    if not recipes:
        st.info(f"No report recipes found below {root / 'reports'}.")
        return
    recipe_path = st.selectbox(
        "Report recipe",
        options=recipes,
        format_func=lambda path: path.relative_to(root).as_posix(),
        key="reporting_workspace_recipe",
    )
    try:
        document = ConfigDocument.open(recipe_path, ScientificReportConfig)
    except ConfigAuthoringError as exc:
        st.error(str(exc))
        return
    recipe = document.config
    st.caption(
        f"Evidence: **{recipe.evidence_status}** · Sections: {len(recipe.sections)} · Source SHA-256: "
        f"`{document.source_sha256}`"
    )
    with st.form("reporting_workspace_preview_form"):
        preview = st.form_submit_button("Preview report", type="primary", icon=":material/preview:")
    if preview:
        try:
            with st.status("Acquiring and freezing report evidence", expanded=True):
                recipe.validate_build_readiness()
                api = _wandb_api() if recipe.sources.wandb is not None else None
                snapshot = recipe.setup_target(wandb_api=api).build()
                st.session_state[_SNAPSHOT_KEY] = snapshot
                st.session_state[_SOURCE_DIGEST_KEY] = document.source_sha256
        except (ScientificReportError, ValueError, OSError) as exc:
            st.error(str(exc))
            return
    snapshot = st.session_state.get(_SNAPSHOT_KEY)
    preview_digest = st.session_state.get(_SOURCE_DIGEST_KEY)
    if snapshot is None:
        st.info("Select Preview report to acquire evidence. Config inspection above is metadata-only.")
        return
    if preview_digest != document.source_sha256:
        st.warning("The recipe changed after this preview. Build a new preview before export.")
        return
    st.success(
        f"Snapshot `{snapshot.snapshot_sha256}` contains {len(snapshot.quantities)} quantities, "
        f"{len(snapshot.tables)} tables, and {len(snapshot.figures)} figures."
    )
    render_report_snapshot(
        snapshot,
        key_prefix="reporting_workspace",
        show_plotly_specifications=True,
    )
    export_path = st.text_input(
        "Export directory",
        value=(PathConfig().root / "build" / "reports" / recipe_path.stem).as_posix(),
        key="reporting_workspace_export_path",
    )
    if st.button("Export exact preview", icon=":material/publish:"):
        try:
            receipt = write_report_snapshot(
                snapshot,
                Path(export_path),
                width=recipe.export.width,
                height=recipe.export.height,
                scale=recipe.export.scale,
                two_dimensional_format=recipe.export.two_dimensional_format,
                webgl_format=recipe.export.webgl_format,
            )
        except ScientificReportError as exc:
            st.error(str(exc))
            return
        st.success(f"Exported `{receipt.destination}` with manifest `{receipt.manifest_sha256}`.")


__all__ = ["render_reporting_workspace"]
