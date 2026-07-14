"""EVL backbone adapter for VIN scorer architectures.

VIN consumes raw EFM snippet dicts as input and queries EVL's 3D neck features
to score candidate poses. This module is the canonical ownership point for the
external EVL dependency; model definitions depend on `EvlBackboneConfig` rather
than importing EVL internals directly.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any, Literal

import hydra
import omegaconf
import torch
from efm3d.aria.aria_constants import (
    ARIA_IMG,
    ARIA_OBB_PRED,
    ARIA_OBB_PRED_PROBS_FULL,
    ARIA_OBB_PRED_PROBS_FULL_VIZ,
    ARIA_OBB_PRED_SEM_ID_TO_NAME,
    ARIA_OBB_PRED_VIZ,
)
from efm3d.aria.tensor_wrapper import TensorWrapper
from efm3d.dataset.wds_dataset import batchify
from pydantic import Field, ValidationInfo, field_validator
from torch import Tensor

from ...configs import PathConfig
from ...utils import BaseConfig, Console, TargetConfig
from ..types import EfmDict, EvlBackboneOutput


def _target_cls() -> type["EvlBackbone"]:
    return EvlBackbone


def filter_backbone_output_for_features_mode(
    output: EvlBackboneOutput,
    *,
    features_mode: Literal["heads", "neck", "both"],
) -> EvlBackboneOutput:
    """Apply ``EvlBackboneConfig.features_mode`` to an EVL output container.

    Args:
        output: Full EVL output container before feature-family filtering.
        features_mode: Feature family requested by the caller.

    Returns:
        Filtered output with unsupported feature families set to ``None`` or
        empty dictionaries.
    """

    if features_mode == "both":
        return output
    if features_mode == "heads":
        return replace(
            output,
            voxel_feat=None,
            occ_feat=None,
            obb_feat=None,
            feat2d_upsampled={},
            token2d={},
        )
    if features_mode == "neck":
        return replace(
            output,
            occ_pr=None,
            occ_input=None,
            free_input=None,
            counts=None,
            counts_m=None,
            cent_pr=None,
            bbox_pr=None,
            clas_pr=None,
            cent_pr_nms=None,
            obbs_pr_nms=None,
            obb_pred=None,
            obb_pred_viz=None,
            obb_pred_sem_id_to_name=None,
            obb_pred_probs_full=None,
            obb_pred_probs_full_viz=None,
        )
    raise ValueError(f"Unsupported EVL features_mode: {features_mode!r}.")


def _resolve_evl_asset_path(value: object, *, root: Path) -> str:
    """Resolve EVL Hydra asset paths against the current project checkout."""

    path = Path(str(value)).expanduser()
    if path.is_absolute() and path.exists():
        return str(path.resolve())

    candidates: list[Path] = []
    parts = path.parts
    for anchor in (".logs", "external"):
        if anchor in parts:
            candidates.append(root / Path(*parts[parts.index(anchor) :]))
    if not path.is_absolute():
        candidates.append(root / path)

    for candidate in candidates:
        if candidate.exists():
            return str(candidate.resolve())
    return str(path.resolve() if not path.is_absolute() else path)


def _normalize_evl_model_config_paths(
    model_config: omegaconf.DictConfig,
    *,
    root: Path,
) -> omegaconf.DictConfig:
    """Patch EFM Hydra config paths that are checkout-local assets."""

    taxonomy_file = omegaconf.OmegaConf.select(model_config, "taxonomy_file")
    if taxonomy_file is not None:
        omegaconf.OmegaConf.update(
            model_config,
            "taxonomy_file",
            _resolve_evl_asset_path(taxonomy_file, root=root),
        )

    ckpt_path = omegaconf.OmegaConf.select(model_config, "video_backbone.image_tokenizer.ckpt_path")
    if ckpt_path is not None:
        omegaconf.OmegaConf.update(
            model_config,
            "video_backbone.image_tokenizer.ckpt_path",
            _resolve_evl_asset_path(ckpt_path, root=root),
        )
    return model_config


class EvlBackboneConfig(TargetConfig["EvlBackbone"]):
    """Configuration for `EvlBackbone`."""

    @property
    def target_type(self) -> type["EvlBackbone"]:
        """Factory target for `BaseConfig.setup_target`."""
        return _target_cls()

    paths: PathConfig = Field(default_factory=PathConfig)
    """Project path resolver."""

    model_cfg: Path = Field(default_factory=lambda: Path(".configs") / "evl_inf_desktop.yaml")
    """Hydra YAML used to instantiate `efm3d.model.evl.EVL`."""

    model_ckpt: Path = Field(default_factory=lambda: Path(".logs") / "ckpts" / "model_lite.pth")
    """Checkpoint containing an ``EVL`` state dict under ``['state_dict']``."""

    device: torch.device = Field(default_factory=lambda: torch.device("cuda" if torch.cuda.is_available() else "cpu"))
    """Torch device to run EVL on (auto-selects CUDA if available)."""

    freeze: bool = True
    """Disable gradients for all EVL parameters when True."""

    features_mode: Literal["heads", "neck", "both"] = "heads"
    """Which EVL features to expose.

    - ``heads``: expose low-dimensional head/evidence tensors (occ_pr, occ_input, counts).
    - ``neck``: expose high-dimensional neck features (neck/occ_feat, neck/obb_feat).
    - ``both``: expose both sets for ablations.
    """

    @field_validator("model_cfg", "model_ckpt", mode="before")
    @classmethod
    def _resolve_paths(cls, value: str | Path, info: ValidationInfo) -> Path:
        paths: PathConfig = info.data.get("paths") or PathConfig()
        path = Path(value)
        if not path.is_absolute():
            path = (paths.root / path).resolve()
        return path.expanduser().resolve()

    _resolve_device = field_validator("device", mode="before")(BaseConfig._resolve_geometry_device)


class EvlBackbone:
    """Frozen EVL backbone wrapper that exposes neck features and voxel grid pose."""

    def __init__(self, config: EvlBackboneConfig) -> None:
        self.config = config
        self.console = Console.with_prefix(self.__class__.__name__)

        if not self.config.model_cfg.exists():
            raise FileNotFoundError(f"Missing EVL model cfg: {self.config.model_cfg}")
        if not self.config.model_ckpt.exists():
            raise FileNotFoundError(f"Missing EVL checkpoint: {self.config.model_ckpt}")

        self.device = torch.device(self.config.device)

        checkpoint = torch.load(self.config.model_ckpt, weights_only=True, map_location=self.device)
        model_config = omegaconf.OmegaConf.load(self.config.model_cfg)
        model_config = _normalize_evl_model_config_paths(model_config, root=self.config.paths.root)
        model = hydra.utils.instantiate(model_config)
        model.load_state_dict(checkpoint["state_dict"], strict=True)
        model.to(self.device)
        model.eval()

        if self.config.freeze:
            for param in model.parameters():
                param.requires_grad_(False)

        self.model = model
        self.voxel_extent = torch.tensor(getattr(model, "ve", [-2.0, 2.0, 0.0, 4.0, -2.0, 2.0]), dtype=torch.float32)

    def _prepare_batch(self, efm: Mapping[str, Any]) -> dict[str, Any]:
        batch: dict[str, Any] = dict(efm)

        img = batch.get(ARIA_IMG[0])
        needs_batchify = isinstance(img, torch.Tensor) and img.ndim == 4  # T C H W
        if needs_batchify:
            batchify(batch, device=self.device)
            return batch

        # Already batched (or missing rgb/img); just move tensor-like values.
        for key, value in batch.items():
            if isinstance(value, (torch.Tensor, TensorWrapper)):
                batch[key] = value.to(self.device)
        return batch

    def forward(self, efm: Mapping[str, Any]) -> EvlBackboneOutput:
        """Run EVL and return the feature volumes needed by VIN.

        Args:
            efm: Raw EFM snippet dict (unbatched ``T×...`` or batched ``B×T×...``).

        Returns:
            `EvlBackboneOutput` with neck features and voxel grid pose.
        """

        batch = self._prepare_batch(efm)
        with torch.no_grad():
            out: EfmDict = self.model(batch)

        occ_feat = out.get("neck/occ_feat")
        obb_feat = out.get("neck/obb_feat")
        occ_pr = out.get("occ_pr")
        occ_input = out.get("voxel/occ_input")
        free_input = out.get("voxel/free_input")
        counts = out.get("voxel/counts")
        counts_m = out.get("voxel/counts_m")
        cent_pr = out.get("cent_pr")
        bbox_pr = out.get("bbox_pr")
        clas_pr = out.get("clas_pr")
        cent_pr_nms = out.get("cent_pr_nms")
        obbs_pr_nms = out.get("obbs_pr_nms")
        pts_world = out.get("voxel/pts_world")
        voxel_feat = out.get("voxel/feat")
        voxel_select_t = out.get("voxel/selectT")
        obb_pred = out.get(ARIA_OBB_PRED)
        obb_pred_viz = out.get(ARIA_OBB_PRED_VIZ)
        obb_pred_sem_id_to_name = out.get(ARIA_OBB_PRED_SEM_ID_TO_NAME)
        obb_pred_probs_full = out.get(ARIA_OBB_PRED_PROBS_FULL)
        obb_pred_probs_full_viz = out.get(ARIA_OBB_PRED_PROBS_FULL_VIZ)

        feat2d_upsampled: dict[str, Tensor] = {}
        token2d: dict[str, Tensor] = {}
        for key, value in out.items():
            if not isinstance(value, torch.Tensor):
                continue
            if key.endswith("/feat2d_upsampled"):
                stream = key.split("/", 1)[0]
                feat2d_upsampled[stream] = value
            elif key.endswith("/token2d"):
                stream = key.split("/", 1)[0]
                token2d[stream] = value

        ref_tensor: Tensor | None = None
        for candidate in (occ_feat, obb_feat, occ_pr, occ_input, counts, voxel_feat):
            if isinstance(candidate, torch.Tensor):
                ref_tensor = candidate
                break
        if ref_tensor is None:
            raise RuntimeError("EVL backbone produced no tensor features; check the model output payload.")

        t_world_voxel = out["voxel/T_world_voxel"]
        voxel_extent = out.get("voxel_extent")
        if voxel_extent is None:
            voxel_extent = self.voxel_extent.to(device=ref_tensor.device, dtype=ref_tensor.dtype)
        if not isinstance(voxel_extent, torch.Tensor):
            raise TypeError(f"Expected voxel_extent Tensor, got {type(voxel_extent)}")

        output = EvlBackboneOutput(
            t_world_voxel=t_world_voxel,
            voxel_extent=voxel_extent,
            voxel_feat=voxel_feat,
            occ_feat=occ_feat,
            obb_feat=obb_feat,
            occ_pr=occ_pr,
            occ_input=occ_input,
            free_input=free_input,
            counts=counts,
            counts_m=counts_m,
            voxel_select_t=voxel_select_t,
            cent_pr=cent_pr,
            bbox_pr=bbox_pr,
            clas_pr=clas_pr,
            cent_pr_nms=cent_pr_nms,
            obbs_pr_nms=obbs_pr_nms,
            obb_pred=obb_pred,
            obb_pred_viz=obb_pred_viz,
            obb_pred_sem_id_to_name=obb_pred_sem_id_to_name,
            obb_pred_probs_full=obb_pred_probs_full,
            obb_pred_probs_full_viz=obb_pred_probs_full_viz,
            pts_world=pts_world,
            feat2d_upsampled=feat2d_upsampled,
            token2d=token2d,
        )
        return filter_backbone_output_for_features_mode(
            output,
            features_mode=self.config.features_mode,
        )
