"""Read-only Optuna study exploration for local sweep databases.

The panel provides objective traces, parameter effects and interactions,
bootstrap evidence, importance estimates, and duplicate-configuration audits.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

try:  # Optional dependency for Optuna diagnostics.
    import optuna  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - optional dependency guard
    optuna = None

from ...configs import OptunaConfig, PathConfig
from .common import _info_popover, _pretty_label, _report_exception

_CACHE_TTL_S = 120


def _safe_key(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]+", "_", value).strip("_")


def _normalize_param_value(value: Any) -> Any:
    """Normalize Optuna param values for dataframe storage."""
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (dict, list, tuple, set)):
        return str(value)
    return value


def _infer_param_kind(series: pd.Series, *, max_categories: int = 12) -> str:
    """Infer whether a parameter should be plotted as numeric or categorical."""
    data = series.dropna()
    if data.empty:
        return "empty"
    if data.dtype == bool:
        return "categorical"

    numeric = pd.to_numeric(data, errors="coerce")
    numeric_ratio = float(np.isfinite(numeric).mean())
    unique = int(data.nunique(dropna=True))
    if unique <= max_categories:
        return "categorical"
    if numeric_ratio >= 0.8:
        return "numeric"
    return "categorical"


def _select_param_columns(df: pd.DataFrame) -> list[str]:
    return sorted(col for col in df.columns if col.startswith("param."))


def _coerce_numeric(series: pd.Series) -> pd.Series:
    """Convert a series to numeric values when possible."""
    numeric = pd.to_numeric(series, errors="coerce")
    return numeric


def _bin_numeric_series(series: pd.Series, *, bins: int) -> pd.Series:
    """Bin numeric values into quantile-based bins for interaction plots."""
    numeric = _coerce_numeric(series)
    numeric = numeric[np.isfinite(numeric)]
    if numeric.empty:
        return pd.Series([], dtype=str)
    quantiles = np.linspace(0.0, 1.0, num=max(bins, 2))
    edges = np.unique(np.nanquantile(numeric, quantiles))
    if edges.size < 2:
        return pd.Series(["all"] * len(series), index=series.index, dtype=str)
    binned = pd.cut(
        _coerce_numeric(series),
        bins=edges,
        include_lowest=True,
    )
    return binned.astype(str)


def _bucket_param(series: pd.Series, *, bins: int) -> pd.Series:
    """Bucket a parameter series as numeric bins or categorical values."""
    kind = _infer_param_kind(series)
    if kind == "numeric":
        return _bin_numeric_series(series, bins=bins)
    return series.astype(str)


@st.cache_data(ttl=_CACHE_TTL_S)
def _list_optuna_db_paths(optuna_dir: Path) -> list[Path]:
    if not optuna_dir.exists():
        return []
    return sorted(
        optuna_dir.glob("*.db"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


@st.cache_data(ttl=_CACHE_TTL_S)
def _list_study_names(storage_uri: str) -> list[str]:
    if optuna is None:
        return []
    try:
        summaries = optuna.study.get_all_study_summaries(storage=storage_uri)
    except Exception:
        return []
    return sorted({summary.study_name for summary in summaries})


@st.cache_data(ttl=_CACHE_TTL_S)
def _load_trials(storage_uri: str, study_name: str) -> pd.DataFrame:
    if optuna is None:
        return pd.DataFrame()
    study = optuna.load_study(study_name=study_name, storage=storage_uri)
    rows: list[dict[str, Any]] = []
    for trial in study.trials:
        params = {f"param.{key}": _normalize_param_value(value) for key, value in (trial.params or {}).items()}
        rows.append(
            {
                "trial": trial.number,
                "state": trial.state.name,
                "value": trial.value,
                "datetime_start": trial.datetime_start,
                "datetime_complete": trial.datetime_complete,
                "duration_s": trial.duration.total_seconds() if trial.duration else None,
                "metric_source": trial.user_attrs.get("metric_source"),
                "config_correction": trial.user_attrs.get("config_correction"),
                "n_params": len(params),
                **params,
            },
        )
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows).sort_values("trial").reset_index(drop=True)
    return df


def _objective_summary(df: pd.DataFrame, *, direction: str) -> dict[str, float]:
    values = pd.to_numeric(df["value"], errors="coerce")
    values = values[np.isfinite(values)]
    if values.empty:
        return {"best": float("nan"), "mean": float("nan"), "median": float("nan")}
    best = float(values.min()) if direction == "minimize" else float(values.max())
    return {
        "best": best,
        "mean": float(values.mean()),
        "median": float(values.median()),
    }


def _plot_objective_over_trials(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        return go.Figure()
    values = pd.to_numeric(df["value"], errors="coerce")
    mean_value = float(values[np.isfinite(values)].mean()) if np.isfinite(values).any() else float("nan")
    fig = px.scatter(
        df,
        x="trial",
        y="value",
        color="state",
        hover_data=["trial", "state", "value", "metric_source"],
        title="Objective by trial",
    )
    if np.isfinite(mean_value):
        x_min = float(df["trial"].min())
        x_max = float(df["trial"].max())
        fig.add_shape(
            type="line",
            x0=x_min,
            x1=x_max,
            y0=mean_value,
            y1=mean_value,
            line={"color": "#444444", "width": 2, "dash": "dash"},
        )
        fig.add_annotation(
            x=x_max,
            y=mean_value,
            xanchor="left",
            yanchor="bottom",
            text=f"mean={mean_value:.4f}",
            showarrow=False,
            font={"size": 10, "color": "#444444"},
        )
    fig.update_layout(xaxis_title="Trial", yaxis_title="Objective")
    return fig


def _plot_param_effect(
    df: pd.DataFrame,
    *,
    param: str,
) -> tuple[go.Figure, pd.DataFrame, dict[str, float] | None]:
    if df.empty or param not in df.columns:
        return go.Figure(), pd.DataFrame(), None

    data = df[["trial", "state", "value", param]].copy()
    data = data[pd.notna(data[param])]
    if data.empty:
        return go.Figure(), pd.DataFrame(), None

    kind = _infer_param_kind(data[param])
    values = pd.to_numeric(data["value"], errors="coerce")
    mean_value = float(values[np.isfinite(values)].mean()) if np.isfinite(values).any() else float("nan")

    if kind == "numeric":
        numeric = pd.to_numeric(data[param], errors="coerce")
        data = data[np.isfinite(numeric)]
        data = data.assign(param_numeric=numeric.loc[data.index])
        fig = px.scatter(
            data,
            x="param_numeric",
            y="value",
            color="state",
            hover_data=["trial", param],
            title=f"Objective vs {param}",
        )
        fig.update_layout(xaxis_title=_pretty_label(param))
        if np.isfinite(mean_value):
            x_min = float(data["param_numeric"].min())
            x_max = float(data["param_numeric"].max())
            fig.add_shape(
                type="line",
                x0=x_min,
                x1=x_max,
                y0=mean_value,
                y1=mean_value,
                line={"color": "#444444", "width": 2, "dash": "dash"},
            )
            fig.add_annotation(
                x=x_max,
                y=mean_value,
                xanchor="left",
                yanchor="bottom",
                text=f"mean={mean_value:.4f}",
                showarrow=False,
                font={"size": 10, "color": "#444444"},
            )
        summary = data.groupby(param, dropna=True)["value"].agg(["count", "mean", "median"]).reset_index()
        reg_stats = None
        if len(data) >= 2:
            x_vals = data["param_numeric"].to_numpy(dtype=float)
            y_vals = pd.to_numeric(data["value"], errors="coerce").to_numpy(dtype=float)
            mask = np.isfinite(x_vals) & np.isfinite(y_vals)
            if np.count_nonzero(mask) >= 2:
                slope, intercept = np.polyfit(x_vals[mask], y_vals[mask], 1)
                y_hat = slope * x_vals[mask] + intercept
                ss_res = float(np.sum((y_vals[mask] - y_hat) ** 2))
                ss_tot = float(np.sum((y_vals[mask] - np.mean(y_vals[mask])) ** 2))
                r2 = float("nan") if ss_tot == 0 else 1.0 - ss_res / ss_tot
                reg_stats = {"slope": float(slope), "intercept": float(intercept), "r2": float(r2)}
        return fig, summary, reg_stats

    data = data.assign(param_cat=data[param].astype(str))
    fig = px.strip(
        data,
        x="param_cat",
        y="value",
        color="state",
        hover_data=["trial", param],
        title=f"Objective vs {param}",
    )
    fig.update_layout(xaxis_title=_pretty_label(param))
    summary = (
        data.groupby("param_cat", dropna=True)["value"]
        .agg(["count", "mean", "median", "min", "max"])
        .reset_index()
        .rename(columns={"param_cat": param})
    )
    if not summary.empty:
        fig.add_trace(
            go.Scatter(
                x=summary[param],
                y=summary["mean"],
                mode="markers+text",
                text=[f"{val:.4f}" for val in summary["mean"]],
                textposition="top center",
                marker={"color": "#222222", "size": 9, "symbol": "diamond"},
                name="mean",
                showlegend=False,
            ),
        )
    return fig, summary, None


def _cliffs_delta(a: np.ndarray, b: np.ndarray) -> float:
    """Compute Cliff's delta effect size (positive if a > b)."""
    if a.size == 0 or b.size == 0:
        return float("nan")
    a = a.reshape(-1, 1)
    b = b.reshape(1, -1)
    greater = np.sum(a > b)
    less = np.sum(a < b)
    denom = float(a.size * b.size)
    return float((greater - less) / denom) if denom > 0 else float("nan")


