"""Presentation contracts for immutable root-store diagnostics."""

# ruff: noqa: S101, SLF001

from collections import Counter
from types import SimpleNamespace

import pytest

from aria_nbv.app.panels import offline_dataset as panel


def test_root_store_diagnostics_use_four_progressive_workspaces(monkeypatch: pytest.MonkeyPatch) -> None:
    """Detailed diagnostics remain reachable without eleven peer-level tabs."""

    sections: list[str] = []
    calls: list[str] = []

    class Context:
        def __enter__(self) -> None:
            return None

        def __exit__(self, *_args: object) -> None:
            return None

    class Column:
        def metric(self, *_args: object, **_kwargs: object) -> None:
            return None

        def json(self, *_args: object, **_kwargs: object) -> None:
            return None

    def tabs(labels: list[str]) -> list[Context]:
        sections.extend(labels)
        return [Context() for _ in labels]

    monkeypatch.setattr(panel.st, "tabs", tabs)
    monkeypatch.setattr(panel.st, "columns", lambda count: [Column() for _ in range(count)])
    monkeypatch.setattr(panel.st, "expander", lambda *_args, **_kwargs: Context())
    monkeypatch.setattr(panel.st, "dataframe", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(panel.st, "json", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(panel, "_offline_summary_rows", lambda _stats: [])
    monkeypatch.setattr(panel, "_block_rows", lambda _stats: [])
    monkeypatch.setattr(panel, "_sample_rows", lambda _stats: [])
    monkeypatch.setattr(panel, "_render_histogram", lambda *_args, **_kwargs: calls.append("histogram"))
    for name in (
        "_render_coverage",
        "_render_rri_components",
        "_render_candidate_geometry",
        "_render_backbone",
        "_render_batch_memory",
        "_render_binner",
    ):
        monkeypatch.setattr(panel, name, lambda *_args, _name=name, **_kwargs: calls.append(_name))

    panel._render_stats(
        SimpleNamespace(
            num_samples=10,
            sampled_samples=4,
            num_scenes=2,
            numeric_bytes=1024,
            split_counts={"train": 8, "val": 2},
            materialized_blocks={"depths": True},
            candidate_count_values=[],
            rri_values=[],
            vin_point_values=[],
            store_dir="/fixture",
            version=8,
            block_shapes={},
            batch_shapes={},
        ),
        hist_bins=20,
        candidate_bins=30,
        binner_classes=5,
        log_y=False,
        coverage=None,
    )

    assert sections == ["Overview", "Content", "Runtime", "Details"]
    assert Counter(calls) == Counter(
        {
            "histogram": 3,
            "_render_coverage": 1,
            "_render_rri_components": 1,
            "_render_candidate_geometry": 1,
            "_render_backbone": 1,
            "_render_batch_memory": 1,
            "_render_binner": 1,
        }
    )
