"""Summary helpers for the VIN v2 scorer.

`aria_nbv.vin.models.v2.VinModelV2` is retained as the seminar-era richer
one-step scorer. This module keeps its diagnostic report builder outside the
model class so the model file can focus on scorer modules, tensor flow, and
state-dict ownership.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import torch
from efm3d.aria.aria_constants import (
    ARIA_CALIB,
    ARIA_IMG,
    ARIA_POSE_T_WORLD_RIG,
)

from ...data_handling import EfmSnippetView, VinSnippetView
from ...utils.rich_summary import capture_tree, rich_summary, summarize

if TYPE_CHECKING:
    from ...data_handling import VinOracleBatch
    from ..models.v2 import VinModelV2


def summarize_vin_v2(
    self: VinModelV2,
    batch: VinOracleBatch,
    *,
    include_torchsummary: bool = True,
    torchsummary_depth: int = 3,
) -> str:
    """Summarize VIN v2 inputs, intermediate tensors, and outputs.

    Parameters
    ----------
    self:
        Concrete `aria_nbv.vin.models.v2.VinModelV2` instance to inspect.
    batch:
        Oracle-labeled VIN batch. The summary accepts raw EFM inputs or cached
        backbone outputs, matching the historical v2 model method.
    include_torchsummary:
        Whether to append per-module `torchsummary` blocks for trainable v2
        components.
    torchsummary_depth:
        Depth passed to `torchsummary.summary` when module summaries are
        enabled.

    Returns
    -------
    str
        Human-readable tree summary plus optional module summaries.
    """
    if batch.efm_snippet_view is None and batch.backbone_out is None:
        raise RuntimeError(
            "VIN v2 summary requires efm inputs or cached backbone outputs.",
        )

    snippet_view = batch.efm_snippet_view
    efm_dict: dict[str, Any] = {}
    efm_forward: EfmSnippetView | VinSnippetView | dict[str, Any]
    if isinstance(snippet_view, EfmSnippetView):
        efm_dict = snippet_view.efm
        efm_forward = snippet_view
    elif isinstance(snippet_view, VinSnippetView):
        if batch.backbone_out is None:
            raise RuntimeError(
                "VIN v2 summary requires cached backbone outputs when using VinSnippetView.",
            )
        efm_forward = snippet_view
    else:
        efm_forward = {}

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
            "VIN v2 summary expected backbone outputs to be available.",
        )
    if snippet_view is None:
        efm_summary = {"note": "cached batch (raw EFM inputs unavailable)"}
    elif isinstance(snippet_view, VinSnippetView):
        efm_summary = {
            "note": "VIN snippet cache (no raw EFM inputs)",
            "vin_snippet.points_world": summarize(snippet_view.points_world),
            "vin_snippet.lengths": summarize(snippet_view.lengths),
            "vin_snippet.t_world_rig": summarize(snippet_view.t_world_rig.tensor()),
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
        "field_in": summarize(debug.field_in),
        "field": summarize(debug.field),
        "global_feat": summarize(debug.global_feat),
        "concat_feats": summarize(debug.feats),
    }
    if debug.pos_grid is not None:
        feature_summary["pos_grid"] = summarize(debug.pos_grid)
    if debug.semidense_feat is not None:
        feature_summary["semidense_feat"] = summarize(
            debug.semidense_feat,
            include_stats=True,
        )
    if debug.semidense_proj is not None:
        feature_summary["semidense_proj"] = summarize(
            debug.semidense_proj,
            include_stats=True,
        )
    if debug.semidense_frustum is not None:
        feature_summary["semidense_frustum"] = summarize(
            debug.semidense_frustum,
            include_stats=True,
        )
    if debug.semidense_proj is not None:
        feature_summary["semidense_proj"] = summarize(
            debug.semidense_proj,
            include_stats=True,
        )
    if debug.traj_feat is not None:
        feature_summary["traj_feat"] = summarize(
            debug.traj_feat,
            include_stats=True,
        )
    if debug.traj_ctx is not None:
        feature_summary["traj_ctx"] = summarize(
            debug.traj_ctx,
            include_stats=True,
        )
    if debug.traj_pose_vec is not None:
        feature_summary["traj_pose_vec"] = summarize(
            debug.traj_pose_vec,
            include_stats=True,
        )
    if debug.traj_pose_enc is not None:
        feature_summary["traj_pose_enc"] = summarize(
            debug.traj_pose_enc,
            include_stats=True,
        )

    summary_dict = {
        "meta": {
            "scene_id": batch.scene_id,
            "snippet_id": batch.snippet_id,
            "device": str(debug.candidate_center_rig_m.device),
            "candidates": summarize(batch.candidate_poses_world_cam),
        },
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
            "candidate_valid": summarize(pred.candidate_valid),
            "voxel_valid_frac": summarize(pred.voxel_valid_frac, include_stats=True),
            "semidense_candidate_vis_frac": summarize(
                getattr(pred, "semidense_candidate_vis_frac", pred.semidense_valid_frac),
                include_stats=True,
            ),
            "semidense_valid_frac": summarize(
                getattr(pred, "semidense_candidate_vis_frac", pred.semidense_valid_frac),
                include_stats=True,
            ),
        },
    }
    for key in ["points/p3s_world", "points/dist_std", "pose/gravity_in_world"]:
        if efm_dict and key in efm_dict:
            summary_dict.setdefault("efm", {})[key] = summarize(efm_dict.get(key))

    tree = rich_summary(
        tree_dict=summary_dict,
        root_label="VIN v2 summary (oracle batch)",
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


__all__ = ["summarize_vin_v2"]
