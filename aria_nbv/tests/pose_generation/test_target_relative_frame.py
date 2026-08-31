"""Cross-contract tests for the canonical target-relative frame."""

from __future__ import annotations

import pytest
import torch

from aria_nbv.geometry import TargetRelativeFrame, TargetRelativeFrameDegeneracyError, TargetRelativeFrameError


def test_target_relative_frame_is_right_handed_invertible_and_versioned() -> None:
    origin = torch.tensor((2.0, -1.0, 0.5), dtype=torch.float64)
    target = torch.tensor((5.0, 3.0, 2.5), dtype=torch.float64)
    frame = TargetRelativeFrame.from_origin_target(origin, target, frame_identity="scene:state:target")

    basis = frame.basis_world_from_frame
    assert basis.T @ basis == pytest.approx(torch.eye(3, dtype=torch.float64))
    assert torch.linalg.det(basis).item() == pytest.approx(1.0)
    assert torch.cross(frame.forward_world, frame.lateral_world, dim=0) == pytest.approx(frame.up_world)
    assert frame.world_to_frame_points(target) == pytest.approx(
        torch.tensor((0.9284766908852594, 0.0, 0.3713906763541037), dtype=torch.float64)
    )
    points = torch.tensor(((2.0, -1.0, 0.5), (3.0, 2.0, 4.0)), dtype=torch.float64)
    assert frame.frame_to_world_points(frame.world_to_frame_points(points)) == pytest.approx(points)
    assert frame.SEMANTIC_VERSION == "target-relative-z-up-v1"
    assert frame.frame_identity == "scene:state:target"


@pytest.mark.parametrize(
    "target",
    [
        (0.0, 0.0, 0.0),
        (0.0, 0.0, 2.0),
        (float("nan"), 1.0, 0.0),
    ],
)
def test_target_relative_frame_rejects_degenerate_or_nonfinite_bearings(
    target: tuple[float, float, float],
) -> None:
    with pytest.raises(TargetRelativeFrameDegeneracyError):
        TargetRelativeFrame.from_origin_target(
            torch.zeros(3),
            torch.tensor(target),
            frame_identity="degenerate",
        )


def test_target_relative_frame_retains_exact_projected_horizontal_delta() -> None:
    origin = torch.tensor((0.125, -0.75, 4.0), dtype=torch.float32)
    target = torch.tensor((3.125, 2.25, 9.5), dtype=torch.float32)
    frame = TargetRelativeFrame.from_origin_target(origin, target, frame_identity="parity")
    up = torch.tensor((0.0, 0.0, 1.0), dtype=torch.float32)
    delta = target - origin
    expected = delta - (delta @ up) * up

    assert torch.equal(frame.horizontal_target_delta_world, expected)


def test_target_relative_frame_factory_uses_one_combined_scalar_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    original = torch.Tensor.item

    def counted_item(tensor: torch.Tensor) -> object:
        nonlocal calls
        calls += 1
        return original(tensor)

    monkeypatch.setattr(torch.Tensor, "item", counted_item)

    TargetRelativeFrame.from_origin_target(
        torch.zeros(3),
        torch.tensor((1.0, 2.0, 3.0)),
        frame_identity="single-sync",
    )

    assert calls == 1


def test_target_relative_frame_rejects_unvalidated_direct_construction() -> None:
    with pytest.raises(TypeError, match="from_origin_target"):
        TargetRelativeFrame()


@pytest.mark.parametrize("epsilon", [0.0, -1.0, float("inf"), float("-inf"), float("nan"), True])
def test_target_relative_frame_rejects_invalid_epsilon_before_tensor_work(epsilon: float) -> None:
    with pytest.raises(TargetRelativeFrameError, match="epsilon"):
        TargetRelativeFrame.from_origin_target(
            torch.zeros(3),
            torch.tensor((1.0, 0.0, 0.0)),
            frame_identity="frame",
            epsilon=epsilon,
        )


@pytest.mark.parametrize("frame_identity", ["", "   "])
def test_target_relative_frame_rejects_empty_identity(frame_identity: str) -> None:
    with pytest.raises(TargetRelativeFrameError, match="identity"):
        TargetRelativeFrame.from_origin_target(
            torch.zeros(3),
            torch.tensor((1.0, 0.0, 0.0)),
            frame_identity=frame_identity,
        )


def test_target_relative_frame_preserves_autograd() -> None:
    target = torch.tensor((2.0, 1.0, 0.5), dtype=torch.float64, requires_grad=True)
    frame = TargetRelativeFrame.from_origin_target(torch.zeros(3, dtype=torch.float64), target, frame_identity="grad")
    value = frame.world_to_frame_points(torch.tensor((1.0, 2.0, 3.0), dtype=torch.float64)).sum()
    value.backward()

    assert target.grad is not None
    assert torch.isfinite(target.grad).all()
