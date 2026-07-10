"""Privileged target evidence resolution for oracle scoring."""

from __future__ import annotations

from typing import TYPE_CHECKING

from efm3d.aria.obb import ObbTW

from .target_selection import (
    TargetCandidateRow,
    _compact_obb_block,
    _valid_obb_data_with_source_indices,
    _world_obbs_for_sample,
)

if TYPE_CHECKING:
    from ..data_handling.offline.dataset import VinOfflineSample


def target_gt_obb_world(row: TargetCandidateRow, sample: "VinOfflineSample") -> ObbTW:
    """Resolve the matched GT target OBB in world coordinates.

    Args:
        row: Oracle-selected target row after GT task admission.
        sample: VIN offline sample carrying ``gt_obbs`` and snippet transform.

    Returns:
        A single-row `ObbTW` in world coordinates.

    Raises:
        ValueError: If the row is not label-valid or the matched GT row cannot
            be resolved.
    """

    if not row.gt_label_valid or row.gt_target_row_id is None:
        raise ValueError("Target row is not GT-label valid; refusing to build target RRI crop.")
    gt_block = _compact_obb_block(sample.gt_obbs)
    if gt_block is None:
        raise ValueError("Target RRI crop requires sample.gt_obbs.")
    gt_world = _world_obbs_for_sample(gt_block[0], sample)
    gt_data, gt_source_indices = _valid_obb_data_with_source_indices(gt_world)
    try:
        gt_index = gt_source_indices.index(int(row.gt_target_row_id))
    except ValueError as exc:
        raise ValueError(f"Matched GT target row {row.gt_target_row_id} is not present in sample.gt_obbs.") from exc
    return ObbTW(gt_data[gt_index].unsqueeze(0))


__all__ = ["target_gt_obb_world"]