def _bootstrap_diff(
    a: np.ndarray,
    b: np.ndarray,
    *,
    stat_fn: Callable[[np.ndarray], float],
    n_boot: int = 500,
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    """Bootstrap distribution of stat_fn(a) - stat_fn(b)."""
    if a.size == 0 or b.size == 0:
        return np.array([], dtype=float)
    if rng is None:
        rng = np.random.default_rng(0)
    boot = np.empty(n_boot, dtype=float)
    for i in range(n_boot):
        a_sample = rng.choice(a, size=a.size, replace=True)
        b_sample = rng.choice(b, size=b.size, replace=True)
        boot[i] = stat_fn(a_sample) - stat_fn(b_sample)
    return boot


def _bootstrap_slope(
    x: np.ndarray,
    y: np.ndarray,
    *,
    n_boot: int = 500,
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    """Bootstrap distribution of linear slope."""
    if x.size == 0 or y.size == 0 or x.size != y.size:
        return np.array([], dtype=float)
    if rng is None:
        rng = np.random.default_rng(0)
    n = x.size
    boot = np.empty(n_boot, dtype=float)
    for i in range(n_boot):
        idx = rng.choice(n, size=n, replace=True)
        boot[i] = np.polyfit(x[idx], y[idx], 1)[0]
    return boot


def _spearman_rho(x: np.ndarray, y: np.ndarray) -> float:
    """Compute Spearman rank correlation without scipy."""
    if x.size == 0 or y.size == 0 or x.size != y.size:
        return float("nan")
    rx = pd.Series(x).rank().to_numpy()
    ry = pd.Series(y).rank().to_numpy()
    if np.std(rx) == 0 or np.std(ry) == 0:
        return float("nan")
    return float(np.corrcoef(rx, ry)[0, 1])


def _evidence_overview(
    df: pd.DataFrame,
    *,
    param_cols: list[str],
    direction: str,
) -> pd.DataFrame:
    """Compute lightweight evidence metrics for all parameters."""
    rows: list[dict[str, Any]] = []
    direction = direction.lower()
    for param in param_cols:
        series = df[param]
        kind = _infer_param_kind(series)
        data = df[["value", param]].copy()
        data = data[pd.notna(data[param])]
        if data.empty:
            continue

        if kind == "categorical":
            stats = (
                data.groupby(param)["value"]
                .agg(["count", "mean", "std", "median"])
                .sort_values("mean", ascending=(direction == "minimize"))
            )
            if stats.shape[0] < 2:
                continue
            best_value = stats.index[0]
            runner_value = stats.index[1]
            best_mean = float(stats.loc[best_value, "mean"])
            runner_mean = float(stats.loc[runner_value, "mean"])
            n_best = int(stats.loc[best_value, "count"])
            n_runner = int(stats.loc[runner_value, "count"])
            best_std = float(stats.loc[best_value, "std"]) if np.isfinite(stats.loc[best_value, "std"]) else 0.0
            runner_std = float(stats.loc[runner_value, "std"]) if np.isfinite(stats.loc[runner_value, "std"]) else 0.0
            se = float(np.sqrt((best_std**2) / max(n_best, 1) + (runner_std**2) / max(n_runner, 1)))
            if direction == "minimize":
                diff_mean = runner_mean - best_mean
            else:
                diff_mean = best_mean - runner_mean
            z = diff_mean / se if se > 0 else float("nan")
            ci_low = diff_mean - 1.96 * se if se > 0 else float("nan")
            ci_high = diff_mean + 1.96 * se if se > 0 else float("nan")

            a = pd.to_numeric(data.loc[data[param] == best_value, "value"], errors="coerce").dropna().to_numpy()
            b = pd.to_numeric(data.loc[data[param] == runner_value, "value"], errors="coerce").dropna().to_numpy()
            cliff = _cliffs_delta(a, b)
            if direction == "minimize":
                cliff = -cliff

            rows.append(
                {
                    "param": param,
                    "kind": kind,
                    "n_total": int(data.shape[0]),
                    "best_value": str(best_value),
                    "runner_value": str(runner_value),
                    "n_best": n_best,
                    "n_runner": n_runner,
                    "best_mean": best_mean,
                    "runner_mean": runner_mean,
                    "diff_mean": float(diff_mean),
                    "evidence_z": float(z),
                    "ci_low": float(ci_low),
                    "ci_high": float(ci_high),
                    "cliffs_delta": float(cliff),
                },
            )
        elif kind == "numeric":
            numeric = pd.to_numeric(data[param], errors="coerce")
            mask = np.isfinite(numeric.to_numpy()) & np.isfinite(pd.to_numeric(data["value"], errors="coerce"))
            if np.count_nonzero(mask) < 3:
                continue
            x = numeric.to_numpy()[mask]
            y = pd.to_numeric(data["value"], errors="coerce").to_numpy()[mask]
            slope, intercept = np.polyfit(x, y, 1)
            residuals = y - (slope * x + intercept)
            s_err = float(np.sqrt(np.sum(residuals**2) / max(x.size - 2, 1)))
            x_var = float(np.sum((x - np.mean(x)) ** 2))
            slope_se = s_err / np.sqrt(x_var) if x_var > 0 else float("nan")
            slope_dir = -slope if direction == "minimize" else slope
            z = slope_dir / slope_se if np.isfinite(slope_se) and slope_se > 0 else float("nan")
            ci_low = slope_dir - 1.96 * slope_se if np.isfinite(slope_se) else float("nan")
            ci_high = slope_dir + 1.96 * slope_se if np.isfinite(slope_se) else float("nan")
            rho = _spearman_rho(x, y)
            rho_dir = -rho if direction == "minimize" else rho
            rows.append(
                {
                    "param": param,
                    "kind": kind,
                    "n_total": int(x.size),
                    "slope": float(slope),
                    "slope_dir": float(slope_dir),
                    "slope_se": float(slope_se),
                    "evidence_z": float(z),
                    "ci_low": float(ci_low),
                    "ci_high": float(ci_high),
                    "spearman_rho": float(rho),
                    "spearman_rho_dir": float(rho_dir),
                },
            )

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def _plot_objective_distribution(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        return go.Figure()
    fig = px.violin(
        df,
        x="state",
        y="value",
        box=True,
        points="all",
        color="state",
        title="Objective distribution by state",
    )
    fig.update_layout(xaxis_title="State", yaxis_title="Objective")
    return fig


def _plot_param_importance(study: Any, df: pd.DataFrame) -> tuple[go.Figure, pd.DataFrame]:
    if optuna is None:
        return go.Figure(), pd.DataFrame()
    if df.empty:
        return go.Figure(), pd.DataFrame()
    try:
        importance = optuna.importance.get_param_importances(study)
    except Exception:
        return go.Figure(), pd.DataFrame()
    if not importance:
        return go.Figure(), pd.DataFrame()
    imp_df = (
        pd.DataFrame({"param": list(importance.keys()), "importance": list(importance.values())})
        .sort_values("importance", ascending=False)
        .reset_index(drop=True)
    )
    fig = px.bar(
        imp_df,
        x="importance",
        y="param",
        orientation="h",
        title="Optuna parameter importance",
    )
    fig.update_layout(yaxis_title="Parameter", xaxis_title="Importance")
    return fig, imp_df


def _interaction_matrix(
    df: pd.DataFrame,
    *,
    param_x: str,
    param_y: str,
    bins: int,
    agg: Callable[[pd.Series], float],
) -> pd.DataFrame:
    if df.empty or param_x not in df.columns or param_y not in df.columns:
        return pd.DataFrame()
    data = df[["value", param_x, param_y]].copy()
    data = data[pd.notna(data[param_x]) & pd.notna(data[param_y])]
    if data.empty:
        return pd.DataFrame()
    data["x_bucket"] = _bucket_param(data[param_x], bins=bins)
    data["y_bucket"] = _bucket_param(data[param_y], bins=bins)
    pivot = data.pivot_table(
        values="value",
        index="y_bucket",
        columns="x_bucket",
        aggfunc=agg,
        dropna=False,
    )
    return pivot


def _plot_interaction_heatmap(pivot: pd.DataFrame, *, param_x: str, param_y: str) -> go.Figure:
    if pivot.empty:
        return go.Figure()
    fig = px.imshow(
        pivot,
        labels={"x": _pretty_label(param_x), "y": _pretty_label(param_y), "color": "Objective"},
        title=f"Interaction: {param_x} × {param_y}",
        text_auto=True,
        aspect="auto",
    )
    fig.update_xaxes(side="top")
    return fig


def _duplicate_configs(df: pd.DataFrame, *, params: list[str]) -> pd.DataFrame:
    if df.empty or not params:
        return pd.DataFrame()
    subset = df[["trial", "value", *params]].copy()
    for param in params:
        subset[param] = subset[param].astype(str)
    subset["signature"] = subset[params].agg("|".join, axis=1)
    grouped = (
        subset.groupby("signature", as_index=False)
        .agg(count=("trial", "count"), mean_value=("value", "mean"), median_value=("value", "median"))
        .sort_values("count", ascending=False)
    )
    grouped = grouped[grouped["count"] > 1]
    return grouped.reset_index(drop=True)


def render_optuna_sweep_page() -> None:
    """Render read-only objective and parameter diagnostics for one study."""

    st.header("Optuna Studies")
    _info_popover(
        "optuna sweep",
        "Inspect Optuna trial objectives and visualize how swept hyperparameters "
        "affect performance. Use this panel to spot impactful toggles and "
        "debug unexpected trial outcomes.",
    )

    if optuna is None:
        st.warning("Optuna is not installed. Install `optuna` to use this panel.")
        return

    paths = PathConfig()
    default_study = OptunaConfig().study_name
    db_paths = _list_optuna_db_paths(paths.optuna)
    db_labels = ["(custom)"] + [path.name for path in db_paths]
    default_db = db_paths[0].name if db_paths else "(custom)"

    with st.sidebar.form("optuna_sweep_form"):
        st.subheader("Optuna study")
        db_choice = st.selectbox(
            "Optuna DB",
            options=db_labels,
            index=db_labels.index(default_db) if default_db in db_labels else 0,
        )
        custom_db = ""
        if db_choice == "(custom)":
            custom_db = st.text_input(
                "Custom DB path",
                value=str(paths.optuna / f"{default_study}.db"),
            )
            db_path = Path(custom_db).expanduser()
        else:
            db_path = (paths.optuna / db_choice).expanduser()
        storage_uri = f"sqlite:///{db_path.resolve().as_posix()}"

        study_names = _list_study_names(storage_uri)
        study_choice = st.selectbox(
            "Study name",
            options=study_names or [default_study],
            index=study_names.index(default_study) if default_study in study_names else 0,
        )
        state_filter = st.multiselect(
            "States",
            options=["COMPLETE", "PRUNED", "FAIL", "RUNNING", "WAITING"],
            default=["COMPLETE", "PRUNED"],
        )
        show_non_finite = st.checkbox("Show non-finite objectives", value=False)
        run_panel = st.form_submit_button("Load sweep")

    trial_query = st.sidebar.text_input(
        "Trial filter (pandas query)",
        value=str(st.session_state.get("optuna_trial_query", "")),
        help="Example: trial > 23 and value < 0.73. Use backticks for column names with dots.",
    )
    st.session_state["optuna_trial_query"] = trial_query

    cache_key = "|".join(
        [
            storage_uri,
            study_choice,
            ",".join(sorted(state_filter)),
            str(bool(show_non_finite)),
        ],
    )
    key_prefix = _safe_key(cache_key or "optuna")
    cache_df_key = "optuna_sweep_df"
    cache_sig_key = "optuna_sweep_sig"

    df: pd.DataFrame | None = None
    if run_panel:
        try:
            df = _load_trials(storage_uri, study_choice)
        except Exception as exc:  # pragma: no cover - UI guard
            _report_exception(exc, context="Failed to load Optuna study")
            return
        st.session_state[cache_df_key] = df
        st.session_state[cache_sig_key] = cache_key
    else:
        cached_sig = st.session_state.get(cache_sig_key)
        if cached_sig == cache_key:
            cached_df = st.session_state.get(cache_df_key)
            if isinstance(cached_df, pd.DataFrame):
                df = cached_df

    if df is None:
        st.caption("Select a study and click 'Load sweep' to view results.")
        return

    if df.empty:
        st.warning("No trials found in the selected study.")
        return

    df = df.copy()
    if state_filter:
        df = df[df["state"].isin(state_filter)]
    if not show_non_finite:
        df = df[np.isfinite(pd.to_numeric(df["value"], errors="coerce"))]
    if trial_query.strip():
        try:
            df = df.query(trial_query, engine="python")
        except Exception as exc:  # pragma: no cover - UI guard
            st.warning(f"Invalid query '{trial_query}': {exc}")

    direction = "minimize"
    try:
        study = optuna.load_study(study_name=study_choice, storage=storage_uri)
        direction = str(study.direction.name).lower()
    except Exception:
        direction = "minimize"

    param_cols = _select_param_columns(df)
    param_cols_vary = [col for col in param_cols if df[col].nunique(dropna=True) > 1]
    if not param_cols:
        st.info("No parameter columns detected in this study.")
        return

    summary = _objective_summary(df, direction=direction)
    tabs = st.tabs(
        [
            "Overview",
            "Parameter effects",
            "Interactions",
            "Importance",
            "Duplicates",
            "Trial table",
        ],
    )

    with tabs[0]:
        col1, col2, col3 = st.columns(3)
        col1.metric("Trials", int(df.shape[0]))
        col2.metric("Best objective", f"{summary['best']:.4f}" if np.isfinite(summary["best"]) else "n/a")
        col3.metric("Median objective", f"{summary['median']:.4f}" if np.isfinite(summary["median"]) else "n/a")

        st.plotly_chart(
            _plot_objective_over_trials(df),
            width="stretch",
            key=f"{key_prefix}_objective",
        )
        st.plotly_chart(
            _plot_objective_distribution(df),
            width="stretch",
            key=f"{key_prefix}_distribution",
        )

        st.subheader("Top trials")
        top_k = st.number_input(
            "Top-K trials",
            min_value=3,
            max_value=50,
            value=min(10, int(df.shape[0])),
            step=1,
        )
        best_df = df.sort_values("value", ascending=(direction == "minimize")).head(int(top_k))
        st.dataframe(
            best_df[["trial", "state", "value", "metric_source", "config_correction"]],
            width="stretch",
        )

    with tabs[1]:
        st.subheader("Parameter effects")
        if param_cols_vary:
            st.caption("Evidence overview (fast, approximate). Use the per-parameter view for bootstrap details.")
            col_a, col_b, col_c = st.columns(3)
            min_group = col_a.number_input("Min trials per group", min_value=2, max_value=30, value=8, step=1)
            z_thresh = col_b.number_input("Evidence threshold (|z|)", min_value=0.5, max_value=5.0, value=2.0, step=0.5)
            show_only_strong = col_c.checkbox("Show only strong evidence", value=False)

            evidence_df = _evidence_overview(df, param_cols=param_cols_vary, direction=direction)
            if not evidence_df.empty:
                evidence_df = evidence_df.copy()
                evidence_df["ci_positive"] = evidence_df["ci_low"] > 0
                evidence_df["min_group_ok"] = True
                mask_min = evidence_df["kind"] == "categorical"
                evidence_df.loc[mask_min, "min_group_ok"] = (evidence_df.loc[mask_min, "n_best"] >= min_group) & (
                    evidence_df.loc[mask_min, "n_runner"] >= min_group
                )
                evidence_df.loc[~mask_min, "min_group_ok"] = evidence_df.loc[~mask_min, "n_total"] >= min_group
                evidence_df["strong_evidence"] = (
                    evidence_df["min_group_ok"]
                    & evidence_df["ci_positive"]
                    & (evidence_df["evidence_z"].abs() >= float(z_thresh))
                )
                if show_only_strong:
                    evidence_df = evidence_df[evidence_df["strong_evidence"]]
                evidence_df = evidence_df.sort_values("evidence_z", ascending=False)
                st.dataframe(evidence_df, width="stretch")
                if not evidence_df.empty:
                    fig = px.bar(
                        evidence_df,
                        x="evidence_z",
                        y="param",
                        color="kind",
                        orientation="h",
                        title="Evidence strength (z-score, positive favors best)",
                    )
                    st.plotly_chart(fig, width="stretch", key=f"{key_prefix}_evidence_overview")
            else:
                st.info("Not enough varying parameters to compute evidence overview.")

        if not param_cols_vary:
            st.info("No varying parameters in the current selection.")
            selected_param = None
        else:
            selected_param = st.selectbox(
                "Parameter",
                options=param_cols_vary,
                index=0,
            )
        if selected_param is not None:
            fig, summary_table, reg_stats = _plot_param_effect(df, param=selected_param)
            if reg_stats is not None:
                c1, c2, c3 = st.columns(3)
                c1.metric("Slope", f"{reg_stats['slope']:.6f}")
                c2.metric("Intercept", f"{reg_stats['intercept']:.6f}")
                r2_val = reg_stats["r2"]
                c3.metric("R²", f"{r2_val:.4f}" if np.isfinite(r2_val) else "n/a")
            st.plotly_chart(
                fig,
                width="stretch",
                key=f"{key_prefix}_param_{_safe_key(selected_param)}",
            )
            if not summary_table.empty:
                st.dataframe(summary_table, width="stretch")

            st.divider()
            st.subheader("Evidence details (bootstrap)")
            boot_samples = st.slider("Bootstrap samples", min_value=200, max_value=2000, value=600, step=100)
            rng = np.random.default_rng(0)
            param_series = df[selected_param]
            kind = _infer_param_kind(param_series)
            if kind == "categorical":
                grouped = df[["value", selected_param]].copy()
                grouped = grouped[pd.notna(grouped[selected_param])]
                if grouped[selected_param].nunique(dropna=True) < 2:
                    st.info("Need at least two categories for bootstrap evidence.")
                else:
                    stats = (
                        grouped.groupby(selected_param)["value"]
                        .agg(["count", "mean"])
                        .sort_values("mean", ascending=(direction == "minimize"))
                    )
                    best_value = stats.index[0]
                    runner_value = stats.index[1]
                    best_vals = (
                        pd.to_numeric(
                            grouped.loc[grouped[selected_param] == best_value, "value"],
                            errors="coerce",
                        )
                        .dropna()
                        .to_numpy()
                    )
                    runner_vals = (
                        pd.to_numeric(
                            grouped.loc[grouped[selected_param] == runner_value, "value"],
                            errors="coerce",
                        )
                        .dropna()
                        .to_numpy()
                    )
                    diff_boot = _bootstrap_diff(
                        runner_vals if direction == "minimize" else best_vals,
                        best_vals if direction == "minimize" else runner_vals,
                        stat_fn=np.mean,
                        n_boot=int(boot_samples),
                        rng=rng,
                    )
                    if diff_boot.size > 0:
                        diff_mean = float(np.mean(diff_boot))
                        diff_std = float(np.std(diff_boot, ddof=1)) if diff_boot.size > 1 else float("nan")
                        ci_low, ci_high = np.percentile(diff_boot, [2.5, 97.5])
                        z = diff_mean / diff_std if np.isfinite(diff_std) and diff_std > 0 else float("nan")
                        cliff = _cliffs_delta(best_vals, runner_vals)
                        if direction == "minimize":
                            cliff = -cliff
                        c1, c2, c3, c4 = st.columns(4)
                        c1.metric("Best", str(best_value))
                        c2.metric("Runner-up", str(runner_value))
                        c3.metric("Δmean (boot)", f"{diff_mean:.4f}")
                        c4.metric("n-sigma", f"{z:.2f}" if np.isfinite(z) else "n/a")
                        st.caption(f"95% CI of Δmean: [{ci_low:.4f}, {ci_high:.4f}] | Cliff's δ: {cliff:.3f}")
                        fig = px.histogram(
                            pd.DataFrame({"diff": diff_boot}),
                            x="diff",
                            nbins=30,
                            title="Bootstrap Δmean distribution (positive favors best)",
                        )
                        st.plotly_chart(
                            fig,
                            width="stretch",
                            key=f"{key_prefix}_boot_diff_{_safe_key(selected_param)}",
                        )
            elif kind == "numeric":
                numeric = pd.to_numeric(param_series, errors="coerce")
                values = pd.to_numeric(df["value"], errors="coerce")
                mask = np.isfinite(numeric.to_numpy()) & np.isfinite(values.to_numpy())
                x = numeric.to_numpy()[mask]
                y = values.to_numpy()[mask]
                if x.size < 3:
                    st.info("Need at least three numeric samples for bootstrap evidence.")
                else:
                    slopes = _bootstrap_slope(x, y, n_boot=int(boot_samples), rng=rng)
                    if slopes.size > 0:
                        slope_raw = float(np.mean(slopes))
                        slope_dir = -slope_raw if direction == "minimize" else slope_raw
                        ci_low, ci_high = np.percentile(slopes, [2.5, 97.5])
                        if direction == "minimize":
                            ci_low, ci_high = -ci_high, -ci_low
                        z = slope_dir / (np.std(slopes, ddof=1) if slopes.size > 1 else np.nan)
                        rho = _spearman_rho(x, y)
                        rho_dir = -rho if direction == "minimize" else rho
                        c1, c2, c3, c4 = st.columns(4)
                        c1.metric("Slope (dir)", f"{slope_dir:.6f}")
                        c2.metric("n-sigma", f"{z:.2f}" if np.isfinite(z) else "n/a")
                        c3.metric("Spearman ρ", f"{rho_dir:.3f}" if np.isfinite(rho_dir) else "n/a")
                        c4.metric("Samples", f"{x.size}")
                        st.caption(f"95% CI (dir): [{ci_low:.6f}, {ci_high:.6f}]")
                        fig = px.histogram(
                            pd.DataFrame({"slope_dir": (-slopes if direction == "minimize" else slopes)}),
                            x="slope_dir",
                            nbins=30,
                            title="Bootstrap slope distribution (directional)",
                        )
                        st.plotly_chart(
                            fig,
                            width="stretch",
                            key=f"{key_prefix}_boot_slope_{_safe_key(selected_param)}",
                        )

    with tabs[2]:
        st.subheader("Parameter interactions")
        col_a, col_b, col_c = st.columns(3)
        param_x = col_a.selectbox("X parameter", options=param_cols, index=0)
        param_y = col_b.selectbox("Y parameter", options=param_cols, index=min(1, len(param_cols) - 1))
        bins = col_c.slider("Numeric bins", min_value=3, max_value=8, value=4, step=1)
        agg_choice = st.selectbox("Aggregate", options=["median", "mean"], index=0)
        agg_fn = np.nanmedian if agg_choice == "median" else np.nanmean
        pivot = _interaction_matrix(df, param_x=param_x, param_y=param_y, bins=int(bins), agg=agg_fn)
        interaction_key = _safe_key(f"{param_x}_{param_y}_{bins}_{agg_choice}")
        st.plotly_chart(
            _plot_interaction_heatmap(pivot, param_x=param_x, param_y=param_y),
            width="stretch",
            key=f"{key_prefix}_interaction_{interaction_key}",
        )
        if not pivot.empty:
            st.dataframe(pivot, width="stretch")

    with tabs[3]:
        st.subheader("Parameter importance")
        try:
            study = optuna.load_study(study_name=study_choice, storage=storage_uri)
        except Exception as exc:  # pragma: no cover - UI guard
            _report_exception(exc, context="Failed to load Optuna study for importance")
        else:
            fig, imp_df = _plot_param_importance(study, df)
            if imp_df.empty:
                st.info("Optuna importance unavailable for this study.")
            else:
                st.plotly_chart(
                    fig,
                    width="stretch",
                    key=f"{key_prefix}_importance",
                )
                st.dataframe(imp_df, width="stretch")

    with tabs[4]:
        st.subheader("Duplicate configurations")
        default_sig = param_cols[:6]
        signature_params = st.multiselect(
            "Signature parameters",
            options=param_cols,
            default=default_sig,
        )
        dup_df = _duplicate_configs(df, params=signature_params)
        if dup_df.empty:
            st.info("No duplicate configurations detected for the selected signature.")
        else:
            st.dataframe(dup_df, width="stretch")

    with tabs[5]:
        st.subheader("Trial table")
        base_cols = ["trial", "state", "value", "metric_source", "config_correction", "n_params"]
        extra_cols = st.multiselect(
            "Additional columns",
            options=param_cols,
            default=param_cols[:4],
        )
        table_cols = [col for col in base_cols + extra_cols if col in df.columns]
        st.dataframe(df[table_cols].sort_values("trial"), width="stretch")


__all__ = [
    "_infer_param_kind",
    "_normalize_param_value",
    "_select_param_columns",
    "render_optuna_sweep_page",
]
