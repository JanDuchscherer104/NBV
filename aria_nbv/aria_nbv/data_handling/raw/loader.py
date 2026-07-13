"""Shared EFM snippet loader for on-demand access."""

from __future__ import annotations

from typing import Any

from ...configs import PathConfig
from ...utils import Verbosity
from .dataset import AseEfmDataset, AseEfmDatasetConfig
from .views import EfmSnippetView


class EfmSnippetLoader:
    """Persistent per-worker loader for on-demand EFM snippets."""

    def __init__(
        self,
        *,
        dataset_payload: dict[str, Any] | None,
        device: str,
        paths: PathConfig,
        include_gt_mesh: bool,
    ) -> None:
        """Store the raw dataset payload and worker-local dataset cache."""
        self._dataset_payload = dict(dataset_payload or {})
        self._device = str(device)
        self._paths = paths
        self._include_gt_mesh = include_gt_mesh
        self._datasets: dict[str, AseEfmDataset] = {}

    def _build_dataset(self, scene_id: str) -> AseEfmDataset:
        """Build and cache a single-scene raw dataset for snippet lookup."""
        payload = dict(self._dataset_payload)
        payload["paths"] = payload.get("paths", self._paths)
        payload["scene_ids"] = [scene_id]
        payload["snippet_ids"] = []
        payload["snippet_key_filter"] = []
        payload["batch_size"] = 1
        payload["device"] = self._device
        payload["wds_shuffle"] = False
        payload["wds_repeat"] = False
        payload["load_meshes"] = bool(self._include_gt_mesh)
        payload.setdefault("require_mesh", False)
        payload["verbosity"] = Verbosity.QUIET
        cfg = AseEfmDatasetConfig(**payload)
        dataset = cfg.setup_target()
        self._datasets[scene_id] = dataset
        return dataset

    def load(self, *, scene_id: str, snippet_id: str) -> EfmSnippetView:
        """Load a snippet view, reusing a cached dataset per scene."""
        for attempt in range(2):
            dataset = self._datasets.get(scene_id)
            if dataset is None:
                dataset = self._build_dataset(scene_id)
            dataset._snippet_key_filter = {snippet_id}  # type: ignore[attr-defined]
            for sample in dataset:
                return sample
            if attempt == 0:
                self._datasets.pop(scene_id, None)
        raise FileNotFoundError(
            f"Failed to locate snippet={snippet_id} in scene={scene_id}.",
        )


__all__ = ["EfmSnippetLoader"]
