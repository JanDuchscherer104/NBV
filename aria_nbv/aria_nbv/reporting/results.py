"""Immutable values, tables, figures, and provenance for scientific reports."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from typing import Literal, TypeAlias

JsonScalar: TypeAlias = None | bool | int | float | str


@dataclass(frozen=True, slots=True)
class SourceIdentity:
    """Frozen identity and provenance for one materialized evidence source."""

    id: str
    """Stable recipe-local source identifier."""

    kind: Literal["rollout", "wandb"]
    """Owning source family."""

    sha256: str
    """Digest of the normalized source identity and acquired evidence."""

    provenance: tuple[tuple[str, JsonScalar], ...]
    """Sorted non-secret provenance key/value pairs."""

    def __post_init__(self) -> None:
        _require_id(self.id, "source")
        if self.kind not in {"rollout", "wandb"}:
            raise ValueError("Source identity kind must be rollout or wandb.")
        _require_sha256(self.sha256, "source identity")
        provenance_keys = tuple(key for key, _ in self.provenance)
        _require_unique_ids(provenance_keys, "source provenance")
        if tuple(sorted(self.provenance, key=lambda item: item[0])) != self.provenance:
            raise ValueError("Source provenance must be sorted by key.")
        _validate_scalars(value for _, value in self.provenance)


@dataclass(frozen=True, slots=True)
class NamedQuantity:
    """One named scalar linked to provenance and optional canonical notation."""

    id: str
    """Globally unique result identifier."""

    value: JsonScalar
    """Typed scalar; missing values remain ``None`` rather than fabricated zeroes."""

    unit: str | None
    """Physical or reporting unit, when meaningful."""

    n: int | None
    """Population size underlying the quantity, when available."""

    aggregation: str
    """Code-owned aggregation name such as ``mean`` or ``count``."""

    source_ids: tuple[str, ...]
    """Source identities that support the value."""

    symbol_id: str | None
    """Canonical Typst symbol ID; ``None`` is an explicit operational opt-out."""

    def __post_init__(self) -> None:
        _require_id(self.id, "quantity")
        _validate_scalar(self.value)
        if self.n is not None and self.n < 0:
            raise ValueError("Quantity support n must be nonnegative.")
        _require_support(self.source_ids, "quantity")
        _require_unique_ids(self.source_ids, "quantity source")


@dataclass(frozen=True, slots=True)
class ReportColumn:
    """One ordered table column and its canonical notation binding."""

    id: str
    """Persisted column identifier."""

    symbol_id: str | None
    """Canonical Typst symbol ID; ``None`` is an explicit operational opt-out."""


@dataclass(frozen=True, slots=True)
class ReportTable:
    """Canonical immutable table with typed scalar cells."""

    id: str
    """Globally unique result identifier."""

    columns: tuple[ReportColumn, ...]
    """Ordered column contract."""

    rows: tuple[tuple[JsonScalar, ...], ...]
    """Canonical row-major scalar values."""

    source_ids: tuple[str, ...]
    """Source identities supporting the table."""

    def __post_init__(self) -> None:
        _require_id(self.id, "table")
        _require_unique_ids(tuple(column.id for column in self.columns), "table column")
        _require_support(self.source_ids, "table")
        _require_unique_ids(self.source_ids, "table source")
        width = len(self.columns)
        for row in self.rows:
            if len(row) != width:
                raise ValueError(f"Table {self.id!r} row width does not match its columns.")
            _validate_scalars(row)


@dataclass(frozen=True, slots=True)
class ReportFigure:
    """Canonical Plotly figure shared by Streamlit and static export."""

    id: str
    """Globally unique result identifier."""

    plotly_json: bytes
    """UTF-8 canonical Plotly JSON with sorted keys and no trace UIDs."""

    source_ids: tuple[str, ...]
    """Source identities supporting the figure."""

    source_result_ids: tuple[str, ...]
    """Snapshot quantity/table results consumed by the figure builder."""

    symbol_ids: tuple[str, ...]
    """Canonical symbol IDs used by axes, legend, or explanation."""

    uses_webgl: bool
    """Whether static export must use the configured raster profile."""

    def __post_init__(self) -> None:
        _require_id(self.id, "figure")
        _require_support(self.source_ids, "figure")
        _require_unique_ids(self.source_ids, "figure source")
        _require_unique_ids(self.source_result_ids, "figure result")
        _require_unique_ids(self.symbol_ids, "figure symbol")
        try:
            payload = json.loads(self.plotly_json)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"Figure {self.id!r} does not contain valid UTF-8 JSON.") from exc
        if _canonical_json(payload) != self.plotly_json:
            raise ValueError(f"Figure {self.id!r} Plotly JSON is not canonical.")


ReportResult: TypeAlias = NamedQuantity | ReportTable | ReportFigure


@dataclass(frozen=True, slots=True)
class ReportSnapshot:
    """Immutable transaction consumed by Streamlit and static/Typst export.

    Exporters accept this object, never a report config. Consequently an export
    cannot reacquire W&B history, reread a rollout store, or recompute a figure
    after the user has previewed it.
    """

    schema_version: Literal["aria-nbv-report-snapshot-v1"]
    """Closed snapshot schema version."""

    evidence_status: Literal["pilot", "confirmatory"]
    """Evidence class enforced during acquisition and publication."""

    config_sha256: str
    """Digest of the canonical validated recipe."""

    notation_sha256: str
    """Digest of the generated canonical notation registry."""

    source_identities: tuple[SourceIdentity, ...]
    """Source identities sorted by stable ID."""

    quantities: tuple[NamedQuantity, ...]
    """Named quantities sorted by result ID."""

    tables: tuple[ReportTable, ...]
    """Tables sorted by result ID."""

    figures: tuple[ReportFigure, ...]
    """Figures sorted by result ID."""

    resolved_recipe: bytes
    """Validated TOML recipe frozen at build time."""

    snapshot_sha256: str
    """Digest of all preceding snapshot fields."""

    def __post_init__(self) -> None:
        if self.schema_version != "aria-nbv-report-snapshot-v1":
            raise ValueError("Unsupported report snapshot schema version.")
        if self.evidence_status not in {"pilot", "confirmatory"}:
            raise ValueError("Snapshot evidence status must be pilot or confirmatory.")
        _require_sha256(self.config_sha256, "snapshot config")
        _require_sha256(self.notation_sha256, "snapshot notation")
        try:
            self.resolved_recipe.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("Snapshot recipe must contain UTF-8 TOML bytes.") from exc
        if not self.snapshot_sha256:
            return
        _require_sha256(self.snapshot_sha256, "snapshot")
        source_ids = tuple(source.id for source in self.source_identities)
        _require_unique_ids(source_ids, "snapshot source")
        if tuple(sorted(source_ids)) != source_ids:
            raise ValueError("Snapshot sources must be sorted by ID.")
        results: tuple[ReportResult, ...] = (*self.quantities, *self.tables, *self.figures)
        result_ids = tuple(result.id for result in results)
        _require_unique_ids(result_ids, "snapshot result")
        if tuple(result.id for result in self.quantities) != tuple(sorted(result.id for result in self.quantities)):
            raise ValueError("Snapshot quantities must be sorted by ID.")
        if tuple(result.id for result in self.tables) != tuple(sorted(result.id for result in self.tables)):
            raise ValueError("Snapshot tables must be sorted by ID.")
        if tuple(result.id for result in self.figures) != tuple(sorted(result.id for result in self.figures)):
            raise ValueError("Snapshot figures must be sorted by ID.")
        source_support = set(source_ids)
        for result in results:
            if not set(result.source_ids).issubset(source_support):
                raise ValueError(f"Result {result.id!r} references an unknown source identity.")
        available_results = {result.id for result in self.quantities} | {result.id for result in self.tables}
        for figure in self.figures:
            if not set(figure.source_result_ids).issubset(available_results):
                raise ValueError(f"Figure {figure.id!r} references an unknown source result.")
        if self.snapshot_sha256 != _snapshot_digest(self):
            raise ValueError("Snapshot digest does not match its canonical contents.")

    @classmethod
    def create(
        cls,
        *,
        evidence_status: Literal["pilot", "confirmatory"],
        config_sha256: str,
        notation_sha256: str,
        source_identities: tuple[SourceIdentity, ...],
        quantities: tuple[NamedQuantity, ...],
        tables: tuple[ReportTable, ...],
        figures: tuple[ReportFigure, ...],
        resolved_recipe: bytes,
    ) -> "ReportSnapshot":
        """Canonicalize ordering and seal a snapshot with its content digest."""

        values = {
            "schema_version": "aria-nbv-report-snapshot-v1",
            "evidence_status": evidence_status,
            "config_sha256": config_sha256,
            "notation_sha256": notation_sha256,
            "source_identities": tuple(sorted(source_identities, key=lambda item: item.id)),
            "quantities": tuple(sorted(quantities, key=lambda item: item.id)),
            "tables": tuple(sorted(tables, key=lambda item: item.id)),
            "figures": tuple(sorted(figures, key=lambda item: item.id)),
            "resolved_recipe": resolved_recipe,
        }
        provisional = cls(**values, snapshot_sha256="")  # type: ignore[arg-type]
        object.__setattr__(provisional, "snapshot_sha256", _snapshot_digest(provisional))
        provisional.__post_init__()
        return provisional

    def result(self, result_id: str) -> ReportResult:
        """Return one result by stable ID or raise ``KeyError``."""

        results: tuple[ReportResult, ...] = (*self.quantities, *self.tables, *self.figures)
        for result in results:
            if result.id == result_id:
                return result
        raise KeyError(result_id)


def canonical_plotly_json(payload: object) -> bytes:
    """Return canonical Plotly JSON with generated trace UIDs removed."""

    if hasattr(payload, "to_plotly_json"):
        payload = payload.to_plotly_json()
    normalized = _strip_uids(payload)
    return _canonical_json(normalized)


def _strip_uids(value: object) -> object:
    if isinstance(value, dict):
        return {str(key): _strip_uids(item) for key, item in value.items() if key != "uid"}
    if isinstance(value, list | tuple):
        return [_strip_uids(item) for item in value]
    if hasattr(value, "tolist"):
        return _strip_uids(value.tolist())
    return value


def _snapshot_digest(snapshot: ReportSnapshot) -> str:
    payload = {
        "schema_version": snapshot.schema_version,
        "evidence_status": snapshot.evidence_status,
        "config_sha256": snapshot.config_sha256,
        "notation_sha256": snapshot.notation_sha256,
        "source_identities": [asdict(item) for item in snapshot.source_identities],
        "quantities": [asdict(item) for item in snapshot.quantities],
        "tables": [asdict(item) for item in snapshot.tables],
        "figures": [
            {
                **asdict(item),
                "plotly_json": item.plotly_json.decode("utf-8"),
            }
            for item in snapshot.figures
        ],
        "resolved_recipe": snapshot.resolved_recipe.decode("utf-8"),
    }
    return hashlib.sha256(_canonical_json(payload)).hexdigest()


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def _require_id(identifier: str, kind: str) -> None:
    if not identifier.strip():
        raise ValueError(f"{kind.title()} ID must be non-empty.")


def _require_unique_ids(identifiers: tuple[str, ...], kind: str) -> None:
    if any(not identifier.strip() for identifier in identifiers) or len(identifiers) != len(set(identifiers)):
        raise ValueError(f"{kind.title()} IDs must be non-empty and unique.")


def _require_support(source_ids: tuple[str, ...], kind: str) -> None:
    if not source_ids:
        raise ValueError(f"{kind.title()} must reference at least one source identity.")


def _require_sha256(value: str, kind: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError(f"{kind.title()} sha256 must contain 64 lowercase hexadecimal characters.")


def _validate_scalars(values: Iterable[JsonScalar]) -> None:
    for value in values:
        _validate_scalar(value)


def _validate_scalar(value: JsonScalar) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Report inputs contain a non-finite numeric value.")
    if value is not None and not isinstance(value, bool | int | float | str):
        raise TypeError(f"Unsupported report scalar {type(value).__name__}.")


__all__ = [
    "JsonScalar",
    "NamedQuantity",
    "ReportColumn",
    "ReportFigure",
    "ReportSnapshot",
    "ReportTable",
    "SourceIdentity",
    "canonical_plotly_json",
]
