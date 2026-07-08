from __future__ import annotations

from pathlib import Path

import pytorch_lightning as pl
import torch
from pytest import MonkeyPatch

from aria_nbv.configs import PathConfig
from aria_nbv.lightning.aria_nbv_experiment import AriaNBVExperimentConfig
from aria_nbv.lightning.lit_module import VinLightningModule, VinLightningModuleConfig
from aria_nbv.rri_metrics.rri_binning import RriOrdinalBinner
from aria_nbv.utils import Console
from aria_nbv.vin.models.scene_myopic import VinModelV3Config


def _seed_default_ase_shard(root: Path) -> None:
    shard = root / ".data" / "ase_efm" / "1" / "shards-0000.tar"
    shard.parent.mkdir(parents=True, exist_ok=True)
    shard.write_bytes(b"test")
    taxonomy = root / "external" / "efm3d" / "efm3d" / "config" / "taxonomy" / "atek_to_efm.csv"
    taxonomy.parent.mkdir(parents=True, exist_ok=True)
    taxonomy.write_text("", encoding="utf-8")
    PathConfig(data_root=root / ".data", external_dir=root / "external")


def _write_checkpoint(
    path: Path,
    module: VinLightningModule,
) -> Path:
    payload = {
        "state_dict": module.state_dict(),
        "hyper_parameters": dict(module.hparams),
        "pytorch-lightning_version": pl.__version__,
    }
    module.on_save_checkpoint(payload)
    torch.save(payload, path)
    return path


def test_resume_checkpoint_overrides_hparams(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    _seed_default_ase_shard(tmp_path)

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


def test_load_for_inference_strictly_loads_initialized_bin_values(tmp_path: Path) -> None:
    cfg = VinLightningModuleConfig(vin=VinModelV3Config(num_classes=3), num_classes=3)
    module = VinLightningModule(config=cfg)
    module._binner = RriOrdinalBinner.fit_from_iterable(
        [torch.tensor([0.1, 0.2, 0.3], dtype=torch.float32)],
        num_classes=3,
    )
    module.prepare_for_inference()
    ckpt_path = _write_checkpoint(tmp_path / "vin-with-binner.ckpt", module)

    loaded = VinLightningModule.load_for_inference(ckpt_path, device="cpu")

    assert loaded.candidate_scorer.head_coral.has_bin_values
    assert loaded.training is False
