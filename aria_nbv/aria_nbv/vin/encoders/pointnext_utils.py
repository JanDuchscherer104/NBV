"""Utility helpers for the optional PointNeXt VIN encoder.

`aria_nbv.vin.encoders.pointnext.PointNeXtSEncoder` wraps an OpenPoints
PointNeXt-S model for semidense point-cloud context. This sidecar owns the
unstructured OpenPoints/checkpoint glue so the `torch.nn.Module` implementation
can stay focused on module lifecycle and tensor contracts.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import torch
from torch import Tensor, nn


def extract_point_encoder_tensor(output: Any) -> Tensor:
    """Return the first tensor-like feature payload from an OpenPoints output.

    Args:
        output: Tensor, mapping, tuple, or list returned by an external point
            encoder. OpenPoints variants commonly use keys such as ``feat`` or
            ``features`` but checkpoint/model wrappers are not fully uniform.

    Returns:
        The first `torch.Tensor` feature payload found.

    Raises:
        TypeError: If no tensor payload can be located.
    """
    if isinstance(output, torch.Tensor):
        return output
    if isinstance(output, dict):
        for key in ("feat", "features", "logits", "pred", "out"):
            value = output.get(key)
            if isinstance(value, torch.Tensor):
                return value
        for value in output.values():
            if isinstance(value, torch.Tensor):
                return value
    if isinstance(output, (tuple, list)):
        for value in output:
            if isinstance(value, torch.Tensor):
                return value
    raise TypeError("Point encoder output did not contain a tensor.")


def load_pointnext_cfg(cfg_path: Path) -> Any:
    """Load a PointNeXt/OpenPoints YAML config with `openpoints.utils.EasyConfig`.

    Args:
        cfg_path: Absolute path to the OpenPoints YAML configuration file.

    Returns:
        Parsed OpenPoints config object.
    """
    from openpoints.utils import EasyConfig

    cfg = EasyConfig()
    cfg.load(str(cfg_path), recursive=True)
    return cfg


def load_checkpoint_strict(model: nn.Module, checkpoint_path: Path) -> None:
    """Load an OpenPoints-style checkpoint with strict PyTorch key matching.

    Args:
        model: PointNeXt module built by OpenPoints.
        checkpoint_path: Path to a checkpoint containing a state dict directly
            or under common wrapper keys such as ``model`` or ``state_dict``.

    Raises:
        RuntimeError: If the checkpoint does not contain a dictionary state
            payload after unwrapping common OpenPoints keys.
    """
    state = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    if isinstance(state, dict):
        for key in ("model", "net", "network", "state_dict", "base_model"):
            if key in state:
                state = state[key]
                break
    if not isinstance(state, dict):
        raise RuntimeError("PointNeXt checkpoint did not contain a state dict.")
    state = {k.replace("module.", ""): v for k, v in state.items()}
    model.load_state_dict(state, strict=True)


__all__ = ["extract_point_encoder_tensor", "load_checkpoint_strict", "load_pointnext_cfg"]
