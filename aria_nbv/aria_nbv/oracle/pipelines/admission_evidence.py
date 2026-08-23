"""Fail-closed, presentation-free views of campaign admission audits.

The campaign writer owns the audit format.  This module only validates and
reduces the immutable JSON artifact; it does not re-run target matching or
infer detector-quality metrics which the audit cannot support.
"""

from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ...targets.protocol import STRICT_GT_IOU_THRESHOLD
from ...utils.fingerprints import stable_msgspec_hash
from .campaign import CAMPAIGN_ADMISSION_AUDIT_SCHEMA_VERSION

SUPPORTED_ADMISSION_AUDIT_SCHEMAS = frozenset({"campaign-admission-audit-v1", CAMPAIGN_ADMISSION_AUDIT_SCHEMA_VERSION})
_ADMITTED_REASON = "admitted"


@dataclass(frozen=True, slots=True)
class AdmissionAuditRow:
    """Validated additive facts for one observed-target audit row."""

    sample_key: str
    scene_id: str
    target_id: str
    reason: str
    admitted: bool
    oriented_iou: float | None
    gt_match_id: str | None
    qualified_gt_match_count: int
    detected_source_row: int | None
    row_kind: str = "observed_target"
    observed_target_count: int = 1

    def to_jsonable(self) -> dict[str, Any]:
        """Return the validated factual row for exports and presentation."""

        return {
            "sample_key": self.sample_key,
            "scene_id": self.scene_id,
            "target_id": self.target_id,
            "reason": self.reason,
            "admitted": self.admitted,
            "oriented_iou": self.oriented_iou,
            "gt_match_id": self.gt_match_id,
            "qualified_gt_match_count": self.qualified_gt_match_count,
            "detected_source_row": self.detected_source_row,
            "row_kind": self.row_kind,
            "observed_target_count": self.observed_target_count,
        }


@dataclass(frozen=True, slots=True)
class AdmissionEvidenceSummary:
    """Deterministic rows suitable for plots, cards, and exports."""

    rows: tuple[AdmissionAuditRow, ...]
    reason_rows: tuple[dict[str, Any], ...]
    iou_rows: tuple[dict[str, Any], ...]
    scene_rows: tuple[dict[str, Any], ...]
    duplicate_gt_rows: tuple[dict[str, Any], ...]
    campaign_id: str
    source_manifest_hash: str
    admission_audit_hash: str

    @property
    def observed_count(self) -> int:
        return sum(row.observed_target_count for row in self.rows if row.row_kind == "observed_target")

    @property
    def zero_observation_sample_count(self) -> int:
        return sum(row.row_kind == "zero_observation_sample" for row in self.rows)

    @property
    def zero_observation_scene_count(self) -> int:
        return len({row.scene_id for row in self.rows if row.row_kind == "zero_observation_sample"})

    @property
    def admitted_count(self) -> int:
        return sum(row.admitted for row in self.rows)

    @property
    def rejected_count(self) -> int:
        return self.observed_count - self.admitted_count

    @property
    def finite_iou_count(self) -> int:
        return len(self.iou_rows)

    @property
    def same_class_scored_count(self) -> int:
        """Return targets for which a finite same-class overlap was scored."""

        return self.finite_iou_count

    @property
    def ambiguous_count(self) -> int:
        return sum(row.qualified_gt_match_count > 1 for row in self.rows)

    def to_jsonable(self) -> dict[str, Any]:
        """Return validated audit evidence without re-reading the artifact."""

        return {
            "campaign_id": self.campaign_id,
            "source_manifest_hash": self.source_manifest_hash,
            "admission_audit_hash": self.admission_audit_hash,
            "counts": {
                "observed": self.observed_count,
                "admitted": self.admitted_count,
                "rejected": self.rejected_count,
                "finite_iou": self.finite_iou_count,
                "same_class_scored": self.same_class_scored_count,
                "ambiguous": self.ambiguous_count,
                "duplicate_gt_groups": len(self.duplicate_gt_rows),
                "zero_observation_samples": self.zero_observation_sample_count,
                "zero_observation_scenes": self.zero_observation_scene_count,
            },
            "reason_rows": list(self.reason_rows),
            "iou_rows": list(self.iou_rows),
            "scene_rows": list(self.scene_rows),
            "duplicate_gt_rows": list(self.duplicate_gt_rows),
            "rows": [row.to_jsonable() for row in self.rows],
        }


