"""Spherical-harmonics pose encoding for VIN.

VIN candidate generation samples camera centers on a (possibly biased) spherical shell around a
reference pose. A natural descriptor for such candidates is therefore expressed in terms of
directions on $\\mathbb{S}^2$ and a scalar radius.

This module provides a lightweight pose encoder based on real spherical harmonics computed via
`e3nn`, plus a 1D Fourier-feature encoding for the radius and a small MLP for additional scalar
pose terms.
"""

from __future__ import annotations

from typing import Literal

import torch
from e3nn import o3  # type: ignore[import-untyped]
from pydantic import Field
from torch import Tensor, nn

from ...utils import TargetConfig
from .fixed_fourier import FourierFeaturesConfig


class ShellShPoseEncoder(nn.Module):
    """Encode shell-based pose descriptors using spherical harmonics.

    Inputs are unit vectors on $\\mathbb{S}^2$:

    - $u$: candidate position direction in the reference frame,
    - $f$: candidate forward direction in the reference frame,

    plus a radius $r=\\lVert t\\rVert$ and optional scalar pose terms (e.g. $\\langle f, -u \\rangle$).
    This representation uses only the forward direction and therefore does **not**
    encode roll about the forward axis. This is acceptable when roll jitter is small;
    use a full SO(3) encoding (e.g. R6D + LFF) when roll sensitivity is required.

    The encoder computes real spherical harmonics up to degree ``lmax`` for $u$ and $f$ and projects
    them into a learnable embedding space. The radius is encoded via **1D Fourier features** (on
    $r$ by default) and projected to a learnable embedding.

    Spherical harmonics supply a directional basis, but the independent dense
    projections, GELU layers, and concatenation do not preserve irreducible
    representations. The emitted embedding is therefore a reference-frame
    directional inductive bias, not an SO(3)-equivariant representation.

    Args:
        lmax: Maximum spherical harmonics degree.
        sh_out_dim: Output dimensionality after projecting each SH vector.
        radius_num_frequencies: Number of Fourier frequencies for the radius encoding.
        radius_out_dim: Output dimensionality after projecting the radius Fourier features.
        radius_include_input: Concatenate the raw radius input to Fourier features when True.
        radius_learnable: Make the radius Fourier frequency matrix learnable when True.
        radius_init_scale: Stddev used to initialize the radius Fourier frequency matrix.
        radius_log_input: Encode $\\log(r+\\varepsilon)$ when True, else encode $r$ directly.
        include_radius: If ``True``, include the radius embedding in the output.
        scalar_in_dim: Number of additional scalar pose features.
        scalar_out_dim: Output dimensionality of the scalar MLP.
        scalar_hidden_dim: Hidden size for the scalar MLP.
        normalization: e3nn SH normalization mode.
        include_scalars: If ``True``, include the scalar MLP output in the embedding.
    """

    def __init__(self, config: "ShellShPoseEncoderConfig") -> None:
        super().__init__()
        self.config = config

        self.lmax = self.config.lmax
        self.normalization = self.config.normalization
        self.include_scalars = self.config.include_scalars
        self.include_radius = self.config.include_radius
        self.radius_log_input = self.config.radius_log_input

        irreps_sh = o3.Irreps.spherical_harmonics(self.lmax)
        sh_in_dim = irreps_sh.dim

        def _proj(in_dim: int, out_dim: int) -> nn.Sequential:
            return nn.Sequential(
                nn.Linear(in_dim, out_dim),
                nn.GELU(),
                nn.Linear(out_dim, out_dim),
            )

        self._irreps_sh = irreps_sh
        self._proj_u = _proj(sh_in_dim, self.config.sh_out_dim)
        self._proj_f = _proj(sh_in_dim, self.config.sh_out_dim)

        radius_ff_cfg = FourierFeaturesConfig(
            input_dim=1,
            num_frequencies=self.config.radius_num_frequencies,
            include_input=self.config.radius_include_input,
            learnable=self.config.radius_learnable,
            init_scale=self.config.radius_init_scale,
        )
        self._radius_ff = radius_ff_cfg.setup_target()
        self._proj_r = _proj(self._radius_ff.output_dim, self.config.radius_out_dim)

        self._scalar_mlp = nn.Sequential(
            nn.Linear(self.config.scalar_in_dim, self.config.scalar_hidden_dim),
            nn.GELU(),
            nn.Linear(self.config.scalar_hidden_dim, self.config.scalar_out_dim),
        )

        self._sh_out_dim = self.config.sh_out_dim
        self._radius_out_dim = self.config.radius_out_dim
        self._scalar_out_dim = self.config.scalar_out_dim

    @property
    def out_dim(self) -> int:
        """Return the concatenated direction, radius, and scalar width."""

        base = 2 * self._sh_out_dim
        if self.include_radius:
            base += self._radius_out_dim
        if self.include_scalars:
            base += self._scalar_out_dim
        return base

    def forward(self, u: Tensor, f: Tensor, *, r: Tensor, scalars: Tensor | None = None) -> Tensor:
        """Encode directions and scalar pose features.

        Args:
            u: ``Tensor["... 3", float32]`` unit direction from reference to candidate center.
            f: ``Tensor["... 3", float32]`` unit forward direction of the candidate camera.
            r: ``Tensor["... 1", float32]`` radius $\\lVert t\\rVert$ of the candidate center in the reference frame.
            scalars: Optional ``Tensor["... scalar_in_dim", float32]`` scalar pose features.

        Returns:
            ``Tensor["... out_dim", float32]`` pose embedding.

        This lower-level module receives the shell descriptor tensors directly.
        Use `aria_nbv.vin.encoders.shell_pose.ShellShPoseEncoderAdapter` when
        the input is an `efm3d.aria.pose.PoseTW` pose.
        """

        if u.shape[-1] != 3 or f.shape[-1] != 3:
            raise ValueError(f"Expected u,f with last dim 3, got {u.shape} and {f.shape}.")
        if r.shape[-1] != 1:
            raise ValueError(f"Expected r[..., 1], got {tuple(r.shape)}.")
        if self.include_scalars and scalars is None:
            raise ValueError("scalars must be provided when include_scalars=True.")

        u_f32 = u.to(dtype=torch.float32)
        f_f32 = f.to(dtype=torch.float32)

        y_u = o3.spherical_harmonics(
            self._irreps_sh,
            u_f32,
            normalize=True,
            normalization=self.normalization,
        )
        y_f = o3.spherical_harmonics(
            self._irreps_sh,
            f_f32,
            normalize=True,
            normalization=self.normalization,
        )

        parts: list[Tensor] = [self._proj_u(y_u), self._proj_f(y_f)]
        if self.include_radius:
            r_f32 = r.to(dtype=torch.float32)
            if self.radius_log_input:
                r_f32 = torch.log(r_f32 + 1e-8)
            r_ff = self._radius_ff(r_f32)
            parts.append(self._proj_r(r_ff))
        if self.include_scalars:
            scalars_f32 = scalars.to(dtype=torch.float32)  # type: ignore[union-attr]
            parts.append(self._scalar_mlp(scalars_f32))
        return torch.cat(parts, dim=-1)


