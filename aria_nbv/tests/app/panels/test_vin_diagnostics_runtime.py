"""Tests for VIN diagnostics runtime setup."""

# ruff: noqa: S101, D103

from __future__ import annotations

from pathlib import Path

import pytest

from aria_nbv.app.panels.vin_utils import _setup_vin_diagnostics_runtime
from aria_nbv.configs import PathConfig
from aria_nbv.lightning.aria_nbv_experiment import AriaNBVExperimentConfig
from aria_nbv.lightning.lit_module import VinLightningModule
from aria_nbv.utils import Stage


def _seed_default_ase_shard(root: Path) -> None:
    shard = root / ".data" / "ase_efm" / "1" / "shards-0000.tar"
    shard.parent.mkdir(parents=True, exist_ok=True)
    shard.write_bytes(b"test")
    taxonomy = root / "external" / "efm3d" / "efm3d" / "config" / "taxonomy" / "atek_to_efm.csv"
    taxonomy.parent.mkdir(parents=True, exist_ok=True)
    taxonomy.write_text("", encoding="utf-8")
    PathConfig(data_root=root / ".data", external_dir=root / "external")


class _DummyDataModule:
    def __init__(self) -> None:
        self.setup_calls: list[Stage] = []

    def setup(self, stage: Stage) -> None:
        self.setup_calls.append(stage)


class _DummyModule:
    def __init__(self, *, fail_prepare: bool = False) -> None:
        self.fail_prepare = fail_prepare
        self.prepare_calls = 0

    def prepare_for_inference(self) -> None:
        self.prepare_calls += 1
        if self.fail_prepare:
            raise RuntimeError("prepare failed")


def test_checkpoint_diagnostics_use_strict_inference_loader(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_default_ase_shard(tmp_path)
    ckpt_path = tmp_path / "vin.ckpt"
    ckpt_path.write_bytes(b"checkpoint")
    cfg = AriaNBVExperimentConfig(ckpt_path=ckpt_path)
    datamodule = _DummyDataModule()
    module = _DummyModule()
    loaded: dict[str, object] = {}

    def _fail_setup_target(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("checkpoint diagnostics must not build a fresh module")

    def _load_for_inference(
        checkpoint_path: Path,
        *,
        fallback_binner_path: Path | None = None,
        device: str = "cpu",
    ) -> _DummyModule:
        loaded["checkpoint_path"] = checkpoint_path
        loaded["fallback_binner_path"] = fallback_binner_path
        loaded["device"] = device
        return module

    monkeypatch.setattr(AriaNBVExperimentConfig, "setup_target", _fail_setup_target)
    monkeypatch.setattr(type(cfg.datamodule_config), "setup_target", lambda _self: datamodule)
    monkeypatch.setattr(VinLightningModule, "load_for_inference", staticmethod(_load_for_inference))

    runtime = _setup_vin_diagnostics_runtime(cfg, stage=Stage.VAL)

    assert runtime.module is module
    assert runtime.datamodule is datamodule
    assert loaded["checkpoint_path"] == ckpt_path
    assert datamodule.setup_calls == [Stage.VAL]


def test_checkpoint_diagnostics_propagate_load_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_default_ase_shard(tmp_path)
    ckpt_path = tmp_path / "bad.ckpt"
    ckpt_path.write_bytes(b"checkpoint")
    cfg = AriaNBVExperimentConfig(ckpt_path=ckpt_path)

    def _load_for_inference(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("checkpoint load failed")

    monkeypatch.setattr(VinLightningModule, "load_for_inference", staticmethod(_load_for_inference))

    with pytest.raises(RuntimeError, match="checkpoint load failed"):
        _setup_vin_diagnostics_runtime(cfg, stage=Stage.TEST)


def test_config_built_diagnostics_fail_closed_on_prepare_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_default_ase_shard(tmp_path)
    cfg = AriaNBVExperimentConfig()
    datamodule = _DummyDataModule()
    module = _DummyModule(fail_prepare=True)

    def _setup_target(
        _self: AriaNBVExperimentConfig,
        setup_stage: Stage,
    ) -> tuple[object, _DummyModule, _DummyDataModule]:
        assert setup_stage is Stage.TRAIN
        return object(), module, datamodule

    monkeypatch.setattr(AriaNBVExperimentConfig, "setup_target", _setup_target)

    with pytest.raises(RuntimeError, match="prepare failed"):
        _setup_vin_diagnostics_runtime(cfg, stage=Stage.TRAIN)

    assert module.prepare_calls == 1
