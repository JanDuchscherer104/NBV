"""Direct rollout inspection, deterministic export, and Rerun launch."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from ....configs import PathConfig
from ....rerun_inspector import RerunInspectorLayerState, RolloutLayerName, RolloutLayerPreset
from ...rerun_launch import (
    RerunLaunchMode,
    RerunLaunchProcess,
    build_rerun_rollout_command,
    format_command,
    poll_rerun_launch,
    rerun_web_url,
    resolve_rollout_launch_config,
    restart_rerun_launch,
    start_rerun_launch,
    stop_rerun_launch,
)
from ..common import _report_exception
from .session import StoredRolloutSession
from .shared import _LAUNCH_HANDLE_KEY, _download_frame, _download_json, _info_popover, _render_plot

_INSPECT_INFO = r"""
This section traces aggregate findings back to exact persisted rows.

Audit identity is (H_a=\operatorname{SHA256}(\text{canonical JSON bytes})),
and its sealed rollout-store identity must equal the selected store manifest
hash before any confirmatory backlink is admissible. Hashing/parsing is lazy
and occurs only after this active section requests provenance.

- Selected depth in metres is privileged oracle/evaluation evidence for the factual selected action. Missing or corrupt depth disables only its preview.
- Candidate and step previews may be bounded for display; their CSV exports contain the complete selected rollout/step population, which is the denominator.
- Rerun reconstructs debugging views from a store, rollout id, configuration, and layer policy. It does not establish matched or statistically conclusive policy evidence.
- Confirmatory backlinks require PASS/readiness, current validation, frozen protocols, exact store identity, matched evidence, and the section-specific scene uncertainty gate.

