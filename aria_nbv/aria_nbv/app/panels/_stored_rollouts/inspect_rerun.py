"""Explicit drill-down queries, exports, and Rerun launch presentation."""

from __future__ import annotations

import hashlib
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any, Protocol, cast

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from ....configs import PathConfig
from ....reporting import ScientificReportConfig
from ....rerun_inspector import RolloutLayerName, RolloutLayerPreset
from ...rerun_launch import (
    RerunLaunchMode,
    build_rerun_rollout_command,
    format_command,
    poll_rerun_launch,
    rerun_web_url,
    resolve_rollout_launch_config,
    restart_rerun_launch,
    start_rerun_launch,
    stop_rerun_launch,
)
from ..common import ExplanationSection, ScientificExplanation, _report_exception
from ..common import download_frame as _download_frame
from ..common import download_json as _download_json
from ..common import render_plot as _render_plot
from .qh_admission import _render_q_h_evidence

_LAUNCH_HANDLE_KEY = "stored_rollouts_rerun_handle"
_ACTIVE_QUERY_STORE_KEY = "stored_rollouts_active_query_store"
_QUERY_SCOPES = ("Rollout summaries", "Factual steps", "Candidates")
_CANDIDATE_POPULATIONS = ("Selected step", "Selected rollout", "Explicit full store")


class _SessionState(Protocol):
    """Minimal mutable state surface used by query callbacks."""

    def __iter__(self) -> Iterator[str]: ...
    def get(self, key: str, default: Any = None) -> Any: ...
    def __setitem__(self, key: str, value: Any) -> None: ...
    def pop(self, key: str, default: Any = None) -> Any: ...


def _canonical_query_store_identity(store_path: Path) -> str:
    """Return a stable compact identity for one canonical immutable-store path."""

    canonical = store_path.expanduser().resolve().as_posix()
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def _integral_scalar(value: Any) -> int:
    """Convert one finite integral dataframe grouping key."""

    if isinstance(value, bool) or not isinstance(value, int | float | np.integer | np.floating):
        raise TypeError(f"Expected an integral numeric scalar, got {type(value).__name__}.")
    numeric = float(value)
    if not np.isfinite(numeric) or not numeric.is_integer():
        raise ValueError(f"Expected an integral numeric scalar, got {value!r}.")
    return int(numeric)


def _query_namespace(store_identity: str, scope: str, candidate_population: str) -> str:
    """Return the disjoint session-state namespace for one query grain."""

    grain = hashlib.sha256(f"{scope}\0{candidate_population}".encode()).hexdigest()[:12]
    return f"stored_query:{store_identity}:{grain}"


def _query_key(namespace: str, name: str) -> str:
    """Return one namespaced query or inspector widget key."""

    return f"{namespace}:{name}"


def _activate_query_store(state: _SessionState, store_identity: str) -> None:
    """Discard query state from the previously active canonical store."""

    previous = state.get(_ACTIVE_QUERY_STORE_KEY)
    if previous is not None and previous != store_identity:
        prefix = f"stored_query:{previous}:"
        for key in [str(value) for value in state if str(value).startswith(prefix)]:
            state.pop(key, None)
    state[_ACTIVE_QUERY_STORE_KEY] = store_identity


