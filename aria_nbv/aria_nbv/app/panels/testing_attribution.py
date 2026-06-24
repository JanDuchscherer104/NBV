"""Testing and attribution panel."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
import torch
from torch import nn
from torch.nn import functional as functional

from ...configs import PathConfig
from ...interpretability.attribution import (
    AttributionEngine,
    AttributionMethod,
    BaselineStrategy,
    InterpretabilityConfig,
)
from ...lightning.lit_module import VinLightningModule
from ...rri_metrics.coral import coral_expected_from_logits, coral_logits_to_prob
from ...vin.encoders import infer_pose_vec_groups
from ...vin.geometry import pos_grid_from_pts_world
from ..state import get_vin_state
from .common import _info_popover


class _VinAttributionHead(nn.Module):
    """Lightweight wrapper to attribute VIN head outputs to input features."""

    def __init__(self, head_mlp: nn.Module, head_coral: nn.Module) -> None:
        super().__init__()
        self.head_mlp = head_mlp
        self.head_coral = head_coral

    def forward(self, feats: torch.Tensor) -> torch.Tensor:
        logits = self.head_coral(self.head_mlp(feats))
        probs = coral_logits_to_prob(logits)
        if getattr(self.head_coral, "has_bin_values", False):
            expected = self.head_coral.expected_from_probs(probs)
            return expected.unsqueeze(-1)
        _, expected_norm = coral_expected_from_logits(logits)
        return expected_norm.unsqueeze(-1)


class _VinPoseAttributionHead(nn.Module):
    """Attribute VIN outputs to the raw pose-vector inputs."""

    def __init__(
        self,
        pose_encoder_lff: nn.Module | None,
        sh_encoder: nn.Module | None,
        head_mlp: nn.Module,
        head_coral: nn.Module,
        *,
        global_feat: torch.Tensor,
        extra_feat: torch.Tensor | None,
    ) -> None:
        super().__init__()
        self.pose_encoder_lff = pose_encoder_lff
        self.sh_encoder = sh_encoder
        self.head_mlp = head_mlp
        self.head_coral = head_coral
        self.register_buffer("global_feat", global_feat, persistent=False)
        if extra_feat is not None:
            self.register_buffer("extra_feat", extra_feat, persistent=False)
        else:
            self.extra_feat = None

    def _encode_pose_vec(self, pose_vec: torch.Tensor) -> torch.Tensor:
        if self.pose_encoder_lff is not None:
            return self.pose_encoder_lff(pose_vec)
        if self.sh_encoder is not None:
            if pose_vec.shape[-1] < 8:
                raise ValueError("Expected pose_vec with at least 8 dims for SH encoder.")
            center_dir = pose_vec[..., 0:3]
            forward_dir = pose_vec[..., 3:6]
            radius = pose_vec[..., 6:7]
            view_alignment = pose_vec[..., 7:8]
            return self.sh_encoder(center_dir, forward_dir, r=radius, scalars=view_alignment)
        raise RuntimeError("Pose encoder does not expose an LFF or SH submodule.")

    def forward(self, pose_vec: torch.Tensor) -> torch.Tensor:
        pose_enc = self._encode_pose_vec(pose_vec)
        parts = [pose_enc, self.global_feat.expand(pose_vec.shape[0], -1)]
        extra_feat = getattr(self, "extra_feat", None)
        if isinstance(extra_feat, torch.Tensor):
            parts.append(extra_feat.expand(pose_vec.shape[0], -1))
        feats = torch.cat(parts, dim=-1)
        logits = self.head_coral(self.head_mlp(feats))
        probs = coral_logits_to_prob(logits)
        if getattr(self.head_coral, "has_bin_values", False):
            expected = self.head_coral.expected_from_probs(probs)
            return expected.unsqueeze(-1)
        _, expected_norm = coral_expected_from_logits(logits)
        return expected_norm.unsqueeze(-1)


class _VinSceneFieldAttributionHead(nn.Module):
    """Attribute VIN outputs to scene-field channel inputs."""

    def __init__(
        self,
        *,
        field_proj: nn.Module,
        global_pooler: nn.Module,
        head_mlp: nn.Module,
        head_coral: nn.Module,
        pose_enc: torch.Tensor,
        pos_grid: torch.Tensor,
        extra_feat: torch.Tensor | None,
    ) -> None:
        super().__init__()
        self.field_proj = field_proj
        self.global_pooler = global_pooler
        self.head_mlp = head_mlp
        self.head_coral = head_coral
        self.register_buffer("pose_enc", pose_enc, persistent=False)
        self.register_buffer("pos_grid", pos_grid, persistent=False)
        if extra_feat is not None:
            self.register_buffer("extra_feat", extra_feat, persistent=False)
        else:
            self.extra_feat = None

    def forward(self, field_in: torch.Tensor) -> torch.Tensor:
        field = self.field_proj(field_in)
        global_feat = self.global_pooler(field, self.pose_enc, pos_grid=self.pos_grid)
        parts = [self.pose_enc, global_feat]
        extra_feat = getattr(self, "extra_feat", None)
        if isinstance(extra_feat, torch.Tensor):
            parts.append(extra_feat)
        feats = torch.cat(parts, dim=-1)
        flat_feats = feats.reshape(-1, feats.shape[-1])
        logits = self.head_coral(self.head_mlp(flat_feats)).reshape(feats.shape[0], feats.shape[1], -1)
        probs = coral_logits_to_prob(logits)
        if getattr(self.head_coral, "has_bin_values", False):
            expected = self.head_coral.expected_from_probs(probs)
            return expected.unsqueeze(-1)
        _, expected_norm = coral_expected_from_logits(logits)
        return expected_norm.unsqueeze(-1)


def render_testing_attribution_page() -> None:
    """Render testing and attribution diagnostics."""
    st.header("Testing & Attribution")
    st.caption("Run lightweight checkpoint checks and VIN head attributions.")

    st.subheader("Attribution explorer (VIN head)")
    _info_popover(
        "vin attribution",
        "Compute Captum attributions over VIN head features for a cached "
        "oracle batch. This attributes the head's predicted RRI score to "
        "its feature inputs (pose encoding, global feature tokens, and "
        "optional extra features).",
    )

    attr_state: dict[str, object] = st.session_state.setdefault(
        "vin_attr_state",
        {},
    )
    paths = PathConfig()

    ckpt_dir = paths.checkpoints
    ckpt_paths = sorted(
        ckpt_dir.glob("*.ckpt"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    ckpt_names = [path.name for path in ckpt_paths]
    ckpt_path: Path | None = None
    if ckpt_names:
        ckpt_choice = st.selectbox(
            "Checkpoint",
            options=ckpt_names,
            index=0,
            key="vin_attr_ckpt_choice",
        )
        ckpt_path = ckpt_dir / ckpt_choice
    else:
        st.info(f"No checkpoints found in {ckpt_dir}.")

    device_choices = ["cpu"] + (["cuda"] if torch.cuda.is_available() else [])
    device_choice = st.selectbox(
        "Attribution device",
        options=device_choices,
        index=0,
        key="vin_attr_device",
    )

    vin_state = get_vin_state()
    if vin_state.batch is None:
        st.warning("Run VIN Diagnostics first to populate a batch for attribution.")
    else:
        st.caption(
            f"Using VIN Diagnostics batch: scene={vin_state.batch.scene_id} snippet={vin_state.batch.snippet_id}",
        )

    resolved_ckpt: Path | None = None
    if ckpt_path is not None:
        try:
            resolved_ckpt = paths.resolve_checkpoint_path(ckpt_path)
        except Exception as exc:  # pragma: no cover - IO guard
            st.error(f"Checkpoint error: {type(exc).__name__}: {exc}")

    module: VinLightningModule | None = attr_state.get("module")  # type: ignore[assignment]
    module_key = (str(resolved_ckpt) if resolved_ckpt else "", device_choice)
    if resolved_ckpt is not None and attr_state.get("module_key") != module_key:
        try:
            module = VinLightningModule.load_for_inference(
                resolved_ckpt,
                device=torch.device(device_choice),
                fallback_binner_path=Path(".logs") / "vin" / "rri_binner.json",
            )
            attr_state["module"] = module
            attr_state["module_key"] = module_key
            attr_state.pop("attr_result", None)
        except Exception as exc:  # pragma: no cover - checkpoint guard
            st.error(f"Failed to load checkpoint: {type(exc).__name__}: {exc}")
            module = None

    num_candidates = int(attr_state.get("num_candidates", 1) or 1)
    vin_state = get_vin_state()
    if vin_state.batch is not None:
        poses = getattr(vin_state.batch, "candidate_poses_world_cam", None)
        tensor = getattr(poses, "tensor", None)
        if isinstance(tensor, torch.Tensor):
            if tensor.ndim >= 2:
                num_candidates = int(tensor.shape[-2])
        else:
            try:
                num_candidates = int(len(poses))
            except TypeError:
                pass

    candidate_mode = st.selectbox(
        "Candidate selection",
        options=[
            "best_pred",
            "best_oracle",
            "min_huber",
            "max_huber",
            "manual",
        ],
        index=0,
        key="vin_attr_candidate_mode",
    )
    manual_idx = st.number_input(
        "Manual candidate index",
        min_value=0,
        max_value=max(0, num_candidates - 1),
        value=0,
        step=1,
        disabled=candidate_mode != "manual",
        key="vin_attr_candidate_idx",
    )

    attr_input = st.selectbox(
        "Attribution input",
        options=["VIN head features", "Pose vector (raw)", "Scene field channels"],
        index=0,
        key="vin_attr_input",
    )

    vector_methods = [
        AttributionMethod.INTEGRATED_GRADIENTS,
        AttributionMethod.NOISE_TUNNEL_IG,
        AttributionMethod.DEEP_LIFT,
        AttributionMethod.INPUT_X_GRADIENT,
        AttributionMethod.FEATURE_ABLATION,
    ]
    field_methods = [
        AttributionMethod.INTEGRATED_GRADIENTS,
        AttributionMethod.DEEP_LIFT,
        AttributionMethod.INPUT_X_GRADIENT,
        AttributionMethod.FEATURE_ABLATION,
    ]
    method_options = field_methods if attr_input == "Scene field channels" else vector_methods
    method = st.selectbox(
        "Attribution method",
        options=method_options,
        index=0,
        key="vin_attr_method",
    )
    baseline = st.selectbox(
        "Baseline",
        options=list(BaselineStrategy),
        index=0,
        key="vin_attr_baseline",
    )
    n_steps = int(
        st.number_input(
            "IG steps",
            min_value=8,
            max_value=256,
            value=32,
            step=8,
            key="vin_attr_ig_steps",
        ),
    )
    use_abs = st.checkbox(
        "Use absolute attributions",
        value=True,
        key="vin_attr_use_abs",
    )

    run_attr = st.button("Compute attributions", key="vin_attr_run")
    if run_attr:
        if module is None:
            st.error("Load a VIN checkpoint to compute attributions.")
        else:
            try:
                vin_state = get_vin_state()
                if vin_state.batch is None:
                    st.error("Run VIN Diagnostics first to populate a batch for attribution.")
                    return
                sample_indices = [0]

                device = torch.device(device_choice)
                module.to(device)
                module.eval()

                raw_scores_list: list[np.ndarray] = []
                field_attr_list: list[np.ndarray] = []
                field_channel_names: list[str] | None = None
                pose_values = None
                pose_groups = None
                pred_scores_list: list[float] = []
                oracle_scores_list: list[float] = []
                candidate_valid_list: list[bool | None] = []
                candidate_indices: list[int] = []
                ablation_accum: dict[str, list[float]] = {
                    "score_full": [],
                    "score_ablated": [],
                    "score_only": [],
                    "delta": [],
                    "rel_delta": [],
                }
                ablation_groups: list[str] = []
                for sample_idx in sample_indices:
                    _ = sample_idx
                    cache_sample = vin_state.batch

                    backbone_out = getattr(cache_sample, "backbone_out", None)
                    if backbone_out is None:
                        raise RuntimeError("VIN diagnostics batch missing backbone outputs.")
                    efm = {}
                    if cache_sample.efm_snippet_view is not None:
                        efm = cache_sample.efm_snippet_view.efm
                    backbone_out = backbone_out.to(device)
                    p3d_cameras = cache_sample.p3d_cameras.to(device)

                    with torch.no_grad():
                        pred, debug = module.vin.forward_with_debug(
                            efm,
                            candidate_poses_world_cam=cache_sample.candidate_poses_world_cam,
                            reference_pose_world_rig=cache_sample.reference_pose_world_rig,
                            p3d_cameras=p3d_cameras,
                            backbone_out=backbone_out,
                        )

                    if not hasattr(debug, "feats"):
                        raise RuntimeError("VIN debug output missing `feats`.")

                    pred_scores = pred.expected_normalized.detach().cpu().squeeze(0)
                    if getattr(module.vin.head_coral, "has_bin_values", False):
                        pred_scores = module.vin.head_coral.expected_from_probs(pred.prob).detach().cpu().squeeze(0)
                    oracle_scores = cache_sample.rri.detach().cpu()
                    valid_mask = debug.candidate_valid.detach().cpu().squeeze(0)
                    num_candidates = int(valid_mask.numel())
                    attr_state["num_candidates"] = num_candidates

                    def _best_idx(scores: torch.Tensor, mask_valid: torch.Tensor) -> int:
                        if scores.numel() == 0:
                            return 0
                        mask = torch.isfinite(scores)
                        if mask_valid.numel() == scores.numel():
                            mask = mask & mask_valid
                        if mask.any():
                            masked = scores.clone()
                            masked[~mask] = -float("inf")
                            return int(masked.argmax().item())
                        return int(scores.nan_to_num(-float("inf")).argmax().item())

                    def _min_idx(scores: torch.Tensor, mask_valid: torch.Tensor) -> int:
                        if scores.numel() == 0:
                            return 0
                        mask = torch.isfinite(scores)
                        if mask_valid.numel() == scores.numel():
                            mask = mask & mask_valid
                        if mask.any():
                            masked = scores.clone()
                            masked[~mask] = float("inf")
                            return int(masked.argmin().item())
                        return int(scores.nan_to_num(float("inf")).argmin().item())

                    def _max_idx(scores: torch.Tensor, mask_valid: torch.Tensor) -> int:
                        return _best_idx(scores, mask_valid)

                    if candidate_mode == "best_oracle":
                        candidate_idx = _best_idx(oracle_scores, valid_mask)
                    elif candidate_mode == "min_huber":
                        huber = functional.smooth_l1_loss(
                            pred_scores.to(dtype=torch.float32),
                            oracle_scores.to(dtype=torch.float32),
                            reduction="none",
                        )
                        candidate_idx = _min_idx(huber, valid_mask)
                    elif candidate_mode == "max_huber":
                        huber = functional.smooth_l1_loss(
                            pred_scores.to(dtype=torch.float32),
                            oracle_scores.to(dtype=torch.float32),
                            reduction="none",
                        )
                        candidate_idx = _max_idx(huber, valid_mask)
                    elif candidate_mode == "manual":
                        candidate_idx = int(min(max(manual_idx, 0), num_candidates - 1))
                    else:
                        candidate_idx = _best_idx(pred_scores, valid_mask)

                    candidate_indices.append(candidate_idx)

                    feat_vec = debug.feats[0, candidate_idx].to(dtype=torch.float32).detach().clone()
                    feat_tensor = feat_vec.unsqueeze(0)
                    pose_vec = (
                        debug.pose_vec[0, candidate_idx].to(dtype=torch.float32).detach().clone()
                        if hasattr(debug, "pose_vec")
                        else None
                    )
                    global_vec = (
                        debug.global_feat[0, candidate_idx].to(dtype=torch.float32).detach().clone()
                        if hasattr(debug, "global_feat")
                        else None
                    )

                    pose_dim = int(debug.pose_enc.shape[-1]) if hasattr(debug, "pose_enc") else 0
                    global_dim = int(debug.global_feat.shape[-1]) if hasattr(debug, "global_feat") else 0
                    total_dim = int(feat_vec.numel())
                    pose_dim = min(pose_dim, total_dim)
                    global_dim = min(global_dim, max(0, total_dim - pose_dim))
                    extra_vec = None
                    if total_dim > pose_dim + global_dim:
                        extra_vec = feat_vec[pose_dim + global_dim :].clone()

                    head_features = _VinAttributionHead(module.vin.head_mlp, module.vin.head_coral).to(device)
                    head_features.eval()
                    if not getattr(module.vin.head_coral, "has_bin_values", False):
                        st.warning(
                            "Bin values not initialized; using normalized expected score.",
                        )

                    group_slices: list[tuple[str, slice]] = []
                    if pose_dim > 0:
                        group_slices.append(("pose_enc", slice(0, pose_dim)))
                    if global_dim > 0:
                        group_slices.append(("global_feat", slice(pose_dim, pose_dim + global_dim)))
                    if total_dim > pose_dim + global_dim:
                        group_slices.append(("extra", slice(pose_dim + global_dim, total_dim)))

                    with torch.no_grad():
                        base_score = float(head_features(feat_tensor).squeeze().item())
                        for name, sl in group_slices:
                            mod = feat_vec.clone()
                            if sl.start < sl.stop:
                                mod[sl] = 0.0
                            ablated = float(head_features(mod.unsqueeze(0)).squeeze().item())
                            only = torch.zeros_like(mod)
                            if sl.start < sl.stop:
                                only[sl] = feat_vec[sl]
                            only_score = float(head_features(only.unsqueeze(0)).squeeze().item())
                            delta = base_score - ablated
                            rel = delta / (abs(base_score) + 1e-6)
                            if name not in ablation_groups:
                                ablation_groups.append(name)
                            ablation_accum["score_full"].append(base_score)
                            ablation_accum["score_ablated"].append(ablated)
                            ablation_accum["score_only"].append(only_score)
                            ablation_accum["delta"].append(delta)
                            ablation_accum["rel_delta"].append(rel)

                    attr_head: nn.Module
                    attr_input_tensor: torch.Tensor
                    if attr_input == "Scene field channels":
                        if not hasattr(debug, "field_in"):
                            raise RuntimeError("VIN debug output missing field_in.")
                        field_in = debug.field_in.to(dtype=torch.float32).detach().clone()
                        if field_in.ndim != 5:
                            raise RuntimeError(
                                f"Expected field_in shape (B,C,D,H,W), got {tuple(field_in.shape)}.",
                            )
                        pose_enc = debug.pose_enc[:, candidate_idx : candidate_idx + 1].to(
                            dtype=field_in.dtype,
                        )
                        backbone_out = debug.backbone_out
                        if backbone_out is None or not isinstance(backbone_out.pts_world, torch.Tensor):
                            raise RuntimeError("Missing backbone voxel center grid for scene-field attribution.")
                        t_world_voxel = backbone_out.t_world_voxel.to(device)
                        pose_world_rig_ref = cache_sample.reference_pose_world_rig.to(device)
                        pos_grid = pos_grid_from_pts_world(
                            backbone_out.pts_world.to(device=device, dtype=field_in.dtype),
                            t_world_voxel=t_world_voxel,
                            pose_world_rig_ref=pose_world_rig_ref,
                            voxel_extent=backbone_out.voxel_extent,
                            grid_shape=(field_in.shape[-3], field_in.shape[-2], field_in.shape[-1]),
                        )
                        extra_feat = extra_vec.unsqueeze(0).unsqueeze(0) if extra_vec is not None else None
                        attr_head = _VinSceneFieldAttributionHead(
                            field_proj=module.vin.field_proj,
                            global_pooler=module.vin.global_pooler,
                            head_mlp=module.vin.head_mlp,
                            head_coral=module.vin.head_coral,
                            pose_enc=pose_enc,
                            pos_grid=pos_grid,
                            extra_feat=extra_feat,
                        ).to(device)
                        attr_input_tensor = field_in
                        if hasattr(module.vin, "config") and hasattr(module.vin.config, "scene_field_channels"):
                            field_channel_names = list(module.vin.config.scene_field_channels)
                        else:
                            field_channel_names = [f"ch_{idx}" for idx in range(field_in.shape[1])]
                    elif attr_input == "Pose vector (raw)":
                        if pose_vec is None:
                            raise RuntimeError("VIN debug output missing pose_vec.")
                        if global_vec is None:
                            raise RuntimeError("VIN debug output missing global_feat.")
                        pose_encoder_lff = getattr(module.vin.pose_encoder, "pose_encoder_lff", None)
                        sh_encoder = getattr(module.vin.pose_encoder, "sh_encoder", None)
                        if pose_encoder_lff is None and sh_encoder is None:
                            raise RuntimeError("Pose encoder does not expose a supported submodule.")
                        attr_head = _VinPoseAttributionHead(
                            pose_encoder_lff=pose_encoder_lff,
                            sh_encoder=sh_encoder,
                            head_mlp=module.vin.head_mlp,
                            head_coral=module.vin.head_coral,
                            global_feat=global_vec.unsqueeze(0),
                            extra_feat=extra_vec.unsqueeze(0) if extra_vec is not None else None,
                        ).to(device)
                        attr_input_tensor = pose_vec.unsqueeze(0)
                        pose_groups = [
                            {"name": name, "start": sl.start, "stop": sl.stop}
                            for name, sl in infer_pose_vec_groups(int(pose_vec.shape[-1]))
                        ]
                        pose_values = pose_vec.detach().cpu().tolist()
                    else:
                        attr_head = head_features
                        attr_input_tensor = feat_tensor

                    attr_head.eval()
                    interp_cfg = InterpretabilityConfig(
                        method=method,
                        baseline=baseline,
                        n_steps=n_steps,
                        use_abs=use_abs,
                    )
                    engine = AttributionEngine(config=interp_cfg, model=attr_head)
                    target = torch.zeros(
                        (attr_input_tensor.shape[0],),
                        device=attr_input_tensor.device,
                        dtype=torch.long,
                    )
                    result = engine.attribute(attr_input_tensor, target=target)
                    raw_attr = result.raw_attribution.detach().cpu().squeeze(0)
                    if attr_input == "Scene field channels":
                        if raw_attr.ndim != 4:
                            raise RuntimeError(
                                f"Expected scene-field attribution shape (C,D,H,W), got {tuple(raw_attr.shape)}.",
                            )
                        field_attr_list.append(raw_attr.numpy())
                    else:
                        if raw_attr.ndim > 1:
                            raw_attr = raw_attr.reshape(-1)
                        raw_scores_list.append(raw_attr.numpy())

                    pred_scores_list.append(
                        float(pred_scores[candidate_idx]) if pred_scores.numel() > candidate_idx else float("nan"),
                    )
                    oracle_scores_list.append(
                        float(oracle_scores[candidate_idx]) if oracle_scores.numel() > candidate_idx else float("nan"),
                    )
                    candidate_valid_list.append(
                        bool(valid_mask[candidate_idx].item()) if valid_mask.numel() > candidate_idx else None,
                    )

                if attr_input == "Scene field channels":
                    if not field_attr_list:
                        raise RuntimeError("No scene-field attribution scores computed.")
                    field_attr_arr = np.stack(field_attr_list, axis=0)
                    field_attr_mean = field_attr_arr.mean(axis=0)
                    field_attr_std = field_attr_arr.std(axis=0)
                    input_dim = int(field_attr_mean.shape[0])
                    raw_scores = np.array([], dtype=np.float32)
                    raw_scores_std = np.array([], dtype=np.float32)
                else:
                    if not raw_scores_list:
                        raise RuntimeError("No attribution scores computed.")
                    raw_scores_arr = np.stack(raw_scores_list, axis=0)
                    raw_scores = raw_scores_arr.mean(axis=0)
                    raw_scores_std = raw_scores_arr.std(axis=0)
                    input_dim = int(raw_scores.shape[0]) if raw_scores.size else 0

                ablation_rows: list[dict[str, float | str]] = []
                if ablation_groups:
                    group_count = len(ablation_groups)
                    for idx, name in enumerate(ablation_groups):
                        offset = idx
                        ablation_rows.append(
                            {
                                "group": name,
                                "score_full": float(np.mean(ablation_accum["score_full"][offset::group_count])),
                                "score_ablated": float(np.mean(ablation_accum["score_ablated"][offset::group_count])),
                                "score_only": float(np.mean(ablation_accum["score_only"][offset::group_count])),
                                "delta": float(np.mean(ablation_accum["delta"][offset::group_count])),
                                "rel_delta": float(np.mean(ablation_accum["rel_delta"][offset::group_count])),
                            },
                        )

                attr_result: dict[str, object] = {
                    "raw_scores": raw_scores.tolist(),
                    "raw_scores_std": raw_scores_std.tolist(),
                    "input_kind": attr_input,
                    "candidate_idx": int(candidate_indices[0]) if candidate_indices else 0,
                    "candidate_indices": candidate_indices,
                    "pred_score": float(np.nanmean(pred_scores_list)) if pred_scores_list else float("nan"),
                    "oracle_score": float(np.nanmean(oracle_scores_list)) if oracle_scores_list else float("nan"),
                    "candidate_valid": (
                        None
                        if not candidate_valid_list or any(val is None for val in candidate_valid_list)
                        else bool(all(candidate_valid_list))
                    ),
                    "pose_dim": pose_dim,
                    "global_dim": global_dim,
                    "total_dim": total_dim,
                    "input_dim": input_dim,
                    "pose_groups": pose_groups,
                    "pose_values": pose_values,
                    "ablation_rows": ablation_rows,
                    "sample_count": len(sample_indices),
                }
                if attr_input == "Scene field channels":
                    attr_result["field_attr_mean"] = field_attr_mean
                    attr_result["field_attr_std"] = field_attr_std
                    attr_result["field_channel_names"] = field_channel_names
                attr_state["attr_result"] = attr_result
            except Exception as exc:  # pragma: no cover - attribution guard
                st.error(f"Attribution failed: {type(exc).__name__}: {exc}")

    attr_result = attr_state.get("attr_result")
    if attr_result is None:
        st.info("Compute attributions to view results.")
        return

    input_kind = str(attr_result.get("input_kind", "VIN head features"))
    raw_scores = np.asarray(attr_result["raw_scores"], dtype=np.float32)
    raw_scores_std = np.asarray(attr_result.get("raw_scores_std", []), dtype=np.float32)
    candidate_idx = int(attr_result["candidate_idx"])
    pred_score = float(attr_result["pred_score"])
    oracle_score = float(attr_result["oracle_score"])
    candidate_valid = attr_result["candidate_valid"]
    pose_dim = int(attr_result["pose_dim"])
    global_dim = int(attr_result["global_dim"])
    total_dim = int(attr_result["total_dim"])
    input_dim = int(attr_result.get("input_dim", total_dim))
    sample_count = int(attr_result.get("sample_count", 1))
    candidate_indices = attr_result.get("candidate_indices") or []

    display_abs = st.checkbox(
        "Display absolute scores",
        value=True,
        key="vin_attr_display_abs",
    )
    normalize_scores = st.checkbox(
        "Normalize display to [0, 1]",
        value=True,
        key="vin_attr_display_norm",
    )
    show_std = st.checkbox(
        "Show attribution std",
        value=False,
        key="vin_attr_show_std",
    )
    scores = np.abs(raw_scores) if display_abs else raw_scores
    if normalize_scores:
        denom = np.max(np.abs(scores)) if scores.size else 1.0
        scores = scores / (denom + 1e-8)

    col_a1, col_a2, col_a3, col_a4 = st.columns(4)
    col_a1.metric("Candidate index", candidate_idx)
    col_a2.metric("Pred RRI (expected)", f"{pred_score:.4f}")
    col_a3.metric("Oracle RRI", f"{oracle_score:.4f}" if np.isfinite(oracle_score) else "n/a")
    col_a4.metric("Candidate valid", str(candidate_valid) if candidate_valid is not None else "n/a")

    if sample_count > 1:
        st.caption(f"Aggregated over {sample_count} samples.")
        if candidate_indices:
            st.caption(f"Candidate indices: {candidate_indices}")

    st.caption(f"Attribution input: {input_kind}")
    st.caption(f"Input dim: {input_dim}")
    st.caption(f"VIN feature dim: {total_dim} (pose={pose_dim}, global={global_dim})")

    if input_kind == "Scene field channels":
        field_attr_mean = attr_result.get("field_attr_mean")
        field_attr_std = attr_result.get("field_attr_std")
        channel_names = attr_result.get("field_channel_names") or []
        if field_attr_mean is None:
            st.error("Scene-field attributions missing.")
            return
        field_attr = np.asarray(field_attr_mean)
        field_attr_s = np.asarray(field_attr_std) if field_attr_std is not None else None
        if field_attr.ndim != 4:
            st.error(f"Expected field attribution shape (C,D,H,W), got {field_attr.shape}.")
            return
        if not channel_names:
            channel_names = [f"ch_{idx}" for idx in range(field_attr.shape[0])]
        if len(channel_names) != field_attr.shape[0]:
            channel_names = [f"ch_{idx}" for idx in range(field_attr.shape[0])]

        if display_abs:
            channel_scores = np.mean(np.abs(field_attr), axis=(1, 2, 3))
        else:
            channel_scores = field_attr.mean(axis=(1, 2, 3))
        if normalize_scores:
            denom = np.max(np.abs(channel_scores)) if channel_scores.size else 1.0
            channel_scores = channel_scores / (denom + 1e-8)

        channel_std = None
        if field_attr_s is not None and field_attr_s.shape == field_attr.shape:
            channel_std = field_attr_s.mean(axis=(1, 2, 3))

        channel_df = pd.DataFrame(
            {
                "channel": channel_names,
                "score": channel_scores,
            },
        )
        if show_std:
            channel_df["std"] = channel_std if channel_std is not None else np.full_like(channel_scores, np.nan)
        st.dataframe(channel_df, width="stretch", height=240)

        sel_idx = int(
            st.selectbox(
                "Channel for heatmap",
                options=list(range(len(channel_names))),
                format_func=lambda i: channel_names[i],
                index=0,
                key="vin_attr_field_channel",
            ),
        )
        proj_mode = st.selectbox(
            "Depth projection",
            options=["mean", "max"],
            index=0,
            key="vin_attr_field_proj",
        )
        channel_map = field_attr[sel_idx]
        if display_abs:
            channel_map = np.abs(channel_map)
        if proj_mode == "max":
            heat = channel_map.max(axis=0)
        else:
            heat = channel_map.mean(axis=0)
        if normalize_scores:
            denom = np.max(np.abs(heat)) if heat.size else 1.0
            heat = heat / (denom + 1e-8)
        st.markdown("**Scene-field spatial attribution (D-projected)**")
        st.image(heat.astype(np.float32), caption=f"{channel_names[sel_idx]} ({proj_mode})", clamp=True)
        return

    group_rows: list[dict[str, float | str]] = []
    if input_kind == "Pose vector (raw)":
        pose_groups = attr_result.get("pose_groups") or []
        pose_values = np.asarray(attr_result.get("pose_values") or [], dtype=np.float32)
        for group in pose_groups:
            start = int(group["start"])
            stop = int(group["stop"])
            group_scores = scores[start:stop] if scores.size else np.array([])
            group_vals = pose_values[start:stop] if pose_values.size else np.array([])
            group_rows.append(
                {
                    "group": str(group["name"]),
                    "score_sum": float(group_scores.sum()) if group_scores.size else float("nan"),
                    "score_mean": float(group_scores.mean()) if group_scores.size else float("nan"),
                    "value_mean": float(group_vals.mean()) if group_vals.size else float("nan"),
                },
            )
    else:
        if pose_dim > 0:
            group_rows.append(
                {
                    "group": "pose_enc",
                    "score_sum": float(scores[:pose_dim].sum()) if scores.size else float("nan"),
                    "score_mean": float(scores[:pose_dim].mean()) if scores.size else float("nan"),
                },
            )
        if global_dim > 0:
            start = pose_dim
            end = pose_dim + global_dim
            group_rows.append(
                {
                    "group": "global_feat",
                    "score_sum": float(scores[start:end].sum()) if scores.size else float("nan"),
                    "score_mean": float(scores[start:end].mean()) if scores.size else float("nan"),
                },
            )
        if total_dim > pose_dim + global_dim:
            start = pose_dim + global_dim
            group_rows.append(
                {
                    "group": "extra",
                    "score_sum": float(scores[start:].sum()) if scores.size else float("nan"),
                    "score_mean": float(scores[start:].mean()) if scores.size else float("nan"),
                },
            )
    if group_rows:
        st.dataframe(pd.DataFrame(group_rows), width="stretch", height=160)

    ablation_rows = attr_result.get("ablation_rows") or []
    if ablation_rows:
        st.markdown("**Group ablation (head features)**")
        st.dataframe(pd.DataFrame(ablation_rows), width="stretch", height=200)

    max_top_k = max(1, min(50, input_dim))
    top_k = int(
        st.slider(
            "Top-k features",
            min_value=1,
            max_value=max_top_k,
            value=min(20, max_top_k),
            step=1,
            key="vin_attr_top_k",
        ),
    )

    def _pose_group_for_idx(idx: int) -> str:
        pose_groups = attr_result.get("pose_groups") or []
        for group in pose_groups:
            start = int(group["start"])
            stop = int(group["stop"])
            if start <= idx < stop:
                return str(group["name"])
        return "pose_vec"

    rank_scores = np.abs(scores) if scores.size else scores
    order = np.argsort(rank_scores)[::-1][:top_k] if scores.size else np.array([], dtype=int)
    rows = []
    for rank, idx in enumerate(order):
        row = {
            "rank": rank + 1,
            "feature_idx": int(idx),
            "group": _pose_group_for_idx(int(idx))
            if input_kind == "Pose vector (raw)"
            else (
                "pose_enc" if int(idx) < pose_dim else "global_feat" if int(idx) < pose_dim + global_dim else "extra"
            ),
            "score": float(scores[idx]),
        }
        if show_std and raw_scores_std.size:
            row["std"] = float(raw_scores_std[idx])
        rows.append(row)
    st.dataframe(pd.DataFrame(rows), width="stretch", height=260)

    if order.size:
        bar_df = pd.DataFrame(
            {"score": scores[order]},
            index=[f"f{int(idx)}" for idx in order],
        )
        st.bar_chart(bar_df, height=240)

    if input_kind == "Pose vector (raw)":
        show_pose_bar = st.checkbox(
            "Show pose-dim bar chart",
            value=True,
            key="vin_attr_pose_bar",
        )
        if show_pose_bar:
            pose_groups = attr_result.get("pose_groups") or []
            pose_group_map = {}
            for group in pose_groups:
                for idx in range(int(group["start"]), int(group["stop"])):
                    pose_group_map[idx] = str(group["name"])
            pose_df = pd.DataFrame(
                {
                    "dim": np.arange(len(scores)),
                    "score": scores,
                    "group": [pose_group_map.get(idx, "pose_vec") for idx in range(len(scores))],
                },
            )
            st.bar_chart(pose_df.set_index("dim")[["score"]], height=200)


__all__ = ["render_testing_attribution_page"]
