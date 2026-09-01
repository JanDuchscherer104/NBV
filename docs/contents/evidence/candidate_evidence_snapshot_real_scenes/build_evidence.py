"""Rebuild canonical candidate plots from the committed real-scene snapshots."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aria_nbv.rollouts.candidate_evidence import (
    CandidateCriterionSnapshot,
    CandidateEvidenceRow,
    CandidateEvidenceSnapshot,
    CandidateFactAvailability,
    CandidateProjectionUnavailableReason,
    CandidateRolloutOverlay,
)
from aria_nbv.rollouts.candidate_plotting import candidate_support_plot_models

ROOT = Path(__file__).resolve().parent


def _snapshot(payload: dict[str, Any]) -> CandidateEvidenceSnapshot:
    """Decode one JSON snapshot through the public immutable constructors."""

    rows = []
    for row_payload in payload.pop("rows"):
        row_payload["admission"] = tuple(
            CandidateCriterionSnapshot(**criterion)
            for criterion in row_payload["admission"]
        )
        for name in (
            "world_pose_availability",
            "projection_availability",
            "semantic_lineage_availability",
            "action_availability",
            "selection_availability",
            "proposal_key_availability",
            "proposal_probability_availability",
            "jitter_availability",
            "admission_availability",
            "generation_frame_availability",
            "legacy_family_label_availability",
            "legacy_admission_availability",
            "legacy_pair_lineage_availability",
        ):
            row_payload[name] = CandidateFactAvailability(row_payload[name])
        for name in ("world_pose_unavailable_reason", "projection_unavailable_reason"):
            if row_payload[name] is not None:
                row_payload[name] = CandidateProjectionUnavailableReason(
                    row_payload[name]
                )
        row_payload["legacy_admission_measurements"] = tuple(
            (str(name), float(value))
            for name, value in row_payload["legacy_admission_measurements"]
        )
        for name in ("center_world_m", "center_target_normalized", "gaze_target_unit"):
            if row_payload[name] is not None:
                row_payload[name] = tuple(float(value) for value in row_payload[name])
        rows.append(CandidateEvidenceRow(**row_payload))
    payload["rows"] = tuple(rows)
    payload["overlay"] = CandidateRolloutOverlay(**payload["overlay"])
    for name in (
        "completion_availability",
        "projection_frame_availability",
        "program_hash_availability",
        "request_hash_availability",
        "execution_hash_availability",
    ):
        payload[name] = CandidateFactAvailability(payload[name])
    if payload["projection_unavailable_reason"] is not None:
        payload["projection_unavailable_reason"] = CandidateProjectionUnavailableReason(
            payload["projection_unavailable_reason"]
        )
    if payload["target_target_normalized"] is not None:
        payload["target_target_normalized"] = tuple(
            float(value) for value in payload["target_target_normalized"]
        )
    return CandidateEvidenceSnapshot(**payload)


def main() -> None:
    """Write exact Plotly JSON and portable HTML views for the captured states."""

    bundle = json.loads((ROOT / "snapshots.json").read_text())
    snapshots = tuple(_snapshot(dict(payload)) for payload in bundle["snapshots"])
    models = candidate_support_plot_models(snapshots, show_view_directions=True)
    for model in models:
        (ROOT / f"{model.key}.plotly.json").write_bytes(model.plotly_json)
        figure = model.build_figure()
        figure.write_html(
            ROOT / f"{model.key}.html",
            include_plotlyjs="cdn",
            full_html=True,
            div_id=model.figure.id.replace(":", "-"),
        )
        figure.write_image(ROOT / f"{model.key}.png", width=1600, height=900, scale=1)
    summary = {
        "schema_revision": "candidate-evidence-real-scene-summary-v1",
        "states": len(snapshots),
        "attempted": sum(snapshot.attempted_count for snapshot in snapshots),
        "hard_valid": sum(snapshot.valid_count for snapshot in snapshots),
        "action": sum(snapshot.action_count or 0 for snapshot in snapshots),
        "selected": sum(snapshot.selected_count or 0 for snapshot in snapshots),
        "source_sha256": [snapshot.source_sha256 for snapshot in snapshots],
        "plot_ids": [model.figure.id for model in models],
    }
    (ROOT / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n"
    )


if __name__ == "__main__":
    main()
