"""Checkpoint setup and no-gradient forward passes for VIN diagnostics.

This module keeps Streamlit out of the compute path. It owns experiment
preparation, checkpoint-backed module/data-module composition, diagnostic
inference, and restoration of the scorer's prior training mode.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import cast

import torch

from ...data_handling.ase_efm.views import EfmSnippetView
from ...data_handling.vin_store.batch import VinOracleBatch
from ...data_handling.vin_store.views import VinSnippetView
from ...lightning.aria_nbv_experiment import AriaNBVExperimentConfig
from ...lightning.lit_datamodule import VinDataModule
from ...lightning.lit_module import VinLightningModule
from ...oracle.pipelines.online_vin import VinOracleOnlineDatasetConfig
from ...utils import Stage
from ...vin.types import VinPrediction
from ...vin.types.diagnostics import VinForwardDiagnostics


@dataclass(frozen=True, slots=True)
class VinDiagnosticsRuntime:
    """Runtime objects needed for one VIN diagnostics pass."""

    module: VinLightningModule
    """Checkpoint-backed Lightning module used for diagnostic inference."""

    datamodule: VinDataModule
    """Configured data module that supplies VIN oracle batches."""


def build_vin_diagnostics_config(
    *,
    toml_path: str | None,
    stage: Stage,
) -> AriaNBVExperimentConfig:
    """Build an experiment config for one VIN diagnostics run.

    Args:
        toml_path: Optional experiment TOML path. Defaults to the online oracle
            source when omitted.
        stage: Data stage used to configure and set up the data module.

    Returns:
        Experiment configuration with training-only services disabled.
    """

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


def setup_vin_diagnostics_runtime(
    cfg: AriaNBVExperimentConfig,
    *,
    stage: Stage,
) -> VinDiagnosticsRuntime:
    """Build checkpoint-backed VIN diagnostics runtime objects.

    Args:
        cfg: Experiment configuration for diagnostics.
        stage: Data stage to initialize.

    Returns:
        Typed module and data-module pair ready for inference.
    """

    ckpt_path = cfg._resolve_ckpt_path()
    if ckpt_path is not None:
        module = VinLightningModule.load_for_inference(
            ckpt_path,
            fallback_binner_path=cfg.module_config.binner_path,
        )
        datamodule = cast(VinDataModule, cfg.datamodule_config.setup_target())
        datamodule.setup(stage=stage)
        return VinDiagnosticsRuntime(module=module, datamodule=datamodule)

    _trainer, module, datamodule = cfg.setup_target(setup_stage=stage)
    module.prepare_for_inference()
    return VinDiagnosticsRuntime(
        module=module,
        datamodule=cast(VinDataModule, datamodule),
    )


def run_vin_diagnostics(
    module: VinLightningModule,
    batch: VinOracleBatch,
) -> tuple[VinPrediction, VinForwardDiagnostics]:
    """Run one diagnostic VIN forward pass and restore the prior model mode.

    Args:
        module: Lightning module that owns the VIN scorer.
        batch: Oracle batch supplying snippet, candidate, and camera inputs.

    Returns:
        VIN prediction and forward diagnostics for the batch.

    Raises:
        RuntimeError: If neither snippet inputs nor usable cached inputs exist.
        TypeError: If the batch exposes an unsupported snippet-view type.
    """

    snippet_view = batch.efm_snippet_view
    if snippet_view is None:
        if batch.backbone_out is None:
            raise RuntimeError(
                "VIN diagnostics require EFM inputs or cached backbone outputs.",
            )
        raise RuntimeError(
            "VIN diagnostics require a VinSnippetView or EfmSnippetView.",
        )
    if not isinstance(snippet_view, (EfmSnippetView, VinSnippetView)):
        raise TypeError(
            f"VIN diagnostics expect a VinSnippetView or EfmSnippetView, got {type(snippet_view)}.",
        )

    backbone_out = batch.backbone_out
    if backbone_out is not None:
        device = backbone_out.voxel_extent.device
        first_parameter = next(module.vin.parameters(), None)
        if first_parameter is not None and first_parameter.device != device:
            module.vin.to(device)
        batch.p3d_cameras = batch.p3d_cameras.to(device)
        backbone_out = backbone_out.to(device)

    was_training = module.vin.training
    module.vin.eval()
    try:
        with torch.no_grad():
            return module.vin.forward_with_debug(
                snippet_view,
                candidate_poses_world_cam=batch.candidate_poses_world_cam,
                reference_pose_world_rig=batch.reference_pose_world_rig,
                p3d_cameras=batch.p3d_cameras,
                backbone_out=backbone_out,
            )
    finally:
        module.vin.train(was_training)


__all__ = [
    "VinDiagnosticsRuntime",
    "build_vin_diagnostics_config",
    "run_vin_diagnostics",
    "setup_vin_diagnostics_runtime",
]