Actor-visible inputs and privileged overlays remain distinct throughout inspection.
"""

_ROLLOUT_WIDGET_KEY = "stored_rollout_inspect_rollout"
_STEP_WIDGET_KEY = "stored_rollout_inspect_step"


def _apply_lineage_handoff(rollout_ids: list[int], steps_by_rollout: dict[int, list[int]]) -> None:
    """Apply one validity/QH lineage handoff before selector widgets instantiate."""

    requested_rollout = st.session_state.pop("stored_rollout_id", None)
    requested_step = st.session_state.pop("stored_step_id", None)
    if requested_rollout not in rollout_ids:
        return
    rollout_id = int(requested_rollout)
    st.session_state[_ROLLOUT_WIDGET_KEY] = rollout_id
    if requested_step in steps_by_rollout.get(rollout_id, ()):
        st.session_state[_STEP_WIDGET_KEY] = int(requested_step)


def render(session: StoredRolloutSession, *, paths: PathConfig) -> None:
    """Render direct factual-row selection, exports, depth, and Rerun lifecycle."""

    st.subheader("Inspect, Export & Rerun")
    _info_popover("Selected-depth and Rerun evidence limits", _INSPECT_INFO)
    audit = session.audit_state()
    with st.expander("Scientific audit provenance and backlinks", expanded=False):
        st.json(
            {
                "path": None if audit.path is None else audit.path.as_posix(),
                "content_sha256": audit.content_sha256,
                "bundle_sha256": audit.bundle_sha256,
                "selected_store_sha256": audit.selected_store_sha256,
                "audit_store_sha256": audit.audit_store_sha256,
                "store_identity_matches": audit.store_identity_matches,
                "status": audit.artifact_status,
                "readiness": audit.readiness,
                "evidence_tier": audit.evidence_tier,
                "blockers": audit.blockers,
                "backlinks": {
                    "reconstruction": "Reconstruction & Return",
                    "policy_effects": "Oracle Headroom & Policies",
                    "candidate_support": "Candidate Generation & Selection",
                    "validity": "Validity & Support",
                },
            },
            expanded=False,
        )

    rollout_ids = session.rollout_ids()
    if not rollout_ids:
        st.warning("This store has no rollout rows to inspect.")
        return
    all_steps = pd.DataFrame(session.steps())
    steps_by_rollout = {
        int(rollout): sorted(group["step_row_id"].astype(int).tolist())
        for rollout, group in all_steps.groupby("rollout_row_id", sort=True)
    }
    _apply_lineage_handoff(rollout_ids, steps_by_rollout)

    if st.session_state.get(_ROLLOUT_WIDGET_KEY) not in rollout_ids:
        st.session_state[_ROLLOUT_WIDGET_KEY] = int(rollout_ids[0])
    rollout_id = int(st.selectbox("Rollout row", rollout_ids, key=_ROLLOUT_WIDGET_KEY))
    steps = pd.DataFrame(session.steps(rollout_row_id=rollout_id))
    step_ids = steps["step_row_id"].astype(int).tolist() if not steps.empty else []
    if not step_ids:
        st.warning("The selected rollout has no persisted steps.")
        return
    if st.session_state.get(_STEP_WIDGET_KEY) not in step_ids:
        st.session_state[_STEP_WIDGET_KEY] = step_ids[0]
    step_id = int(st.selectbox("Step row", step_ids, key=_STEP_WIDGET_KEY))

    _download_frame("Download selected-rollout step CSV", f"rollout-{rollout_id}-steps.csv", steps)
    candidates = pd.DataFrame(session.candidates(rollout_row_id=rollout_id, step_row_id=step_id))
    preview_limit = int(st.number_input("Candidate preview row limit", min_value=1, max_value=5000, value=200, step=25))
    shown = candidates.head(preview_limit)
    st.caption(
        f"Showing {len(shown):,} of {len(candidates):,} selected-step candidate rows. "
        f"The CSV contains all {len(candidates):,} rows."
    )
    st.dataframe(shown, hide_index=True, width="stretch")
    _download_frame(
        "Download selected-step candidate CSV",
        f"rollout-{rollout_id}-step-{step_id}-candidates.csv",
        candidates,
    )

    depth_rows = pd.DataFrame(session.selected_depth_summary(rollout_row_id=rollout_id))
    selected_depth = depth_rows[depth_rows["step_row_id"] == step_id] if not depth_rows.empty else depth_rows
    with st.expander("Privileged selected-depth evaluation artifact", expanded=not selected_depth.empty):
        st.warning("Selected depth is privileged oracle/evaluation evidence, never actor-visible policy input.")
        if selected_depth.empty:
            st.info("No selected-depth row exists for this step; direct inspection and Rerun remain available.")
        else:
            st.dataframe(selected_depth, hide_index=True, width="stretch")
            preview = session.selected_depth_preview(step_row_id=step_id)
            if bool(preview.get("available")):
                figure = px.imshow(
                    np.asarray(preview["depth_m"]),
                    color_continuous_scale="Turbo",
                    labels={"color": "depth (m)"},
                    title="Selected-action mesh depth",
                )
                _render_plot(figure)
            else:
                warning = str(preview.get("warning") or "not persisted")
                st.info(f"Selected-depth preview is unavailable: {warning}")

    with st.expander("Metadata and complete selected-rollout steps"):
        st.json(session.manifest_payload, expanded=False)
        st.dataframe(steps, hide_index=True, width="stretch")
    _download_json(
        "Download selected metadata JSON",
        f"rollout-{rollout_id}-metadata.json",
        session.manifest_payload,
    )
    _render_evidence_bundle_download(session)
    _render_rerun_launcher(store_path=session.store_path, rollout_id=rollout_id, paths=paths)


def _render_evidence_bundle_download(session: StoredRolloutSession) -> None:
    st.markdown("#### Canonical evidence bundle")
    status = _evidence_status(
        st.radio("Evidence status", options=["pilot", "confirmatory"], horizontal=True, key="evidence_status")
    )
    acknowledge = st.checkbox(
        "I acknowledge that confirmatory status requires frozen protocols and matched evidence.",
        value=False,
        disabled=status != "confirmatory",
    )
    export_blockers = session.confirmatory_export_blockers() if status == "confirmatory" else ()
    confirmatory_ready = not export_blockers
    if status == "confirmatory" and not confirmatory_ready:
        blocker_text = "; ".join(export_blockers)
        st.error(f"Confirmatory export is blocked: {blocker_text}")
    allowed = status == "pilot" or acknowledge and confirmatory_ready
    if allowed:
        st.download_button(
            "Download deterministic evidence bundle",
            data=lambda: session.evidence_bundle(evidence_status=status),
            file_name=f"rollout-evidence-{status}.json",
            mime="application/json",
            on_click="ignore",
            help="Built lazily on click and cached by live store plus selected audit content identity.",
        )
    elif status == "confirmatory" and confirmatory_ready:
        st.info("Acknowledge the confirmatory evidence contract to enable this download.")


def _evidence_status(value: object) -> Literal["pilot", "confirmatory"]:
    """Narrow Streamlit's selected value to the evidence-bundle contract."""

    if value == "pilot":
        return "pilot"
    if value == "confirmatory":
        return "confirmatory"
    raise ValueError(f"Unknown evidence status: {value!r}")


