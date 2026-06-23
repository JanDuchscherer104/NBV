"""CLI entry points for `AriaNBVExperimentConfig`.

This module exists so we can expose stable console scripts via `[project.scripts]`
in `aria_nbv/pyproject.toml` (unlike `aria_nbv/scripts/*.py`, which are not
importable when the package is installed).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from pydantic import AliasChoices, Field, field_validator
from pydantic._internal._utils import deep_update
from pydantic_settings import PydanticBaseSettingsSource, SettingsConfigDict

from aria_nbv.configs import PathConfig
from aria_nbv.lightning.aria_nbv_experiment import AriaNBVExperimentConfig
from aria_nbv.utils import BaseConfig, Console, Verbosity
from aria_nbv.utils.wandb_utils import (
    WANDB_STEP_KEYS,
    _ensure_wandb_api,
    _get_run,
    _load_runs_filtered,
    build_dynamics_dataframe,
    build_run_dataframes,
    collect_run_media_images,
    load_run_histories,
)


def _ensure_run_mode(argv: list[str], run_mode: str) -> list[str]:
    for arg in argv:
        if arg.startswith("--run-mode") or arg.startswith("--run_mode"):
            return argv
    return ["--run-mode", run_mode, *argv]


def _extract_config_path(argv: list[str]) -> Path | None:
    """Return a config path from CLI arguments without building default configs.

    `CLIAriaNBVExperimentConfig` is intentionally rich enough to parse full
    experiment overrides, but constructing it also constructs nested defaults.
    For offline TOML runs those defaults are irrelevant and may require raw ASE
    shards or external EFM assets that the offline config does not use. This
    small pre-parser lets `main` seed the settings model from the TOML first.
    """

    flag_names = {"--config-path", "--config_path"}
    for index, arg in enumerate(argv):
        if arg in flag_names:
            if index + 1 >= len(argv):
                raise ValueError(f"{arg} requires a path argument.")
            return Path(argv[index + 1])
        for prefix in ("--config-path=", "--config_path="):
            if arg.startswith(prefix):
                return Path(arg.split("=", 1)[1])
    return None


class CLIAriaNBVExperimentConfig(AriaNBVExperimentConfig):
    """CLI-enabled experiment config with optional TOML config path."""

    config_path: Path | None = Field(
        default=None,
        validation_alias=AliasChoices("config-path", "config_path"),
    )
    """Path to a TOML configuration file."""

    model_config = SettingsConfigDict(
        arbitrary_types_allowed=True,
        validate_default=True,
        validate_assignment=True,
        cli_parse_args=True,
        cli_kebab_case=True,
        cli_implicit_flags=True,
        cli_avoid_json=True,
        env_prefix="ARIA_NBV_",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[Any],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Use pydantic's CLI source so `_cli_parse_args` is honored."""
        del settings_cls, env_settings, dotenv_settings, file_secret_settings
        return (init_settings,)


