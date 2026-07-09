"""CORAL ordinal regression utilities for RRI-derived labels.

This module uses the MIT-licensed reference implementation from
[`coral-pytorch`](https://raschka-research-group.github.io/coral-pytorch/).

VIN-NBV trains the RRI predictor via ordinal classification and uses a ranking-aware
loss (CORAL) to penalize distant misclassifications more strongly than nearby ones.
The expected value decoded from CORAL logits is a one-step ranking proxy; oracle
RRI and endpoint target-quality metrics remain the geometry-grounded evaluation
signals.
"""

from __future__ import annotations

import math
from typing import Literal

import torch
from coral_pytorch.layers import CoralLayer as _CoralLayer
from coral_pytorch.losses import coral_loss as _coral_loss
from torch import Tensor, nn

from .ordinal_binning import ordinal_labels_to_levels


def coral_loss(
    logits: Tensor,
    labels: Tensor,
    *,
    num_classes: int,
    importance_weights: Tensor | None = None,
    reduction: Literal["mean", "sum", "none"] = "mean",
) -> Tensor:
    """Compute CORAL loss (sum of binary cross-entropies over thresholds).

    Args:
        logits: ``Tensor["... K-1", float32]`` threshold logits.
        labels: ``Tensor["...", int64]`` ordinal labels in ``[0, K-1]``.
        num_classes: Number of ordinal classes ``K``.
        importance_weights: Optional per-threshold weights ``Tensor["K-1"]``.
        reduction: Reduction mode.

    Returns:
        Loss tensor. If reduction="none": ``Tensor["..."]``.
    """

    levels = ordinal_labels_to_levels(labels, num_classes=num_classes)

    # `coral_pytorch.losses.coral_loss` expects logits and levels with identical shapes.
    loss = _coral_loss(
        logits.reshape(-1, logits.shape[-1]),
        levels.reshape(-1, levels.shape[-1]),
        importance_weights=importance_weights,
        reduction=None if reduction == "none" else reduction,
    )
    if reduction == "none":
        return loss.reshape(labels.shape)
    return loss


def coral_logits_to_prob(logits: Tensor) -> Tensor:
    """Convert CORAL logits to a proper class distribution.

    Args:
        logits: ``Tensor["... K-1"]``

    Returns:
        ``Tensor["... K"]`` probabilities that sum to 1 along the last dim.
    """

    if logits.shape[-1] < 1:
        raise ValueError("Expected logits with last dim K-1 >= 1.")

    p_gt = torch.sigmoid(logits)  # P(y > k), shape (..., K-1)
    k_minus_1 = p_gt.shape[-1]
    num_classes = k_minus_1 + 1

    probs: list[Tensor] = []
    probs.append(1.0 - p_gt[..., 0])
    for k in range(1, k_minus_1):
        probs.append(p_gt[..., k - 1] - p_gt[..., k])
    probs.append(p_gt[..., -1])

    prob = torch.stack(probs, dim=-1)
    prob = torch.clamp(prob, min=0.0, max=1.0)
    prob = prob / (prob.sum(dim=-1, keepdim=True) + 1e-8)

    assert prob.shape[-1] == num_classes
    return prob


def coral_random_loss(num_classes: int) -> float:
    """Expected CORAL loss for a random classifier.

    For random logits, each threshold probability is 0.5, yielding a
    binary cross-entropy of log(2) per threshold.

    Args:
        num_classes: Number of ordinal classes ``K``.

    Returns:
        Expected CORAL loss for uniform random predictions.
    """
    num_thresholds = max(1, int(num_classes) - 1)
    return float(num_thresholds * math.log(2.0))


def _softplus_inverse(x: Tensor) -> Tensor:
    """Approximate inverse of softplus for positive targets."""
    eps = torch.finfo(x.dtype).eps if x.dtype.is_floating_point else 1e-6
    return torch.log(torch.expm1(x.clamp_min(eps)))


