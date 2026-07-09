"""Stateless one-step RRI prediction metrics."""

from __future__ import annotations

import torch
from torch import Tensor


def topk_accuracy_from_probs(probs: Tensor, labels: Tensor, *, top_k: int) -> Tensor:
    """Compute top-k accuracy from class probabilities."""
    if top_k < 1:
        raise ValueError("top_k must be >= 1.")
    if probs.numel() == 0 or labels.numel() == 0:
        return torch.tensor(float("nan"), device=probs.device)
    if probs.ndim != 2:
        raise ValueError(f"Expected probs with shape (N, K), got {tuple(probs.shape)}.")
    labels = labels.reshape(-1)
    if probs.shape[0] != labels.shape[0]:
        raise ValueError(
            f"Expected probs and labels to have matching first dimension, got {probs.shape[0]} and {labels.shape[0]}.",
        )
    k = min(int(top_k), probs.shape[-1])
    topk = probs.topk(k=k, dim=-1).indices
    correct = (topk == labels.unsqueeze(-1)).any(dim=-1)
    return correct.to(dtype=torch.float32).mean()


__all__ = ["topk_accuracy_from_probs"]
