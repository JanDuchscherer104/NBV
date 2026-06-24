"""Normalization helper functions shared by VIN modules and training setup."""

from __future__ import annotations


def largest_divisor_leq(n: int, max_divisor: int) -> int:
    """Return the largest divisor of ``n`` that is less than or equal to a cap.

    `torch.nn.GroupNorm` requires ``num_groups`` to divide ``num_channels``
    exactly. VIN configs often expose an upper-bound group count for tuning, so
    this helper maps that requested cap to the nearest valid divisor.

    Args:
        n: Channel dimension that must be divided by the result.
        max_divisor: Maximum permitted group count.

    Returns:
        Largest valid group count, always at least ``1``.
    """
    g = min(max_divisor, n)
    while g > 1 and (n % g) != 0:
        g -= 1
    return max(1, g)


__all__ = ["largest_divisor_leq"]