class ShellShPoseEncoderConfig(TargetConfig[ShellShPoseEncoder]):
    """Config-as-factory wrapper for `ShellShPoseEncoder`."""

    @property
    def target_type(self) -> type[ShellShPoseEncoder]:
        """Return the runtime shell encoder type constructed by this config."""

        return ShellShPoseEncoder

    kind: Literal["shell_sh"] = "shell_sh"
    """Discriminator for pose-encoder selection."""

    lmax: int = Field(default=2, ge=0)
    """Maximum spherical harmonics degree."""

    sh_out_dim: int = Field(default=16, gt=0)
    """Projection dimension for each SH vector (for $u$ and $f$)."""

    radius_num_frequencies: int = Field(default=6, gt=0)
    """Number of Fourier frequencies for the 1D radius encoding."""

    radius_out_dim: int = Field(default=16, gt=0)
    """Projection dimension for the encoded radius."""

    radius_include_input: bool = True
    """Concatenate the raw radius input to Fourier features when True."""

    radius_learnable: bool = True
    """Make the radius Fourier frequency matrix learnable when True."""

    radius_init_scale: float = Field(default=1.0, gt=0.0)
    """Stddev used to initialize the radius Fourier frequency matrix."""

    radius_log_input: bool = False
    """Encode $r$ directly by default; set to ``True`` to encode $\\log(r+\\varepsilon)`` instead."""

    include_radius: bool = True
    """Include radius features in the embedding when True."""

    scalar_in_dim: int = Field(default=1, gt=0)
    """Number of additional scalar pose features (e.g. $\\langle f, -u \\rangle$)."""

    scalar_out_dim: int = Field(default=16, gt=0)
    """Output dimension of the scalar MLP."""

    scalar_hidden_dim: int = Field(default=32, gt=0)
    """Hidden dimension of the scalar MLP."""

    normalization: Literal["component", "norm"] = "component"
    """e3nn spherical harmonics normalization mode."""

    include_scalars: bool = True
    """Include scalar features in the embedding when True."""


__all__ = [
    "ShellShPoseEncoder",
    "ShellShPoseEncoderConfig",
]
