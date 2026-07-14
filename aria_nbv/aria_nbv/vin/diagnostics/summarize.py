"""Summary helpers for VIN v3 inputs, predictions, and cached batch structure.

This module provides a text report spanning actor-visible tensors, candidate
CORAL outputs, optional oracle-labelled metrics, and trainable-module structure.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import torch
from efm3d.aria.aria_constants import (
    ARIA_CALIB,
    ARIA_IMG,
    ARIA_POSE_T_WORLD_RIG,
)
from torch.nn import functional as functional

from ...data_handling import (
    EfmSnippetView,
    VinSnippetView,
    is_efm_snippet_view_instance,
    is_vin_snippet_view_instance,
)
from ...rri_metrics.coral import coral_monotonicity_violation_rate
from ...utils.rich_summary import capture_tree, rich_summary, summarize
from .summary_stats import pearson_corr, quantile_stats, spearman_corr

if TYPE_CHECKING:
    from ...data_handling import VinOracleBatch
    from ..models.scene_myopic import VinModelV3


def summarize_vin_v3(
    self: VinModelV3,
    batch: VinOracleBatch,
    *,
    include_torchsummary: bool = True,
    torchsummary_depth: int = 3,
) -> str:
    """Build a human-readable VIN-Core report for one oracle-labelled batch.

    The summary runs a debug forward pass from the batch's snippet view and
    cached actor-visible EVL evidence, then reports tensor shapes/statistics,
    candidate validity diagnostics, CORAL monotonicity, and optional comparison
    with oracle labels. Oracle values are used only in the report; they are not
    passed into the scorer.

    Args:
        self: VIN-Core scorer to inspect.
        batch: Batch carrying candidates, camera rows, cached evidence, and
            optional oracle supervision.
        include_torchsummary: Include a parameter/module summary when ``True``.
        torchsummary_depth: Maximum nested module depth for that summary.

    Returns:
        Rendered multiline diagnostic report. The scorer's original training
        mode is restored before returning.
    """

    if batch.efm_snippet_view is None and batch.backbone_out is None:
        raise RuntimeError(
            "VIN v3 summary requires efm inputs or cached backbone outputs.",
        )

    snippet_view = batch.efm_snippet_view
    efm_dict: dict[str, Any] = {}
    efm_forward: EfmSnippetView | VinSnippetView
    if is_efm_snippet_view_instance(snippet_view):
        efm_dict = snippet_view.efm
        efm_forward = snippet_view
    elif is_vin_snippet_view_instance(snippet_view):
        efm_forward = snippet_view
    else:
        raise RuntimeError(
            "VIN v3 summary requires a VinSnippetView or EfmSnippetView in the batch.",
        )

    was_training = self.training
    self.eval()
    with torch.no_grad():
        pred, debug = self.forward_with_debug(
            efm_forward,
            candidate_poses_world_cam=batch.candidate_poses_world_cam,
            reference_pose_world_rig=batch.reference_pose_world_rig,
            p3d_cameras=batch.p3d_cameras,
            backbone_out=batch.backbone_out,
        )
    if was_training:
        self.train()

    backbone_out = debug.backbone_out
    if backbone_out is None:
        raise RuntimeError(
            "VIN v3 summary expected backbone outputs to be available.",
        )
    if snippet_view is None:
        efm_summary = {"note": "cached batch (raw EFM inputs unavailable)"}
    elif is_vin_snippet_view_instance(snippet_view):
        points_world = snippet_view.points_world
        points_mask = torch.isfinite(points_world[..., :3]).all(dim=-1)
        valid_points = int(points_mask.sum().item())
        total_points = int(points_mask.numel())
        inv_dist_std_stats = None
        obs_count_stats = None
        if points_world.shape[-1] >= 4:
            inv_dist_std_stats = quantile_stats(points_world[..., 3][points_mask])
        if points_world.shape[-1] >= 5:
            obs_count_stats = quantile_stats(points_world[..., 4][points_mask])
        efm_summary = {
            "note": "VIN offline-store snippet (no raw EFM inputs)",
            "vin_snippet.points_world": summarize(snippet_view.points_world, include_stats=True),
            "vin_snippet.lengths": summarize(snippet_view.lengths, include_stats=True),
            "vin_snippet.t_world_rig": summarize(snippet_view.t_world_rig.tensor()),
            "vin_snippet.valid_points": f"{valid_points}/{total_points}",
            "vin_snippet.inv_dist_std": inv_dist_std_stats,
            "vin_snippet.obs_count": obs_count_stats,
        }
    else:
        efm_summary = {
            **{key: summarize(efm_dict.get(key)) for key in ARIA_IMG},
            **{key: summarize(efm_dict.get(key)) for key in ARIA_CALIB},
            ARIA_POSE_T_WORLD_RIG: summarize(efm_dict.get(ARIA_POSE_T_WORLD_RIG)),
        }
    backbone_summary = {
        "occ_pr": summarize(backbone_out.occ_pr),
        "occ_input": summarize(backbone_out.occ_input),
        "counts": summarize(backbone_out.counts),
        "cent_pr": summarize(backbone_out.cent_pr),
        "voxel/pts_world": summarize(backbone_out.pts_world),
        "T_world_voxel": summarize(backbone_out.t_world_voxel),
        "voxel_extent": summarize(backbone_out.voxel_extent),
    }
    optional_backbone = {
        "free_input": backbone_out.free_input,
        "counts_m": backbone_out.counts_m,
        "voxel_feat": backbone_out.voxel_feat,
        "occ_feat": backbone_out.occ_feat,
        "obb_feat": backbone_out.obb_feat,
        "bbox_pr": backbone_out.bbox_pr,
        "clas_pr": backbone_out.clas_pr,
        "cent_pr_nms": backbone_out.cent_pr_nms,
        "obbs_pr_nms": backbone_out.obbs_pr_nms,
        "obb_pred": backbone_out.obb_pred,
        "obb_pred_viz": backbone_out.obb_pred_viz,
        "obb_pred_probs_full": backbone_out.obb_pred_probs_full,
        "obb_pred_probs_full_viz": backbone_out.obb_pred_probs_full_viz,
        "voxel_select_t": backbone_out.voxel_select_t,
        "feat2d_upsampled": backbone_out.feat2d_upsampled,
        "token2d": backbone_out.token2d,
    }
    for key, value in optional_backbone.items():
        if value is not None:
            backbone_summary[key] = summarize(value)

    feature_summary = {
        "field_in": summarize(debug.field_in, include_stats=True),
        "field": summarize(debug.field, include_stats=True),
        "global_feat": summarize(debug.global_feat, include_stats=True),
        "concat_feats": summarize(debug.feats, include_stats=True),
    }
    if debug.pos_grid is not None:
        feature_summary["pos_grid"] = summarize(debug.pos_grid, include_stats=True)
    if debug.semidense_proj is not None:
        feature_summary["semidense_proj"] = summarize(
            debug.semidense_proj,
            include_stats=True,
        )
    if debug.semidense_grid_feat is not None:
        feature_summary["semidense_grid_feat"] = summarize(
            debug.semidense_grid_feat,
            include_stats=True,
        )
    if debug.voxel_proj is not None:
        feature_summary["voxel_proj"] = summarize(
            debug.voxel_proj,
            include_stats=True,
        )
    traj_summary: dict[str, str] = {}
    if debug.traj_feat is not None:
        traj_summary["traj_feat"] = summarize(debug.traj_feat, include_stats=True)
    if debug.traj_ctx is not None:
        traj_summary["traj_ctx"] = summarize(debug.traj_ctx, include_stats=True)
    if debug.traj_pose_vec is not None:
        traj_summary["traj_pose_vec"] = summarize(debug.traj_pose_vec, include_stats=True)
    if debug.traj_pose_enc is not None:
        traj_summary["traj_pose_enc"] = summarize(debug.traj_pose_enc, include_stats=True)

    expected_rri = None
    if getattr(self.head_coral, "has_bin_values", False):
        try:
            expected_rri = self.head_coral.expected_from_probs(pred.prob)
        except Exception:
            expected_rri = None
    entropy = None
    try:
        prob = pred.prob.clamp_min(1e-12)
        entropy = (-prob * torch.log(prob)).sum(dim=-1)
    except Exception:
        entropy = None
    monotonicity = coral_monotonicity_violation_rate(pred.logits)

    candidate_radius = torch.linalg.vector_norm(debug.candidate_center_rig_m, dim=-1)
    candidate_valid_rate = float(pred.candidate_valid.to(dtype=torch.float32).mean().item())
    metrics_dict: dict[str, Any] = {
        "candidate_valid_rate": candidate_valid_rate,
        "candidate_radius_m": quantile_stats(candidate_radius),
        "voxel_valid_frac": quantile_stats(pred.voxel_valid_frac) if pred.voxel_valid_frac is not None else None,
        "semidense_candidate_vis_frac": (
            quantile_stats(pred.semidense_candidate_vis_frac) if pred.semidense_candidate_vis_frac is not None else None
        ),
        "coral_monotonicity_violation_rate": quantile_stats(monotonicity),
        "coral_entropy": quantile_stats(entropy) if entropy is not None else None,
    }
    if batch.rri is not None:
        corr = {
            "pearson": pearson_corr(batch.rri, pred.expected_normalized),
            "spearman": spearman_corr(batch.rri, pred.expected_normalized),
        }
        metrics_dict["oracle_rri_vs_expected_normalized"] = corr

    summary_dict = {
        "meta": {
            "scene_id": batch.scene_id,
            "snippet_id": batch.snippet_id,
            "device": str(debug.candidate_center_rig_m.device),
            "candidates": summarize(batch.candidate_poses_world_cam),
        },
        "metrics": metrics_dict,
        "efm": efm_summary,
        "backbone": backbone_summary,
        "pose": {
            "candidate_center_rig_m": summarize(
                debug.candidate_center_rig_m,
                include_stats=True,
            ),
            "pose_vec": summarize(debug.pose_vec, include_stats=True),
            "pose_enc": summarize(debug.pose_enc),
        },
        "features": feature_summary,
        "outputs": {
            "logits": summarize(pred.logits),
            "prob": summarize(pred.prob),
            "expected": summarize(pred.expected, include_stats=True),
            "expected_normalized": summarize(
                pred.expected_normalized,
                include_stats=True,
            ),
            "expected_rri": summarize(expected_rri, include_stats=True),
            "candidate_valid": summarize(pred.candidate_valid),
            "voxel_valid_frac": summarize(pred.voxel_valid_frac, include_stats=True),
            "semidense_candidate_vis_frac": summarize(pred.semidense_candidate_vis_frac, include_stats=True),
        },
    }
    if traj_summary:
        summary_dict["trajectory"] = traj_summary
    for key in ["points/p3s_world", "points/dist_std", "pose/gravity_in_world"]:
        if key in efm_dict:
            summary_dict.setdefault("efm", {})[key] = summarize(efm_dict.get(key))

    tree = rich_summary(
        tree_dict=summary_dict,
        root_label="VIN v3 summary (oracle batch)",
        with_shape=True,
        is_print=False,
    )
    lines: list[str] = [capture_tree(tree), ""]

    trainable_params = sum(p.numel() for p in self.parameters() if p.requires_grad)
    total_params = sum(p.numel() for p in self.parameters())
    lines.append(
        f"Trainable VIN params: {trainable_params:,} (vin total params: {total_params:,}; EVL frozen not counted)",
    )
    lines.append("")

    def _add_candidate_table(title: str, indices: torch.Tensor, *, batch_idx: int) -> None:
        def _get_scalar(values: torch.Tensor | None, b: int, n: int) -> float:
            if values is None:
                return float("nan")
            if values.ndim == 1:
                return float(values[n].item())
            if values.ndim == 2:
                return float(values[b, n].item())
            return float(values.reshape(-1)[n].item())

        def _get_bool(values: torch.Tensor, b: int, n: int) -> bool:
            if values.ndim == 1:
                return bool(values[n].item())
            if values.ndim == 2:
                return bool(values[b, n].item())
            return bool(values.reshape(-1)[n].item())

        lines.append(title)
        header = "idx  expected  exp_rri    vox   sem   rad_m  valid"
        if batch.rri is not None:
            header += "  oracle_rri"
        lines.append(header)
        for idx in indices.tolist():
            expected = _get_scalar(pred.expected_normalized, batch_idx, idx)
            vox_val = _get_scalar(pred.voxel_valid_frac, batch_idx, idx)
            sem_val = _get_scalar(pred.semidense_candidate_vis_frac, batch_idx, idx)
            rad = _get_scalar(candidate_radius, batch_idx, idx)
            valid = _get_bool(pred.candidate_valid, batch_idx, idx)
            exp_rri_val = float("nan")
            if expected_rri is not None:
                exp_rri_val = _get_scalar(expected_rri, batch_idx, idx)
            row = f"{idx:3d}  {expected:7.3f}  {exp_rri_val:7.4f}  {vox_val:5.2f}  {sem_val:5.2f}  {rad:5.2f}  {valid!s:>5}"
            if batch.rri is not None:
                oracle_val = _get_scalar(batch.rri, batch_idx, idx)
                row += f"  {oracle_val:9.4f}"
            lines.append(row)
        lines.append("")

    batch_size = int(pred.expected_normalized.shape[0]) if pred.expected_normalized.ndim == 2 else 1
    num_candidates = int(pred.expected_normalized.shape[1]) if pred.expected_normalized.ndim == 2 else 0
    if batch_size > 0 and num_candidates > 0:
        max_show_batches = min(batch_size, 2)
        k = min(8, num_candidates)
        for b in range(max_show_batches):
            scores = pred.expected_normalized[b]
            topk = torch.topk(scores, k=k, largest=True).indices
            bottomk = torch.topk(scores, k=k, largest=False).indices
            lines.append(f"Candidate ranking (batch {b})")
            lines.append("")
            _add_candidate_table(f"Top-{k} by expected_normalized:", topk, batch_idx=b)
            _add_candidate_table(f"Bottom-{k} by expected_normalized:", bottomk, batch_idx=b)

    if include_torchsummary:
        from torchsummary import summary as torch_summary

        pose_vec = debug.pose_vec.reshape(
            debug.pose_vec.shape[0] * debug.pose_vec.shape[1],
            -1,
        )
        feats_2d = debug.feats.reshape(
            debug.feats.shape[0] * debug.feats.shape[1],
            -1,
        )

        pose_encoder_lff = self.pose_encoder_lff
        if pose_encoder_lff is not None:
            lines.append("torchsummary: pose_encoder_lff (trainable)")
            lines.append(
                str(
                    torch_summary(
                        pose_encoder_lff,
                        input_data=pose_vec,
                        verbose=0,
                        depth=torchsummary_depth,
                        device=debug.candidate_center_rig_m.device,
                    ),
                ),
            )
            lines.append("")
        else:
            lines.append("torchsummary: pose_encoder (non-LFF) skipped")
            lines.append("")

        lines.append("torchsummary: field_proj (trainable)")
        lines.append(
            str(
                torch_summary(
                    self.field_proj,
                    input_data=debug.field_in,
                    verbose=0,
                    depth=torchsummary_depth,
                    device=debug.candidate_center_rig_m.device,
                ),
            ),
        )
        lines.append("")

        lines.append("torchsummary: scorer MLP (trainable)")
        lines.append(
            str(
                torch_summary(
                    self.head_mlp,
                    input_data=feats_2d,
                    verbose=0,
                    depth=torchsummary_depth,
                    device=debug.candidate_center_rig_m.device,
                ),
            ),
        )
        lines.append("")

        lines.append("torchsummary: CORAL head (trainable)")
        lines.append(
            str(
                torch_summary(
                    self.head_coral,
                    input_data=self.head_mlp(feats_2d),
                    verbose=0,
                    depth=torchsummary_depth,
                    device=debug.candidate_center_rig_m.device,
                ),
            ),
        )

    return "\n".join(lines)
