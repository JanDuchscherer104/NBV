from __future__ import annotations

import importlib

import pytest

import aria_nbv.vin.types as vin_types
from aria_nbv.vin.types import (
    EfmDict,
    EvlBackboneOutput,
    FieldBundle,
    VinPrediction,
    VinV3ForwardDiagnostics,
)
from aria_nbv.vin.types.backbone import EfmDict as LeafEfmDict
from aria_nbv.vin.types.backbone import EvlBackboneOutput as LeafEvlBackboneOutput
from aria_nbv.vin.types.diagnostics import VinForwardDiagnostics as LeafVinForwardDiagnostics
from aria_nbv.vin.types.diagnostics import VinV2ForwardDiagnostics as LeafVinV2ForwardDiagnostics
from aria_nbv.vin.types.diagnostics import VinV3ForwardDiagnostics as LeafVinV3ForwardDiagnostics
from aria_nbv.vin.types.model_inputs import FieldBundle as LeafFieldBundle
from aria_nbv.vin.types.prediction import VinPrediction as LeafVinPrediction


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


def test_backbone_types_are_leaf_owned_and_aggregated() -> None:
    """The aggregate import path should expose EVL DTOs owned by the backbone leaf."""
    assert EfmDict is LeafEfmDict
    assert EvlBackboneOutput is LeafEvlBackboneOutput


def test_prediction_types_are_leaf_owned_and_aggregated() -> None:
    """The aggregate import path should expose scorer outputs owned by the prediction leaf."""
    assert VinPrediction is LeafVinPrediction


def test_model_input_types_are_leaf_owned_and_aggregated() -> None:
    """The aggregate import path should expose DTOs owned by the leaf module."""
    assert FieldBundle is LeafFieldBundle


def test_diagnostics_types_are_leaf_owned_and_aggregated() -> None:
    """Only the active V3 diagnostic remains on the aggregate import path."""

    assert not hasattr(vin_types, "VinForwardDiagnostics")
    assert not hasattr(vin_types, "VinV2ForwardDiagnostics")
    assert VinV3ForwardDiagnostics is LeafVinV3ForwardDiagnostics
    assert LeafVinForwardDiagnostics is not None
    assert LeafVinV2ForwardDiagnostics is not None


def test_experimental_diagnostics_import_paths_are_removed() -> None:
    for module_name in (
        "aria_nbv.vin.experimental.types",
        "aria_nbv.vin.experimental.plotting",
    ):
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(module_name)
