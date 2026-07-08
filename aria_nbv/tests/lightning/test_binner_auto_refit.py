"""Ensure binner auto-refits when num_classes mismatches at training start."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
import torch

pytest.importorskip("pytorch_lightning")

from aria_nbv.lightning.aria_nbv_experiment import AriaNBVExperimentConfig
from aria_nbv.lightning.lit_module import VinLightningModuleConfig
from aria_nbv.rri_metrics.rri_binning import RriOrdinalBinner
from aria_nbv.vin import VinModelV3Config


@dataclass(slots=True)
class _DummyBatch:
    rri: torch.Tensor
    scene_id: str
    snippet_id: str


class _DummyDataModule:
    def __init__(self, batches: list[_DummyBatch]) -> None:
        self._batches = batches

    def train_dataloader(self) -> list[_DummyBatch]:
        return self._batches


def test_auto_refit_binner_on_num_classes_mismatch(tmp_path: Path) -> None:
    rri = torch.linspace(0.0, 1.0, steps=32)
    binner_path = tmp_path / "rri_binner.json"

    old_binner = RriOrdinalBinner.fit_from_iterable([rri], num_classes=3)
    old_binner.save(binner_path, overwrite=True)

    batches = [
        _DummyBatch(rri=rri, scene_id="scene0", snippet_id="snip0"),
        _DummyBatch(rri=rri * 2.0, scene_id="scene1", snippet_id="snip1"),
    ]
    datamodule = _DummyDataModule(batches)

    module_cfg = VinLightningModuleConfig(
        vin=VinModelV3Config(num_classes=5),
        num_classes=5,
        binner_path=binner_path,
    )
    exp_cfg = AriaNBVExperimentConfig(
        out_dir=tmp_path / "run",
        module_config=module_cfg,
    )

    exp_cfg._ensure_binner_matches_num_classes(datamodule=datamodule)

    new_binner = RriOrdinalBinner.load(binner_path)
    assert new_binner.num_classes == 5


def test_fit_binner_run_mode_honors_overwrite_flag(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Ensure CLI binner preflights can refresh their configured JSON path."""

    captured: dict[str, bool] = {}

    def _fit_binner_and_save(
        self: AriaNBVExperimentConfig,
        datamodule: Any | None = None,
        *,
        overwrite: bool = False,
    ) -> Path:
        del self, datamodule
        captured["overwrite"] = overwrite
        return tmp_path / "rri_binner.json"

    monkeypatch.setattr(
        AriaNBVExperimentConfig,
        "fit_binner_and_save",
        _fit_binner_and_save,
    )

    cfg = AriaNBVExperimentConfig(
        run_mode="fit_binner",
        fit_binner_overwrite=True,
    )

    cfg.run()

    assert captured == {"overwrite": True}
