"""Tests for the canonical PointNeXt VIN encoder surface."""

from __future__ import annotations

import importlib

import pytest
import torch

from aria_nbv.vin.encoders import PointNeXtSEncoder, PointNeXtSEncoderConfig
from aria_nbv.vin.encoders.pointnext_utils import extract_point_encoder_tensor


def test_pointnext_encoder_is_exported_from_canonical_encoder_package() -> None:
    assert PointNeXtSEncoderConfig().target_type is PointNeXtSEncoder


def test_extract_point_encoder_tensor_accepts_common_openpoints_payloads() -> None:
    tensor = torch.ones(2, 3)

    assert extract_point_encoder_tensor(tensor) is tensor
    assert extract_point_encoder_tensor({"feat": tensor}) is tensor
    assert extract_point_encoder_tensor({"ignored": "x", "features": tensor}) is tensor
    assert extract_point_encoder_tensor((None, tensor)) is tensor

    with pytest.raises(TypeError, match="did not contain a tensor"):
        extract_point_encoder_tensor({"feat": "not-a-tensor"})


def test_experimental_pointnext_import_path_is_removed() -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("aria_nbv.vin.experimental.pointnext_encoder")
