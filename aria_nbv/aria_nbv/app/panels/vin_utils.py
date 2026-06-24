"""VIN diagnostics helpers for panels."""

from __future__ import annotations

from pathlib import Path

import torch

from ...data_handling import (
    EfmSnippetView,
    VinOracleBatch,
    VinOracleOnlineDatasetConfig,
    VinSnippetView,
)
from ...lightning.aria_nbv_experiment import AriaNBVExperimentConfig
from ...lightning.lit_module import VinLightningModule, VinLightningModuleConfig
from ...rri_metrics.rri_binning import RriOrdinalBinner
from ...utils import Stage
from ...vin.types import VinForwardDiagnostics, VinPrediction


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


def _load_vin_module_from_checkpoint(
    *,
    checkpoint_path: Path,
    device: torch.device | str,
) -> VinLightningModule:
    payload = torch.load(checkpoint_path, map_location="cpu")
    hparams = payload.get("hyper_parameters", {})
    if isinstance(hparams, dict) and "config" in hparams and isinstance(hparams["config"], dict):
        config_payload = hparams["config"]
    elif isinstance(hparams, dict):
        config_payload = hparams
    else:
        config_payload = {}
    config = VinLightningModuleConfig(**config_payload)
    module = VinLightningModule(config=config)
    module.on_load_checkpoint(payload)
    state_dict = payload.get("state_dict")
    if state_dict is None:
        raise RuntimeError("Checkpoint missing state_dict.")
    module.load_state_dict(state_dict, strict=False)
    module.to(torch.device(device))
    module.eval()
    try:
        if getattr(module, "_binner", None) is None:
            binner = None
            if module.config.binner_path is not None:
                try:
                    binner = module._load_binner_from_config()
                except Exception:
                    binner = None
            if binner is None:
                default_binner_path = Path(".logs") / "vin" / "rri_binner.json"
                try:
                    binner = RriOrdinalBinner.load(default_binner_path)
                except Exception:
                    binner = None
            if binner is not None:
                module._binner = binner
        module._maybe_init_bin_values()
    except Exception:
        pass
    return module


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
    "_load_vin_module_from_checkpoint",
    "_run_vin_debug",
]
