"""Read-only detected and GT OBB population evidence from a VIN store.

The inventory is deliberately separate from the training-bundle composer and
from Streamlit.  It reads the manifest-declared compact OBB blocks only;
missing blocks and malformed rows are reported as unavailable evidence rather
than being inferred from raw source snippets.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np
import plotly.graph_objects as go
import torch
from efm3d.aria.obb import ObbTW
from plotly.subplots import make_subplots

from ...reporting.notation import TheoryReferences
from ...reporting.results import canonical_plotly_json
from ...utils.semantic_names import semantic_class_name
from .format import VinOfflineIndexRecord, VinOfflineManifest
from .store import VinOfflineStoreConfig, VinOfflineStoreReader

TargetPopulation = Literal["detected", "gt"]

_IMPLEMENTATION_SOURCE_URL = (
    "https://github.com/JanDuchscherer104/ARIA-NBV/blob/main/"
    "aria_nbv/aria_nbv/data_handling/vin_store/target_inventory.py"
)


@dataclass(frozen=True, slots=True)
class CanonicalPlotlyFigure:
    """Immutable Plotly JSON evidence reconstructed freshly by presentation code."""

    key: str
    plotly_json: bytes
    explanation: "TargetFigureExplanation"

    def build_figure(self) -> go.Figure:
        """Return a new mutable figure without mutating canonical evidence bytes."""

        return go.Figure(json.loads(self.plotly_json))


@dataclass(frozen=True, slots=True)
class TargetFigureExplanation:
    """Domain-neutral interpretation and provenance for one frozen figure."""

    question: str
    answer: str
    denominator_missingness: str
    units: str
    interpretation: str
    warning: str
    source_fields: tuple[str, ...]
    external_implementation_reference: str
    evidence_role: Literal["provenance"]
    theory: TheoryReferences


@dataclass(frozen=True, slots=True)
class TargetPopulationSummary:
    """Factual coverage summary which keeps unavailable populations explicit."""

    population: TargetPopulation
    available: bool
    unavailable_reason: str | None
    valid_row_count: int | None
    physical_sample_count: int | None
    zero_target_sample_count: int | None
    excluded_padding_count: int
    excluded_nonfinite_count: int
    excluded_invalid_geometry_count: int


@dataclass(frozen=True, slots=True)
class TargetInventoryAcquisitionIdentity:
    """Generation and complete request identity bound during deep acquisition."""

    identity_version: str
    """Generation identity schema version."""

    generation_digest: str
    """Digest of the filesystem generation verified around acquisition."""

    request_digest: str
    """Digest of the complete deep-inspection request."""


@dataclass(frozen=True, slots=True)
class TargetInventoryReport:
    """Frozen, presentation-neutral inventory reduction and figure evidence."""

    inventory: "TargetInventory"
    summaries: tuple[TargetPopulationSummary, ...]
    figures: tuple[CanonicalPlotlyFigure, ...]
    admission_handoff: str
    provenance: tuple[tuple[str, str], ...]
    acquisition: TargetInventoryAcquisitionIdentity | None = None

    def to_jsonable(self) -> dict[str, Any]:
        """Return deterministic download-ready report evidence."""

        return {
            "inventory": self.inventory.to_jsonable(),
            "summaries": [
                {
                    "population": summary.population,
                    "available": summary.available,
                    "unavailable_reason": summary.unavailable_reason,
                    "valid_row_count": summary.valid_row_count,
                    "physical_sample_count": summary.physical_sample_count,
                    "zero_target_sample_count": summary.zero_target_sample_count,
                    "excluded_padding_count": summary.excluded_padding_count,
                    "excluded_nonfinite_count": summary.excluded_nonfinite_count,
                    "excluded_invalid_geometry_count": summary.excluded_invalid_geometry_count,
                }
                for summary in self.summaries
            ],
            "figures": [
                {
                    "key": figure.key,
                    "plotly_json": figure.plotly_json.decode("utf-8"),
                    "explanation": {
                        "question": figure.explanation.question,
                        "answer": figure.explanation.answer,
                        "denominator_missingness": figure.explanation.denominator_missingness,
                        "units": figure.explanation.units,
                        "interpretation": figure.explanation.interpretation,
                        "warning": figure.explanation.warning,
                        "source_fields": list(figure.explanation.source_fields),
                        "external_implementation_reference": figure.explanation.external_implementation_reference,
                        "evidence_role": figure.explanation.evidence_role,
                        "theory": {"term_ids": list(figure.explanation.theory.term_ids)},
                    },
                }
                for figure in self.figures
            ],
            "admission_handoff": self.admission_handoff,
            "provenance": dict(self.provenance),
            "acquisition": (
                None
                if self.acquisition is None
                else {
                    "identity_version": self.acquisition.identity_version,
                    "generation_digest": self.acquisition.generation_digest,
                    "request_digest": self.acquisition.request_digest,
                }
            ),
        }

    def export_bytes(self) -> bytes:
        """Serialize exactly the report shown by the application."""

        return (json.dumps(self.to_jsonable(), indent=2, sort_keys=True) + "\n").encode("utf-8")


@dataclass(frozen=True, slots=True)
class TargetSampleCount:
    """Target count for one VIN sample, including zero-target samples."""

    sample_index: int
    sample_key: str
    scene_id: str
    snippet_id: str
    split: str
    count: int

    def to_jsonable(self) -> dict[str, Any]:
        """Return a JSON-compatible sample count row."""

        return {
            "sample_index": self.sample_index,
            "sample_key": self.sample_key,
            "scene_id": self.scene_id,
            "snippet_id": self.snippet_id,
            "split": self.split,
            "count": self.count,
        }


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
    excluded_invalid_geometry_count: int
    sample_rows: tuple[TargetSampleCount, ...]
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
            "excluded_invalid_geometry_count": self.excluded_invalid_geometry_count,
            "sample_rows": [row.to_jsonable() for row in self.sample_rows],
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

    try:
        reader = VinOfflineStoreReader(VinOfflineStoreConfig(store_dir=store))
    except Exception as exc:
        reason = f"root_store_unreadable:{type(exc).__name__}:{exc}"
        return TargetInventory(store.as_posix(), _unavailable("detected", reason), _unavailable("gt", reason))
    return TargetInventory(
        store.as_posix(),
        _inspect_population("detected", manifest, records, reader),
        _inspect_population("gt", manifest, records, reader),
    )


def build_target_inventory_report(
    inventory: TargetInventory,
    *,
    acquisition: TargetInventoryAcquisitionIdentity | None = None,
) -> TargetInventoryReport:
    """Purely reduce factual target inventory evidence into a frozen report."""

    populations = (inventory.detected, inventory.gt)
    return TargetInventoryReport(
        inventory=inventory,
        summaries=tuple(_population_summary(population) for population in populations),
        figures=_inventory_figures(populations),
        admission_handoff=(
            "This inventory describes source coverage only; Campaign Generation owns immutable admission, "
            "including strict same-class oriented IoU > 0.20 and exactly one qualifying GT match."
        ),
        provenance=(
            ("implementation", "aria_nbv.data_handling.vin_store.target_inventory"),
            ("theory", "persisted detected and GT OBB populations remain separate evidence roles"),
        ),
        acquisition=acquisition,
    )


def _population_summary(population: TargetPopulationEvidence) -> TargetPopulationSummary:
    if not population.available:
        return TargetPopulationSummary(population.population, False, population.reason, None, None, None, 0, 0, 0)
    return TargetPopulationSummary(
        population.population,
        True,
        None,
        population.row_count,
        len(population.sample_rows),
        sum(sample.count == 0 for sample in population.sample_rows),
        population.excluded_padding_count,
        population.excluded_nonfinite_count,
        population.excluded_invalid_geometry_count,
    )


_THEORY = TheoryReferences(
    term_ids=("observed-target-selection", "ground-truth-target-evaluation", "oriented-bounding-box")
)


def _explanation(key: str, *, units: str, source_fields: tuple[str, ...]) -> TargetFigureExplanation:
    return TargetFigureExplanation(
        question=f"What does the {key.replace('-', ' ')} evidence show?",
        answer="It reports persisted target-inventory provenance without changing admission decisions.",
        denominator_missingness="Unavailable populations are omitted from traces and retained as unavailable report summaries.",
        units=units,
        interpretation="Compare detected and ground-truth populations only within their factual available support.",
        warning="This is source coverage evidence, not campaign admission or evaluation output.",
        source_fields=source_fields,
        external_implementation_reference=_IMPLEMENTATION_SOURCE_URL,
        evidence_role="provenance",
        theory=_THEORY,
    )


def _figure(key: str, figure: go.Figure, *, units: str, source_fields: tuple[str, ...]) -> CanonicalPlotlyFigure:
    return CanonicalPlotlyFigure(
        key, canonical_plotly_json(figure), _explanation(key, units=units, source_fields=source_fields)
    )


def _inventory_figures(
    populations: tuple[TargetPopulationEvidence, TargetPopulationEvidence],
) -> tuple[CanonicalPlotlyFigure, ...]:
    """Build only the characterized factual target-inventory figure family."""

    available = tuple(population for population in populations if population.available)
    if not available:
        return ()
    figures: list[CanonicalPlotlyFigure] = []
    exclusion_fields = (
        ("padding", "excluded_padding_count"),
        ("non-finite", "excluded_nonfinite_count"),
        ("invalid geometry", "excluded_invalid_geometry_count"),
    )
    if any(getattr(population, field) for population in available for _reason, field in exclusion_fields):
        figures.append(
            _figure(
                "exclusions",
                go.Figure(
                    [
                        go.Bar(
                            name=population.population,
                            x=[reason for reason, _field in exclusion_fields],
                            y=[getattr(population, field) for _reason, field in exclusion_fields],
                        )
                        for population in available
                    ]
                ).update_layout(barmode="group", xaxis_title="Exclusion reason", yaxis_title="Excluded rows"),
                units="rows",
                source_fields=(
                    "TargetPopulationEvidence.population",
                    "TargetPopulationEvidence.excluded_padding_count",
                    "TargetPopulationEvidence.excluded_nonfinite_count",
                    "TargetPopulationEvidence.excluded_invalid_geometry_count",
                ),
            )
        )
    sample_figure = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        row_heights=(0.25, 0.75),
        vertical_spacing=0.03,
    )
    has_sample_traces = False
    for population in available:
        counts = [sample.count for sample in population.sample_rows]
        if counts:
            has_sample_traces = True
            sample_figure.add_trace(
                go.Histogram(name=population.population, x=counts),
                row=2,
                col=1,
            )
            sample_figure.add_trace(
                go.Box(name=f"{population.population} marginal", x=counts, orientation="h", showlegend=False),
                row=1,
                col=1,
            )
    if has_sample_traces:
        figures.append(
            _figure(
                "per-sample-counts",
                sample_figure.update_layout(
                    barmode="overlay",
                    xaxis2_title="Finite valid OBB rows per physical sample",
                    yaxis2_title="Sample frequency",
                    yaxis_showticklabels=False,
                ),
                units="rows per sample",
                source_fields=(
                    "TargetPopulationEvidence.population",
                    "TargetPopulationEvidence.sample_rows",
                    "TargetSampleCount.count",
                ),
            )
        )
    class_traces: list[go.Bar] = []
    for population in available:
        classes = sorted({row.class_name for row in population.rows})
        if classes:
            class_traces.append(
                go.Bar(
                    name=population.population,
                    x=classes,
                    y=[sum(row.class_name == name for row in population.rows) for name in classes],
                    customdata=[
                        [len({row.scene_id for row in population.rows if row.class_name == name})] for name in classes
                    ],
                    hovertemplate="class=%{x}<br>target rows=%{y}<br>distinct scenes=%{customdata[0]}<extra></extra>",
                )
            )
    if class_traces:
        figures.append(
            _figure(
                "class-support",
                go.Figure(class_traces).update_layout(
                    barmode="group", xaxis_title="Semantic class", yaxis_title="Target rows"
                ),
                units="target rows",
                source_fields=(
                    "TargetPopulationEvidence.population",
                    "TargetInventoryRow.class_name",
                    "TargetInventoryRow.scene_id",
                ),
            )
        )
    for key, attribute, label in (
        ("obb-volume", "volume", "log10(volume [m^3])"),
        ("obb-aspect-ratio", "aspect_ratio", "log10(largest extent / smallest extent)"),
    ):
        traces = []
        for population in available:
            values = [
                float(getattr(row, attribute))
                for row in population.rows
                if getattr(row, attribute) is not None and float(getattr(row, attribute)) > 0.0
            ]
            if values:
                traces.append(
                    go.Histogram(
                        name=population.population,
                        x=[float(np.log10(value)) for value in values],
                        histnorm="probability",
                    )
                )
        if traces:
            figures.append(
                _figure(
                    key,
                    go.Figure(traces).update_layout(barmode="overlay", xaxis_title=label, yaxis_title="Probability"),
                    units=label,
                    source_fields=("TargetPopulationEvidence.population", f"TargetInventoryRow.{attribute}"),
                )
            )
    detected = next((population for population in available if population.population == "detected"), None)
    if detected is not None and detected.rows:
        classes = sorted({row.class_name for row in detected.rows})
        figures.append(
            _figure(
                "detection-confidence",
                go.Figure(
                    [
                        go.Histogram(name=name, x=[row.confidence for row in detected.rows if row.class_name == name])
                        for name in classes
                    ]
                ).update_layout(
                    barmode="relative", xaxis_title="Detection confidence", yaxis_title="Detected target rows"
                ),
                units="confidence",
                source_fields=(
                    "TargetPopulationEvidence.population",
                    "TargetInventoryRow.confidence",
                    "TargetInventoryRow.class_name",
                ),
            )
        )
    return tuple(figures)


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
    invalid_geometry_count = 0
    sample_counts: Counter[int] = Counter({record.sample_index: 0 for record in records})
    scene_counts: Counter[str] = Counter({record.scene_id: 0 for record in records})
    split_counts: Counter[str] = Counter({record.split: 0 for record in records})
    try:
        for record in records:
            values = np.asarray(reader.read_numeric_block(record, block_name))
            if values.ndim < 2 or values.shape[-1] != 34:
                return _unavailable(population, f"{block_name}_shape_invalid:{list(values.shape)}")
            semantic_names = reader.read_optional_record(record, f"{population}.obb_sem_id_to_name")
            for target_index, raw in enumerate(values.reshape(-1, values.shape[-1])):
                finite = bool(np.all(np.isfinite(raw)))
                if not finite:
                    nonfinite_count += 1
                    continue
                if bool(np.all(raw == -1.0)):
                    padding_count += 1
                    continue
                obb = ObbTW(torch.as_tensor(raw, dtype=torch.float32).reshape(1, -1))
                extents_array = obb.bb3_diagonal.detach().cpu().numpy().reshape(-1)
                center_array = obb.bb3_center_world.detach().cpu().numpy().reshape(-1)
                if extents_array.size != 3 or center_array.size != 3:
                    invalid_geometry_count += 1
                    continue
                extents = (float(extents_array[0]), float(extents_array[1]), float(extents_array[2]))
                center = (float(center_array[0]), float(center_array[1]), float(center_array[2]))
                positive = bool(np.all(extents_array > 0.0))
                if not positive:
                    invalid_geometry_count += 1
                    continue
                volume = float(np.prod(extents_array))
                diagonal = float(np.linalg.norm(extents_array))
                minimum = float(np.min(extents_array))
                aspect_ratio = float(np.max(extents_array) / minimum)
                semantic_id = int(obb.sem_id.reshape(-1)[0].item())
                sample_counts[record.sample_index] += 1
                scene_counts[record.scene_id] += 1
                split_counts[record.split] += 1
                rows.append(
                    TargetInventoryRow(
                        population=population,
                        sample_index=record.sample_index,
                        sample_key=record.sample_key,
                        scene_id=record.scene_id,
                        snippet_id=record.snippet_id,
                        split=record.split,
                        source_row=target_index,
                        target_index=target_index,
                        semantic_id=semantic_id,
                        instance_id=int(obb.inst_id.reshape(-1)[0].item()),
                        class_name=semantic_class_name(semantic_id, semantic_names),
                        confidence=float(obb.prob.reshape(-1)[0].item()),
                        center=center,
                        extents=extents,
                        diagonal=diagonal,
                        volume=volume,
                        aspect_ratio=aspect_ratio,
                    ),
                )
    except Exception as exc:
        return _unavailable(population, f"{block_name}_block_unreadable:{type(exc).__name__}:{exc}")
    return _available(
        population,
        rows,
        padding_count,
        nonfinite_count,
        invalid_geometry_count,
        records,
        sample_counts,
        scene_counts,
        split_counts,
    )


def _available(
    population: TargetPopulation,
    rows: list[TargetInventoryRow],
    padding_count: int,
    nonfinite_count: int,
    invalid_geometry_count: int,
    records: tuple[VinOfflineIndexRecord, ...],
    sample_counts: Counter[Any],
    scene_counts: Counter[str],
    split_counts: Counter[str],
) -> TargetPopulationEvidence:
    classes = Counter(row.class_name for row in rows)
    sample_rows = tuple(
        TargetSampleCount(
            record.sample_index,
            record.sample_key,
            record.scene_id,
            record.snippet_id,
            record.split,
            sample_counts[record.sample_index],
        )
        for record in records
    )
    return TargetPopulationEvidence(
        population,
        True,
        None,
        tuple(rows),
        padding_count,
        nonfinite_count,
        invalid_geometry_count,
        sample_rows,
        tuple(sorted(sample_counts.items())),
        tuple(sorted(scene_counts.items())),
        tuple(sorted(split_counts.items())),
        tuple(sorted(classes.items())),
    )


def _unavailable(population: TargetPopulation, reason: str) -> TargetPopulationEvidence:
    return TargetPopulationEvidence(population, False, reason, (), 0, 0, 0, (), (), (), (), ())


__all__ = [
    "CanonicalPlotlyFigure",
    "TargetInventory",
    "TargetInventoryAcquisitionIdentity",
    "TargetInventoryReport",
    "TargetInventoryRow",
    "TargetFigureExplanation",
    "TargetPopulation",
    "TargetPopulationEvidence",
    "TargetPopulationSummary",
    "TargetSampleCount",
    "build_target_inventory_report",
    "inspect_target_inventory",
]
