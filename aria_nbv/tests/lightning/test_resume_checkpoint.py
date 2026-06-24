from __future__ import annotations

from pathlib import Path

import pytorch_lightning as pl
import torch
from pytest import MonkeyPatch

from aria_nbv.lightning.aria_nbv_experiment import AriaNBVExperimentConfig
from aria_nbv.lightning.lit_module import VinLightningModule, VinLightningModuleConfig
from aria_nbv.utils import Console
from aria_nbv.vin.models.v3 import VinModelV3Config


def _write_checkpoint(
    path: Path,
    module: VinLightningModule,
) -> Path:
    payload = {
        "state_dict": module.state_dict(),
        "hyper_parameters": dict(module.hparams),
        "pytorch-lightning_version": pl.__version__,
    }
    torch.save(payload, path)
    return path


def test_resume_checkpoint_overrides_hparams(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    base_cfg = VinLightningModuleConfig(vin=VinModelV3Config(head_dropout=0.01))
    module = VinLightningModule(config=base_cfg)
    ckpt_path = _write_checkpoint(tmp_path / "vin.ckpt", module)

    new_cfg = base_cfg.model_copy(deep=True)
    new_cfg.vin.head_dropout = 0.25
    exp_cfg = AriaNBVExperimentConfig(module_config=new_cfg)
    console = Console.with_prefix("test", "resume")

    def _fail_load_from_checkpoint(*args: object, **kwargs: object) -> None:
        raise AssertionError("load_from_checkpoint should not be called during resume setup.")

    monkeypatch.setattr(
        VinLightningModule,
        "load_from_checkpoint",
        staticmethod(_fail_load_from_checkpoint),
    )

    loaded = exp_cfg._init_module_for_resume(ckpt_path, console=console)

    assert loaded.config.vin.head_dropout == new_cfg.vin.head_dropout