class CLIWandbAnalysisConfig(BaseConfig):
    """CLI config for W&B run exports and local figure discovery."""

    entity: str | None = Field(
        default=None,
        validation_alias=AliasChoices("entity", "wandb-entity", "wandb_entity"),
    )
    """W&B entity (user/team). Defaults to WANDB_ENTITY env var."""

    project: str = Field(
        default="aria-nbv",
        validation_alias=AliasChoices("project", "wandb-project", "wandb_project"),
    )
    """W&B project name (default: aria-nbv)."""

    run_ids: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("run-ids", "run_ids", "runs", "ids"),
    )
    """Optional run ids to select from the filtered run list."""

    run_paths: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("run-paths", "run_paths"),
    )
    """Optional full W&B run paths (entity/project/runs/<id>)."""

    max_runs: int = Field(
        default=50,
        validation_alias=AliasChoices("max-runs", "max_runs"),
    )
    """Max runs fetched before filtering by ids/tags/etc."""

    name_regex: str | None = Field(
        default=None,
        validation_alias=AliasChoices("name-regex", "name_regex"),
    )
    """Optional regex to match run names or ids."""

    states: list[str] = Field(
        default_factory=lambda: ["finished"],
        validation_alias=AliasChoices("states", "state"),
    )
    """Allowed run states (default: finished)."""

    tags: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("tags", "tag"),
    )
    """Optional run tags to match (any-match)."""

    group: str | None = Field(
        default=None,
        validation_alias=AliasChoices("group", "wandb-group", "wandb_group"),
    )
    """Optional group filter."""

    job_type: str | None = Field(
        default=None,
        validation_alias=AliasChoices("job-type", "job_type"),
    )
    """Optional job_type filter."""

    min_steps: float | None = Field(
        default=None,
        validation_alias=AliasChoices("min-steps", "min_steps"),
    )
    """Optional minimum step count for filtering."""

    max_steps: float | None = Field(
        default=None,
        validation_alias=AliasChoices("max-steps", "max_steps"),
    )
    """Optional maximum step count for filtering."""

    history_rows: int = Field(
        default=20000,
        validation_alias=AliasChoices("history-rows", "history_rows"),
    )
    """Max history rows to fetch per run."""

    history_keys: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("history-keys", "history_keys"),
    )
    """Optional history keys to fetch (empty = all)."""

    base_metrics: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("base-metrics", "base_metrics"),
    )
    """Optional base metrics for dynamics summaries."""

    segment_frac: float = Field(
        default=0.2,
        ge=0.05,
        le=0.5,
        validation_alias=AliasChoices("segment-frac", "segment_frac"),
    )
    """Fraction used to define early/late windows for dynamics statistics."""

    output_dir: Path | None = Field(
        default=None,
        validation_alias=AliasChoices("output-dir", "output_dir"),
    )
    """Directory for exported CSV files (defaults to .logs/wandb/analysis)."""

    export_meta: bool = True
    """Export run metadata CSV."""

    export_summary: bool = True
    """Export run summary CSV."""

    export_config: bool = True
    """Export flattened run config CSV."""

    export_histories: bool = True
    """Export per-run history CSVs."""

    export_dynamics: bool = True
    """Export run dynamics summary CSV."""

    export_figures_manifest: bool = True
    """Export manifest of local train/val figure images."""

    include_latest_figures: bool = True
    """Include .logs/wandb/wandb/latest-run in local figure search."""

    verbosity: Verbosity = Verbosity.NORMAL
    """Verbosity level for logging progress."""

    model_config = SettingsConfigDict(
        arbitrary_types_allowed=True,
        validate_default=True,
        validate_assignment=True,
        cli_parse_args=True,
        cli_kebab_case=True,
        cli_implicit_flags=True,
        cli_avoid_json=True,
        env_prefix="ARIA_NBV_WANDB_",
    )

    @field_validator("run_ids", "run_paths", "tags", "states", "history_keys", "base_metrics", mode="before")
    @classmethod
    def _split_csv_list(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, (list, tuple, set)):
            return [str(item).strip() for item in value if str(item).strip()]
        return [str(value)]


def _merge_with_toml(
    base_cfg: AriaNBVExperimentConfig,
    overrides: dict[str, Any],
) -> dict[str, Any]:
    return deep_update(base_cfg.model_dump(), overrides)


def main(argv: list[str] | None = None) -> None:
    """Run training/eval/binner fitting for the configured experiment."""

    argv = list(sys.argv[1:] if argv is None else argv)
    paths = PathConfig()
    console = Console.with_prefix("cli", "main")

    early_config_path = _extract_config_path(argv)
    if early_config_path is None:
        cli_cfg = CLIAriaNBVExperimentConfig(_cli_parse_args=argv)
        config_path = cli_cfg.config_path
    else:
        config_path = early_config_path

    if config_path is None:
        cfg = cli_cfg
    else:
        config_path = paths.resolve_config_toml_path(config_path, must_exist=True)
        base_cfg = AriaNBVExperimentConfig.from_toml(config_path)
        cli_cfg = CLIAriaNBVExperimentConfig(
            **base_cfg.model_dump(),
            _cli_parse_args=argv,
        )
        overrides = cli_cfg.model_dump(exclude_unset=True)
        overrides.pop("config_path", None)
        merged = _merge_with_toml(base_cfg, overrides)
        cfg = AriaNBVExperimentConfig.model_validate(merged)
    cfg.datamodule_config.source.inspect()
    cfg.module_config.inspect()
    try:
        cfg.run()
    except KeyboardInterrupt:
        console.warn("Interrupted by user (Ctrl+C).")
        raise SystemExit(130) from None


def fit_binner_main() -> None:
    """Convenience entry point that forces `--fit-binner-only`."""

    argv = list(sys.argv[1:])
    if "--fit-binner-only" not in argv and "--fit_binner_only" not in argv:
        argv = ["--fit-binner-only", *argv]
    main(argv)


def train_main() -> None:
    """Convenience entry point that forces `--run-mode train`."""

    argv = _ensure_run_mode(list(sys.argv[1:]), "train")
    main(argv)


def summarize_main() -> None:
    """Convenience entry point that forces `--run-mode summarize-vin`."""

    argv = _ensure_run_mode(list(sys.argv[1:]), "summarize-vin")
    main(argv)


def optuna_main() -> None:
    """Convenience entry point that forces `--run-mode optuna`."""

    argv = _ensure_run_mode(list(sys.argv[1:]), "optuna")
    main(argv)


