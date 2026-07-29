"""Automatic reconstruction, return, and temporal rollout evidence."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from ....rollouts.inspection import (
    reconstruction_endpoint_rows,
    reconstruction_endpoint_summary_rows,
    reconstruction_metric_summary_rows,
    temporal_metric_summary_rows,
)
from .session import StoredRolloutSession
from .shared import _download_frame, _info_popover, _render_plot

_METRIC_FAMILIES = {
    "Cumulative reconstruction": (
        "cumulative_target_root_gain",
        "cumulative_target_rri",
    ),
    "Selected one-step evidence": (
        "selected_target_root_gain",
        "selected_target_rri",
    ),
    "Selection distribution": (
        "selected_probability",
        "selected_entropy",
    ),
}

_RECONSTRUCTION_INFO = r"""
For target-cropped reconstruction error \(\Delta_t^e\), the selected one-step
root gain and state-relative RRI are

$$
r_{t,\mathrm{root}}^e=\frac{\Delta_t^e-\Delta_{t+1}^e}{\Delta_0^e+\varepsilon},
\qquad
\mathrm{RRI}_{t,\mathrm{state}}^e=\frac{\Delta_t^e-\Delta_{t+1}^e}{\Delta_t^e+\varepsilon}.
$$

The cumulative root-normalized gain is the primary comparable reconstruction
quantity. Target RRI remains a state-relative diagnostic. Selected probability
and policy entropy explain how concentrated the persisted actor decision was;
they do not establish causal policy superiority. Negative finite gain is poor
but valid evidence. Invalidity is a separate mask/reason contract and is shown
only in **Validity & Support**.
"""


def _filter_rows(steps: pd.DataFrame) -> pd.DataFrame:
    """Apply optional display filters without changing the fixed metric plan."""

    columns = st.columns(3)
    selected: dict[str, list[object]] = {}
    for column, field, label in zip(
        columns,
        ("scene", "policy", "horizon"),
        ("Scenes", "Policies", "Horizons"),
        strict=True,
    ):
        if field not in steps:
            continue
        options = sorted(steps[field].dropna().unique().tolist(), key=str)
        selected[field] = column.multiselect(label, options=options, default=options)
    filtered = steps
    for field, values in selected.items():
        filtered = filtered.loc[filtered[field].isin(values)]
    return filtered


def _metric_plan(summary: pd.DataFrame) -> dict[str, str]:
    return {str(row.metric): str(row.label) for row in summary.itertuples() if int(row.finite_count) > 0}


def _numeric_value(row: dict[str, object], field: str) -> float:
    """Return one required numeric summary value with an explicit type boundary."""

    value = row[field]
    if not isinstance(value, (int, float)):
        raise TypeError(f"Temporal summary field {field!r} is not numeric: {value!r}")
    return float(value)


def _temporal_small_multiples(rows: list[dict[str, object]], labels: dict[str, str]) -> None:
    """Render every available metric under exact policy-by-horizon strata."""

    for family, metrics in _METRIC_FAMILIES.items():
        family_rows: list[dict[str, object]] = []
        for metric in metrics:
            if metric not in labels:
                continue
            for row in temporal_metric_summary_rows(rows, metric=metric, group_fields=("policy", "horizon")):
                family_rows.append(
                    {
                        **row,
                        "metric_label": labels[metric],
                        "policy × horizon": f"{row.get('policy')} × H={row.get('horizon')}",
                        "iqr_plus": (
                            None
                            if row.get("median") is None
                            else _numeric_value(row, "q75") - _numeric_value(row, "median")
                        ),
                        "iqr_minus": (
                            None
                            if row.get("median") is None
                            else _numeric_value(row, "median") - _numeric_value(row, "q25")
                        ),
                    }
                )
        frame = pd.DataFrame(family_rows)
        if frame.empty:
            continue
        st.markdown(f"#### {family}")
        figure = px.line(
            frame,
            x="step_index",
            y="median",
            color="policy × horizon",
            facet_row="metric_label",
            markers=True,
            error_y="iqr_plus",
            error_y_minus="iqr_minus",
            hover_data=("finite_count", "missing_count", "mean", "min", "max"),
            title=f"{family}: median and IQR by factual depth",
        )
        figure.update_yaxes(matches=None)
        _render_plot(figure)


def _endpoint_evidence(rows: list[dict[str, object]], labels: dict[str, str]) -> None:
    endpoints = pd.DataFrame(reconstruction_endpoint_rows(rows))
    if endpoints.empty:
        return
    available = [metric for metrics in _METRIC_FAMILIES.values() for metric in metrics if metric in labels]
    if not available:
        return
    long = endpoints.melt(
        id_vars=[field for field in ("rollout_row_id", "scene", "policy", "horizon") if field in endpoints],
        value_vars=available,
        var_name="metric",
        value_name="endpoint_value",
    ).dropna(subset=["endpoint_value"])
    long["metric_label"] = long["metric"].map(labels)
    long["policy × horizon"] = long.apply(lambda row: f"{row.get('policy')} × H={row.get('horizon')}", axis=1)
    figure = px.histogram(
        long,
        x="endpoint_value",
        color="policy × horizon",
        facet_row="metric_label",
        marginal="box",
        barmode="overlay",
        opacity=0.55,
        title="Factual endpoint distributions",
    )
    figure.update_xaxes(matches=None)
    _render_plot(figure)

    endpoint_summary = pd.DataFrame(reconstruction_endpoint_summary_rows(rows))
    st.markdown("#### Endpoint policy × horizon summary")
    st.dataframe(endpoint_summary, hide_index=True, width="stretch")
    _download_frame("Download endpoint summary CSV", "reconstruction-endpoints.csv", endpoint_summary)


def _raw_rollout_drilldown(steps: pd.DataFrame, labels: dict[str, str]) -> None:
    rollout_ids = sorted(int(value) for value in steps["rollout_row_id"].dropna().unique().tolist())
    if not rollout_ids:
        return
    with st.expander("Raw factual rollout drill-down", expanded=False):
        rollout_row_id = st.selectbox("Rollout", options=rollout_ids, key="reconstruction_raw_rollout")
        selected = steps.loc[steps["rollout_row_id"] == rollout_row_id].sort_values("step_index")
        metrics = [metric for metrics in _METRIC_FAMILIES.values() for metric in metrics if metric in labels]
        long = selected.melt(
            id_vars=[field for field in ("rollout_row_id", "step_row_id", "step_index", "policy") if field in selected],
            value_vars=metrics,
            var_name="metric",
            value_name="value",
        ).dropna(subset=["value"])
        long["metric_label"] = long["metric"].map(labels)
        figure = px.line(
            long,
            x="step_index",
            y="value",
            facet_row="metric_label",
            markers=True,
            hover_data=("step_row_id", "policy"),
            title=f"All persisted quantities for rollout {rollout_row_id}",
        )
        figure.update_yaxes(matches=None)
        _render_plot(figure)
        st.dataframe(selected, hide_index=True, width="stretch")


def render(session: StoredRolloutSession) -> None:
    """Render automatic all-metric reconstruction evidence."""

    st.subheader("Reconstruction & Return")
    _info_popover("Reconstruction and return theory", _RECONSTRUCTION_INFO)
    steps = pd.DataFrame(session.steps())
    if steps.empty:
        st.info("No factual rollout steps are available.")
        return
    filtered = _filter_rows(steps)
    if filtered.empty:
        st.info("The optional display filters exclude every factual step.")
        return
    rows = filtered.to_dict("records")
    summary = pd.DataFrame(reconstruction_metric_summary_rows(rows))
    labels = _metric_plan(summary)
    if not labels:
        st.info("None of the six reconstruction/selection quantities is finite in this store.")
        return

    st.caption(
        "Every available quantity is shown automatically. Curves and endpoint summaries use exact policy × horizon strata; "
        "scene, policy, and horizon controls only filter the displayed population."
    )
    st.dataframe(summary, hide_index=True, width="stretch")
    _download_frame("Download all-metric summary CSV", "reconstruction-metric-summary.csv", summary)
    _temporal_small_multiples(rows, labels)
    _endpoint_evidence(rows, labels)
    _raw_rollout_drilldown(filtered, labels)
    _download_frame("Download factual selected-chain CSV", "selected-chain-evidence.csv", filtered)


__all__ = ["render"]
