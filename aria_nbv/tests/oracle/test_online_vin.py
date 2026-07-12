"""Behavior locks for online Oracle-labelled VIN generation."""

from __future__ import annotations

from collections.abc import Iterator
from types import SimpleNamespace

import pytest
import torch
from efm3d.aria.pose import PoseTW
from torch.utils.data import IterableDataset

from aria_nbv.data_handling import VinOracleBatch
from aria_nbv.oracle.pipelines.online_vin import VinOracleOnlineDataset
from aria_nbv.utils import Verbosity


class _Sample:
    def __init__(self, index: int) -> None:
        self.scene_id = f"scene-{index}"
        self.snippet_id = f"snippet-{index}"
        self.pruned_with: set[str] | None = None

    def prune_efm(self, keep_keys: set[str]) -> _Sample:
        self.pruned_with = keep_keys
        return self


class _Samples(IterableDataset[_Sample]):
    def __init__(self, count: int) -> None:
        super().__init__()
        self.count = count

    def __iter__(self) -> Iterator[_Sample]:
        return iter(_Sample(index) for index in range(self.count))


class _Labeler:
    def __init__(self, outcomes: list[object]) -> None:
        self.outcomes = iter(outcomes)

    def run(self, sample: _Sample) -> object:
        outcome = next(self.outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return _label(sample, rri=outcome)


def _label(sample: _Sample, *, rri: object) -> SimpleNamespace:
    values = torch.as_tensor(rri, dtype=torch.float32)
    zeros = torch.zeros_like(values)
    poses = PoseTW.from_Rt(torch.eye(3).repeat(values.numel(), 1, 1), torch.zeros((values.numel(), 3)))
    return SimpleNamespace(
        sample=sample,
        depths=SimpleNamespace(
            poses=poses,
            reference_pose=PoseTW.from_Rt(torch.eye(3), torch.zeros(3)),
            p3d_cameras=object(),
        ),
        rri=SimpleNamespace(
            rri=values,
            pm_dist_before=zeros,
            pm_dist_after=zeros,
            pm_acc_before=zeros,
            pm_comp_before=zeros,
            pm_acc_after=zeros,
            pm_comp_after=zeros,
        ),
    )


def _dataset(*outcomes: object, max_attempts: int = 2) -> VinOracleOnlineDataset:
    return VinOracleOnlineDataset(
        base=_Samples(len(outcomes)),
        labeler=_Labeler(list(outcomes)),  # type: ignore[arg-type]
        max_attempts_per_batch=max_attempts,
        verbosity=Verbosity.QUIET,
        efm_keep_keys={"rgb"},
    )


def test_online_source_retries_invalid_labels_and_builds_batch() -> None:
    batch = next(iter(_dataset(ValueError("invalid"), [0.25, 0.5])))

    assert isinstance(batch, VinOracleBatch)
    assert batch.scene_id == "scene-1"
    assert batch.snippet_id == "snippet-1"
    assert batch.candidate_count.item() == 2
    assert torch.equal(batch.rri, torch.tensor([0.25, 0.5]))
    assert batch.efm_snippet_view.pruned_with == {"rgb"}  # type: ignore[union-attr]


def test_online_source_skips_nonfinite_labels_without_spending_retry_budget() -> None:
    batch = next(iter(_dataset([float("nan")], [0.5], max_attempts=1)))

    assert torch.equal(batch.rri, torch.tensor([0.5]))


def test_online_source_raises_after_retry_budget_is_exhausted() -> None:
    with pytest.raises(RuntimeError, match="Exceeded max_attempts_per_batch=2"):
        next(iter(_dataset(ValueError("first"), ValueError("second"))))
