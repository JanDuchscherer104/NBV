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
from aria_nbv.rollouts.candidate_benchmark import benchmark_binding_from_reader
from aria_nbv.rollouts.inspection import candidate_audit_rows

matplotlib.rcParams["svg.hashsalt"] = "aria-nbv-candidate-generation-scaleup-pilot-v1"


@dataclass(frozen=True)
class Profile:
    """One frozen evaluator arm and its human-readable label."""

    key: str
    label: str
    run_dir: str
    decision: str
    delta_from_realistic_core: tuple[str, ...]
    metrics_sha256: str
    rollout_manifest_sha256: str
    rollout_store_content_sha256: str


SEED = 20260728
SOURCE_SAMPLES = ("ASE_889_Atek_000008", "ASE_8517_Atek_000000")
EXPECTED_SCENES = ("8517", "889")
SOURCE_MANIFEST_SHA256 = (
    "d6e771d1582394cde9005be3185dc9cfbb875cab5fc004f184922a25dc996f56"
)
WRITER_CONFIG_SHA256 = (
    "2b83170a16d62730562a1f5438d55af0bf9dd79d0f52b776543e429c2a687681"
)
EXPECTED_CANDIDATES_PER_PROFILE = 120

PROFILES = (
    Profile(
        "realistic_core",
        "Current 24/24/12",
        "0000-realistic-core-v3",
        "baseline",
        (),
        "35d89c678316efa47fd9983cc0d8d535760822215efe11d749532bcced441908",
        "178ad0a7abae133a3e5ef6f7fbbd769cd6a2f1529e61bc6567e4d467d2f8dc66",
        "484a5f994ca949374b31d7376928041230e56af4a394939054a63fa86fe76f8d",
    ),
    Profile(
        "forward_target_glance",
        "Target glance",
        "0001-forward-target-glance",
        "discard",
        (
            "forward_local count: 24 -> 18",
            "target_bearing_local count: 24 -> 18",
            "add forward_target_glance count 12: position=forward_local, view=target_point",
        ),
        "287cfcf724f938dab1c57551c5a56fae79e4c9e8d0f84f2bd920e44e8e6b23ac",
        "5b7eae188b7e1006b36660b22583093feeb8798f71199ab0914e7ae8d65bfb0f",
        "4b323972f88ae1425ef7c89eba644db934bb8f0adb82d12e052c01a757840536",
    ),
    Profile(
        "radius_stratified",
        "Near/far strata",
        "0002-radius-stratified",
        "discard",
        (
            "replace target_bearing_local count 24, radius=[0.4, 1.1] m",
            "add target_bearing_near count 12, radius=[0.4, 0.65] m",
            "add target_bearing_far count 12, radius=[0.65, 1.1] m",
        ),
        "97c73fc8c56260a3460b75481f2b00a63e4309bbddb7adf496d4fcf3ee1aff49",
        "950637dcb557ddcac22acd6ff389b989887e965093727a0faefc851463ae8456",
        "f09cc2d9b6c1c976ac091ec8fcdb8703eb101f4238b1af3c996a1f4855069391",
    ),
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


def _require_equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise ValueError(f"{label}: expected {expected!r}, got {actual!r}")


def _require_store_content_hash(reader: Any, expected: str, label: str) -> str:
    """Require the frozen hash of every file in one consumed rollout store."""

    actual = benchmark_binding_from_reader(reader)["store_content_sha256"]
    _require_equal(actual, expected, f"{label} rollout store content hash")
    return actual


def _quantiles(
    rows: list[dict[str, Any]], key: str, *, absolute: bool = False
) -> dict[str, Any]:
    values = [_finite(row[key]) for row in rows]
    finite = np.asarray(
        [value for value in values if value is not None], dtype=np.float64
    )
    result: dict[str, Any] = {
        "count": int(finite.size),
        "missing_count": len(rows) - int(finite.size),
    }
    if not finite.size:
        return result
    if absolute:
        finite = np.abs(finite)
    quantiles = np.quantile(finite, [0.0, 0.05, 0.25, 0.5, 0.75, 0.95, 1.0])
    result.update(
        {
            "min": float(quantiles[0]),
            "q05": float(quantiles[1]),
            "q25": float(quantiles[2]),
            "median": float(quantiles[3]),
            "q75": float(quantiles[4]),
            "q95": float(quantiles[5]),
            "max": float(quantiles[6]),
        }
    )
    return result


def _reason_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        if row["actor_action"]:
            continue
        reason = str(row["invalid_reason"] or "UNSPECIFIED")
        counts[reason] = counts.get(reason, 0) + 1
    return dict(sorted(counts.items()))


def _family_state_diagnostics(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    keys = sorted({(str(row["scene"]), str(row["mixture"])) for row in rows})
    for scene, mixture in keys:
        cell = [
            row for row in rows if row["scene"] == scene and row["mixture"] == mixture
        ]
        diagnostics.append(
            {
                "scene": scene,
                "mixture": mixture,
                "candidate_count": len(cell),
                "actor_valid_count": sum(bool(row["actor_action"]) for row in cell),
                "invalid_reason_counts": _reason_counts(cell),
                "motion_step_length_m": _quantiles(cell, "motion_step_length_m"),
                "motion_abs_height_delta_m": _quantiles(
                    cell, "motion_height_delta_m", absolute=True
                ),
                "motion_backward_step_m": _quantiles(cell, "motion_backward_step_m"),
                "motion_abs_yaw_delta_deg": _quantiles(
                    cell, "motion_yaw_delta_deg", absolute=True
                ),
                "target_root_gain": _quantiles(cell, "target_root_gain"),
                "target_rri": _quantiles(cell, "target_rri"),
                "path_collision_applicable_count": sum(
                    bool(row["path_collision_applicable"]) for row in cell
                ),
                "path_collision_evaluated_count": sum(
                    bool(row["path_collision_evaluated"]) for row in cell
                ),
                "path_collision_count": sum(
                    row["path_collision"] is True for row in cell
                ),
            }
        )
    return diagnostics


def _point(row: dict[str, Any]) -> dict[str, Any]:
    distance = max(float(row["target_distance_m"]), 1e-6)
    return {
        "scene": str(row["scene"]),
        "mixture": str(row["mixture"]),
        "forward_over_target_distance": float(row["decision_relative_z_m"]) / distance,
        "lateral_over_target_distance": float(row["decision_relative_x_m"]) / distance,
        "up_over_target_distance": float(row["decision_relative_y_m"]) / distance,
        "target_forward_over_target_distance": float(row["root_to_target_z_m"])
        / distance,
        "target_lateral_over_target_distance": float(row["root_to_target_x_m"])
        / distance,
        "actor_valid": bool(row["actor_action"]),
        "invalid_reason": row["invalid_reason"],
        "invalid_reason_bitset": int(row["invalid_reason_bitset"]),
        "selected": bool(row["selected"]),
        "q_train": bool(row["q_train"]),
        "target_in_fov": row["target_in_fov"],
        "target_view_angle_deg": _finite(row["target_view_angle_deg"]),
        "target_root_gain": _finite(row["target_root_gain"]),
        "target_rri": _finite(row["target_rri"]),
        "scene_rri": _finite(row["scene_rri"]),
        "motion_step_length_m": _finite(row["motion_step_length_m"]),
        "motion_height_delta_m": _finite(row["motion_height_delta_m"]),
        "motion_backward_step_m": _finite(row["motion_backward_step_m"]),
        "motion_yaw_delta_deg": _finite(row["motion_yaw_delta_deg"]),
        "free_space_margin_m": _finite(row["free_space_margin_m"]),
        "path_collision_applicable": bool(row["path_collision_applicable"]),
        "path_collision_evaluated": bool(row["path_collision_evaluated"]),
        "path_collision": row["path_collision"],
        "path_min_clearance_m": _finite(row["path_min_clearance_m"]),
        "view_jitter_yaw_deg": _finite(row["view_jitter_yaw_deg"]),
        "view_jitter_pitch_deg": _finite(row["view_jitter_pitch_deg"]),
        "view_jitter_is_bounded": row["view_jitter_is_bounded"],
    }


def _load_evidence(measurements: Path) -> dict[str, Any]:
    profiles: list[dict[str, Any]] = []
    for profile in PROFILES:
        run = measurements / "runs" / profile.run_dir
        metrics_path = run / "metrics.json"
        rollout_manifest_path = run / "rollouts.zarr" / "manifest.json"
        artifact_manifest = json.loads(
            (run / "artifact-manifest.json").read_text(encoding="utf-8")
        )
        _require_equal(
            artifact_manifest["profile"], profile.key, f"{profile.key} profile"
        )
        _require_equal(
            artifact_manifest["samples"],
            len(SOURCE_SAMPLES),
            f"{profile.key} sample count",
        )
        _require_equal(artifact_manifest["seed"], SEED, f"{profile.key} seed")
        _require_equal(
            artifact_manifest["source_manifest_sha256"],
            SOURCE_MANIFEST_SHA256,
            f"{profile.key} source manifest",
        )
        _require_equal(
            artifact_manifest["writer_config_sha256"],
            WRITER_CONFIG_SHA256,
            f"{profile.key} writer config",
        )
        _require_equal(
            _sha256(metrics_path), profile.metrics_sha256, f"{profile.key} metrics hash"
        )
        _require_equal(
            _sha256(rollout_manifest_path),
            profile.rollout_manifest_sha256,
            f"{profile.key} rollout manifest hash",
        )
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))["metrics"]
        reader = RolloutZarrStoreReader(run / "rollouts.zarr")
        rollout_store_content_sha256 = _require_store_content_hash(
            reader, profile.rollout_store_content_sha256, profile.key
        )
        rows = candidate_audit_rows(reader)
        _require_equal(
            len(rows), EXPECTED_CANDIDATES_PER_PROFILE, f"{profile.key} audit rows"
        )
        _require_equal(
            metrics["candidate_count"],
            EXPECTED_CANDIDATES_PER_PROFILE,
            f"{profile.key} metrics rows",
        )
        _require_equal(
            metrics["state_count"], len(SOURCE_SAMPLES), f"{profile.key} metric states"
        )
        _require_equal(
            tuple(sorted({row["scene"] for row in rows})),
            EXPECTED_SCENES,
            f"{profile.key} scenes",
        )
        required_geometry = (
            "decision_relative_x_m",
            "decision_relative_y_m",
            "decision_relative_z_m",
            "root_to_target_x_m",
            "root_to_target_z_m",
            "target_distance_m",
        )
        missing_geometry = [
            {"scene": row["scene"], "candidate_row_id": row["candidate_row_id"]}
            for row in rows
            if any(row[name] is None for name in required_geometry)
        ]
        if missing_geometry:
            raise ValueError(
                f"{profile.key}: {len(missing_geometry)} rows lack required plot geometry"
            )
        points = [_point(row) for row in rows]
        actor_valid_rows = [row for row in rows if row["actor_action"]]
        profiles.append(
            {
                "key": profile.key,
                "label": profile.label,
                "decision": profile.decision,
                "delta_from_realistic_core": list(profile.delta_from_realistic_core),
                "metrics": metrics,
                "input_validation": {
                    "audit_row_count": len(rows),
                    "expected_audit_row_count": EXPECTED_CANDIDATES_PER_PROFILE,
                    "scene_count": len({row["scene"] for row in rows}),
                    "expected_scene_count": len(SOURCE_SAMPLES),
                    "dropped_plot_row_count": 0,
                    "metrics_sha256": profile.metrics_sha256,
                    "rollout_manifest_sha256": profile.rollout_manifest_sha256,
                    "rollout_store_content_sha256": rollout_store_content_sha256,
                },
                "diagnostics": {
                    "invalid_reason_counts": _reason_counts(rows),
                    "motion_step_length_m": _quantiles(rows, "motion_step_length_m"),
                    "motion_abs_height_delta_m": _quantiles(
                        rows, "motion_height_delta_m", absolute=True
                    ),
                    "motion_backward_step_m": _quantiles(
                        rows, "motion_backward_step_m"
                    ),
                    "motion_abs_yaw_delta_deg": _quantiles(
                        rows, "motion_yaw_delta_deg", absolute=True
                    ),
                    "actor_valid_motion_step_length_m": _quantiles(
                        actor_valid_rows, "motion_step_length_m"
                    ),
                    "actor_valid_motion_abs_height_delta_m": _quantiles(
                        actor_valid_rows, "motion_height_delta_m", absolute=True
                    ),
                    "actor_valid_motion_backward_step_m": _quantiles(
                        actor_valid_rows, "motion_backward_step_m"
                    ),
                    "actor_valid_motion_abs_yaw_delta_deg": _quantiles(
                        actor_valid_rows, "motion_yaw_delta_deg", absolute=True
                    ),
                    "target_root_gain": _quantiles(rows, "target_root_gain"),
                    "target_rri": _quantiles(rows, "target_rri"),
                    "path_collision_applicable_count": sum(
                        bool(row["path_collision_applicable"]) for row in rows
                    ),
                    "path_collision_evaluated_count": sum(
                        bool(row["path_collision_evaluated"]) for row in rows
                    ),
                    "path_collision_count": sum(
                        row["path_collision"] is True for row in rows
                    ),
                },
                "family_state_diagnostics": _family_state_diagnostics(rows),
                "points": points,
                "rollout_manifest_sha256": profile.rollout_manifest_sha256,
                "rollout_store_content_sha256": rollout_store_content_sha256,
            }
        )
    return {
        "schema_id": "aria-nbv-candidate-generation-scaleup-pilot-v1",
        "evidence_class": "exploratory_train_only_two_scene_pilot",
        "implementation_revision": "b8df705545abfa3ebd68d0ade197d9bfc0504286",
        "seed": SEED,
        "device": "NVIDIA GeForce RTX 3080 Ti",
        "source_samples": list(SOURCE_SAMPLES),
        "source_manifest_sha256": SOURCE_MANIFEST_SHA256,
        "writer_config_sha256": WRITER_CONFIG_SHA256,
        "evaluator_fingerprint": "sha256:e2bfc9c1636b6e2882b0c534605c460998b60378074af3f75c572a6f1538e89a",
        "rerender_requirement": "local frozen measurement bundle; raw rollout stores are not published in this PR",
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
    figure.suptitle(
        "Candidate-generation profile scorecard", fontsize=17, fontweight="bold"
    )

    validity = [
        100.0 * profile["metrics"]["actor_valid_fraction"] for profile in profiles
    ]
    framing = [
        100.0 * profile["metrics"]["target_in_fov_fraction"] for profile in profiles
    ]
    axes[0, 0].bar(x - 0.18, validity, 0.36, label="hard-valid", color="#4E79A7")
    axes[0, 0].bar(x + 0.18, framing, 0.36, label="target in FOV", color="#59A14F")
    axes[0, 0].set_ylabel("candidate rows / %")
    axes[0, 0].set_ylim(0, 100)
    axes[0, 0].set_title("Validity and actor-visible framing")
    axes[0, 0].legend(frameon=False, loc="upper right")

    worst = [profile["metrics"]["worst_state_valid_count"] for profile in profiles]
    collapsed = [
        profile["metrics"]["family_zero_valid_state_count"] for profile in profiles
    ]
    axes[0, 1].bar(x - 0.18, worst, 0.36, label="worst-state valid", color="#76B7B2")
    axes[0, 1].bar(
        x + 0.18, collapsed, 0.36, label="zero-valid family-states", color="#E15759"
    )
    axes[0, 1].axhline(
        15, color="#111827", linestyle="--", linewidth=1, label="root floor = 15"
    )
    axes[0, 1].set_ylabel("count")
    axes[0, 1].set_title("Aggregate support can hide family collapse")
    axes[0, 1].legend(frameon=False, loc="upper right")

    gain = [
        profile["metrics"]["mean_state_best_target_root_gain"] for profile in profiles
    ]
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
        axes[1, 1].text(
            index,
            throughput[index] + 0.015,
            f"{memory_gib:.2f} GiB",
            ha="center",
            fontsize=9,
        )

    for axis in axes.flat:
        _style_axis(axis)
        axis.set_xticks(x, labels, rotation=10, ha="right")
    figure.savefig(
        output,
        format="svg",
        metadata={"Date": None, "Creator": "ARIA-NBV evidence renderer"},
    )
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

    figure, axes = plt.subplots(
        1, 3, figsize=(15.5, 5.4), sharex=True, sharey=True, constrained_layout=True
    )
    figure.suptitle(
        "Candidate centres in proposal frames", fontsize=17, fontweight="bold"
    )
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
            points = [
                point for point in profile["points"] if point["mixture"] == mixture
            ]
            color = COLORS.get(mixture, "#9C755F")
            invalid = [point for point in points if not point["actor_valid"]]
            valid = [
                point
                for point in points
                if point["actor_valid"] and not point["selected"]
            ]
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
        axis.scatter(
            [0],
            [0],
            marker="+",
            s=95,
            linewidths=1.8,
            color="#111827",
            label="reference pose",
        )
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
        axis.set_title(
            f"{profile['label']}\n{profile['decision'].upper()}", fontsize=12
        )
        axis.set_xlim(*x_limits)
        axis.set_ylim(*y_limits)
        axis.set_aspect("equal", adjustable="box")
        axis.set_xlabel("proposal forward / target distance")
        axis.grid(color="#E5E7EB", linewidth=0.7, alpha=0.9)
        axis.legend(frameon=False, fontsize=7.5, loc="best")
    axes[0].set_ylabel("proposal lateral / target distance")
    figure.savefig(
        output,
        format="svg",
        metadata={"Date": None, "Creator": "ARIA-NBV evidence renderer"},
    )
    plt.close(figure)
    _normalize_svg(output)


def _finite_point_values(
    profile: dict[str, Any],
    key: str,
    *,
    absolute: bool = False,
    actor_valid_only: bool = False,
) -> np.ndarray:
    values = [
        point[key]
        for point in profile["points"]
        if point[key] is not None and (not actor_valid_only or point["actor_valid"])
    ]
    array = np.asarray(values, dtype=np.float64)
    return np.abs(array) if absolute else array


def _render_motion_signal(evidence: dict[str, Any], output: Path) -> None:
    profiles = evidence["profiles"]
    labels = [profile["label"] for profile in profiles]
    figure, axes = plt.subplots(2, 2, figsize=(12.2, 7.3), constrained_layout=True)
    figure.suptitle(
        "Motion-envelope and oracle-signal distributions",
        fontsize=17,
        fontweight="bold",
    )
    panels = (
        (
            "motion_step_length_m",
            False,
            True,
            "Step length (m)",
            "Valid-candidate displacement",
        ),
        (
            "motion_height_delta_m",
            True,
            True,
            "Absolute height delta (m)",
            "Valid vertical motion",
        ),
        (
            "motion_yaw_delta_deg",
            True,
            True,
            "Absolute yaw delta (deg)",
            "Valid view-direction change",
        ),
        (
            "target_root_gain",
            False,
            False,
            "Target-root gain",
            "Oracle training-signal support",
        ),
    )
    for axis, (key, absolute, actor_valid_only, ylabel, title) in zip(
        axes.flat, panels, strict=True
    ):
        values = [
            _finite_point_values(
                profile,
                key,
                absolute=absolute,
                actor_valid_only=actor_valid_only,
            )
            for profile in profiles
        ]
        axis.boxplot(
            values, showfliers=True, flierprops={"markersize": 2.5, "alpha": 0.35}
        )
        axis.set_xticks(np.arange(1, len(labels) + 1), labels, rotation=10, ha="right")
        axis.set_ylabel(ylabel)
        axis.set_title(title)
        _style_axis(axis)
    figure.savefig(
        output,
        format="svg",
        metadata={"Date": None, "Creator": "ARIA-NBV evidence renderer"},
    )
    plt.close(figure)
    _normalize_svg(output)


def _render_invalid_reasons(evidence: dict[str, Any], output: Path) -> None:
    profiles = evidence["profiles"]
    reasons = sorted(
        {
            reason
            for profile in profiles
            for reason in profile["diagnostics"]["invalid_reason_counts"]
        }
    )
    figure, axes = plt.subplots(
        1, len(profiles), figsize=(15.5, 5.5), constrained_layout=True
    )
    figure.suptitle(
        "Hard-invalid reasons by candidate family", fontsize=17, fontweight="bold"
    )
    maximum = 1
    matrices: list[tuple[list[str], np.ndarray]] = []
    for profile in profiles:
        mixtures = sorted({point["mixture"] for point in profile["points"]})
        matrix = np.zeros((len(mixtures), len(reasons)), dtype=np.int64)
        for family_state in profile["family_state_diagnostics"]:
            row_index = mixtures.index(family_state["mixture"])
            for reason, count in family_state["invalid_reason_counts"].items():
                matrix[row_index, reasons.index(reason)] += count
        maximum = max(maximum, int(matrix.max(initial=0)))
        matrices.append((mixtures, matrix))
    for axis, profile, (mixtures, matrix) in zip(axes, profiles, matrices, strict=True):
        axis.imshow(matrix, cmap="Reds", vmin=0, vmax=maximum, aspect="auto")
        for row_index in range(matrix.shape[0]):
            for column_index in range(matrix.shape[1]):
                count = int(matrix[row_index, column_index])
                axis.text(
                    column_index,
                    row_index,
                    str(count),
                    ha="center",
                    va="center",
                    color="white" if count > maximum / 2 else "#111827",
                    fontsize=9,
                )
        axis.set_xticks(np.arange(len(reasons)), reasons, rotation=35, ha="right")
        axis.set_yticks(np.arange(len(mixtures)), mixtures)
        axis.set_title(profile["label"])
    axes[0].set_ylabel("candidate family")
    figure.savefig(
        output,
        format="svg",
        metadata={"Date": None, "Creator": "ARIA-NBV evidence renderer"},
    )
    plt.close(figure)
    _normalize_svg(output)


def _write_artifact_manifest(output: Path) -> None:
    filenames = (
        "evidence.json",
        "profile-summary.svg",
        "candidate-support.svg",
        "motion-signal.svg",
        "invalid-reasons.svg",
    )
    manifest = {
        "schema_id": "aria-nbv-candidate-generation-scaleup-pilot-artifacts-v1",
        "files": {filename: _sha256(output / filename) for filename in filenames},
    }
    (output / "artifact-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


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
    _render_motion_signal(evidence, output / "motion-signal.svg")
    _render_invalid_reasons(evidence, output / "invalid-reasons.svg")
    _write_artifact_manifest(output)


if __name__ == "__main__":
    main()
