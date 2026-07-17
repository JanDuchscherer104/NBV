"""Select VIN submodules and compute detached gradient-norm diagnostics.

The helpers aggregate parameter gradients without modifying autograd state and
bound logging cardinality through explicit depth, include, and exclude rules.
"""

from __future__ import annotations

from fnmatch import fnmatch
from typing import Literal

from pydantic import Field
from torch import nn

from .base_config import BaseConfig

GradNormType = Literal["L1", "L2", "Linf"]


def _match_any(name: str, patterns: list[str]) -> bool:
    for pattern in patterns:
        cleaned = pattern.lstrip(".")
        if cleaned.startswith("vin."):
            cleaned = cleaned[4:]
        if fnmatch(name, cleaned):
            return True
    return False


def _module_depth(relative_name: str) -> int:
    if not relative_name:
        return 1
    return 1 + len(relative_name.split("."))


def _grad_norm_from_params(params: list[nn.Parameter], norm_type: GradNormType) -> float:
    if norm_type == "Linf":
        max_val = 0.0
        for param in params:
            if param.grad is None:
                continue
            max_val = max(max_val, float(param.grad.detach().abs().max().item()))
        return max_val

    if norm_type == "L1":
        total = 0.0
        for param in params:
            if param.grad is None:
                continue
            total += float(param.grad.detach().abs().sum().item())
        return total

    total_sq = 0.0
    for param in params:
        if param.grad is None:
            continue
        grad_norm = float(param.grad.detach().norm(2).item())
        total_sq += grad_norm * grad_norm
    return float(total_sq**0.5)


def _collect_grad_norm_targets(
    vin: nn.Module,
    cfg: "GradNormLoggingConfig",
) -> list[tuple[str, list[nn.Parameter]]]:
    targets: dict[str, list[nn.Parameter]] = {}
    for relative_name, module in vin.named_modules():
        name = "vin" if not relative_name else relative_name
        depth = _module_depth(relative_name)
        match_depth = depth == cfg.group_depth
        match_include = bool(cfg.include) and _match_any(name, cfg.include)
        if not (match_depth or match_include):
            continue
        if cfg.exclude and _match_any(name, cfg.exclude):
            continue
        params = [param for param in module.parameters() if param.requires_grad]
        if not params:
            continue
        targets[name] = params

    names = sorted(targets)
    if cfg.max_items is not None:
        names = names[: cfg.max_items]
    return [(name, targets[name]) for name in names]


class GradNormLoggingConfig(BaseConfig):
    """Configuration for gradient norm logging."""

    enabled: bool = True
    """Whether to log gradient norms during training."""

    group_depth: int = Field(default=2, ge=1)
    """Module depth relative to ``vin`` (1 = vin, 2 = vin.<child>)."""

    include: list[str] = Field(default_factory=list)
    """Glob patterns to include explicitly (relative to ``vin``)."""

    exclude: list[str] = Field(default_factory=list)
    """Glob patterns to exclude (relative to ``vin``)."""

    norm_type: GradNormType = "L2"
    """Norm type used for logging."""

    max_items: int | None = Field(default=32, ge=1)
    """Maximum number of modules to log (None disables the cap)."""
