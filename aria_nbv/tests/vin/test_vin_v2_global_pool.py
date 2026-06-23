"""Unit tests for VIN pose-conditioned global pooling."""

# ruff: noqa: S101

import torch
from torch import nn

from aria_nbv.vin.encoders import LearnableFourierFeaturesConfig
from aria_nbv.vin.modules import PoseConditionedGlobalPool


def test_global_pool_positional_embedding_does_not_leak_into_values() -> None:
    """Positional embeddings should affect keys but not values."""
    pos_cfg = LearnableFourierFeaturesConfig(
        input_dim=3,
        fourier_dim=4,
        hidden_dim=4,
        output_dim=4,
    )
    pool = PoseConditionedGlobalPool(
        field_dim=4,
        pose_dim=4,
        pool_size=2,
        num_heads=2,
        pos_grid_encoder=pos_cfg,
    )

    pool.norm_q = nn.Identity()
    pool.norm_kv = nn.Identity()
    pool.mlp_norm = nn.Identity()
    pool.mlp = nn.Linear(4, 4, bias=False)
    nn.init.zeros_(pool.mlp.weight)

    nn.init.zeros_(pool.q_proj.weight)
    nn.init.zeros_(pool.q_proj.bias)
    nn.init.zeros_(pool.kv_proj.weight)
    nn.init.zeros_(pool.kv_proj.bias)
    nn.init.zeros_(pool.pos_proj.weight)
    nn.init.constant_(pool.pos_proj.bias, 1.0)

    field = torch.zeros((1, 4, 2, 2, 2), dtype=torch.float32)
    pose_enc = torch.zeros((1, 1, 4), dtype=torch.float32)
    pos_grid = torch.zeros((1, 3, 2, 2, 2), dtype=torch.float32)

    out = pool(field, pose_enc, pos_grid=pos_grid)
    assert torch.allclose(out, torch.zeros_like(out))
