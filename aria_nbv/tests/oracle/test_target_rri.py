"""Focused target-RRI cache lifetime tests."""

from __future__ import annotations

from collections import OrderedDict
from typing import Any, cast

import torch

from aria_nbv.oracle.target_rri import TargetRriScorer


def test_target_geometry_cache_evicts_invalidated_entries() -> None:
    scorer = object.__new__(TargetRriScorer)
    scorer._prepared_target_geometry = OrderedDict()

    for version in range(3):
        tensor = torch.tensor([version], dtype=torch.float32)
        geometry = cast(Any, (object(), tensor, tensor, tensor, tensor, tensor))
        scorer._cache_target_geometry(("source-version", version), geometry)

    assert list(scorer._prepared_target_geometry) == [
        ("source-version", 1),
        ("source-version", 2),
    ]
