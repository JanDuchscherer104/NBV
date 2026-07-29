"""Tests for the VIN diagnostics runtime."""

# ruff: noqa: S101

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

import aria_nbv.app.panels.vin_diagnostics_runtime as runtime
from aria_nbv.configs import PathConfig
from aria_nbv.data_handling.offline.source import VinOfflineSourceConfig
from aria_nbv.oracle.pipelines.online_vin import VinOracleOnlineDatasetConfig
from aria_nbv.utils import Stage


class _FailingVin(torch.nn.Module):
    """Minimal VIN module whose diagnostic forward always fails."""

    def __init__(self) -> None:
        super().__init__()
        self.anchor = torch.nn.Parameter(torch.zeros(()))

    def forward_with_debug(self, *_args: object, **_kwargs: object) -> tuple[object, object]:
        raise RuntimeError("diagnostic forward failed")


def _seed_default_ase_paths(root: Path) -> None:
    shard = root / ".data" / "ase_efm" / "1" / "shards-0000.tar"
    shard.parent.mkdir(parents=True, exist_ok=True)
    shard.write_bytes(b"test")
    taxonomy = root / "external" / "efm3d" / "efm3d" / "config" / "taxonomy" / "atek_to_efm.csv"
    taxonomy.parent.mkdir(parents=True, exist_ok=True)
    taxonomy.write_text("", encoding="utf-8")


def test_build_experiment_config_defaults_to_online_source(tmp_path: Path) -> None:
    original_paths = PathConfig().model_dump()
    _seed_default_ase_paths(tmp_path)
    try:
        PathConfig(data_root=tmp_path / ".data", external_dir=tmp_path / "external")
        cfg = runtime.build_vin_diagnostics_config(toml_path=None, stage=Stage.TRAIN)
    finally:
        PathConfig(**original_paths)

    assert PathConfig().model_dump() == original_paths

    assert cfg.run_mode == "summarize_vin"
    assert cfg.stage is Stage.TRAIN
    assert cfg.trainer_config.use_wandb is False
    assert cfg.datamodule_config.num_workers == 0
    assert cfg.datamodule_config.batch_size is None
    assert isinstance(cfg.datamodule_config.source, VinOracleOnlineDatasetConfig)


def test_build_experiment_config_preserves_toml_source() -> None:
    toml_path = Path(__file__).resolve().parents[3] / ".configs/training/vin/offline_only.toml"
    cfg = runtime.build_vin_diagnostics_config(toml_path=str(toml_path), stage=Stage.VAL)

    assert cfg.run_mode == "summarize_vin"
    assert cfg.stage is Stage.VAL
    assert cfg.trainer_config.use_wandb is False
    assert isinstance(cfg.datamodule_config.source, VinOfflineSourceConfig)
    assert cfg.module_config.vin.apply_cw90_correction is False


@pytest.mark.parametrize("training", [True, False])
def test_run_vin_diagnostics_restores_model_mode_after_failure(
    monkeypatch: pytest.MonkeyPatch,
    training: bool,
) -> None:
    class _Snippet:
        pass

    monkeypatch.setattr(runtime, "VinSnippetView", _Snippet)
    vin = _FailingVin()
    vin.train(training)
    module = SimpleNamespace(vin=vin)
    batch = SimpleNamespace(
        efm_snippet_view=_Snippet(),
        backbone_out=None,
        candidate_poses_world_cam=object(),
        reference_pose_world_rig=object(),
        p3d_cameras=object(),
    )

    with pytest.raises(RuntimeError, match="diagnostic forward failed"):
        runtime.run_vin_diagnostics(module, batch)  # type: ignore[arg-type]

    assert vin.training is training
