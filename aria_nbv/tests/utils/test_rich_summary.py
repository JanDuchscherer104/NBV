"""Regression tests for compact tensor and collection summaries."""

from __future__ import annotations

import torch

from aria_nbv.utils import summarize, summarize_shape
from aria_nbv.utils.summary import summarize as legacy_summarize


def test_summarize_preserves_public_tensor_contract() -> None:
    tensor = torch.tensor([1.0, float("nan"), 3.0])

    assert summarize(tensor) == {
        "shape": (3,),
        "dtype": "torch.float32",
        "device": "cpu",
    }
    assert summarize(tensor, include_stats=True) == {
        "shape": (3,),
        "dtype": "torch.float32",
        "device": "cpu",
        "min": 1.0,
        "max": 3.0,
        "mean": 2.0,
    }


def test_summarize_preserves_collection_and_shape_contracts() -> None:
    assert summarize(None) is None
    assert summarize([1, 2, 3]) == {"len": 3}
    assert summarize_shape(torch.zeros(2, 3)) == "(2, 3) float32 cpu"
    assert summarize_shape([1, 2]) == "list(len=2)"


def test_legacy_summary_module_reexports_canonical_implementation() -> None:
    assert legacy_summarize is summarize
