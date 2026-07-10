"""Unit tests for VIN ordinal RRI binning utilities."""

from __future__ import annotations

from pathlib import Path

import pytest
import torch

from aria_nbv.rri_metrics.ordinal import RriOrdinalBinner


def test_binner_save_does_not_overwrite(tmp_path: Path) -> None:
    rri = torch.linspace(0.0, 1.0, steps=128)

    binner1 = RriOrdinalBinner.fit_from_iterable([rri], num_classes=5)
    binner2 = RriOrdinalBinner.fit_from_iterable([rri * 2.0], num_classes=5)

    base = tmp_path / "rri_binner.json"
    path1 = binner1.save(base)
    path2 = binner2.save(base)

    assert path1 == base
    assert path2 != base
    assert path2.name.startswith("rri_binner-")

    loaded1 = RriOrdinalBinner.load(path1)
    loaded2 = RriOrdinalBinner.load(path2)

    assert loaded1.num_classes == binner1.num_classes
    assert torch.allclose(loaded1.edges, binner1.edges.to(dtype=torch.float32))

    assert loaded2.num_classes == binner2.num_classes
    assert torch.allclose(loaded2.edges, binner2.edges.to(dtype=torch.float32))


def test_fit_data_can_refit_edges_for_different_k(tmp_path: Path) -> None:
    rri0 = torch.linspace(0.0, 1.0, steps=64)
    rri1 = torch.linspace(0.5, 2.0, steps=64)
    fit_path = tmp_path / "fit_data.pt"

    binner5 = RriOrdinalBinner.fit_from_iterable(
        [rri0, rri1],
        num_classes=5,
        fit_data_path=fit_path,
        resume=False,
    )
    binner7 = RriOrdinalBinner.fit_from_iterable(
        [],
        num_classes=7,
        fit_data_path=fit_path,
        resume=True,
    )

    assert binner5.edges.numel() == 4
    assert binner7.edges.numel() == 6
    assert torch.all(binner7.edges[1:] >= binner7.edges[:-1])

    assert fit_path.exists()


def test_fit_binner_from_iterable_saves_fit_data_on_keyboard_interrupt(tmp_path: Path) -> None:
    save_path = tmp_path / "fit_data.pt"

    def _iter():
        yield torch.tensor([0.1, 0.2, 0.3])
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        RriOrdinalBinner.fit_from_iterable(
            _iter(),
            num_classes=3,
            fit_data_path=save_path,
        )

    assert save_path.exists()
    state = torch.load(save_path, map_location="cpu", weights_only=True)
    rri_loaded = torch.cat(state["rri_chunks"], dim=0)
    assert torch.allclose(rri_loaded, torch.tensor([0.1, 0.2, 0.3], dtype=torch.float32))


def test_rri_ordinal_binner_fit_and_transform() -> None:
    num_classes = 5
    rri = torch.tensor(
        [0.05, 0.10, 0.20, 0.30, 0.01, 0.02, 0.03, 0.04],
        dtype=torch.float32,
    )

    binner = RriOrdinalBinner.fit_from_iterable([rri], num_classes=num_classes)
    assert binner.edges.shape == (num_classes - 1,)
    assert torch.all(binner.edges[1:] > binner.edges[:-1])

    labels = binner.transform(rri)
    assert labels.shape == (8,)
    assert labels.dtype == torch.int64
    assert int(labels.min()) >= 0
    assert int(labels.max()) <= num_classes - 1


def test_rri_ordinal_binner_degenerate_fallback() -> None:
    num_classes = 5
    rri = torch.zeros(32, dtype=torch.float32)
    binner = RriOrdinalBinner.fit_from_iterable([rri], num_classes=num_classes)
    assert binner.edges.shape == (num_classes - 1,)
    assert torch.all(binner.edges[1:] > binner.edges[:-1])
