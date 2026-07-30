"""Resolve one immutable VIN sample for offline Rerun inspection.

This module owns selector precedence and read-only dataset instantiation:
stable sample key first, then scene/snippet identity, then split-local index.
The selected sample retains source-store identity and is never copied back or
modified by the inspector.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from aria_nbv.data_handling import VinOfflineDataset, VinOfflineDatasetConfig
from aria_nbv.data_handling.identifiers import compact_ase_atek_sample_id
from aria_nbv.data_handling.vin_store.dataset import VinOfflineSample

from ._config import RerunInspectorSelectionConfig


@dataclass(frozen=True, slots=True)
class SelectedRerunSample:
    """Selected offline sample plus human-readable selection context."""

    sample: VinOfflineSample
    """Selected offline sample."""

    index: int | None
    """Index used inside the instantiated dataset, when known."""

    description: str
    """Human-readable selector description."""


def _dataset_config_for_selection(
    dataset_config: VinOfflineDatasetConfig,
    selection: RerunInspectorSelectionConfig,
) -> VinOfflineDatasetConfig:
    """Return a read-only sample dataset config honoring selection precedence."""

    split = "all" if selection.sample_key or selection.scene_id else selection.split
    return dataset_config.model_copy(
        deep=True,
        update={
            "split": split,
            "return_format": "sample",
            "map_location": "cpu",
        },
    )


def _select_by_sample_key(dataset: VinOfflineDataset, sample_key: str) -> SelectedRerunSample:
    """Find one sample by stable sample key."""

    for index in range(len(dataset)):
        sample = dataset[index]
        if not isinstance(sample, VinOfflineSample):
            raise TypeError("Rerun sample selection requires VinOfflineDatasetConfig.return_format='sample'.")
        if sample.sample_key == sample_key or compact_ase_atek_sample_id(
            sample.sample_key
        ) == compact_ase_atek_sample_id(sample_key):
            return SelectedRerunSample(
                sample=sample,
                index=index,
                description=f"sample_key={compact_ase_atek_sample_id(sample_key)}",
            )
    raise LookupError(f"No offline sample found for sample_key={sample_key!r}.")


def _select_by_scene_snippet(dataset: VinOfflineDataset, *, scene_id: str, snippet_id: str) -> SelectedRerunSample:
    """Find one sample by ``(scene_id, snippet_id)``."""

    found = dataset.get_by_scene_snippet(scene_id=scene_id, snippet_id=snippet_id)
    if found is not None:
        return SelectedRerunSample(
            sample=found,
            index=None,
            description=f"scene_id={scene_id} snippet_id={compact_ase_atek_sample_id(snippet_id)}",
        )

    for index in range(len(dataset)):
        sample = dataset[index]
        if not isinstance(sample, VinOfflineSample):
            raise TypeError("Rerun sample selection requires VinOfflineDatasetConfig.return_format='sample'.")
        if sample.scene_id == scene_id and compact_ase_atek_sample_id(sample.snippet_id) == compact_ase_atek_sample_id(
            snippet_id
        ):
            return SelectedRerunSample(
                sample=sample,
                index=index,
                description=f"scene_id={scene_id} snippet_id={compact_ase_atek_sample_id(snippet_id)}",
            )
    raise LookupError(f"No offline sample found for scene_id={scene_id!r}, snippet_id={snippet_id!r}.")


def select_rerun_sample(
    *,
    dataset_config: VinOfflineDatasetConfig,
    selection: RerunInspectorSelectionConfig,
) -> SelectedRerunSample:
    """Select one offline sample using sample-key, pair, then split/index precedence."""

    resolved_config = _dataset_config_for_selection(dataset_config, selection)
    dataset = cast(VinOfflineDataset, resolved_config.setup_target())

    if selection.sample_key:
        return _select_by_sample_key(dataset, selection.sample_key)

    if selection.scene_id and selection.snippet_id:
        return _select_by_scene_snippet(dataset, scene_id=selection.scene_id, snippet_id=selection.snippet_id)

    if selection.index >= len(dataset):
        raise IndexError(
            f"selection.index={selection.index} is out of range for split={selection.split!r} "
            f"with {len(dataset)} samples.",
        )
    sample = dataset[selection.index]
    if not isinstance(sample, VinOfflineSample):
        raise TypeError("Rerun sample selection requires VinOfflineDatasetConfig.return_format='sample'.")
    return SelectedRerunSample(
        sample=sample,
        index=selection.index,
        description=f"split={selection.split} index={selection.index}",
    )


__all__ = ["SelectedRerunSample", "select_rerun_sample"]
