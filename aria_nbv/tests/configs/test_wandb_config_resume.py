"""Tests for W&B resume configuration."""

# ruff: noqa: S101

from __future__ import annotations

from typing import TYPE_CHECKING

from aria_nbv.configs import wandb_config

if TYPE_CHECKING:
    import pytest


class _DummyWandbLogger:
    def __init__(self, *args: object, **kwargs: object) -> None:
        self.args: tuple[object, ...] = args
        self.kwargs: dict[str, object] = dict(kwargs)


def test_wandb_config_resume_and_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """Resume params should flow into WandbLogger init kwargs."""
    monkeypatch.setattr(wandb_config, "WandbLogger", _DummyWandbLogger)

    cfg = wandb_config.WandbConfig(
        project="aria-nbv",
        run_id="1wz4g6ex",
        resume="allow",
    )
    logger = cfg.setup_target()

    assert logger.kwargs["id"] == "1wz4g6ex"
    assert logger.kwargs["resume"] == "allow"


def test_wandb_config_init_kwargs_excludes_lightning_only_options() -> None:
    cfg = wandb_config.WandbConfig(
        project="aria-performance",
        run_id="result-1",
        group="goal-a",
        job_type="performance-goal",
        offline=True,
        log_model=True,
        prefix="train",
    )

    assert cfg.init_kwargs()["mode"] == "offline"
    assert cfg.init_kwargs()["id"] == "result-1"
    assert cfg.init_kwargs()["group"] == "goal-a"
    assert "log_model" not in cfg.init_kwargs()
    assert "prefix" not in cfg.init_kwargs()
