from __future__ import annotations

from aria_nbv.vin.types import EfmDict, FieldBundle
from aria_nbv.vin.types.model_inputs import FieldBundle as LeafFieldBundle


def test_efm_dict_contains_expected_keys() -> None:
    expected = {
        "occ_pr",
        "voxel_extent",
        "rgb/feat2d_upsampled",
        "rgb/token2d",
        "voxel/feat",
        "voxel/counts",
        "voxel/counts_m",
        "voxel/pts_world",
        "voxel/T_world_voxel",
        "voxel/selectT",
        "voxel/occ_input",
        "neck/occ_feat",
        "neck/obb_feat",
        "cent_pr",
        "bbox_pr",
        "clas_pr",
        "obbs_pr_nms",
        "cent_pr_nms",
        "obbs/pred/sem_id_to_name",
        "obbs/pred",
        "obbs/pred_viz",
        "obbs/pred/probs_full",
        "obbs/pred/probs_ful_viz",
    }

    assert expected.issubset(EfmDict.__annotations__)


def test_model_input_types_are_leaf_owned_and_aggregated() -> None:
    """The aggregate import path should expose DTOs owned by the leaf module."""
    assert FieldBundle is LeafFieldBundle