def _normalized_query_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Copy a projection into deterministic columns, row order, and RangeIndex."""

    normalized = frame.loc[:, sorted(str(column) for column in frame.columns)].copy()
    row_keys = [
        column
        for column in ("rollout_row_id", "step_row_id", "candidate_row_id", "target_row_id")
        if column in normalized
    ]
    if row_keys:
        normalized = normalized.sort_values(row_keys, kind="mergesort")
    return normalized.reset_index(drop=True)


def _evaluate_query_frame(frame: pd.DataFrame, expression: str) -> pd.DataFrame:
    """Evaluate one trusted-local pandas expression against a copied frame."""

    source = _normalized_query_frame(frame)
    if not expression.strip():
        return source
    result = source.query(
        expression,
        engine="python",
        local_dict={},
        global_dict={},
    )
    return result.loc[:, source.columns].copy().reset_index(drop=True)


def _clear_query_state(state: _SessionState, namespace: str) -> None:
    """Clear expression/result state without mutating rollout or step selection."""

    for name in (
        "draft_expression",
        "applied_expression",
        "last_valid_result",
        "last_error",
        "selected_result_row",
        "pending_promotion",
        "source_signature",
    ):
        state.pop(_query_key(namespace, name), None)


def _apply_query_state(
    state: _SessionState,
    namespace: str,
    source: pd.DataFrame,
) -> None:
    """Apply the draft expression, preserving the last valid result on error."""

    draft = str(state.get(_query_key(namespace, "draft_expression"), ""))
    try:
        result = _evaluate_query_frame(source, draft)
    except Exception as exc:
        state[_query_key(namespace, "last_error")] = f"{type(exc).__name__}: {exc}"
        return
    state[_query_key(namespace, "applied_expression")] = draft
    state[_query_key(namespace, "last_valid_result")] = result
    state[_query_key(namespace, "last_error")] = None
    state.pop(_query_key(namespace, "selected_result_row"), None)
    state.pop(_query_key(namespace, "pending_promotion"), None)


def _queue_query_promotion(namespace: str, payload: dict[str, int | None]) -> None:
    """Streamlit callback that writes only a pending promotion record."""

    st.session_state[_query_key(namespace, "pending_promotion")] = dict(payload)


def _apply_query_callback(namespace: str, source: pd.DataFrame) -> None:
    """Apply callback evaluated only after the operator presses Apply."""

    _apply_query_state(cast(_SessionState, st.session_state), namespace, source)


def _clear_query_callback(namespace: str, signature: str) -> None:
    """Clear callback that runs before expression/result widgets instantiate."""

    _clear_query_state(cast(_SessionState, st.session_state), namespace)
    st.session_state[_query_key(namespace, "source_signature")] = signature


def _consume_pending_promotion(
    state: _SessionState,
    namespace: str,
    *,
    rollout_ids: list[int],
    steps_by_rollout: dict[int, list[int]],
) -> str | None:
    """Validate and apply pending ids before rollout/step widgets instantiate."""

    pending_key = _query_key(namespace, "pending_promotion")
    pending = state.pop(pending_key, None)
    if not isinstance(pending, dict):
        return None
    try:
        rollout_id = int(pending["rollout_row_id"])
    except (KeyError, TypeError, ValueError):
        return "Pending query promotion has no valid rollout_row_id; prior selection was preserved."
    if rollout_id not in rollout_ids:
        return f"Pending query promotion references stale rollout_row_id={rollout_id}; prior selection was preserved."
    valid_steps = steps_by_rollout.get(rollout_id, [])
    if not valid_steps:
        return f"Pending query promotion rollout_row_id={rollout_id} has no persisted steps; prior selection was preserved."
    requested_step = pending.get("step_row_id")
    try:
        step_id = valid_steps[0] if requested_step is None else int(requested_step)
    except (TypeError, ValueError):
        return "Pending query promotion has no valid step_row_id; prior selection was preserved."
    if step_id not in valid_steps:
        return (
            f"Pending query promotion references stale step_row_id={step_id} for rollout_row_id={rollout_id}; "
            "prior selection was preserved."
        )
    state[_query_key(namespace, "rollout_widget")] = rollout_id
    state[_query_key(namespace, "step_widget")] = step_id
    return None


def _query_source_frame(
    session_handle: Any,
    *,
    scope: str,
    candidate_population: str,
    rollout_id: int,
    step_id: int,
    all_steps: pd.DataFrame,
) -> pd.DataFrame:
    """Return the normalized source projection for one explicit query grain."""

    if scope == "Rollout summaries":
        if all_steps.empty:
            return _normalized_query_frame(all_steps)
        endpoints = (
            all_steps.sort_values(["rollout_row_id", "step_index"], kind="mergesort")
            .groupby("rollout_row_id", as_index=False, sort=True)
            .tail(1)
        )
        return _normalized_query_frame(endpoints)
    if scope == "Factual steps":
        return _normalized_query_frame(all_steps)
    if scope != "Candidates":
        raise ValueError(f"Unsupported query scope: {scope}")
    if candidate_population == "Selected step":
        rows = session_handle.candidates(rollout_row_id=rollout_id, step_row_id=step_id)
    elif candidate_population == "Selected rollout":
        rows = session_handle.candidates(rollout_row_id=rollout_id)
    elif candidate_population == "Explicit full store":
        rows = session_handle.candidates()
    else:
        raise ValueError(f"Unsupported candidate population: {candidate_population}")
    return _normalized_query_frame(pd.DataFrame(rows))


def _query_source_signature(frame: pd.DataFrame) -> str:
    """Return a deterministic identity for the active immutable source population."""

    identifiers = [
        column for column in ("rollout_row_id", "step_row_id", "candidate_row_id") if column in frame.columns
    ]
    payload = "\0".join(frame.columns.astype(str).tolist()).encode("utf-8")
    if identifiers and not frame.empty:
        hashed = np.asarray(pd.util.hash_pandas_object(frame[identifiers], index=False).values)
        payload += hashed.tobytes()
    return hashlib.sha256(payload).hexdigest()


def _promotion_payload(row: pd.Series) -> dict[str, int | None]:
    """Extract exact owning rollout/step ids from one normalized query row."""

    rollout = row.get("rollout_row_id")
    step = row.get("step_row_id")
    return {
        "rollout_row_id": None if pd.isna(rollout) else int(rollout),
        "step_row_id": None if pd.isna(step) else int(step),
    }


def _render_query_workbench(
    namespace: str,
    source: pd.DataFrame,
    *,
    scope: str,
    candidate_population: str,
) -> None:
    """Render trusted-local pandas querying, complete export, and row promotion."""

    st.markdown("#### Query and promote evidence")
    st.caption(
        "Trusted local operator feature: the expression is evaluated only against a copied normalized DataFrame "
        'with `df.query(expression, engine="python")`. It is not a security sandbox and never mutates the store.'
    )
    st.caption(f"Available columns: {', '.join(f'`{column}`' for column in source.columns)}")
    st.caption(
        "Examples: `cumulative_target_root_gain > 0.5`, `selected_target_root_gain < 0`, "
        '`position == "lateral_target_bypass" and actor_action`, `root_distance_m > 1.0`.'
    )
    signature = _query_source_signature(source)
    signature_key = _query_key(namespace, "source_signature")
    if st.session_state.get(signature_key) not in (None, signature):
        _clear_query_state(cast(_SessionState, st.session_state), namespace)
    st.session_state[signature_key] = signature
    draft_key = _query_key(namespace, "draft_expression")
    st.text_area("Pandas query expression", key=draft_key, placeholder="Leave empty to match every row")
    col_apply, col_clear = st.columns(2)
    col_apply.button(
        "Apply query",
        key=_query_key(namespace, "apply"),
        type="primary",
        on_click=_apply_query_callback,
        args=(namespace, source),
    )
    col_clear.button(
        "Clear query",
        key=_query_key(namespace, "clear"),
        on_click=_clear_query_callback,
        args=(namespace, signature),
    )
    error = st.session_state.get(_query_key(namespace, "last_error"))
    if error:
        st.error(f"Query failed; the last valid result is preserved. {error}")
    result = st.session_state.get(_query_key(namespace, "last_valid_result"))
    result = source if result is None else result
    result = _normalized_query_frame(result)
    preview_limit = int(
        st.number_input(
            "Query preview row limit",
            min_value=1,
            max_value=10_000,
            value=200,
            step=50,
            key=_query_key(namespace, "preview_limit"),
        )
    )
    shown = result.head(preview_limit)
    applied = str(st.session_state.get(_query_key(namespace, "applied_expression"), ""))
    st.caption(
        f"Scope: {scope}; candidate population: {candidate_population}. Applied expression: {applied or '(empty)'}. "
        f"Input rows: {len(source):,}; matched rows: {len(result):,}; displayed rows: {len(shown):,}; "
        f"exported rows: {len(result):,}. Preview truncation never affects export."
    )
    st.dataframe(shown, hide_index=True, width="stretch")
    _download_frame("Download queried rows CSV", "stored-rollout-query.csv", result)
    if result.empty or "rollout_row_id" not in result:
        st.info("No matched row with a rollout_row_id is available for promotion.")
        return
    choices = result.index.astype(int).tolist()
    selection_key = _query_key(namespace, "selected_result_row")
    if st.session_state.get(selection_key) not in choices:
        st.session_state[selection_key] = choices[0]
    selected_index = int(
        st.selectbox(
            "Matched row to promote",
            options=choices,
            key=selection_key,
            format_func=lambda index: _query_row_label(_query_result_row(result, int(index))),
        )
    )
    payload = _promotion_payload(_query_result_row(result, selected_index))
    st.button(
        "Promote queried row",
        key=_query_key(namespace, "promote"),
        on_click=_queue_query_promotion,
        args=(namespace, payload),
        type="primary",
    )


def _query_result_row(frame: pd.DataFrame, index: int) -> pd.Series[Any]:
    """Return one query-result row with the runtime shape pandas guarantees."""

    row = frame.loc[index]
    if not isinstance(row, pd.Series):
        raise TypeError("query result row selection did not produce a pandas Series")
    return row


def _query_row_label(row: pd.Series[Any]) -> str:
    """Format stable ids for one query-result promotion choice."""

    fields = [
        f"{name}={int(row[name])}"
        for name in ("rollout_row_id", "step_row_id", "candidate_row_id")
        if name in row and not pd.isna(row[name])
    ]
    return " · ".join(fields)


def _render_inspect_export_rerun(
    session_handle: Any,
    *,
    store_path: Path,
    manifest_payload: dict[str, Any],
    paths: PathConfig,
    s2_recipe: ScientificReportConfig,
    s2_section_id: str,
    s2_recipe_label: str,
) -> None:
    st.subheader("Drill-down")
    store_identity = _canonical_query_store_identity(store_path)
    _activate_query_store(cast(_SessionState, st.session_state), store_identity)
    scope_key = f"stored_query:{store_identity}:scope"
    population_key = f"stored_query:{store_identity}:candidate_population"
    scope = st.selectbox("Query scope", options=_QUERY_SCOPES, key=scope_key)
    candidate_population = (
        st.selectbox("Candidate population", options=_CANDIDATE_POPULATIONS, key=population_key)
        if scope == "Candidates"
        else "not_applicable"
    )
    namespace = _query_namespace(store_identity, scope, candidate_population)

    rollout_ids = session_handle.rollout_ids()
    if not rollout_ids:
        st.warning("This store has no rollout rows to inspect or query.")
        return
    all_steps = pd.DataFrame(session_handle.steps())
    required_step_fields = {"rollout_row_id", "step_row_id"}
    missing_step_fields = sorted(required_step_fields.difference(all_steps.columns))
    if missing_step_fields:
        st.warning(
            "Drill-down is unavailable: the selected store does not expose the current factual step fields "
            f"({', '.join(missing_step_fields)}). Store validation and corpus summaries remain available."
        )
        return
    steps_by_rollout = {
        _integral_scalar(rollout): sorted(group["step_row_id"].astype(int).tolist())
        for rollout, group in all_steps.groupby("rollout_row_id", sort=True)
    }
    promotion_error = _consume_pending_promotion(
        cast(_SessionState, st.session_state),
        namespace,
        rollout_ids=[int(value) for value in rollout_ids],
        steps_by_rollout=steps_by_rollout,
    )
    if promotion_error:
        st.error(promotion_error)
    rollout_widget_key = _query_key(namespace, "rollout_widget")
    step_widget_key = _query_key(namespace, "step_widget")
    legacy_rollout = st.session_state.pop("stored_rollout_id", None)
    legacy_step = st.session_state.pop("stored_step_id", None)
    if legacy_rollout in rollout_ids:
        st.session_state[rollout_widget_key] = int(legacy_rollout)
        if legacy_step in steps_by_rollout.get(int(legacy_rollout), []):
            st.session_state[step_widget_key] = int(legacy_step)
    requested_rollout = st.session_state.get(rollout_widget_key)
    if requested_rollout not in rollout_ids:
        st.session_state[rollout_widget_key] = int(rollout_ids[0])
    rollout_id = int(
        st.selectbox(
            "Rollout row",
            rollout_ids,
            key=rollout_widget_key,
        )
    )
    steps = pd.DataFrame(session_handle.steps(rollout_row_id=rollout_id))
    step_ids = steps["step_row_id"].astype(int).tolist() if not steps.empty else []
    if not step_ids:
        st.warning("The selected rollout has no persisted steps.")
        return
    requested_step = st.session_state.get(step_widget_key)
    if requested_step not in step_ids:
        st.session_state[step_widget_key] = step_ids[0]
    step_id = int(st.selectbox("Step row", step_ids, key=step_widget_key))

    if scope == "Candidates" and candidate_population == "Explicit full store":
        st.warning(
            "Explicit full-store candidate query selected. This materializes the heavyweight normalized candidate audit; "
            "use Selected step or Selected rollout for routine inspection."
        )
    query_source = _query_source_frame(
        session_handle,
        scope=scope,
        candidate_population=candidate_population,
        rollout_id=rollout_id,
        step_id=step_id,
        all_steps=all_steps,
    )
    _render_query_workbench(
        namespace,
        query_source,
        scope=scope,
        candidate_population=candidate_population,
    )

    candidates = pd.DataFrame(
        session_handle.candidates(
            rollout_row_id=rollout_id,
            step_row_id=step_id,
        )
    )
    preview_limit = int(st.number_input("Candidate preview row limit", min_value=1, max_value=5000, value=200, step=25))
    shown = candidates.head(preview_limit)
    st.caption(
        f"Showing {len(shown):,} of {len(candidates):,} filtered candidate rows. Download contains all {len(candidates):,} rows."
    )
    st.dataframe(shown, hide_index=True, width="stretch")
    _download_frame(
        "Download selected-step candidate CSV", f"rollout-{rollout_id}-step-{step_id}-candidates.csv", candidates
    )

    depth_rows = pd.DataFrame(session_handle.depth_summary(rollout_row_id=rollout_id))
    selected_depth = depth_rows[depth_rows["step_row_id"] == step_id] if not depth_rows.empty else depth_rows
    with st.expander("Privileged selected-depth evaluation artifact", expanded=not selected_depth.empty):
        st.warning("Selected depth is privileged oracle/evaluation evidence, never actor-visible policy input.")
        if selected_depth.empty:
            st.info("No selected-depth row exists for this step.")
        else:
            st.dataframe(selected_depth, hide_index=True, width="stretch")
            preview = session_handle.selected_depth_preview(step_row_id=step_id)
            if bool(preview.get("available")):
                array = preview["depth_m"]
                fig = px.imshow(
                    np.asarray(array),
                    color_continuous_scale="Turbo",
                    labels={"color": "depth (m)"},
                    title="Selected-action mesh depth",
                )
                _render_plot(
                    fig,
                    ScientificExplanation(
                        question="Is the persisted selected-action depth artifact finite, aligned, and geometrically plausible?",
                        answer="This view checks one persisted selected-action depth artifact; display downsampling does not change the underlying row statistics.",
                        sections=(
                            ExplanationSection(
                                "Metric and units",
                                "Mesh depth is measured in metres; invalid pixels are masked and finite support is retained.",
                            ),
                            ExplanationSection(
                                "Denominator and comparison",
                                "The denominator is the finite valid-mask support in selected_depth. Compare only compatible camera calibration and depth representation.",
                            ),
                            ExplanationSection(
                                "Expected pattern and warning",
                                "Finite depth should align with the selected candidate and target crop. Missing or corrupt depth disables this view without erasing factual rollout rows.",
                            ),
                        ),
                        evidence_role="oracle/evaluation",
                        source_fields=(
                            "selected_depth/depth_m",
                            "selected_depth/valid_mask",
                            "steps/selected_candidate_row_id",
                        ),
                    ),
                )
            else:
                warning = str(preview.get("warning") or "not persisted")
                st.info(f"No selected-depth row is available for this step: {warning}")

    with st.expander("Metadata and advanced normalized tables"):
        st.json(manifest_payload, expanded=False)
        st.dataframe(steps, hide_index=True, width="stretch")
    _download_json("Download selected metadata JSON", f"rollout-{rollout_id}-metadata.json", manifest_payload)
    _render_q_h_evidence(
        session_handle,
        s2_recipe=s2_recipe,
        s2_section_id=s2_section_id,
        s2_recipe_label=s2_recipe_label,
    )
    _render_evidence_bundle_download(session_handle)
    _render_rerun_launcher(store_path=store_path, rollout_id=rollout_id, paths=paths)


def _render_evidence_bundle_download(session_handle: Any) -> None:
    st.markdown("#### Canonical evidence bundle")
    status = st.radio("Evidence status", options=["pilot", "confirmatory"], horizontal=True, key="evidence_status")
    acknowledge = st.checkbox(
        "I acknowledge that confirmatory status requires frozen protocols and matched evidence.",
        value=False,
        disabled=status != "confirmatory",
    )
    allowed = status == "pilot" or acknowledge
    if allowed:
        st.download_button(
            "Download deterministic evidence bundle",
            data=lambda: session_handle.evidence_bundle(status),
            file_name=f"rollout-evidence-{status}.json",
            mime="application/json",
            on_click="ignore",
            help="Built lazily on click, then cached by immutable store path and evidence status.",
        )
    else:
        st.info("Acknowledge the confirmatory evidence contract to enable this download.")


def _render_rerun_launcher(*, store_path: Path, rollout_id: int, paths: PathConfig) -> None:
    st.markdown("#### Rerun launch")
    base_config = st.text_input(
        "Rerun inspector config",
        value=str(paths.root / ".configs" / "rerun_offline.toml"),
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
        overrides: Mapping[RolloutLayerName | str, Mapping[str, bool]]
        mutable_overrides: dict[RolloutLayerName | str, Mapping[str, bool]] = {}
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
            mutable_overrides[layer] = {"included": included, "visible": bool(visible and included)}
        overrides = mutable_overrides

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
            if previous is not None and previous.process.poll() is None:
                stop_rerun_launch(previous)
            url = (
                rerun_web_url(web_viewer_port=web_port, ws_server_port=grpc_port, lan=lan)
                if mode is RerunLaunchMode.serve_web
                else None
            )
            handle = start_rerun_launch(
                command,
                artifact_dir=artifact_dir,
                config_path=resolved.config_path,
                rrd_path=None if mode is RerunLaunchMode.native_live else save_path,
                url=url,
            )
            st.session_state[_LAUNCH_HANDLE_KEY] = handle
        except Exception as exc:
            _report_exception(exc, context="Rerun launch failed")

    handle = st.session_state.get(_LAUNCH_HANDLE_KEY)
    if handle is not None:
        verify_url = handle.url is not None
        status = poll_rerun_launch(handle, verify_url=verify_url)
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
                st.session_state[_LAUNCH_HANDLE_KEY] = restart_rerun_launch(handle)
            except Exception as exc:
                _report_exception(exc, context="Rerun restart failed")
            else:
                st.rerun()
        if col_stop.button("Stop Rerun"):
            stop_rerun_launch(handle)
            st.session_state.pop(_LAUNCH_HANDLE_KEY, None)
            st.rerun()
