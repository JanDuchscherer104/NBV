"""Backbone adapters used by VIN scorer architectures.

The package owns wrappers around large external perception models. Current VIN
scorers use the EVL adapter in `aria_nbv.vin.backbones.evl` to expose
actor-visible voxel evidence and feature volumes.
"""

from __future__ import annotations

from .evl import EvlBackbone, EvlBackboneConfig, filter_backbone_output_for_features_mode

__all__ = ["EvlBackbone", "EvlBackboneConfig", "filter_backbone_output_for_features_mode"]
