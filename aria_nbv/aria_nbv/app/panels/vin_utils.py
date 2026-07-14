"""Runtime construction and forward-pass helpers for VIN diagnostics.

This module provides experiment preparation, checkpoint-backed module/data
setup, and no-gradient debug inference while keeping Streamlit out of the
compute path.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import torch

from ...data_handling import (
    EfmSnippetView,
    VinOracleBatch,
    VinOracleOnlineDatasetConfig,
    VinSnippetView,
)
from ...lightning.aria_nbv_experiment import AriaNBVExperimentConfig
from ...lightning.lit_module import VinLightningModule
from ...utils import Stage
from ...vin.types import VinPrediction
from ...vin.types.diagnostics import VinForwardDiagnostics


@dataclass(frozen=True, slots=True)
class _VinDiagnosticsRuntime:
    """Runtime objects needed for one VIN diagnostics pass."""

    module: VinLightningModule
    """Checkpoint-backed VIN Lightning module in evaluation mode."""

    datamodule: object
    """Prepared stage-aware data module that owns diagnostic batch iteration."""


def _build_experiment_config(
    *,
    toml_path: str | None,
    stage: Stage,
) -> AriaNBVExperimentConfig:
    if toml_path:
        cfg = AriaNBVExperimentConfig.from_toml(Path(toml_path))
    else:
        cfg = AriaNBVExperimentConfig()

    cfg.run_mode = "summarize_vin"
    cfg.stage = stage
    cfg.trainer_config.use_wandb = False

    if toml_path is None:
        cfg.datamodule_config.num_workers = 0
        cfg.datamodule_config.source = VinOracleOnlineDatasetConfig()

    return cfg


def _setup_vin_diagnostics_runtime(
    cfg: AriaNBVExperimentConfig,
    *,
    stage: Stage,
) -> _VinDiagnosticsRuntime:
    """Build checkpoint-backed VIN diagnostics runtime objects."""

    ckpt_path = cfg._resolve_ckpt_path()
    if ckpt_path is not None:
        module = VinLightningModule.load_for_inference(
            ckpt_path,
            fallback_binner_path=cfg.module_config.binner_path,
        )
        datamodule = cfg.datamodule_config.setup_target()
        datamodule.setup(stage=stage)
        return _VinDiagnosticsRuntime(module=module, datamodule=datamodule)

    _trainer, module, datamodule = cfg.setup_target(setup_stage=stage)
    module.prepare_for_inference()
    return _VinDiagnosticsRuntime(module=module, datamodule=datamodule)


def _run_vin_debug(
    module: "VinLightningModule",
    batch: VinOracleBatch,
) -> tuple[VinPrediction, VinForwardDiagnostics]:
    was_training = module.vin.training
    module.vin.eval()
    snippet_view = batch.efm_snippet_view
    if snippet_view is None:
        if batch.backbone_out is None:
            raise RuntimeError(
                "VIN debug requires efm inputs or cached backbone outputs.",
            )
        raise RuntimeError("VIN debug requires a VinSnippetView or EfmSnippetView.")
    if isinstance(snippet_view, (EfmSnippetView, VinSnippetView)):
        efm = snippet_view
    elif hasattr(snippet_view, "points_world"):
        efm = snippet_view
    else:
        raise TypeError(
            f"VIN debug expects a VinSnippetView or EfmSnippetView, got {type(snippet_view)}.",
        )
    backbone_out = batch.backbone_out
    if backbone_out is not None:
        device = backbone_out.voxel_extent.device
        if next(module.vin.parameters()).device != device:
            module.vin.to(device)
        batch = batch.to(device) if hasattr(batch, "to") else batch
        backbone_out = backbone_out.to(device)
        if hasattr(batch, "p3d_cameras"):
            batch.p3d_cameras = batch.p3d_cameras.to(device)
    with torch.no_grad():
        pred, debug = module.vin.forward_with_debug(
            efm,
            candidate_poses_world_cam=batch.candidate_poses_world_cam,
            reference_pose_world_rig=batch.reference_pose_world_rig,
            p3d_cameras=batch.p3d_cameras,
            backbone_out=backbone_out,
        )
    if was_training:
        module.vin.train()
    return pred, debug


__all__ = [
    "_build_experiment_config",
    "_run_vin_debug",
    "_setup_vin_diagnostics_runtime",
]