def wandb_main(argv: list[str] | None = None) -> None:
    """Export W&B summaries, histories, dynamics, and local figure manifests."""

    argv = list(sys.argv[1:] if argv is None else argv)
    console = Console.with_prefix("wandb-cli", "main")
    cfg = CLIWandbAnalysisConfig(_cli_parse_args=argv)
    console.set_verbosity(cfg.verbosity)

    entity = cfg.entity or os.environ.get("WANDB_ENTITY", "")
    project = cfg.project or os.environ.get("WANDB_PROJECT", "aria-nbv")
    api_key = os.environ.get("WANDB_API_KEY", "")

    api = _ensure_wandb_api(api_key or None)

    runs: list[Any] = []
    if cfg.run_paths:
        for run_path in cfg.run_paths:
            runs.append(_get_run(api, run_path))
    else:
        if not entity:
            raise ValueError("Provide --entity or set WANDB_ENTITY for W&B run retrieval.")
        runs = _load_runs_filtered(
            api=api,
            entity=entity,
            project=project,
            max_runs=cfg.max_runs,
            name_regex=cfg.name_regex,
            states=cfg.states,
            tags=set(cfg.tags),
            group=cfg.group or "",
            job_type=cfg.job_type or "",
            min_steps=cfg.min_steps,
            max_steps=cfg.max_steps,
        )
        if cfg.run_ids:
            run_ids = set(cfg.run_ids)
            runs = [
                run
                for run in runs
                if str(getattr(run, "id", "")) in run_ids or str(getattr(run, "name", "")) in run_ids
            ]

    if not runs:
        console.warn("No runs matched the provided filters.")
        return

    output_dir = cfg.output_dir
    if output_dir is None:
        output_dir = PathConfig().wandb / "analysis"
    output_dir.mkdir(parents=True, exist_ok=True)
    console.log(f"Writing exports to {output_dir}")

    meta_df, summary_df, config_df = build_run_dataframes(runs)
    if cfg.export_meta and not meta_df.empty:
        meta_path = output_dir / "wandb_runs_meta.csv"
        meta_df.to_csv(meta_path)
        console.log(f"Wrote metadata: {meta_path}")
    if cfg.export_summary and not summary_df.empty:
        summary_path = output_dir / "wandb_runs_summary.csv"
        summary_df.to_csv(summary_path)
        console.log(f"Wrote summary: {summary_path}")
    if cfg.export_config and not config_df.empty:
        config_path = output_dir / "wandb_runs_config.csv"
        config_df.to_csv(config_path)
        console.log(f"Wrote config: {config_path}")

    histories = load_run_histories(
        runs,
        keys=cfg.history_keys or None,
        max_rows=cfg.history_rows,
        replace_inf=True,
    )
    if cfg.export_histories:
        history_dir = output_dir / "histories"
        history_dir.mkdir(parents=True, exist_ok=True)
        for run in runs:
            run_id = str(getattr(run, "id", ""))
            history = histories.get(run_id)
            if history is None or history.empty:
                continue
            out_path = history_dir / f"{run_id}.csv"
            history.to_csv(out_path, index=False)
        console.log(f"Wrote histories to {history_dir}")

    if cfg.export_dynamics:
        dynamics_df = build_dynamics_dataframe(
            runs,
            histories,
            base_metrics=cfg.base_metrics or None,
            prefer_x_keys=list(WANDB_STEP_KEYS),
            segment_frac=cfg.segment_frac,
        )
        if not dynamics_df.empty:
            dynamics_path = output_dir / "wandb_runs_dynamics.csv"
            dynamics_df.to_csv(dynamics_path, index=False)
            console.log(f"Wrote dynamics: {dynamics_path}")

    if cfg.export_figures_manifest:
        rows: list[dict[str, str]] = []
        for run in runs:
            run_id = str(getattr(run, "id", ""))
            media = collect_run_media_images(
                run_id,
                include_latest=cfg.include_latest_figures,
            )
            for path in media.get("train_figures", []):
                rows.append({"run_id": run_id, "split": "train", "path": str(path)})
            for path in media.get("val_figures", []):
                rows.append({"run_id": run_id, "split": "val", "path": str(path)})
        if rows:
            import pandas as pd

            fig_path = output_dir / "wandb_figures_manifest.csv"
            pd.DataFrame(rows).to_csv(fig_path, index=False)
            console.log(f"Wrote figures manifest: {fig_path}")


if __name__ == "__main__":
    main()

__all__ = [
    "fit_binner_main",
    "main",
    "optuna_main",
    "summarize_main",
    "train_main",
    "wandb_main",
]
