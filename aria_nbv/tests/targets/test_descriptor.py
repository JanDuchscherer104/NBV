"""Tests for actor-safe target descriptors."""

# ruff: noqa: S101

from __future__ import annotations

import dataclasses

import pytest

import aria_nbv.targets as targets
from aria_nbv.targets import TargetDescriptor


def _descriptor() -> TargetDescriptor:
    return TargetDescriptor(
        target_id="scene:snippet:target",
        sem_id=28,
        class_name="window",
        pose_world_object=(1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 1.0, 2.0, 3.0),
        extents_m=(0.4, 0.5, 0.6),
        relative_pose_reference_object=(1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.1, 0.2, 0.3),
    )


def test_targets_root_exports_only_descriptor() -> None:
    assert targets.__all__ == ["TargetDescriptor"]


def test_target_descriptor_exposes_sanitized_instruction_fields() -> None:
    descriptor = _descriptor()

    assert descriptor.center_world == pytest.approx((1.0, 2.0, 3.0))
    assert descriptor.center_world_tensor().tolist() == pytest.approx([1.0, 2.0, 3.0])
    assert {field.name for field in dataclasses.fields(descriptor)} == {
        "target_id",
        "sem_id",
        "class_name",
        "pose_world_object",
        "extents_m",
        "relative_pose_reference_object",
    }


def test_target_descriptor_rejects_invalid_shapes_and_extents() -> None:
    kwargs = dataclasses.asdict(_descriptor())

    with pytest.raises(ValueError, match="pose_world_object"):
        TargetDescriptor(**{**kwargs, "pose_world_object": (1.0,)})
    with pytest.raises(ValueError, match="extents_m"):
        TargetDescriptor(**{**kwargs, "extents_m": (0.5, 0.5)})
    with pytest.raises(ValueError, match="positive"):
        TargetDescriptor(**{**kwargs, "extents_m": (0.5, 0.0, 0.5)})
