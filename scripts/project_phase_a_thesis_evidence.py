#!/usr/bin/env python3
"""Project authenticated Phase-A evidence into deterministic thesis artifacts."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path
from typing import Any

from aria_nbv.rollouts.candidate_benchmark import (
    CandidateFamilyPhaseAExpectation,
    CandidateSupportFailure,
    read_candidate_family_phase_a,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs/contents/evidence/candidate_family_phase_a_wp02.json"
PROJECTION = (
    ROOT / "docs/contents/evidence/candidate_family_phase_a_wp02_projection.json"
)
FIGURE = ROOT / "docs/contents/evidence/candidate_family_phase_a_wp02_audit_heatmap.svg"
COMMAND = "make phase-a-thesis-projection"
SCHEMA_ID = "aria-nbv-phase-a-thesis-projection-v2"
EXPECTED_SOURCE = CandidateFamilyPhaseAExpectation(
    source_manifest_sha256="d6e771d1582394cde9005be3185dc9cfbb875cab5fc004f184922a25dc996f56",
    source_store_manifest_hash="605453ba11869e40",
    source_cache_version="10",
    split_manifest_hash="4780c7cde1b811bf",
    source_store_dir="vin_offline_rollout_campaign100_v10_rebuilt",
    writer_config_sha256="4ae05a1e4066756a47f9ba00d914b8f4337321ae8dcd161a62228d02f71d0587",
    generation_revision_hash="a2ae86b7463930c9",
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json(payload: dict[str, Any]) -> bytes:
    return (
        json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
        + b"\n"
    )


def _load_evidence() -> tuple[Any, dict[str, Any], str]:
    source_bytes = SOURCE.read_bytes()
    payload = json.loads(source_bytes)
    return (
        read_candidate_family_phase_a(SOURCE, expected=EXPECTED_SOURCE),
        payload,
        _sha256(source_bytes),
    )


def _audit_identities(preflight: Any) -> tuple[tuple[str, str], ...]:
    identities = tuple(
        dict.fromkeys((scene, state) for scene, state, _ in preflight.cells)
    )
    selected: list[tuple[str, str]] = []
    for scenes in preflight.audit_strata.values():
        identity = next((item for item in identities if item[0] in scenes), None)
        if identity is not None:
            selected.append(identity)
    return tuple(dict.fromkeys(selected))


def build_projection() -> dict[str, Any]:
    evidence, raw, source_sha256 = _load_evidence()
    preflight = evidence.preflight
    applicable_cells = tuple(
        cell for _, _, cell in preflight.cells if cell.applicable is True
    )
    blockers = tuple(preflight.blockers)
    identities = _audit_identities(preflight)
    script_sha256 = _sha256(Path(__file__).read_bytes())
    config = raw["preflight"]["config"]
    lineage = tuple(json.loads(record["lineage"]) for record in raw["records"])
    provenances = tuple(json.loads(record["provenance"]) for record in raw["records"])
    geometry_revisions = sorted({row["geometry_revision"] for row in lineage})
    family_identities = sorted({row["family_identity"] for row in lineage})
    target_sources = sorted({row["target_source"] for row in provenances})

    payload: dict[str, Any] = {
        "schema_id": SCHEMA_ID,
        "source": {
            "path": str(SOURCE.relative_to(ROOT)),
            "file_sha256": source_sha256,
            "artifact_sha256": raw["artifact_sha256"],
            "source_manifest_sha256": evidence.source_manifest_sha256,
            "source_store_manifest_hash": evidence.source_store_manifest_hash,
            "split_manifest_hash": evidence.split_manifest_hash,
        },
        "generation": {
            "command": COMMAND,
            "projector_path": str(Path(__file__).relative_to(ROOT)),
            "projector_sha256": script_sha256,
            "implementation_revision": evidence.implementation_revision,
            "generation_revision_hash": evidence.generation_revision["revision_hash"],
            "writer_config_sha256": evidence.writer_config_sha256,
        },
        "counts": {
            "source_rows": evidence.source_row_count,
            "scenes": evidence.scene_count,
            "target_states": evidence.target_state_count,
            "attempted_candidates": sum(cell.attempted for cell in applicable_cells),
            "compact_valid_candidates": sum(cell.selected for cell in applicable_cells),
            "collapsed_state_family_cells": sum(
                blocker.code is CandidateSupportFailure.FAMILY_COLLAPSE
                for blocker in blockers
            ),
            "states_below_target_family_floor": len(
                {
                    blocker.state_key
                    for blocker in blockers
                    if blocker.code is CandidateSupportFailure.LOW_TARGET_FAMILY_SUPPORT
                }
            ),
            "states_below_root_support": len(
                {
                    blocker.state_key
                    for blocker in blockers
                    if blocker.code is CandidateSupportFailure.LOW_ROOT_SUPPORT
                }
            ),
            "excluded_source_rows": len(evidence.excluded_source_rows),
        },
        "flat_gain": {
            "available": preflight.flat_gain.available,
            "label_denominator": preflight.flat_gain.denominator,
            "eligible_state_denominator": preflight.flat_gain.eligible_state_denominator,
            "reason": preflight.flat_gain.reason,
        },
        "gate": {"passed": preflight.go, "blocker_count": len(blockers)},
        "experiment_contract": {
            "candidate_width": config["query_width"],
            "candidate_families": config["configured_families"],
            "family_floor_revision": config["family_floor_revision"],
            "known_applicability_required": config["require_known_applicability"],
            "candidate_identity_fields": ["scene_key", "state_key", "candidate_id"],
            "family_attribution_rule": family_identities,
            "coordinate_revisions": geometry_revisions,
            "target_sources": target_sources,
            "proposal_randomness": "bound by writer-config and generation-revision hashes",
            "selection_randomness": "not applicable: Phase-A stops before policy selection",
            "reward_execution": "not applicable: no rendering, reward labels, or executed transition",
            "action_support": "final_valid_action_shell with attempted, valid, and selected rows retained",
            "label_support": "absent by design; target-root gain and diagnostic RRI denominators are zero",
            "gaze_variant_identity": "historical v4 bundle retains candidate rows but no non-null gaze-jitter identity",
        },
        "audit_identities": [
            {"scene_key": scene, "state_key": state} for scene, state in identities
        ],
    }
    payload["projection_sha256"] = _sha256(_canonical_json(payload))
    return payload


def _short_state(state: str) -> str:
    parts = {
        item.split("=", 1)[0]: item.split("=", 1)[1]
        for item in state.split(":")
        if "=" in item
    }
    return f"sem={parts.get('sem', '?')} · inst={parts.get('inst', '?')} · idx={parts.get('idx', '?')}"


def build_svg(projection: dict[str, Any]) -> bytes:
    evidence, _, _ = _load_evidence()
    identities = tuple(
        (row["scene_key"], row["state_key"]) for row in projection["audit_identities"]
    )
    cell_by_key = {
        (scene, state, cell.family): cell
        for scene, state, cell in evidence.preflight.cells
    }
    families = tuple(sorted({cell.family for _, _, cell in evidence.preflight.cells}))
    width, height = 1500, 720
    left, top, cell_w, cell_h = 430, 128, 275, 49

    def color(value: float) -> str:
        start, end = (239, 246, 255), (8, 81, 156)
        rgb = tuple(round(a + (b - a) * value) for a, b in zip(start, end, strict=True))
        return f"rgb({rgb[0]},{rgb[1]},{rgb[2]})"

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<style>text{font-family:Inter,Arial,sans-serif;fill:#172033}.title{font-size:25px;font-weight:650}.meta{font-size:13px;fill:#526070}.axis{font-size:15px;font-weight:600}.row{font-size:13px}.cell{font-size:14px;font-weight:650}</style>",
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<text class="title" x="40" y="42">Phase-A candidate-family support audit</text>',
        '<text class="meta" x="40" y="68">One deterministic factual state per persisted audit stratum; cells report compact-valid / attempted.</text>',
        f'<text class="meta" x="40" y="91">Evidence {html.escape(projection["source"]["artifact_sha256"][:16])} · projection {html.escape(projection["projection_sha256"][:16])}</text>',
    ]
    for column, family in enumerate(families):
        x = left + column * cell_w + cell_w / 2
        out.append(
            f'<text class="axis" x="{x}" y="114" text-anchor="middle">{html.escape(family)}</text>'
        )
    for row_index, (scene, state) in enumerate(identities):
        y = top + row_index * cell_h
        out.append(
            f'<text class="row" x="40" y="{y + 19}">{html.escape(scene)} · {html.escape(_short_state(state))}</text>'
        )
        for column, family in enumerate(families):
            cell = cell_by_key[(scene, state, family)]
            ratio = 0.0 if cell.attempted == 0 else cell.selected / cell.attempted
            x = left + column * cell_w
            out.append(
                f'<rect x="{x}" y="{y}" width="{cell_w - 8}" height="{cell_h - 7}" rx="4" fill="{color(ratio)}"/>'
            )
            text_color = "#ffffff" if ratio >= 0.52 else "#172033"
            label = (
                "N/A"
                if cell.applicable is False
                else "?"
                if cell.applicable is None
                else f"{cell.selected}/{cell.attempted} ({ratio:.0%})"
            )
            out.append(
                f'<text class="cell" x="{x + (cell_w - 8) / 2}" y="{y + 26}" text-anchor="middle" style="fill:{text_color}">{html.escape(label)}</text>'
            )
    out.extend(
        [
            f'<text class="meta" x="40" y="{height - 55}">All 100 factual states, exact identities, exclusions, and gate predicates remain in the authenticated JSON bundle.</text>',
            f'<text class="meta" x="40" y="{height - 32}">Regenerate and verify with: {html.escape(COMMAND)}</text>',
            "</svg>",
        ]
    )
    return ("\n".join(out) + "\n").encode()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="fail if checked-in projections are stale"
    )
    args = parser.parse_args()
    projection = build_projection()
    projection_bytes = _canonical_json(projection)
    figure_bytes = build_svg(projection)
    expected = ((PROJECTION, projection_bytes), (FIGURE, figure_bytes))
    if args.check:
        stale = [
            str(path.relative_to(ROOT))
            for path, data in expected
            if not path.exists() or path.read_bytes() != data
        ]
        if stale:
            parser.error("stale Phase-A thesis projection: " + ", ".join(stale))
        return 0
    for path, data in expected:
        path.write_bytes(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