class MonotoneBinValues(nn.Module):
    """Learnable, monotone bin representatives ``u_k``.

    We parameterize ``u_k`` via a base value and positive deltas:

        u_0 in R
        u_k = u_0 + sum_{j=1..k} softplus(delta_j)

    This guarantees ``u_0 <= u_1 <= ... <= u_{K-1}`` while keeping gradients stable.
    """

    def __init__(self, num_classes: int, init_values: Tensor, *, min_delta: float = 1e-6) -> None:
        super().__init__()
        if int(num_classes) < 2:
            raise ValueError("num_classes must be >= 2.")
        if init_values.numel() != int(num_classes):
            raise ValueError(
                f"init_values must have shape (K,), got {tuple(init_values.shape)} for K={num_classes}.",
            )
        init_values = init_values.detach().to(dtype=torch.float32)
        deltas = torch.diff(init_values).clamp_min(float(min_delta))
        self.u0 = nn.Parameter(init_values[:1].clone())
        self.delta_unconstrained = nn.Parameter(_softplus_inverse(deltas))
        self.register_buffer("_num_classes", torch.tensor(int(num_classes)))

    @property
    def num_classes(self) -> int:
        return int(self._num_classes.item())

    def values(self) -> Tensor:
        """Return monotone bin representatives ``u_k``."""
        deltas = torch.nn.functional.softplus(self.delta_unconstrained)
        u_tail = self.u0 + torch.cumsum(deltas, dim=0)
        return torch.cat([self.u0, u_tail], dim=0)

    def reset_from_values(self, values: Tensor, *, min_delta: float = 1e-6) -> None:
        """Re-initialize from target values (keeps monotonicity)."""
        if values.numel() != self.num_classes:
            raise ValueError(
                f"Expected {self.num_classes} values, got {tuple(values.shape)}.",
            )
        values = values.detach().to(dtype=self.u0.dtype, device=self.u0.device)
        deltas = torch.diff(values).clamp_min(float(min_delta))
        with torch.no_grad():
            self.u0.copy_(values[:1])
            self.delta_unconstrained.copy_(_softplus_inverse(deltas))


def coral_expected_from_logits(logits: Tensor) -> tuple[Tensor, Tensor]:
    """Compute expected ordinal value from CORAL logits.

    Args:
        logits: ``Tensor["... K-1"]``.

    Returns:
        Tuple of ``(expected, expected_normalized)`` where:
        - expected is in ``[0, K-1]``
        - expected_normalized is in ``[0, 1]``
    """

    # In CORAL, the logits parameterize the probabilities P(y > k).
    # The expected rank label is E[y] = sum_{k=0}^{K-2} P(y > k).
    prob_gt = torch.sigmoid(logits)
    expected = prob_gt.sum(dim=-1)
    expected_normalized = expected / max(1.0, float(prob_gt.shape[-1]))
    return expected, expected_normalized


def coral_logits_to_label(logits: Tensor, *, threshold: float = 0.5) -> Tensor:
    """Decode CORAL logits into ordinal class labels via threshold counting.

    CORAL models the probabilities ``P(y > k)`` for thresholds ``k=0..K-2``.
    The predicted label is therefore the number of thresholds whose
    probability exceeds ``threshold`` (default 0.5).

    Args:
        logits: ``Tensor["... K-1"]`` threshold logits.
        threshold: Probability threshold for counting ``P(y > k)``.

    Returns:
        ``Tensor["...", int64]`` predicted ordinal labels in ``[0, K-1]``.
    """
    if logits.shape[-1] < 1:
        raise ValueError("Expected logits with last dim K-1 >= 1.")

    prob_gt = torch.sigmoid(logits)
    return (prob_gt > float(threshold)).sum(dim=-1).to(dtype=torch.int64)