def read_campaign_admission_evidence(
    source: Path | str | Mapping[str, Any],
    *,
    expected_campaign_id: str | None = None,
    expected_source_manifest_hash: str | None = None,
    expected_audit_hash: str | None = None,
) -> AdmissionEvidenceSummary:
    """Validate and summarize one supported campaign admission audit.

    The function deliberately fails closed: malformed top-level metadata,
    tampered rows, impossible IoU values, and inconsistent admission states
    raise :class:`ValueError` before any summary is returned.  A mapping input
    is useful for callers that already loaded an artifact; path input remains
    the normal presentation-free boundary.
    """

    payload = _load_payload(source)
    schema = _required_str(payload, "schema_version")
    if schema not in SUPPORTED_ADMISSION_AUDIT_SCHEMAS:
        raise ValueError(f"unsupported admission audit schema: {schema!r}")
    campaign_id = _required_str(payload, "campaign_id")
    source_hash = _required_str(payload, "source_manifest_hash")
    claimed_hash = _required_str(payload, "admission_audit_hash")
    raw_rows = payload.get("rows")
    if not isinstance(raw_rows, list):
        raise ValueError("admission audit rows must be a list")
    try:
        actual_hash = stable_msgspec_hash(raw_rows)
    except (TypeError, ValueError) as exc:
        raise ValueError("admission audit rows are not canonical JSON values") from exc
    if claimed_hash != actual_hash:
        raise ValueError("admission audit hash does not match rows")
    if expected_audit_hash is not None and claimed_hash != expected_audit_hash:
        raise ValueError("admission audit hash does not match expected identity")
    if expected_campaign_id is not None and campaign_id != expected_campaign_id:
        raise ValueError("admission audit campaign identity does not match")
    if expected_source_manifest_hash is not None and source_hash != expected_source_manifest_hash:
        raise ValueError("admission audit source identity does not match")

    rows = tuple(_parse_row(raw, index=index) for index, raw in enumerate(raw_rows))
    return _summarize(rows, campaign_id, source_hash, claimed_hash)


def _load_payload(source: Path | str | Mapping[str, Any]) -> Mapping[str, Any]:
    if isinstance(source, Mapping):
        return source
    path = Path(source)
    try:
        with path.open(encoding="utf-8") as stream:
            payload = json.load(stream)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read admission audit: {path}") from exc
    if not isinstance(payload, Mapping):
        raise ValueError("admission audit root must be an object")
    return payload


def _parse_row(raw: Any, *, index: int) -> AdmissionAuditRow:
    if not isinstance(raw, Mapping):
        raise ValueError(f"admission audit row {index} must be an object")
    sample_key = _required_str(raw, "sample_key", index=index)
    scene_id = _required_str(raw, "scene_id", index=index)
    target_id = _optional_str(raw, "target_id", index=index) or ""
    reason = _required_str(raw, "reason", index=index)
    observed_count_raw = raw.get("observed_target_count")
    row_kind_raw = raw.get("row_kind")
    # Older writer output omitted ``row_kind`` but emitted the complete
    # sentinel tuple. Infer only that exact tuple; partial combinations fail closed.
    if row_kind_raw is None and (
        observed_count_raw == 0
        and target_id == ""
        and raw.get("admitted") is False
        and reason == "excluded_no_observed_target"
    ):
        row_kind = "zero_observation_sample"
    else:
        row_kind = row_kind_raw if row_kind_raw is not None else "observed_target"
    if row_kind not in {"observed_target", "zero_observation_sample"}:
        raise ValueError(f"admission audit row {index} row_kind is unsupported")
    observed_count = raw.get("observed_target_count", 1 if row_kind == "observed_target" else 0)
    if type(observed_count) is not int or observed_count < 0:
        raise ValueError(f"admission audit row {index} observed_target_count must be non-negative integer")
    admitted = raw.get("admitted")
    if type(admitted) is not bool:
        raise ValueError(f"admission audit row {index} admitted must be boolean")
    if row_kind == "zero_observation_sample":
        if observed_count != 0 or target_id or admitted:
            raise ValueError(f"admission audit row {index} zero-observation sentinel is malformed")
        if reason != "excluded_no_observed_target":
            raise ValueError(f"admission audit row {index} zero-observation sentinel has wrong reason")
    elif observed_count != 1:
        raise ValueError(f"admission audit row {index} observed-target row must describe exactly one target")
    iou = raw.get("oriented_iou")
    if iou is not None:
        if type(iou) not in (int, float) or isinstance(iou, bool) or not math.isfinite(float(iou)):
            raise ValueError(f"admission audit row {index} oriented_iou must be finite")
        iou = float(iou)
        if not 0.0 <= iou <= 1.0:
            raise ValueError(f"admission audit row {index} oriented_iou is outside [0, 1]")
    if admitted != (reason == _ADMITTED_REASON):
        raise ValueError(f"admission audit row {index} admitted/reason mismatch")
    if admitted and iou is None:
        raise ValueError(f"admission audit row {index} admitted row has no IoU")
    qualified = raw.get("qualified_gt_match_count", raw.get("gt_match_count", 0))
    if type(qualified) is not int or qualified < 0:
        raise ValueError(f"admission audit row {index} qualified match count must be non-negative integer")
    if admitted and qualified != 1:
        raise ValueError(f"admission audit row {index} admitted row must have one qualifying GT")
    if admitted and iou is not None and iou <= STRICT_GT_IOU_THRESHOLD:
        raise ValueError(
            f"admission audit row {index} admitted IoU must be strictly greater than {STRICT_GT_IOU_THRESHOLD:.2f}"
        )
    gt_match_id = _optional_str(raw, "gt_match_id", index=index)
    source_row = raw.get("detected_source_row")
    if source_row is not None and (type(source_row) is not int or source_row < 0):
        raise ValueError(f"admission audit row {index} detected source row is invalid")
    if row_kind == "zero_observation_sample" and (
        iou is not None
        or qualified != 0
        or raw.get("gt_match_count", 0) != 0
        or gt_match_id is not None
        or source_row is not None
    ):
        raise ValueError(f"admission audit row {index} zero-observation sentinel contains GT evidence")
    return AdmissionAuditRow(
        sample_key,
        scene_id,
        target_id,
        reason,
        admitted,
        iou,
        gt_match_id,
        qualified,
        source_row,
        row_kind,
        observed_count,
    )


