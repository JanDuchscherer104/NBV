"""W&B helper utilities for analysis and local media retrieval.

These helpers are designed to be chain-friendly for pandas workflows (they
return new dataframes instead of mutating inputs) and provide optional plotting
wrappers for quick run comparisons.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

import numpy as np

from .reporting import _linear_slope, _segment_indices

if TYPE_CHECKING:
    import pandas as pd
    from matplotlib.axes import Axes
    from matplotlib.figure import Figure


WANDB_STEP_KEYS: tuple[str, ...] = ("trainer/global_step", "global_step", "_step", "epoch")


class WandbRun(Protocol):
    """Minimal W&B Run interface used by these utilities."""

    id: str
    """Stable W&B run identifier."""

    name: str
    """Human-readable run display name."""

    state: str
    """Remote lifecycle state such as `running` or `finished`."""

    group: str | None
    """Optional experiment group label."""

    job_type: str | None
    """Optional W&B job-role label."""

    tags: Sequence[str] | None
    """Optional ordered run tags."""

    created_at: Any
    """Creation timestamp in the representation returned by the W&B client."""

    summary: Mapping[str, Any] | None
    """Final or latest scalar summary payload."""

    config: Mapping[str, Any] | None
    """Serialized run configuration payload."""

    def history(self, keys: list[str] | None = None, samples: int | None = None) -> Any:
        """Return history data (typically a pandas.DataFrame or list of dicts)."""
        ...  # pragma: no cover - protocol signature only


class WandbApi(Protocol):
    """Minimal W&B API interface used by these utilities."""

    def viewer(self) -> Any:
        """Return metadata for the authenticated viewer and its teams."""
        ...  # pragma: no cover - protocol signature only

    def projects(self, entity: str) -> Iterable[Any]:
        """Iterate projects visible under one W&B entity."""
        ...  # pragma: no cover - protocol signature only

    def runs(self, path: str, order: str | None = None) -> Iterable[WandbRun]:
        """Iterate runs under an `entity/project` path in API order."""
        ...  # pragma: no cover - protocol signature only

    def run(self, path: str) -> WandbRun:
        """Fetch one run by its fully qualified W&B path."""
        ...  # pragma: no cover - protocol signature only


def _flatten_mapping(
    mapping: Mapping[str, Any],
    *,
    prefix: str = "",
    sep: str = ".",
) -> dict[str, Any]:
    """Flatten nested mappings to dot-separated keys, skipping private keys."""

    def _normalize_value(value: Any) -> Any:
        if isinstance(value, np.generic):
            return value.item()
        if value is None or isinstance(value, (str, bool, int, float, np.number)):
            return value
        if isinstance(value, (list, tuple, set)):
            return ", ".join(str(item) for item in value)
        return str(value)

    flat: dict[str, Any] = {}
    for key, value in mapping.items():
        key_str = str(key)
        if key_str.startswith("_"):
            continue
        full_key = f"{prefix}{sep}{key_str}" if prefix else key_str
        if isinstance(value, Mapping):
            flat.update(_flatten_mapping(value, prefix=full_key, sep=sep))
        else:
            flat[full_key] = _normalize_value(value)
    return flat


def _safe_mapping(raw: Any) -> dict[str, Any]:
    """Safely coerce a W&B mapping-like object to a plain dict."""
    if raw is None:
        return {}
    try:
        return dict(raw)
    except Exception:  # pragma: no cover - defensive guard
        return {}


def build_autoresearch_run_dataframe(runs: Iterable[WandbRun]) -> "pd.DataFrame":
    """Return the read-only autoresearch evidence rows embedded in W&B configs.

    The bridge writes this compact identity data under ``aria_autoresearch``;
    metrics remain ordinary W&B summaries.  Runs without that namespace are
    intentionally excluded, so the panel never infers campaign state from a
    run name, tag, or mutable W&B history.
    """
    import pandas as pd

    rows: list[dict[str, Any]] = []
    for run in runs:
        config = _flatten_mapping(_safe_mapping(getattr(run, "config", None)))
        goal_slug = config.get("aria_autoresearch.goal_slug")
        if not goal_slug:
            continue
        summary = _safe_mapping(getattr(run, "summary", None))
        rows.append(
            {
                "id": str(getattr(run, "id", "")),
                "run_name": str(getattr(run, "name", "")),
                "state": str(getattr(run, "state", "")),
                "goal_slug": goal_slug,
                "iteration": config.get("aria_autoresearch.iteration"),
                "checkpoint_status": config.get("aria_autoresearch.checkpoint_status", ""),
                "hypothesis": config.get("aria_autoresearch.hypothesis", ""),
                "research_source_count": config.get("aria_autoresearch.research_source_count"),
                "candidate_revision": config.get("aria_autoresearch.candidate_revision", ""),
                "baseline_revision": config.get("aria_autoresearch.baseline_revision", ""),
                "evaluator_fingerprint": config.get("aria_autoresearch.evaluator_fingerprint", ""),
                "result_sha256": config.get("aria_autoresearch.result_sha256", ""),
                "runtime_s": summary.get("aria_autoresearch/runtime_s"),
                "peak_memory_mb": summary.get("aria_autoresearch/peak_memory_mb"),
            }
        )
    return pd.DataFrame(rows)


def _list_entities(api: WandbApi) -> list[str]:
    """Return available entities (user + teams) for the current API token."""
    entities: list[str] = []
    try:
        viewer = api.viewer()
    except Exception:  # pragma: no cover - API guard
        viewer = None
    if viewer is None:
        return []
    for attr in ("entity", "username", "name"):
        value = getattr(viewer, attr, None)
        if isinstance(value, str) and value:
            entities.append(value)
    teams = getattr(viewer, "teams", None)
    if teams:
        for team in teams:
            name = getattr(team, "name", None)
            if isinstance(name, str) and name:
                entities.append(name)
    return list(dict.fromkeys(entities))


def _list_projects(api: WandbApi, *, entity: str) -> list[str]:
    """Return available projects for a given entity."""
    projects: list[str] = []
    if not entity:
        return projects
    try:
        iterator = api.projects(entity)
    except Exception:  # pragma: no cover - API guard
        return projects
    for project in iterator:
        name = getattr(project, "name", None)
        if isinstance(name, str) and name:
            projects.append(name)
        elif isinstance(project, dict):
            value = project.get("name")
            if isinstance(value, str) and value:
                projects.append(value)
    return list(dict.fromkeys(projects))


def _list_runs(
    api: WandbApi,
    *,
    entity: str,
    project: str,
    max_runs: int,
) -> list[WandbRun]:
    """Fetch up to max_runs from W&B, ordered by recency when supported."""
    try:
        iterator = api.runs(f"{entity}/{project}", order="-created_at")
    except TypeError:  # pragma: no cover - older API versions
        iterator = api.runs(f"{entity}/{project}")
    runs: list[WandbRun] = []
    for run in iterator:
        runs.append(run)
        if max_runs and len(runs) >= max_runs:
            break
    return runs


def _extract_run_steps(run: WandbRun, *, keys: tuple[str, ...] = WANDB_STEP_KEYS) -> float | None:
    """Extract the best-available step count from a run summary."""
    summary = _safe_mapping(getattr(run, "summary", None))
    for key in keys:
        value = summary.get(key)
        if value is None:
            continue
        if isinstance(value, (int, float, np.number)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                continue
    return None


def _format_timestamp(value: Any) -> str:
    """Render timestamps consistently for run tables."""
    if value is None:
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return str(value)


def _run_metadata(run: WandbRun) -> dict[str, Any]:
    """Extract a lightweight metadata row for a run."""
    tags = list(getattr(run, "tags", []) or [])
    steps = _extract_run_steps(run)
    return {
        "id": str(getattr(run, "id", "")),
        "name": str(getattr(run, "name", "")),
        "state": str(getattr(run, "state", "")),
        "group": str(getattr(run, "group", "")),
        "job_type": str(getattr(run, "job_type", "")),
        "tags": ", ".join(tags),
        "created_at": _format_timestamp(getattr(run, "created_at", None)),
        "steps": steps if steps is not None else np.nan,
    }


def _filter_runs(
    runs: list[WandbRun],
    *,
    name_regex: re.Pattern[str] | None,
    states: list[str],
    tags: set[str],
    group: str,
    job_type: str,
    min_steps: float | None,
    max_steps: float | None,
) -> list[WandbRun]:
    """Filter runs by state, regex, tags, group, job_type, and steps."""
    filtered: list[WandbRun] = []
    for run in runs:
        state = str(getattr(run, "state", "") or "")
        if states and state not in states:
            continue
        name = str(getattr(run, "name", "") or "")
        run_id = str(getattr(run, "id", "") or "")
        if name_regex and not (name_regex.search(name) or name_regex.search(run_id)):
            continue
        run_group = str(getattr(run, "group", "") or "")
        if group and run_group != group:
            continue
        run_job_type = str(getattr(run, "job_type", "") or "")
        if job_type and run_job_type != job_type:
            continue
        run_tags = set(getattr(run, "tags", []) or [])
        if tags and not (run_tags & tags):
            continue
        if min_steps is not None or max_steps is not None:
            steps = _extract_run_steps(run)
            if steps is None:
                continue
            if min_steps is not None and steps < min_steps:
                continue
            if max_steps is not None and steps > max_steps:
                continue
        filtered.append(run)
    return filtered


def _resolve_x_key(
    history: "pd.DataFrame",
    preferred_keys: Sequence[str],
) -> tuple[str, "pd.DataFrame"]:
    """Pick the best x-axis key and return (x_key, history_copy).

    Returns a copy with an added ``row`` column when no preferred step key
    exists, keeping the helper chain-friendly (no in-place mutation).
    """
    for key in preferred_keys:
        if key in history.columns:
            return key, history
    if "row" in history.columns:
        return "row", history
    return "row", history.assign(row=np.arange(len(history)))


def _finite_values(values: np.ndarray) -> np.ndarray:
    """Return only finite values to avoid empty-slice warnings."""
    return values[np.isfinite(values)]


def _finite_mean(values: np.ndarray) -> float:
    """Return the mean of finite values or NaN when none are finite."""
    finite = _finite_values(values)
    if finite.size == 0:
        return float("nan")
    return float(finite.mean())


def _summarize_metric(
    history: "pd.DataFrame",
    *,
    metric_key: str,
    x_key: str,
    segment_frac: float,
) -> dict[str, float]:
    """Compute basic dynamics statistics for a metric."""
    if metric_key not in history.columns or x_key not in history.columns:
        return {}
    df_metric = history[[x_key, metric_key]].dropna().sort_values(x_key)
    if df_metric.empty:
        return {}
    values = df_metric[metric_key].to_numpy(dtype=float)
    steps = df_metric[x_key].to_numpy(dtype=float)
    early, mid, late = _segment_indices(len(df_metric), segment_frac)
    finite = _finite_values(values)
    mean_mid = float("nan") if mid.start >= mid.stop else _finite_mean(values[mid])
    return {
        "last": float(values[-1]),
        "min": float(np.nan) if finite.size == 0 else float(finite.min()),
        "max": float(np.nan) if finite.size == 0 else float(finite.max()),
        "mean_early": _finite_mean(values[early]),
        "mean_mid": mean_mid,
        "mean_late": _finite_mean(values[late]),
        "slope_early": _linear_slope(steps[early], values[early]),
        "slope_late": _linear_slope(steps[late], values[late]),
    }


def _summarize_gap(
    history: "pd.DataFrame",
    *,
    x_key: str,
    train_key: str,
    val_key: str,
) -> dict[str, float]:
    """Summarize the train/val gap over the run."""
    if train_key not in history.columns or val_key not in history.columns:
        return {}
    df_gap = history[[x_key, train_key, val_key]].dropna().sort_values(x_key)
    if df_gap.empty:
        return {}
    gap = df_gap[train_key] - df_gap[val_key]
    return {
        "gap_last": float(gap.iloc[-1]),
        "gap_mean": float(gap.mean()),
        "gap_slope": _linear_slope(df_gap[x_key].to_numpy(dtype=float), gap.to_numpy(dtype=float)),
    }


def _load_wandb_history(
    run: WandbRun,
    *,
    keys: list[str] | None,
    max_rows: int,
) -> "pd.DataFrame":
    """Fetch a raw W&B history dataframe (no cleanup)."""
    import pandas as pd

    history = run.history(keys=keys, samples=int(max_rows))
    if isinstance(history, pd.DataFrame):
        return history
    return pd.DataFrame(history)


def _load_wandb_history_clean(
    run: WandbRun,
    *,
    keys: list[str] | None,
    max_rows: int,
    replace_inf: bool = True,
) -> "pd.DataFrame":
    """Load W&B history with basic cleanup (optional inf -> nan).

    Returns a new dataframe suitable for chaining.
    """
    history = _load_wandb_history(run, keys=keys, max_rows=max_rows)
    if replace_inf:
        return history.replace([np.inf, -np.inf], np.nan)
    return history


def _metric_pairs_with_pattern(
    columns: list[str],
    *,
    pattern: str,
) -> dict[str, dict[str, dict[str, str]]]:
    """Group metric column names into train/val + suffix buckets."""
    pairs: dict[str, dict[str, dict[str, str]]] = {}
    regex = re.compile(pattern)
    for name in columns:
        match = regex.match(name)
        if not match:
            continue
        stage, base, suffix = match.groups()
        suffix = suffix or "raw"
        pairs.setdefault(base, {}).setdefault(stage, {})[suffix] = name
    return pairs


def _metric_pairs(columns: list[str]) -> dict[str, dict[str, dict[str, str]]]:
    """Group metric columns using the default train/val naming convention."""
    return _metric_pairs_with_pattern(
        columns,
        pattern=r"^(train|val)/(.+?)(?:_(step|epoch))?$",
    )


def _select_metric_key(stage_map: dict[str, str], prefer: str) -> str | None:
    """Select the best metric key for a stage, preferring step/epoch suffixes."""
    if prefer in stage_map:
        return stage_map[prefer]
    if "raw" in stage_map:
        return stage_map["raw"]
    if stage_map:
        return next(iter(stage_map.values()))
    return None


def _ensure_wandb_api(api_key: str | None = None) -> WandbApi:
    """Instantiate the W&B API client, importing lazily."""
    try:
        import wandb  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - optional dependency guard
        raise RuntimeError("wandb is required for API access.") from exc
    return wandb.Api(api_key=api_key) if api_key else wandb.Api()


def _load_runs_filtered(
    *,
    entity: str,
    project: str,
    max_runs: int = 100,
    name_regex: str | None = None,
    states: list[str] | None = None,
    tags: set[str] | None = None,
    group: str | None = None,
    job_type: str | None = None,
    min_steps: float | None = None,
    max_steps: float | None = None,
    api_key: str | None = None,
    api: WandbApi | None = None,
) -> list[WandbRun]:
    """Load runs for an entity/project and apply filters."""
    if api is None:
        api = _ensure_wandb_api(api_key)
    runs = _list_runs(api, entity=entity, project=project, max_runs=max_runs)
    compiled = re.compile(name_regex) if name_regex else None
    return _filter_runs(
        runs,
        name_regex=compiled,
        states=states or [],
        tags=tags or set(),
        group=group or "",
        job_type=job_type or "",
        min_steps=min_steps,
        max_steps=max_steps,
    )


def _get_run(api: WandbApi, run_path: str) -> WandbRun:
    """Fetch a single run by its W&B path."""
    return api.run(run_path)


def build_run_dataframes(
    runs: Sequence[WandbRun],
) -> tuple["pd.DataFrame", "pd.DataFrame", "pd.DataFrame"]:
    """Build meta/summary/config dataframes from W&B runs.

    Returns new dataframes suitable for method chaining.
    """
    import pandas as pd

    meta_rows = [_run_metadata(run) for run in runs]
    meta_df = pd.DataFrame(meta_rows).set_index("id") if meta_rows else pd.DataFrame()

    summary_rows: list[dict[str, Any]] = []
    config_rows: list[dict[str, Any]] = []
    for run in runs:
        run_id = str(getattr(run, "id", ""))
        summary = _flatten_mapping(_safe_mapping(getattr(run, "summary", None)))
        config = _flatten_mapping(_safe_mapping(getattr(run, "config", None)))
        summary_rows.append({"id": run_id, **summary})
        config_rows.append({"id": run_id, **config})

    summary_df = pd.DataFrame(summary_rows).set_index("id") if summary_rows else pd.DataFrame()
    config_df = pd.DataFrame(config_rows).set_index("id") if config_rows else pd.DataFrame()
    return meta_df, summary_df, config_df


def load_run_histories(
    runs: Sequence[WandbRun],
    *,
    keys: list[str] | None = None,
    max_rows: int = 2000,
    replace_inf: bool = True,
) -> dict[str, "pd.DataFrame"]:
    """Fetch history dataframes for each run (by id)."""
    histories: dict[str, "pd.DataFrame"] = {}
    for run in runs:
        run_id = str(getattr(run, "id", ""))
        history = _load_wandb_history_clean(
            run,
            keys=keys,
            max_rows=max_rows,
            replace_inf=replace_inf,
        )
        histories[run_id] = history
    return histories


def build_dynamics_dataframe(
    runs: Sequence[WandbRun],
    histories: Mapping[str, "pd.DataFrame"],
    *,
    base_metrics: Sequence[str] | None = None,
    prefer_x_keys: Sequence[str] | None = None,
    segment_frac: float = 0.2,
) -> "pd.DataFrame":
    """Compute per-run dynamics summaries for selected base metrics.

    Returns a new dataframe suitable for method chaining.
    """
    import pandas as pd

    prefer_keys = list(prefer_x_keys) if prefer_x_keys else list(WANDB_STEP_KEYS)
    rows: list[dict[str, Any]] = []

    for run in runs:
        run_id = str(getattr(run, "id", ""))
        history = histories.get(run_id)
        if history is None or history.empty:
            continue
        history = history.copy()
        x_key, history = _resolve_x_key(history, prefer_keys)
        pairs = _metric_pairs(list(history.columns))
        prefer_suffix = "epoch" if "epoch" in x_key else "step"
        bases = list(base_metrics) if base_metrics else sorted(pairs)

        for base in bases:
            train_key = _select_metric_key(pairs.get(base, {}).get("train", {}), prefer_suffix)
            val_key = _select_metric_key(pairs.get(base, {}).get("val", {}), prefer_suffix)
            if train_key is None and val_key is None:
                continue
            row: dict[str, Any] = {
                "run_id": run_id,
                "run_name": str(getattr(run, "name", run_id)),
                "base": base,
                "x_key": x_key,
                "train_key": train_key or "",
                "val_key": val_key or "",
            }
            if train_key:
                train_summary = _summarize_metric(
                    history,
                    metric_key=train_key,
                    x_key=x_key,
                    segment_frac=segment_frac,
                )
                row.update({f"train_{key}": value for key, value in train_summary.items()})
            if val_key:
                val_summary = _summarize_metric(
                    history,
                    metric_key=val_key,
                    x_key=x_key,
                    segment_frac=segment_frac,
                )
                row.update({f"val_{key}": value for key, value in val_summary.items()})
            if train_key and val_key:
                row.update(
                    _summarize_gap(history, x_key=x_key, train_key=train_key, val_key=val_key),
                )
            rows.append(row)

    return pd.DataFrame(rows)


def _resolve_wandb_root(wandb_root: Path | None = None) -> Path:
    """Resolve the local W&B root directory (auto-detect nested layout)."""
    if wandb_root is None:
        from ..configs.path_config import PathConfig

        wandb_root = PathConfig().wandb
    root = Path(wandb_root).expanduser().resolve()
    nested = root / "wandb"
    if nested.exists():
        return nested
    return root


def list_run_dirs(
    run_id: str | None,
    *,
    wandb_root: Path | None = None,
    include_latest: bool = True,
) -> list[Path]:
    """List local W&B run directories for a run id (and optionally latest-run)."""
    root = _resolve_wandb_root(wandb_root)
    dirs: list[Path] = []
    if include_latest:
        latest = root / "latest-run"
        if latest.exists():
            dirs.append(latest)
    if run_id:
        for path in root.glob(f"run-*-{run_id}"):
            if path.is_dir():
                dirs.append(path)
    return list(dict.fromkeys(dirs))


def collect_run_media_images(
    run_id: str | None,
    *,
    wandb_root: Path | None = None,
    include_latest: bool = True,
    extensions: tuple[str, ...] = (".png", ".jpg", ".jpeg", ".svg"),
) -> dict[str, list[Path]]:
    """Collect local train/val figure image files for a W&B run."""
    run_dirs = list_run_dirs(run_id, wandb_root=wandb_root, include_latest=include_latest)
    train_files: list[Path] = []
    val_files: list[Path] = []
    for run_dir in run_dirs:
        media_root = run_dir / "files" / "media" / "images"
        for label, bucket in (("train-figures", train_files), ("val-figures", val_files)):
            target = media_root / label
            if not target.exists():
                continue
            for path in sorted(target.iterdir()):
                if path.is_file() and path.suffix.lower() in extensions:
                    bucket.append(path)
    return {
        "train_figures": list(dict.fromkeys(train_files)),
        "val_figures": list(dict.fromkeys(val_files)),
        "run_dirs": run_dirs,
    }


def prepare_history_long_dataframe(
    histories: Mapping[str, "pd.DataFrame"],
    *,
    metric: str,
    prefer_x_keys: Sequence[str] | None = None,
    run_name_map: Mapping[str, str] | None = None,
) -> "pd.DataFrame":
    """Build a long-form dataframe for plotting metric curves.

    Args:
        histories: Mapping of run_id -> history dataframe.
        metric: Metric column name to extract.
        prefer_x_keys: Preferred x-axis keys (defaults to WANDB_STEP_KEYS).
        run_name_map: Optional map of run_id -> display name.

    Returns:
        Long-form dataframe with columns: run_id, run_name, step, value.
    """
    import pandas as pd

    prefer_keys = list(prefer_x_keys) if prefer_x_keys else list(WANDB_STEP_KEYS)
    rows: list[dict[str, Any]] = []
    for run_id, history in histories.items():
        if history is None or history.empty or metric not in history.columns:
            continue
        x_key, history = _resolve_x_key(history.copy(), prefer_keys)
        df = history[[x_key, metric]].dropna().sort_values(x_key)
        if df.empty:
            continue
        run_name = run_name_map.get(run_id, run_id) if run_name_map else run_id
        rows.extend(
            {
                "run_id": run_id,
                "run_name": run_name,
                "step": float(step),
                "value": float(value),
            }
            for step, value in zip(df[x_key], df[metric], strict=False)
        )
    return pd.DataFrame(rows)


def plot_metric_curves(
    histories: Mapping[str, "pd.DataFrame"],
    *,
    metric: str,
    prefer_x_keys: Sequence[str] | None = None,
    run_name_map: Mapping[str, str] | None = None,
    ax: "Axes | None" = None,
) -> tuple["Figure", "Axes"]:
    """Plot metric curves across runs using seaborn."""
    import matplotlib.pyplot as plt
    import seaborn as sns

    df_long = prepare_history_long_dataframe(
        histories,
        metric=metric,
        prefer_x_keys=prefer_x_keys,
        run_name_map=run_name_map,
    )
    if ax is None:
        fig, ax = plt.subplots(figsize=(8, 4))
    else:
        fig = ax.figure
    if not df_long.empty:
        sns.lineplot(data=df_long, x="step", y="value", hue="run_name", ax=ax)
    ax.set_title(f"{metric} over time")
    ax.set_xlabel("step")
    ax.set_ylabel(metric)
    return fig, ax


def plot_dynamics_scatter(
    dynamics_df: "pd.DataFrame",
    *,
    x: str = "train_last",
    y: str = "val_last",
    hue: str = "run_name",
    style: str | None = "base",
    ax: "Axes | None" = None,
) -> tuple["Figure", "Axes"]:
    """Scatter plot comparing train vs val dynamics summary."""
    import matplotlib.pyplot as plt
    import seaborn as sns

    if ax is None:
        fig, ax = plt.subplots(figsize=(6, 4))
    else:
        fig = ax.figure
    sns.scatterplot(data=dynamics_df, x=x, y=y, hue=hue, style=style, ax=ax)
    ax.set_title(f"{y} vs {x}")
    return fig, ax


def plot_dynamics_bar(
    dynamics_df: "pd.DataFrame",
    *,
    metric: str = "val_last",
    base: str | None = None,
    ax: "Axes | None" = None,
) -> tuple["Figure", "Axes"]:
    """Bar plot of a chosen dynamics metric across runs."""
    import matplotlib.pyplot as plt
    import seaborn as sns

    if ax is None:
        fig, ax = plt.subplots(figsize=(8, 4))
    else:
        fig = ax.figure
    plot_df = dynamics_df.copy()
    if base is not None:
        plot_df = plot_df[plot_df["base"] == base]
    sns.barplot(data=plot_df, x="run_name", y=metric, ax=ax)
    ax.set_title(f"{metric} by run")
    ax.tick_params(axis="x", rotation=45)
    return fig, ax


__all__ = [
    "WANDB_STEP_KEYS",
    "WandbApi",
    "WandbRun",
    "_ensure_wandb_api",
    "_extract_run_steps",
    "_filter_runs",
    "_flatten_mapping",
    "_format_timestamp",
    "_get_run",
    "_linear_slope",
    "_list_entities",
    "_list_projects",
    "_list_runs",
    "_load_runs_filtered",
    "_load_wandb_history",
    "_load_wandb_history_clean",
    "_metric_pairs",
    "_metric_pairs_with_pattern",
    "_resolve_x_key",
    "_run_metadata",
    "_safe_mapping",
    "_segment_indices",
    "_select_metric_key",
    "_summarize_gap",
    "_summarize_metric",
    "build_dynamics_dataframe",
    "build_autoresearch_run_dataframe",
    "build_run_dataframes",
    "collect_run_media_images",
    "list_run_dirs",
    "load_run_histories",
    "plot_dynamics_bar",
    "plot_dynamics_scatter",
    "plot_metric_curves",
    "prepare_history_long_dataframe",
]