def _render_rerun_launcher(*, store_path: Path, rollout_id: int, paths: PathConfig) -> None:
    st.markdown("#### Rerun launch")
    base_config = st.text_input(
        "Rerun inspector config",
        value=str(paths.resolve_config_toml_path("rerun_offline.toml")),
        key="stored_rerun_config",
    )
    artifact_dir = Path(
        st.text_input(
            "Launch artifact directory",
            value=str(paths.root / ".logs" / "rerun" / "stored_rollouts"),
            key="stored_rerun_artifact_dir",
        )
    ).expanduser()
    preset = st.selectbox(
        "Layer preset",
        options=list(RolloutLayerPreset),
        format_func=lambda value: str(value.value).replace("_", " ").title(),
    )
    with st.expander("Advanced included and initially visible layers"):
        overrides: dict[
            RolloutLayerName | str,
            RerunInspectorLayerState | Mapping[str, bool],
        ] = {}
        defaults = resolve_rollout_launch_config(
            base_config_path=base_config,
            artifact_dir=artifact_dir,
            preset=preset,
        ).config.rollout_layers
        for layer in RolloutLayerName:
            state = getattr(defaults, layer.value)
            col_name, col_inc, col_vis = st.columns([3, 1, 1])
            col_name.markdown(layer.value.replace("_", " ").title())
            included = col_inc.checkbox("Included", value=state.included, key=f"rerun_inc_{layer.value}")
            visible = col_vis.checkbox(
                "Visible",
                value=state.visible and included,
                disabled=not included,
                key=f"rerun_vis_{layer.value}",
            )
            overrides[layer] = RerunInspectorLayerState(
                included=included,
                visible=bool(visible and included),
            )

    mode = st.selectbox(
        "Launch mode",
        options=list(RerunLaunchMode),
        format_func=lambda value: {
            RerunLaunchMode.native_live: "Native live spawn",
            RerunLaunchMode.native_view: "Save then open native viewer",
            RerunLaunchMode.serve_web: "Save then serve web",
            RerunLaunchMode.save_only: "Save-only artifact",
        }[value],
    )
    save_path = artifact_dir / f"rollout-{rollout_id}.rrd"
    web_port = int(st.number_input("Web viewer port", min_value=1, max_value=65535, value=9090))
    grpc_port = int(st.number_input("Rerun gRPC/proxy port", min_value=1, max_value=65535, value=9877))
    lan = st.checkbox("Expose web viewer on the LAN", value=False, disabled=mode is not RerunLaunchMode.serve_web)

    try:
        resolved = resolve_rollout_launch_config(
            base_config_path=base_config,
            artifact_dir=artifact_dir,
            preset=preset,
            overrides=overrides,
        )
        command = build_rerun_rollout_command(
            config_path=resolved.config_path,
            rollout_store=store_path,
            rollout_row_id=rollout_id,
            mode=mode,
            save_path=None if mode is RerunLaunchMode.native_live else save_path,
            web_viewer_port=web_port,
            ws_server_port=grpc_port,
            lan=lan,
        )
    except Exception as exc:
        st.error(f"Rerun launch configuration is invalid: {type(exc).__name__}: {exc}")
        return
    st.code(format_command(command), language="bash")
    st.caption(f"Resolved layer policy: `{resolved.config_path}` · digest `{resolved.digest[:16]}`")

    if st.button("Launch Rerun", type="primary"):
        try:
            previous = st.session_state.get(_LAUNCH_HANDLE_KEY)
            if isinstance(previous, RerunLaunchProcess) and previous.process.poll() is None:
                stop_rerun_launch(previous)
            url = (
                rerun_web_url(web_viewer_port=web_port, ws_server_port=grpc_port, lan=lan)
                if mode is RerunLaunchMode.serve_web
                else None
            )
            launched_handle = start_rerun_launch(
                command,
                artifact_dir=artifact_dir,
                config_path=resolved.config_path,
                rrd_path=None if mode is RerunLaunchMode.native_live else save_path,
                url=url,
            )
            st.session_state[_LAUNCH_HANDLE_KEY] = launched_handle
        except Exception as exc:
            _report_exception(exc, context="Rerun launch failed")

    active_handle = st.session_state.get(_LAUNCH_HANDLE_KEY)
    if isinstance(active_handle, RerunLaunchProcess):
        verify_url = active_handle.url is not None
        status = poll_rerun_launch(active_handle, verify_url=verify_url)
        (st.success if status.healthy else st.warning)(status.message)
        st.caption(
            f"PID {status.pid} · running={status.running} · exit={status.exit_code} · "
            f"config={status.config_path} · rrd={status.rrd_path}"
        )
        if status.url and status.url_reachable:
            st.link_button("Open Rerun Web Viewer", status.url)
            if st.checkbox("Embed viewer inline", value=False):
                st.components.v1.iframe(status.url, height=720, scrolling=True)
        with st.expander("Rerun stdout/stderr"):
            st.code(status.stdout_tail or "(no stdout)", language="text")
            st.code(status.stderr_tail or "(no stderr)", language="text")
        col_restart, col_stop = st.columns(2)
        if col_restart.button("Restart Rerun"):
            try:
                st.session_state[_LAUNCH_HANDLE_KEY] = restart_rerun_launch(active_handle)
            except Exception as exc:
                _report_exception(exc, context="Rerun restart failed")
            else:
                st.rerun()
        if col_stop.button("Stop Rerun"):
            stop_rerun_launch(active_handle)
            st.session_state.pop(_LAUNCH_HANDLE_KEY, None)
            st.rerun()


__all__ = ["render"]
