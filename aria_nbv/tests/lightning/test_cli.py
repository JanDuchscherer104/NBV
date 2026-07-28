"""Regression tests for Lightning CLI config entry points."""

from __future__ import annotations

# ruff: noqa: S101
import sys
from pathlib import Path

from aria_nbv.data_handling.offline.source import VinOfflineSourceConfig
from aria_nbv.lightning import cli
from aria_nbv.lightning.aria_nbv_experiment import AriaNBVExperimentConfig
from aria_nbv.utils import BaseConfig


def _write_train_wandb_toml(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                'run_mode = "train"',
                "",
                "[datamodule_config]",
                "num_workers = 16",
                "batch_size = 16",
                "persistent_workers = true",
                "shuffle = true",
                "",
                "[datamodule_config.source]",
                'kind = "offline"',
                "",
                "[datamodule_config.source.offline]",
                "include_efm_snippet = true",
                "",
                "[trainer_config]",
                "use_wandb = true",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_ensure_run_mode_injects_requested_mode_before_config_args() -> None:
    """Convenience entry points inject their mode when the CLI omits one."""
    argv = ["--config-path", "offline_only.toml"]

    resolved = cli._ensure_run_mode(argv, "summarize-vin")

    assert resolved == ["--run-mode", "summarize-vin", "--config-path", "offline_only.toml"]


def test_ensure_run_mode_preserves_explicit_cli_mode() -> None:
    """An explicit CLI run mode remains the caller's highest-precedence override."""
    argv = ["--run-mode", "dump-config", "--config-path", "offline_only.toml"]

    resolved = cli._ensure_run_mode(argv, "summarize-vin")

    assert resolved == argv


def test_extract_config_path_without_constructing_full_cli_config() -> None:
    """The early config parser supports both split and equals-style flags."""
    assert cli._extract_config_path(["--config-path", "offline_only.toml"]) == Path("offline_only.toml")
    assert cli._extract_config_path(["--config_path=offline_only.toml"]) == Path("offline_only.toml")
    assert cli._extract_config_path(["--run-mode", "train"]) is None


def test_toml_merge_uses_cli_run_mode_over_train_config_and_disables_wandb(tmp_path: Path) -> None:
    """Direct merge keeps the summarize override above TOML training defaults."""
    config_path = tmp_path / "offline_only.toml"
    _write_train_wandb_toml(config_path)
    base_cfg = AriaNBVExperimentConfig.from_toml(config_path)
    cli_cfg = cli.CLIAriaNBVExperimentConfig(
        **base_cfg.model_dump(), _cli_parse_args=["--run-mode", "summarize-vin", "--config-path", str(config_path)]
    )
    overrides = cli_cfg.model_dump(exclude_unset=True)
    overrides.pop("config_path", None)

    merged = cli._merge_with_toml(base_cfg, overrides)
    cfg = AriaNBVExperimentConfig.model_validate(merged)

    assert base_cfg.run_mode == "train"
    assert base_cfg.trainer_config.use_wandb is True
    assert base_cfg.datamodule_config.num_workers == 16
    assert base_cfg.datamodule_config.batch_size == 16
    assert base_cfg.datamodule_config.persistent_workers is True
    assert base_cfg.datamodule_config.shuffle is True
    assert isinstance(base_cfg.datamodule_config.source, VinOfflineSourceConfig)
    assert base_cfg.datamodule_config.source.offline.include_efm_snippet is True
    assert cfg.run_mode == "summarize_vin"
    assert cfg.trainer_config.use_wandb is False
    assert cfg.datamodule_config.num_workers == 0
    assert cfg.datamodule_config.batch_size == 1
    assert cfg.datamodule_config.persistent_workers is False
    assert cfg.datamodule_config.shuffle is False
    assert isinstance(cfg.datamodule_config.source, VinOfflineSourceConfig)
    assert cfg.datamodule_config.source.offline.include_efm_snippet is False


def test_summarize_main_overrides_toml_train_mode_without_training(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """`nbv-summary --config-path ...` must summarize even when TOML says train."""
    config_path = tmp_path / "offline_only.toml"
    _write_train_wandb_toml(config_path)
    captured: dict[str, AriaNBVExperimentConfig] = {}

    def capture_summary(self: AriaNBVExperimentConfig) -> None:
        captured["cfg"] = self

    def fail_training(self: AriaNBVExperimentConfig, *args: object, **kwargs: object) -> None:
        del self, args, kwargs
        raise AssertionError("nbv-summary dispatched to the training path")

    monkeypatch.setattr(sys, "argv", ["nbv-summary", "--config-path", str(config_path)])
    monkeypatch.setattr(BaseConfig, "inspect", lambda self, show_docs=False: None)
    monkeypatch.setattr(AriaNBVExperimentConfig, "summarize_vin", capture_summary)
    monkeypatch.setattr(AriaNBVExperimentConfig, "setup_target_and_run", fail_training)

    cli.summarize_main()

    cfg = captured["cfg"]
    assert cfg.run_mode == "summarize_vin"
    assert cfg.trainer_config.use_wandb is False
    assert cfg.datamodule_config.num_workers == 0
    assert cfg.datamodule_config.batch_size == 1
    assert cfg.datamodule_config.persistent_workers is False
    assert cfg.datamodule_config.shuffle is False
    assert isinstance(cfg.datamodule_config.source, VinOfflineSourceConfig)
    assert cfg.datamodule_config.source.offline.include_efm_snippet is False


def test_main_skips_rich_config_inspection_when_disabled(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Smoke configs can keep CLI logs focused on the run outcome."""

    config_path = tmp_path / "quiet.toml"
    config_path.write_text(
        "\n".join(
            [
                'run_mode = "dump_config"',
                "inspect_config = false",
                "",
                "[trainer_config]",
                "use_wandb = false",
                "",
                "[datamodule_config.source]",
                'kind = "offline"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    inspect_calls = 0
    captured: dict[str, AriaNBVExperimentConfig] = {}

    def count_inspect(self: BaseConfig, show_docs: bool = False) -> None:
        del self, show_docs
        nonlocal inspect_calls
        inspect_calls += 1

    def capture_run(self: AriaNBVExperimentConfig) -> None:
        captured["cfg"] = self

    monkeypatch.setattr(BaseConfig, "inspect", count_inspect)
    monkeypatch.setattr(AriaNBVExperimentConfig, "run", capture_run)

    cli.main(["--config-path", str(config_path)])

    assert captured["cfg"].inspect_config is False
    assert inspect_calls == 0


def test_offline_smoke_config_disables_heavy_debug_metrics() -> None:
    """The checked-in two-epoch smoke config should stay quiet and bounded."""

    repo_root = Path(__file__).resolve().parents[3]
    cfg = AriaNBVExperimentConfig.from_toml(repo_root / ".configs/training/vin/offline_smoke_2epoch.toml")

    assert cfg.inspect_config is False
    assert cfg.module_config.log_spearman is False


def test_summary_and_plot_modes_use_smoke_datamodule_defaults_after_validation() -> None:
    """Smoke-only modes keep validation cheap after training TOML values merge."""
    summary_cfg = AriaNBVExperimentConfig.model_validate(
        {
            "run_mode": "summarize-vin",
            "trainer_config": {"use_wandb": True},
            "datamodule_config": {
                "num_workers": 16,
                "batch_size": 16,
                "persistent_workers": True,
                "shuffle": True,
                "source": {"kind": "offline", "offline": {"include_efm_snippet": True}},
            },
        }
    )
    plot_cfg = AriaNBVExperimentConfig.model_validate(
        {
            "run_mode": "plot-vin-encodings",
            "trainer_config": {"use_wandb": True},
            "datamodule_config": {
                "num_workers": 8,
                "batch_size": 8,
                "persistent_workers": True,
                "shuffle": True,
                "source": {"kind": "offline", "offline": {"include_efm_snippet": True}},
            },
        }
    )

    assert summary_cfg.run_mode == "summarize_vin"
    assert summary_cfg.trainer_config.use_wandb is False
    assert summary_cfg.datamodule_config.num_workers == 0
    assert summary_cfg.datamodule_config.batch_size == 1
    assert summary_cfg.datamodule_config.persistent_workers is False
    assert summary_cfg.datamodule_config.shuffle is False
    assert isinstance(summary_cfg.datamodule_config.source, VinOfflineSourceConfig)
    assert summary_cfg.datamodule_config.source.offline.include_efm_snippet is False
    assert plot_cfg.run_mode == "plot_vin_encodings"
    assert plot_cfg.trainer_config.use_wandb is False
    assert plot_cfg.datamodule_config.num_workers == 0
    assert plot_cfg.datamodule_config.batch_size == 1
    assert plot_cfg.datamodule_config.persistent_workers is False
    assert plot_cfg.datamodule_config.shuffle is False
    assert isinstance(plot_cfg.datamodule_config.source, VinOfflineSourceConfig)
    assert plot_cfg.datamodule_config.source.offline.include_efm_snippet is False


def test_train_mode_preserves_training_datamodule_defaults_after_validation() -> None:
    """Training keeps TOML-provided loader and raw-snippet settings unchanged."""
    cfg = AriaNBVExperimentConfig.model_validate(
        {
            "run_mode": "train",
            "trainer_config": {"use_wandb": True},
            "datamodule_config": {
                "num_workers": 16,
                "batch_size": 16,
                "persistent_workers": True,
                "shuffle": True,
                "source": {"kind": "offline", "offline": {"include_efm_snippet": True}},
            },
        }
    )

    assert cfg.run_mode == "train"
    assert cfg.trainer_config.use_wandb is True
    assert cfg.datamodule_config.num_workers == 16
    assert cfg.datamodule_config.batch_size == 16
    assert cfg.datamodule_config.persistent_workers is True
    assert cfg.datamodule_config.shuffle is True
    assert isinstance(cfg.datamodule_config.source, VinOfflineSourceConfig)
    assert cfg.datamodule_config.source.offline.include_efm_snippet is True


def test_experiment_defaults_trainer_root_to_run_output_dir(tmp_path: Path) -> None:
    """Logger-free Lightning artifacts should stay under the experiment output dir."""
    cfg = AriaNBVExperimentConfig.model_validate(
        {
            "out_dir": tmp_path / "offline-smoke",
            "trainer_config": {"use_wandb": False},
            "datamodule_config": {"source": {"kind": "offline"}},
        }
    )

    assert cfg.trainer_config.default_root_dir == cfg.resolved_out_dir