def _summarize(
    rows: tuple[AdmissionAuditRow, ...],
    campaign_id: str,
    source_hash: str,
    audit_hash: str,
) -> AdmissionEvidenceSummary:
    target_rows = tuple(row for row in rows if row.row_kind == "observed_target")
    reason_counts = Counter(row.reason for row in target_rows)
    reason_rows = tuple(
        {"reason": reason, "count": reason_counts[reason], "admitted": reason == _ADMITTED_REASON}
        for reason in sorted(reason_counts)
    )
    iou_rows = tuple(
        {
            "sample_key": row.sample_key,
            "scene_id": row.scene_id,
            "target_id": row.target_id,
            "reason": row.reason,
            "admitted": row.admitted,
            "oriented_iou": row.oriented_iou,
        }
        for row in target_rows
        if row.oriented_iou is not None
    )
    scene_acc: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for row in target_rows:
        scene_acc[row.scene_id][0] += 1
        scene_acc[row.scene_id][1] += int(row.admitted)
    scene_rows = tuple(
        {
            "scene_id": scene,
            "observed_count": values[0],
            "admitted_count": values[1],
            "admission_rate": values[1] / values[0] if values[0] else None,
        }
        for scene, values in sorted(scene_acc.items())
    )
    matches: dict[tuple[str, str], list[AdmissionAuditRow]] = defaultdict(list)
    for row in target_rows:
        if row.gt_match_id:
            matches[(row.sample_key, row.gt_match_id)].append(row)
    duplicate_rows = tuple(
        {
            "sample_key": sample_key,
            "gt_match_id": gt_match_id,
            "scene_id": entries[0].scene_id,
            "matched_target_count": len(entries),
            "admitted_target_count": sum(entry.admitted for entry in entries),
        }
        for (sample_key, gt_match_id), entries in sorted(matches.items())
        if len(entries) > 1
    )
    return AdmissionEvidenceSummary(
        rows, reason_rows, iou_rows, scene_rows, duplicate_rows, campaign_id, source_hash, audit_hash
    )


def _required_str(raw: Mapping[str, Any], key: str, *, index: int | None = None) -> str:
    value = raw.get(key)
    if type(value) is not str or not value:
        suffix = f" row {index}" if index is not None else ""
        raise ValueError(f"admission audit{suffix} {key} must be a non-empty string")
    return value


def _optional_str(raw: Mapping[str, Any], key: str, *, index: int) -> str | None:
    value = raw.get(key)
    if value is None or value == "":
        return None
    if type(value) is not str:
        raise ValueError(f"admission audit row {index} {key} must be a string")
    return value


__all__ = [
    "AdmissionAuditRow",
    "AdmissionEvidenceSummary",
    "SUPPORTED_ADMISSION_AUDIT_SCHEMAS",
    "read_campaign_admission_evidence",
]
