"""Read-only detected and GT OBB population evidence from a VIN store.

The inventory is deliberately separate from the training-bundle composer and
from Streamlit.  It reads the manifest-declared compact OBB blocks only;
missing blocks and malformed rows are reported as unavailable evidence rather
than being inferred from raw source snippets.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np

from ...utils.semantic_names import semantic_class_name
from .format import VinOfflineIndexRecord, VinOfflineManifest
from .store import VinOfflineStoreConfig, VinOfflineStoreReader

TargetPopulation = Literal["detected", "gt"]


@dataclass(frozen=True, slots=True)
class TargetInventoryRow:
    """One finite, non-padding compact OBB row."""

    population: TargetPopulation
    sample_index: int
    sample_key: str
    scene_id: str
    snippet_id: str
    split: str
    source_row: int
    target_index: int
    semantic_id: int
    instance_id: int
    class_name: str
    confidence: float
    center: tuple[float, float, float]
    extents: tuple[float, float, float]
    diagonal: float
    volume: float
    aspect_ratio: float | None

    def to_jsonable(self) -> dict[str, Any]:
        """Return a compact JSON-compatible row without the raw OBB payload."""

        return {
            "population": self.population,
            "sample_index": self.sample_index,
            "sample_key": self.sample_key,
            "scene_id": self.scene_id,
            "snippet_id": self.snippet_id,
            "split": self.split,
            "source_row": self.source_row,
            "target_index": self.target_index,
            "semantic_id": self.semantic_id,
            "instance_id": self.instance_id,
            "class_name": self.class_name,
            "confidence": self.confidence,
            "center": list(self.center),
            "extents": list(self.extents),
            "diagonal": self.diagonal,
            "volume": self.volume,
            "aspect_ratio": self.aspect_ratio,
        }


@dataclass(frozen=True, slots=True)
class TargetPopulationEvidence:
    """Inventory evidence for one detected or GT population."""

    population: TargetPopulation
    available: bool
    reason: str | None
    rows: tuple[TargetInventoryRow, ...]
    excluded_padding_count: int
    excluded_nonfinite_count: int
    sample_counts: tuple[tuple[int, int], ...]
    scene_counts: tuple[tuple[str, int], ...]
    split_counts: tuple[tuple[str, int], ...]
    class_counts: tuple[tuple[str, int], ...]

    @property
    def row_count(self) -> int:
        """Return the number of valid rows."""

        return len(self.rows)

    def to_jsonable(self) -> dict[str, Any]:
        """Return deterministic download-ready evidence."""

        return {
            "population": self.population,
            "available": self.available,
            "reason": self.reason,
            "row_count": self.row_count,
            "excluded_padding_count": self.excluded_padding_count,
            "excluded_nonfinite_count": self.excluded_nonfinite_count,
            "sample_counts": {str(key): value for key, value in self.sample_counts},
            "scene_counts": dict(self.scene_counts),
            "split_counts": dict(self.split_counts),
            "class_counts": dict(self.class_counts),
            "rows": [row.to_jsonable() for row in self.rows],
        }


@dataclass(frozen=True, slots=True)
class TargetInventory:
    """Complete detected/GT target inventory for one immutable VIN root."""

    path: str
    detected: TargetPopulationEvidence
    gt: TargetPopulationEvidence

    def to_jsonable(self) -> dict[str, Any]:
        """Return deterministic JSON-compatible evidence."""

        return {
            "path": self.path,
            "detected": self.detected.to_jsonable(),
            "gt": self.gt.to_jsonable(),
        }


def inspect_target_inventory(root_store: Path | str) -> TargetInventory:
    """Inspect manifest-declared detected and GT OBB blocks.

    The scan is read-only and deterministic in sample-index/row order.  A
    population is unavailable when its manifest flag or any shard block is
    absent, or when a block has an invalid shape.  No raw-source fallback is
    attempted.
    """

    store = Path(root_store).expanduser().resolve()
    try:
        manifest = VinOfflineManifest.read(store / "manifest.json")
        records = tuple(VinOfflineIndexRecord.read_many(store / "sample_index.jsonl"))
    except Exception as exc:
        reason = f"root_store_unreadable:{type(exc).__name__}:{exc}"
        return TargetInventory(store.as_posix(), _unavailable("detected", reason), _unavailable("gt", reason))

    reader = VinOfflineStoreReader(VinOfflineStoreConfig(store_dir=store))
    return TargetInventory(
        store.as_posix(),
        _inspect_population("detected", manifest, records, reader),
        _inspect_population("gt", manifest, records, reader),
    )


def _inspect_population(
    population: TargetPopulation,
    manifest: VinOfflineManifest,
    records: tuple[VinOfflineIndexRecord, ...],
    reader: VinOfflineStoreReader,
) -> TargetPopulationEvidence:
    flag = (
        population == "gt"
        and manifest.materialized_blocks.gt_obbs
        or (population == "detected" and manifest.materialized_blocks.detected_obbs)
    )
    block_name = f"{population}.obbs"
    if not flag:
        return _unavailable(population, f"{block_name}_not_materialized")
    shard_specs = {spec.shard_id: spec for spec in manifest.shards}
    missing = sorted(
        {
            record.shard_id
            for record in records
            if record.shard_id not in shard_specs or block_name not in shard_specs[record.shard_id].blocks
        }
    )
    if missing:
        return _unavailable(population, f"{block_name}_block_missing:{','.join(missing)}")

    rows: list[TargetInventoryRow] = []
    padding_count = 0
    nonfinite_count = 0
    try:
        for record in records:
            values = np.asarray(reader.read_numeric_block(record, block_name))
            if values.ndim < 2 or values.shape[-1] != 34:
                return _unavailable(population, f"{block_name}_shape_invalid:{list(values.shape)}")
            for target_index, raw in enumerate(values.reshape(-1, values.shape[-1])):
                finite = bool(np.all(np.isfinite(raw)))
                if not finite:
                    nonfinite_count += 1
                    continue
                if bool(np.all(raw == -1.0)):
                    padding_count += 1
                    continue
                bounds = np.asarray(raw[:6], dtype=np.float64).reshape(3, 2)
                extents_array = bounds[:, 1] - bounds[:, 0]
                center_array = (bounds[:, 1] + bounds[:, 0]) / 2.0
                extents = tuple(float(value) for value in extents_array)
                center = tuple(float(value) for value in center_array)
                positive = bool(np.all(extents_array > 0.0))
                volume = float(np.prod(extents_array)) if positive else 0.0
                diagonal = float(np.linalg.norm(extents_array))
                minimum = float(np.min(extents_array)) if positive else 0.0
                aspect_ratio = float(np.max(extents_array) / minimum) if minimum > 0.0 else None
                semantic_id = int(np.rint(raw[30]))
                rows.append(
                    TargetInventoryRow(
                        population=population,
                        sample_index=record.sample_index,
                        sample_key=record.sample_key,
                        scene_id=record.scene_id,
                        snippet_id=record.snippet_id,
                        split=record.split,
                        source_row=record.row,
                        target_index=target_index,
                        semantic_id=semantic_id,
                        instance_id=int(np.rint(raw[31])),
                        class_name=semantic_class_name(
                            semantic_id,
                            reader.read_optional_record(record, f"{population}.obb_sem_id_to_name"),
                        ),
                        confidence=float(raw[32]),
                        center=center,
                        extents=extents,
                        diagonal=diagonal,
                        volume=volume,
                        aspect_ratio=aspect_ratio,
                    ),
                )
    except Exception as exc:
        return _unavailable(population, f"{block_name}_block_unreadable:{type(exc).__name__}:{exc}")
    return _available(population, rows, padding_count, nonfinite_count)


def _available(
    population: TargetPopulation,
    rows: list[TargetInventoryRow],
    padding_count: int,
    nonfinite_count: int,
) -> TargetPopulationEvidence:
    sample = Counter(row.sample_index for row in rows)
    scene = Counter(row.scene_id for row in rows)
    split = Counter(row.split for row in rows)
    classes = Counter(row.class_name for row in rows)
    return TargetPopulationEvidence(
        population,
        True,
        None,
        tuple(rows),
        padding_count,
        nonfinite_count,
        tuple(sorted(sample.items())),
        tuple(sorted(scene.items())),
        tuple(sorted(split.items())),
        tuple(sorted(classes.items())),
    )


def _unavailable(population: TargetPopulation, reason: str) -> TargetPopulationEvidence:
    return TargetPopulationEvidence(population, False, reason, (), 0, 0, (), (), (), ())


__all__ = [
    "TargetInventory",
    "TargetInventoryRow",
    "TargetPopulationEvidence",
    "inspect_target_inventory",
]