def coral_monotonicity_violation_rate(logits: Tensor) -> Tensor:
    """Compute the fraction of monotonicity violations in CORAL probabilities.

    CORAL expects ``P(y > k)`` to be non-increasing with ``k``. This returns
    the per-sample fraction of threshold pairs that violate this ordering.

    Args:
        logits: ``Tensor["... K-1"]`` threshold logits.

    Returns:
        ``Tensor["..."]`` fraction of violations in ``[0, 1]``.
    """
    if logits.shape[-1] < 2:
        return torch.zeros(logits.shape[:-1], device=logits.device, dtype=torch.float32)

    prob_gt = torch.sigmoid(logits)
    violations = prob_gt[..., 1:] > prob_gt[..., :-1]
    return violations.to(dtype=torch.float32).mean(dim=-1)


class CoralLayer(nn.Module):
    """CORAL output layer with shared weights and per-threshold biases.

    This implements logits:
        logit_k = w^T x + b_k,  k = 0..K-2
    """

    def __init__(self, in_dim: int, num_classes: int, *, preinit_bias: bool = True) -> None:
        super().__init__()
        self.layer = _CoralLayer(size_in=int(in_dim), num_classes=int(num_classes), preinit_bias=bool(preinit_bias))
        self.bin_values: MonotoneBinValues | None = None
        self._num_classes = int(num_classes)

    def forward(self, x: Tensor) -> Tensor:
        """Compute threshold logits.

        Args:
            x: ``Tensor["... in_dim"]``.

        Returns:
            ``Tensor["... K-1"]``.
        """

        return self.layer(x)

    @property
    def num_classes(self) -> int:
        return self._num_classes

    @property
    def has_bin_values(self) -> bool:
        return self.bin_values is not None

    def init_bin_values(self, values: Tensor, *, overwrite: bool = False) -> None:
        """Initialize (or re-initialize) monotone bin representatives ``u_k``."""
        if self.bin_values is None:
            self.bin_values = MonotoneBinValues(self._num_classes, values)
            return
        if overwrite:
            self.bin_values.reset_from_values(values)

    def init_bias_from_priors(self, priors: Tensor, *, overwrite: bool = True) -> None:
        """Initialize CORAL biases from class priors.

        Args:
            priors: ``Tensor["K"]`` class priors that sum to 1.
            overwrite: If True, overwrite the current bias values.
        """
        if priors.numel() != int(self._num_classes):
            raise ValueError(
                f"Expected {self._num_classes} priors, got {tuple(priors.shape)}.",
            )
        if not overwrite:
            return
        priors = priors.to(dtype=torch.float32, device=self.layer.coral_bias.device)
        priors = priors / priors.sum().clamp_min(1e-6)
        p_gt = torch.flip(torch.cumsum(torch.flip(priors, dims=[0]), dim=0), dims=[0])[1:]
        eps = torch.finfo(p_gt.dtype).eps
        p_gt = p_gt.clamp(min=eps, max=1.0 - eps)
        bias = torch.log(p_gt / (1.0 - p_gt))
        with torch.no_grad():
            self.layer.coral_bias.copy_(bias)

    def expected_from_probs(self, probs: Tensor) -> Tensor:
        """Compute expected continuous value using learnable bin values."""
        if self.bin_values is None:
            raise RuntimeError("Bin values not initialized. Call init_bin_values(...).")
        values = self.bin_values.values().to(device=probs.device, dtype=probs.dtype)
        return (probs * values.view(*([1] * (probs.ndim - 1)), -1)).sum(dim=-1)

    def expected_from_logits(self, logits: Tensor) -> Tensor:
        """Convert logits to marginals and compute expected continuous value."""
        probs = coral_logits_to_prob(logits)
        return self.expected_from_probs(probs)

    def bin_value_regularizer(self, target_values: Tensor) -> Tensor:
        """L2 penalty to keep learnable bin values close to target values."""
        if self.bin_values is None:
            return torch.tensor(0.0, device=target_values.device)
        values = self.bin_values.values().to(device=target_values.device, dtype=target_values.dtype)
        return torch.mean((values - target_values) ** 2)
