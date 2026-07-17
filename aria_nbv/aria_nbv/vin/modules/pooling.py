"""Pose-conditioned pooling modules for VIN scene fields.

This module owns candidate-query attention over shared voxel-grid tokens.
"""

from __future__ import annotations

from torch import Tensor, nn
from torch.nn import functional as functional

from ..encoders import LearnableFourierFeaturesConfig


class PoseConditionedGlobalPool(nn.Module):
    """Attend over a coarse voxel field with candidate pose queries.

    The module summarizes a projected voxel field into one descriptor per
    candidate pose. It down-samples the field into tokens, encodes each token's
    normalized position grid, and uses candidate pose embeddings as attention
    queries over voxel content.

    Positional embeddings are added only to keys. Values stay pure field-content
    projections, so attention weights depend on position while the returned
    descriptors remain content summaries conditioned by pose.

    Each candidate query attends to the same voxel-token set independently;
    queries never attend to one another. Permuting the ``N_q`` pose rows thus
    permutes the ``N_q`` outputs. The normalized position encoder makes the
    block reference-frame-aware, but does not enforce SE(3) equivariance or a
    graph-isomorphism invariant.
    """

    def __init__(
        self,
        *,
        field_dim: int,
        pose_dim: int,
        pool_size: int,
        num_heads: int,
        pos_grid_encoder: LearnableFourierFeaturesConfig,
    ) -> None:
        """Initialize the pooling block.

        Args:
            field_dim: Channel dimension of the projected voxel field.
            pose_dim: Dimension of candidate pose embeddings.
            pool_size: Maximum side length of the adaptive 3D pooling grid.
            num_heads: Number of attention heads. Must divide ``field_dim``.
            pos_grid_encoder: Config-as-factory for the XYZ position encoder.
        """
        super().__init__()
        if pool_size <= 0:
            raise ValueError("pool_size must be > 0.")
        if field_dim % num_heads != 0:
            raise ValueError(
                f"field_dim ({field_dim}) must be divisible by num_heads ({num_heads}).",
            )

        self.pool_size = int(pool_size)
        self.kv_proj = nn.Linear(field_dim, field_dim)
        self.q_proj = nn.Linear(pose_dim, field_dim)
        self.pos_grid_encoder = pos_grid_encoder.setup_target()
        self.pos_proj = nn.Linear(self.pos_grid_encoder.out_dim, field_dim)
        self.attn = nn.MultiheadAttention(
            embed_dim=field_dim,
            num_heads=num_heads,
            batch_first=True,
        )
        self.norm_q = nn.LayerNorm(field_dim)
        self.norm_kv = nn.LayerNorm(field_dim)
        self.mlp = nn.Sequential(
            nn.Linear(field_dim, field_dim * 2),
            nn.GELU(),
            nn.Linear(field_dim * 2, field_dim),
        )
        self.mlp_norm = nn.LayerNorm(field_dim)

    def forward(self, field: Tensor, pose_enc: Tensor, *, pos_grid: Tensor) -> Tensor:
        """Return pose-conditioned global field descriptors.

        Args:
            field: ``Tensor["B C D H W"]`` projected voxel field.
            pose_enc: ``Tensor["B N_q E", float32]`` candidate pose embeddings.
            pos_grid: ``Tensor["B 3 D H W"]`` normalized voxel positions.

        Returns:
            ``Tensor["B N_q C", float32]`` global features for each candidate.
        """
        if field.ndim != 5:
            raise ValueError(
                f"Expected field shape (B,C,D,H,W), got {tuple(field.shape)}.",
            )
        if pose_enc.ndim != 3:
            raise ValueError(
                f"Expected pose_enc shape (B,N,E), got {tuple(pose_enc.shape)}.",
            )
        if pos_grid.ndim != 5 or pos_grid.shape[1] != 3:
            raise ValueError(
                f"Expected pos_grid shape (B,3,D,H,W), got {tuple(pos_grid.shape)}.",
            )

        grid = min(
            self.pool_size,
            int(field.shape[-3]),
            int(field.shape[-2]),
            int(field.shape[-1]),
        )
        field_ds = functional.adaptive_avg_pool3d(field, output_size=(grid, grid, grid))
        tokens = field_ds.flatten(2).transpose(1, 2)
        kv_tokens = self.kv_proj(tokens)

        pos_ds = functional.adaptive_avg_pool3d(
            pos_grid,
            output_size=(grid, grid, grid),
        )
        pos_tokens = pos_ds.flatten(2).transpose(1, 2)
        pos_enc = self.pos_grid_encoder(pos_tokens.to(dtype=kv_tokens.dtype))
        pos_emb = self.pos_proj(pos_enc)
        keys = kv_tokens + pos_emb
        values = kv_tokens
        queries = self.q_proj(pose_enc.to(dtype=kv_tokens.dtype))

        queries_norm = self.norm_q(queries)
        keys_norm = self.norm_kv(keys)
        values_norm = self.norm_kv(values)
        attn_out, _ = self.attn(
            queries_norm,
            keys_norm,
            values_norm,
            need_weights=False,
        )
        out = queries + attn_out
        out = out + self.mlp(self.mlp_norm(out))
        return out


__all__ = ["PoseConditionedGlobalPool"]
