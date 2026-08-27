#!/usr/bin/env python3
"""Render the public two-scene candidate-generation pilot evidence bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

from aria_nbv.rollouts import RolloutZarrStoreReader
from aria_nbv.rollouts.inspection import candidate_audit_rows

matplotlib.rcParams["svg.hashsalt"] = "aria-nbv-candidate-generation-scaleup-pilot-v1"


@dataclass(frozen=True)
class Profile:
    """One frozen evaluator arm and its human-readable label."""

    key: str
    label: str
    run_dir: str
    decision: str


PROFILES = (
    Profile("realistic_core", "Current 24/24/12", "0000-realistic-core-v3", "baseline"),
    Profile("forward_target_glance", "Target glance", "0001-forward-target-glance", "discard"),
    Profile("radius_stratified", "Near/far strata", "0002-radius-stratified", "discard"),
)

COLORS = {
    "forward_local": "#4E79A7",
    "forward_target_glance": "#F28E2B",
    "lateral_target_bypass": "#E15759",
    "target_bearing_local": "#59A14F",
    "target_bearing_near": "#76B7B2",
    "target_bearing_far": "#B07AA1",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _finite(value: Any) -> float | None:
    if value is None:
        return None
    number = float(value)
    return number if np.isfinite(number) else None


def _point(row: dict[str, Any]) -> dict[str, Any]:
    distance = max(float(row["target_distance_m"]), 1e-6)
    return {
        "scene": str(row["scene"]),
        "mixture": str(row["mixture"]),
        "forward_over_target_distance": float(row["decision_relative_z_m"]) / distance,
        "lateral_over_target_distance": float(row["decision_relative_x_m"]) / distance,
        "up_over_target_distance": float(row["decision_relative_y_m"]) / distance,
        "target_forward_over_target_distance": float(row["root_to_target_z_m"]) / distance,
        "target_lateral_over_target_distance": float(row["root_to_target_x_m"]) / distance,
        "actor_valid": bool(row["actor_action"]),
        "selected": bool(row["selected"]),
        "target_in_fov": row["target_in_fov"],
        "target_view_angle_deg": _finite(row["target_view_angle_deg"]),
        "target_root_gain": _finite(row["target_root_gain"]),
        "view_jitter_yaw_deg": _finite(row["view_jitter_yaw_deg"]),
        "view_jitter_pitch_deg": _finite(row["view_jitter_pitch_deg"]),
        "view_jitter_is_bounded": row["view_jitter_is_bounded"],
    }


def _load_evidence(measurements: Path) -> dict[str, Any]:
    profiles: list[dict[str, Any]] = []
    for profile in PROFILES:
        run = measurements / "runs" / profile.run_dir
        metrics = json.loads((run / "metrics.json").read_text(encoding="utf-8"))["metrics"]
        rows = candidate_audit_rows(RolloutZarrStoreReader(run / "rollouts.zarr"))
        points = [
            _point(row)
            for row in rows
            if all(
                row[name] is not None
                for name in (
                    "decision_relative_x_m",
                    "decision_relative_y_m",
                    "decision_relative_z_m",
                    "root_to_target_x_m",
                    "root_to_target_z_m",
                    "target_distance_m",
                )
            )
        ]
        profiles.append(
            {
                "key": profile.key,
                "label": profile.label,
                "decision": profile.decision,
                "metrics": metrics,
                "points": points,
                "rollout_manifest_sha256": _sha256(run / "rollouts.zarr" / "manifest.json"),
            }
        )
    return {
        "schema_id": "aria-nbv-candidate-generation-scaleup-pilot-v1",
        "evidence_class": "exploratory_train_only_two_scene_pilot",
        "implementation_revision": "b8df705545abfa3ebd68d0ade197d9bfc0504286",
        "seed": 20260728,
        "device": "NVIDIA GeForce RTX 3080 Ti",
        "source_samples": ["ASE_889_Atek_000008", "ASE_8517_Atek_000000"],
        "source_manifest_sha256": "d6e771d1582394cde9005be3185dc9cfbb875cab5fc004f184922a25dc996f56",
        "writer_config_sha256": "2b83170a16d62730562a1f5438d55af0bf9dd79d0f52b776543e429c2a687681",
        "evaluator_fingerprint": "sha256:e2bfc9c1636b6e2882b0c534605c460998b60378074af3f75c572a6f1538e89a",
        "profiles": profiles,
    }


def _style_axis(axis: plt.Axes) -> None:
    axis.spines[["top", "right"]].set_visible(False)
    axis.grid(axis="y", color="#D9DEE7", linewidth=0.7, alpha=0.8)
    axis.set_axisbelow(True)


def _normalize_svg(path: Path) -> None:
    """Remove renderer-only trailing spaces while preserving SVG semantics."""
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join(line.rstrip() for line in lines) + "\n", encoding="utf-8")


def _render_summary(evidence: dict[str, Any], output: Path) -> None:
    profiles = evidence["profiles"]
    labels = [profile["label"] for profile in profiles]
    x = np.arange(len(profiles))
    figure, axes = plt.subplots(2, 2, figsize=(12.2, 7.3), constrained_layout=True)
    figure.suptitle("Candidate-generation profile scorecard", fontsize=17, fontweight="bold")

    validity = [100.0 * profile["metrics"]["actor_valid_fraction"] for profile in profiles]
    framing = [100.0 * profile["metrics"]["target_in_fov_fraction"] for profile in profiles]
    axes[0, 0].bar(x - 0.18, validity, 0.36, label="hard-valid", color="#4E79A7")
    axes[0, 0].bar(x + 0.18, framing, 0.36, label="target in FOV", color="#59A14F")
    axes[0, 0].set_ylabel("candidate rows / %")
    axes[0, 0].set_ylim(0, 100)
    axes[0, 0].set_title("Validity and actor-visible framing")
    axes[0, 0].legend(frameon=False, loc="upper right")

    worst = [profile["metrics"]["worst_state_valid_count"] for profile in profiles]
    collapsed = [profile["metrics"]["family_zero_valid_state_count"] for profile in profiles]
    axes[0, 1].bar(x - 0.18, worst, 0.36, label="worst-state valid", color="#76B7B2")
    axes[0, 1].bar(x + 0.18, collapsed, 0.36, label="zero-valid family-states", color="#E15759")
    axes[0, 1].axhline(15, color="#111827", linestyle="--", linewidth=1, label="root floor = 15")
    axes[0, 1].set_ylabel("count")
    axes[0, 1].set_title("Aggregate support can hide family collapse")
    axes[0, 1].legend(frameon=False, loc="upper right")

    gain = [profile["metrics"]["mean_state_best_target_root_gain"] for profile in profiles]
    regret = [profile["metrics"]["mean_selected_regret"] for profile in profiles]
    axes[1, 0].bar(x - 0.18, gain, 0.36, label="best target-root gain", color="#B07AA1")
    axes[1, 0].bar(x + 0.18, regret, 0.36, label="selected regret", color="#F28E2B")
    axes[1, 0].set_ylabel("root-normalized gain")
    axes[1, 0].set_title("Measured training signal")
    axes[1, 0].legend(frameon=False, loc="upper right")

    throughput = [profile["metrics"]["valid_candidates_per_s"] for profile in profiles]
    axes[1, 1].bar(x, throughput, 0.56, color=["#4E79A7", "#BAB0AC", "#BAB0AC"])
    axes[1, 1].set_ylabel("hard-valid candidates / s")
    axes[1, 1].set_title("End-to-end GPU throughput (cold-start sensitive)")
    for index, profile in enumerate(profiles):
        memory_gib = profile["metrics"]["peak_memory_mb"] / 1024.0
        axes[1, 1].text(index, throughput[index] + 0.015, f"{memory_gib:.2f} GiB", ha="center", fontsize=9)

    for axis in axes.flat:
        _style_axis(axis)
        axis.set_xticks(x, labels, rotation=10, ha="right")
    figure.savefig(output, format="svg", metadata={"Date": None, "Creator": "ARIA-NBV evidence renderer"})
    plt.close(figure)
    _normalize_svg(output)


def _render_support(evidence: dict[str, Any], output: Path) -> None:
    profiles = evidence["profiles"]
    all_points = [point for profile in profiles for point in profile["points"]]
    x_values = [point["forward_over_target_distance"] for point in all_points]
    y_values = [point["lateral_over_target_distance"] for point in all_points]
    x_pad = 0.08 * max(1.0, max(x_values) - min(x_values))
    y_pad = 0.08 * max(1.0, max(y_values) - min(y_values))
    x_limits = (min(x_values) - x_pad, max(x_values) + x_pad)
    y_limits = (min(y_values) - y_pad, max(y_values) + y_pad)

    figure, axes = plt.subplots(1, 3, figsize=(15.5, 5.4), sharex=True, sharey=True, constrained_layout=True)
    figure.suptitle("Candidate centres in proposal frames", fontsize=17, fontweight="bold")
    figure.text(
        0.5,
        0.925,
        "Coordinates are normalized by root-to-target distance; crosses are hard-invalid, stars are selected",
        ha="center",
        color="#6B7280",
        fontsize=10,
    )
    for axis, profile in zip(axes, profiles, strict=True):
        mixtures = sorted({point["mixture"] for point in profile["points"]})
        for mixture in mixtures:
            points = [point for point in profile["points"] if point["mixture"] == mixture]
            color = COLORS.get(mixture, "#9C755F")
            invalid = [point for point in points if not point["actor_valid"]]
            valid = [point for point in points if point["actor_valid"] and not point["selected"]]
            selected = [point for point in points if point["selected"]]
            if invalid:
                axis.scatter(
                    [point["forward_over_target_distance"] for point in invalid],
                    [point["lateral_over_target_distance"] for point in invalid],
                    marker="x",
                    s=18,
                    linewidths=0.8,
                    color=color,
                    alpha=0.25,
                )
            if valid:
                axis.scatter(
                    [point["forward_over_target_distance"] for point in valid],
                    [point["lateral_over_target_distance"] for point in valid],
                    marker="o",
                    s=20,
                    color=color,
                    alpha=0.72,
                    edgecolors="none",
                    label=mixture,
                )
            if selected:
                axis.scatter(
                    [point["forward_over_target_distance"] for point in selected],
                    [point["lateral_over_target_distance"] for point in selected],
                    marker="*",
                    s=135,
                    color=color,
                    edgecolors="#111827",
                    linewidths=0.8,
                    zorder=5,
                )
        targets: dict[str, tuple[float, float]] = {}
        for point in profile["points"]:
            targets.setdefault(
                point["scene"],
                (
                    point["target_forward_over_target_distance"],
                    point["target_lateral_over_target_distance"],
                ),
            )
        axis.scatter([0], [0], marker="+", s=95, linewidths=1.8, color="#111827", label="reference pose")
        axis.scatter(
            [target[0] for target in targets.values()],
            [target[1] for target in targets.values()],
            marker="D",
            s=48,
            color="#F2C80F",
            edgecolors="#111827",
            linewidths=0.6,
            label="observed target centre",
        )
        axis.set_title(f"{profile['label']}\n{profile['decision'].upper()}", fontsize=12)
        axis.set_xlim(*x_limits)
        axis.set_ylim(*y_limits)
        axis.set_aspect("equal", adjustable="box")
        axis.set_xlabel("proposal forward / target distance")
        axis.grid(color="#E5E7EB", linewidth=0.7, alpha=0.9)
        axis.legend(frameon=False, fontsize=7.5, loc="best")
    axes[0].set_ylabel("proposal lateral / target distance")
    figure.savefig(output, format="svg", metadata={"Date": None, "Creator": "ARIA-NBV evidence renderer"})
    plt.close(figure)
    _normalize_svg(output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--measurements-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    output = args.output_dir.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    evidence = _load_evidence(args.measurements_root.expanduser().resolve())
    (output / "evidence.json").write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _render_summary(evidence, output / "profile-summary.svg")
    _render_support(evidence, output / "candidate-support.svg")


if __name__ == "__main__":
    main()
