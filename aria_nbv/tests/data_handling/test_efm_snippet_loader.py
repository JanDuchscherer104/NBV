"""Tests for the main data-handling EFM snippet loader."""

from __future__ import annotations

from typing import TYPE_CHECKING

from aria_nbv.configs import PathConfig
from aria_nbv.data_handling.raw.loader import EfmSnippetLoader

if TYPE_CHECKING:
    from collections.abc import Iterator

    import pytest


def test_loader_rebuilds_dataset_on_miss(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rebuild dataset if the stream has already passed the target snippet."""
    instances: list[object] = []

    class DummyDataset:
        def __init__(self, *, yield_sample: bool) -> None:
            self._yield_sample = yield_sample
            self._snippet_key_filter: set[str] = set()

        def __iter__(self) -> Iterator[dict[str, bool]]:
            if self._yield_sample:
                return iter([{"ok": True}])
            return iter([])

    def _build_dataset(self: EfmSnippetLoader, scene_id: str) -> DummyDataset:  # type: ignore[override]
        yield_sample = len(instances) > 0
        dataset = DummyDataset(yield_sample=yield_sample)
        instances.append(dataset)
        self._datasets[scene_id] = dataset  # type: ignore[attr-defined]
        return dataset

    monkeypatch.setattr(
        EfmSnippetLoader,
        "_build_dataset",
        _build_dataset,
        raising=True,
    )

    loader = EfmSnippetLoader(
        dataset_payload={},
        device="cpu",
        paths=PathConfig(),
        include_gt_mesh=False,
    )

    sample = loader.load(scene_id="scene_0", snippet_id="000001")
    expected_instances = 2
    assert sample == {"ok": True}  # noqa: S101
    assert len(instances) == expected_instances  # noqa: S101
