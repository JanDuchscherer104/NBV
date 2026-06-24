"""Tests for canonical VIN shell-pose encoders."""

from __future__ import annotations

import torch
from efm3d.aria.pose import PoseTW

from aria_nbv.vin.encoders import (
    FourierFeaturesConfig,
    ShellLffPoseEncoderConfig,
    ShellShPoseEncoderAdapterConfig,
    infer_pose_vec_groups,
)
from aria_nbv.vin.encoders.shell_descriptor import encode_shell_pose_descriptor


def _pose_at_x() -> PoseTW:
    rotation = torch.eye(3, dtype=torch.float32).unsqueeze(0)
    translation = torch.tensor([[2.0, 0.0, 0.0]], dtype=torch.float32)
    return PoseTW.from_Rt(rotation, translation)


def test_shell_descriptor_uses_reference_frame_center_and_forward_axis() -> None:
    descriptor = encode_shell_pose_descriptor(_pose_at_x())

    assert descriptor.center_m.shape == (1, 3)
    assert descriptor.pose_vec.shape == (1, 8)
    torch.testing.assert_close(descriptor.center_dir, torch.tensor([[1.0, 0.0, 0.0]]))
    torch.testing.assert_close(descriptor.forward_dir, torch.tensor([[0.0, 0.0, 1.0]]))
    torch.testing.assert_close(descriptor.radius_m, torch.tensor([[2.0]]))
    torch.testing.assert_close(descriptor.view_alignment, torch.tensor([[0.0]]))


def test_shell_lff_pose_encoder_preserves_pose_output_contract() -> None:
    encoder = ShellLffPoseEncoderConfig().setup_target()
    out = encoder.encode(_pose_at_x())

    assert out.pose_vec.shape == (1, 8)
    assert out.pose_enc.shape == (1, encoder.out_dim)
    assert out.center_dir is not None
    assert out.forward_dir is not None
    assert out.radius_m is not None
    assert out.view_alignment is not None


def test_shell_sh_adapter_preserves_pose_output_contract() -> None:
    encoder = ShellShPoseEncoderAdapterConfig().setup_target()
    out = encoder.encode(_pose_at_x())

    assert out.pose_vec.shape == (1, 8)
    assert out.pose_enc.shape == (1, encoder.out_dim)


def test_fixed_fourier_and_pose_groups_are_public_encoder_helpers() -> None:
    fixed = FourierFeaturesConfig(input_dim=1, num_frequencies=3).setup_target()
    assert fixed(torch.ones(2, 1)).shape == (2, 7)
    assert infer_pose_vec_groups(8) == [
        ("center_dir", slice(0, 3)),
        ("forward_dir", slice(3, 6)),
        ("radius", slice(6, 7)),
        ("view_alignment", slice(7, 8)),
    ]
