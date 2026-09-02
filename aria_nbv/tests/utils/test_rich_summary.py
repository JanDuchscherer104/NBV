"""Regression tests for compact tensor and collection summaries."""

from __future__ import annotations

import torch

from aria_nbv.utils import rich_summary, summarize, summarize_shape
from aria_nbv.utils.rich_summary import capture_tree, summary_markdown, summary_rows


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


def test_capture_tree_is_ansi_free_for_web_and_log_renderers() -> None:
    tree = rich_summary({"sample": {"shape": (2, 3), "valid": True}}, is_print=False)

    rendered = capture_tree(tree)

    assert "sample" in rendered
    assert "\x1b[" not in rendered


def test_summary_rows_are_shared_between_text_and_streamlit_adapters() -> None:
    summary = {
        "tensor": {"shape": (2, 3), "dtype": "torch.float32", "device": "cpu"},
        "nested": {"count": 3},
        "items": ["a", "b"],
    }
    rows = summary_rows(summary)
    assert [(row.path, row.kind) for row in rows] == [
        (("tensor",), "tensor"),
        (("nested", "count"), "scalar"),
        (("items",), "sequence"),
    ]
    markdown = summary_markdown(summary)
    assert "`tensor` (tensor)" in markdown
    assert "`nested/count` (scalar): 3" in markdown
