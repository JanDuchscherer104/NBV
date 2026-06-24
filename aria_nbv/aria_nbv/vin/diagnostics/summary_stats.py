"""Small tensor statistics used by VIN diagnostic summaries.

The helpers in this module support human-readable VIN reports such as
`aria_nbv.vin.diagnostics.summarize.summarize_vin_v3`. They intentionally avoid
stateful `torchmetrics` objects and rollout-specific mask semantics from
`aria_nbv.rri_metrics` because summaries are one-shot diagnostics over whatever
finite tensor values are available.
"""

from __future__ import annotations

import torch
from torch import Tensor


def finite_1d(values: Tensor) -> Tensor:
    """Return finite values from ``values`` as a detached float32 vector.

    Parameters
    ----------
    values:
        Tensor with arbitrary shape and numeric dtype.

    Returns
    -------
    Tensor
        One-dimensional ``float32`` tensor containing only finite values. The
        returned tensor is detached from autograd so diagnostics cannot keep a
        training graph alive.
    """
    flat = values.detach().reshape(-1).to(dtype=torch.float32)
    return flat[torch.isfinite(flat)]


def pearson_corr(x: Tensor, y: Tensor) -> float | None:
    """Compute a finite-value Pearson correlation for diagnostic reporting.

    ``x`` and ``y`` are independently filtered to finite one-dimensional values,
    then truncated to the shorter length. This mirrors the historical VIN
    summary behavior and is meant for lightweight reports, not aligned
    mask-aware training metrics.

    Returns ``None`` when fewer than two paired values remain or either vector
    has near-zero variance.
    """
    x_f = finite_1d(x)
    y_f = finite_1d(y)
    num = min(int(x_f.numel()), int(y_f.numel()))
    if num < 2:
        return None
    x_f = x_f[:num]
    y_f = y_f[:num]
    x_f = x_f - x_f.mean()
    y_f = y_f - y_f.mean()
    denom = x_f.std(unbiased=False) * y_f.std(unbiased=False)
    if float(denom.item()) < 1e-12:
        return None
    return float((x_f * y_f).mean().item() / denom.item())


def ordinal_ranks(values: Tensor) -> Tensor:
    """Assign zero-based ordinal ranks with the current diagnostic tie policy.

    Ties are not averaged: equal values inherit the deterministic order returned
    by `torch.argsort`. This preserves the original VIN summary behavior and
    keeps the helper unsuitable as a statistical replacement for SciPy's
    ``rankdata``.
    """
    order = torch.argsort(values)
    ranks = torch.empty_like(order, dtype=torch.float32)
    ranks[order] = torch.arange(order.numel(), device=order.device, dtype=torch.float32)
    return ranks


def spearman_corr(x: Tensor, y: Tensor) -> float | None:
    """Compute the VIN diagnostic Spearman-style rank correlation.

    The function applies `ordinal_ranks` to independently finite-filtered and
    length-truncated vectors, then delegates to `pearson_corr`.
    """
    x_f = finite_1d(x)
    y_f = finite_1d(y)
    num = min(int(x_f.numel()), int(y_f.numel()))
    if num < 2:
        return None
    x_f = x_f[:num]
    y_f = y_f[:num]
    return pearson_corr(ordinal_ranks(x_f), ordinal_ranks(y_f))


def quantile_stats(values: Tensor) -> dict[str, float] | None:
    """Summarize finite values with the VIN report's compact quantile schema.

    Parameters
    ----------
    values:
        Tensor with arbitrary shape.

    Returns
    -------
    dict[str, float] | None
        ``{"min", "median", "p95", "mean"}`` for finite values, or ``None``
        when the input contains no finite values.
    """
    values_f = finite_1d(values)
    if values_f.numel() == 0:
        return None
    quantiles = torch.quantile(
        values_f,
        torch.tensor([0.0, 0.5, 0.95], device=values_f.device, dtype=values_f.dtype),
    )
    return {
        "min": float(quantiles[0].item()),
        "median": float(quantiles[1].item()),
        "p95": float(quantiles[2].item()),
        "mean": float(values_f.mean().item()),
    }


__all__ = [
    "finite_1d",
    "ordinal_ranks",
    "pearson_corr",
    "quantile_stats",
    "spearman_corr",
]
