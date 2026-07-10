"""Reusable candidate scoring heads for VIN architectures.

This module owns small, task-level prediction heads that sit after scene,
trajectory, and pose encoders. The heads are intentionally separate from
`aria_nbv.vin.models` so myopic, multi-step, and legacy seminar scorer variants
can share ordinal prediction logic without importing from experimental modules.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field
from torch import Tensor, nn

from ...utils import TargetConfig
from ..ordinal import CoralLayer


class VinScorerHead(nn.Module):
    """Predict ordinal RRI logits from per-candidate feature vectors.

    `VinScorerHead` is the shared MLP-plus-CORAL head used when a VIN scorer
    represents candidate quality as ordinal Relative Reconstruction Improvement
    bins. It consumes the final feature tensor produced by an architecture and
    returns threshold logits compatible with `aria_nbv.vin.ordinal`.
    """

    def __init__(self, config: "VinScorerHeadConfig", *, in_dim: int | None = None) -> None:
        """Build the MLP and CORAL threshold layer.

        Args:
            config: Config-as-factory instance that owns head width, depth,
                dropout, activation, and ordinal class count.
            in_dim: Optional feature dimension. When omitted, the first layer is
                lazy and initializes on the first forward pass.
        """
        super().__init__()
        self.config = config

        act: nn.Module
        match self.config.activation:
            case "relu":
                act = nn.ReLU()
            case "gelu":
                act = nn.GELU()

        hidden_dim = self.config.hidden_dim
        layers: list[nn.Module] = []
        if in_dim is None:
            layers.append(nn.LazyLinear(hidden_dim))
        else:
            layers.append(nn.Linear(in_dim, hidden_dim))
        layers.append(act)
        if self.config.dropout > 0:
            layers.append(nn.Dropout(p=self.config.dropout))

        for _ in range(self.config.num_layers - 1):
            layers.append(nn.Linear(hidden_dim, hidden_dim))
            layers.append(act)
            if self.config.dropout > 0:
                layers.append(nn.Dropout(p=self.config.dropout))

        self.mlp = nn.Sequential(*layers)
        self.coral = CoralLayer(
            in_dim=hidden_dim,
            num_classes=self.config.num_classes,
            preinit_bias=self.config.coral_preinit_bias,
        )

    def forward(self, x: Tensor) -> Tensor:
        """Return CORAL threshold logits for candidate features.

        Args:
            x: ``Tensor["... F"]`` feature vectors, where leading dimensions are
                preserved as candidate or batch axes.

        Returns:
            ``Tensor["... K-1"]`` CORAL logits for ``K`` ordinal RRI classes.
        """
        return self.coral(self.mlp(x))


class VinScorerHeadConfig(TargetConfig[VinScorerHead]):
    """Configure the shared VIN ordinal scoring head."""

    @property
    def target_type(self) -> type[VinScorerHead]:
        """Factory target for `BaseConfig.setup_target`."""
        return VinScorerHead

    hidden_dim: int = Field(default=128, gt=0)
    """Hidden dimension for MLP layers."""

    num_layers: int = Field(default=1, ge=1)
    """Number of MLP layers before the CORAL layer."""

    dropout: float = Field(default=0.0, ge=0.0, lt=1.0)
    """Dropout probability in the MLP."""

    num_classes: int = Field(default=15, ge=2)
    """Number of ordinal bins (VIN-NBV uses 15)."""

    coral_preinit_bias: bool = True
    """Whether to initialize CORAL threshold biases with ordinal defaults."""

    activation: Literal["gelu", "relu"] = "gelu"
    """Activation function."""

    def setup_target(self, *, in_dim: int | None = None) -> VinScorerHead:
        """Instantiate the configured scoring head.

        Args:
            in_dim: Optional input feature width passed to `VinScorerHead`.

        Returns:
            Runtime scoring module.
        """
        return self.target(self, in_dim=in_dim)


__all__ = ["VinScorerHead", "VinScorerHeadConfig"]
