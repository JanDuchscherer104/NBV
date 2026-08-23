"""Bounded operator UI for the CUDA rollout campaign CLI."""

from __future__ import annotations

import json
import math
import re
import shlex
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st

from aria_nbv.oracle.pipelines.admission_evidence import read_campaign_admission_evidence
from aria_nbv.oracle.pipelines.campaign import CudaRolloutCampaignConfig
from aria_nbv.utils.config_paths import resolve_config_toml_path

from ..scientific_labels import TheoryReferences
from ._stored_rollouts.shared import ExplanationSection, ScientificExplanation
from ._stored_rollouts.shared import plot_control_key as _plot_control_key
from ._stored_rollouts.shared import render_plot as _render_plot

_DEFAULT_CONFIG = ".configs/build_rollouts_v1_cuda_campaign.toml"
_REVIEWED_CONFIGS = (
    _DEFAULT_CONFIG,
    ".configs/build_rollouts_v1_cuda_campaign_pilot_corrected_v10.toml",
)
_SAFE_SESSION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
_MAX_NEW_UNITS = 100
_MAX_TIME_BUDGET_MINUTES = 24 * 60
_MAX_FREE_DISK_FLOOR_GB = 1024
_ADMISSION_STATE_KEY = "campaign_generation_admission_evidence"


def _admission_audit_identity(path: Path) -> tuple[str, int, int, int, int] | None:
    """Bind admission state to one immutable audit entry."""

    try:
        resolved = path.resolve()
        stat = resolved.stat()
    except OSError:
        return None
    return (resolved.as_posix(), stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)


@st.cache_data(show_spinner="Validating campaign admission evidence…", max_entries=8)
def _cached_admission_evidence(
    path: str,
    identity: tuple[str, int, int, int, int],
    *,
    campaign_id: str,
    source_manifest_hash: str,
    admission_audit_hash: str,
) -> dict[str, Any]:
    """Read one provenance-bound audit while retaining its identity in the cache key."""

    del identity
    return read_campaign_admission_evidence(
        Path(path),
        expected_campaign_id=campaign_id,
        expected_source_manifest_hash=source_manifest_hash,
        expected_audit_hash=admission_audit_hash,
    ).to_jsonable()


def _render_admission_figure(figure: Any, explanation: ScientificExplanation, key: str) -> None:
    """Render one admission figure through the shared scientific explanation seam."""

    _render_plot(figure, explanation, log_y_key=_plot_control_key("campaign-admission", key))


def _admission_explanation(kind: str, *, threshold: float) -> ScientificExplanation:
    """Build consistent scientific context for one admission audit figure."""

    if kind == "reasons":
        question = "Why did observed targets enter or leave campaign admission?"
        answer = "Each bar counts an audited actor-visible target; rejection reasons remain explicit and are never converted into low-quality training examples."
        metric = "Counts of observed targets; the denominator is the audited observed-target population."
        denominator = "Ambiguous, unmatched, invalid, and below-threshold rows remain in the denominator with their persisted reason."
        intuition = (
            "A large rejected share identifies target-source or matching coverage work, not a policy-quality score."
        )
        theory = TheoryReferences(
            equation_ids=(
                "entity.target_identity_iou",
                "entity.target_identity_threshold",
                "entity.target_identity_qualified_count",
            )
        )
    elif kind == "iou":
        question = "How much same-class oriented 3D overlap supports target association?"
        answer = "The ECDF shows the empirical overlap distribution for audited same-class candidate/GT comparisons. Admission requires exactly one qualifying match strictly above the threshold."
        metric = "Oriented 3D IoU is dimensionless; the dashed line marks the strict threshold. Equality is rejected."
        denominator = "Only scored same-class comparisons enter the ECDF; missing or invalid geometry is not silently treated as zero overlap."
        intuition = (
            "The curve crossing the threshold shows availability of geometric evidence, not correctness by itself."
        )
        theory = None
    else:
        question = "How is admission coverage distributed across source scenes?"
        answer = "Each scene contributes one admission-rate observation, preventing target-dense scenes from dominating this availability diagnostic."
        metric = "Admission rate is the fraction of observed targets admitted within one scene."
        denominator = "The denominator is observed targets in that scene; scenes with no observed targets are not fabricated into zero-rate samples."
        intuition = "Variation across scenes indicates source or matching heterogeneity and should be inspected alongside target counts."
        theory = None
    return ScientificExplanation(
        question=question,
        answer=answer,
        sections=(
            ExplanationSection(
                "population",
                "Validated campaign admission evidence is bound to one campaign, source manifest, and audit identity.",
            ),
            ExplanationSection("metric / units", metric),
            ExplanationSection("denominator / missingness", denominator),
            ExplanationSection(
                "evidence role",
                "Admission is privileged oracle/evaluation evidence; it is not actor-visible input or a training mask.",
            ),
            ExplanationSection("intuition", intuition),
            ExplanationSection(
                "warning", f"Same-class oriented-IoU threshold is strict: > {threshold:.2f}; equality does not qualify."
            ),
        ),
        evidence_role="oracle/evaluation",
        source_fields=(
            "oracle.pipelines.admission_evidence.read_campaign_admission_evidence",
            "admission-audit.json",
            "campaign/source/audit binding",
        ),
        theory=theory,
        external_references=(
            (
                "Admission evidence contract",
                "https://github.com/JanDuchscherer104/ARIA-NBV/blob/main/aria_nbv/aria_nbv/oracle/pipelines/admission_evidence.py",
            ),
        ),
    )


def _render_admission_audit(payload: dict[str, Any], *, threshold: float) -> None:
    """Render validated admission evidence as metrics and plot-first diagnostics."""

    counts = payload["counts"]
    metric_groups = (
        (
            ("Observed targets", "observed"),
            ("Admitted", "admitted"),
            ("Rejected", "rejected"),
            ("Same-class overlap scored", "same_class_scored"),
        ),
        (
            ("Zero-target samples", "zero_observation_samples"),
            ("Scenes containing zero-target samples", "scenes_with_zero_observation_samples"),
            ("Zero-only scenes", "zero_only_scenes"),
            ("Ambiguous", "ambiguous"),
            ("Duplicate GT groups", "duplicate_gt_groups"),
        ),
    )
    for group in metric_groups:
        for column, (label, key) in zip(st.columns(len(group)), group, strict=True):
            column.metric(label, f"{int(counts.get(key, 0)):,}")
    reason_frame = pd.DataFrame(payload.get("reason_rows", []))
    if not reason_frame.empty:
        _render_admission_figure(
            px.bar(reason_frame, x="reason", y="count", color="admitted", title="Observed-target admission outcomes"),
            _admission_explanation("reasons", threshold=threshold),
            "reasons",
        )
    iou_frame = pd.DataFrame(payload.get("iou_rows", []))
    if not iou_frame.empty:
        figure = px.ecdf(
            iou_frame,
            x="oriented_iou",
            color="reason",
            markers=True,
            title="Same-class oriented-IoU empirical distribution",
        )
        figure.add_vline(x=float(threshold), line_dash="dash", annotation_text=f"strict admission > {threshold:.2f}")
        _render_admission_figure(
            figure,
            _admission_explanation("iou", threshold=threshold),
            "iou",
        )
    scene_frame = pd.DataFrame(payload.get("scene_rows", []))
    observed_scene_frame = scene_frame.dropna(subset=["admission_rate"])
    if not observed_scene_frame.empty:
        _render_admission_figure(
            px.histogram(
                observed_scene_frame,
                x="admission_rate",
                title="Admission-rate distribution across scenes with observed targets",
            ),
            _admission_explanation("scenes", threshold=threshold),
            "scenes",
        )
    with st.expander("Admission evidence rows and export", expanded=False):
        st.dataframe(pd.DataFrame(payload.get("rows", [])), hide_index=True, width="stretch")
        st.download_button(
            "Download validated admission evidence JSON",
            data=json.dumps(payload, indent=2, sort_keys=True) + "\n",
            file_name="campaign_admission_evidence.json",
            mime="application/json",
            on_click="ignore",
        )


def _render_admission_section(campaign: Any, plan_path: Path) -> None:
    """Load campaign admission evidence only after explicit user dispatch."""

    cfg = campaign.config
    audit_path = cfg.output_root / "admission-audit.json"
    identity = _admission_audit_identity(audit_path)
    st.subheader("Target admission audit")
    st.caption(
        f"Same-class oriented-IoU admission requires exactly one match strictly greater than {cfg.observed_target_iou_threshold:.2f}; equality is rejected."
    )
    if st.button(
        "Load admission audit",
        disabled=identity is None or not plan_path.is_file(),
        key="campaign_load_admission_audit",
    ):
        try:
            assert identity is not None
            plan = campaign.load_plan(plan_path)
            payload = _cached_admission_evidence(
                audit_path.as_posix(),
                identity,
                campaign_id=cfg.campaign_id,
                source_manifest_hash=plan.source_manifest_hash,
                admission_audit_hash=plan.admission_audit_hash,
            )
            st.session_state[_ADMISSION_STATE_KEY] = (identity, payload)
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            st.session_state.pop(_ADMISSION_STATE_KEY, None)
            st.error(f"Admission evidence unavailable: {exc}")
    state = st.session_state.get(_ADMISSION_STATE_KEY)
    if state is not None and state[0] != identity:
        st.session_state.pop(_ADMISSION_STATE_KEY, None)
        state = None
    if state is None:
        st.info("Render a deterministic plan, then load the provenance-bound admission audit.")
        return
    _render_admission_audit(state[1], threshold=cfg.observed_target_iou_threshold)


def build_campaign_argv(
    action: str,
    *,
    config_path: Path,
    plan_path: Path | None = None,
    source_manifest: Path | None = None,
    max_new_units: int | None = None,
    time_budget_minutes: int | None = None,
    free_disk_floor_gb: int | None = None,
) -> list[str]:
    """Build the exact PATH-independent argv delegated to the campaign CLI."""
    if action not in {"preflight", "plan", "smoke", "run", "resume", "status"}:
        raise ValueError(f"unsupported campaign action: {action}")
    argv = [
        sys.executable,
        "-m",
        "aria_nbv.oracle.pipelines.cli",
        "--campaign",
        action,
        "--config-path",
        str(config_path),
    ]
    if action in {"run", "resume"}:
        if plan_path is None:
            raise ValueError("plan path is required")
        controls = {
            "max_new_units": (max_new_units, _MAX_NEW_UNITS, "--max-new-units"),
            "time_budget_minutes": (time_budget_minutes, _MAX_TIME_BUDGET_MINUTES, "--time-budget-minutes"),
            "free_disk_floor_gb": (free_disk_floor_gb, _MAX_FREE_DISK_FLOOR_GB, "--free-disk-floor-gb"),
        }
        for name, (value, maximum, flag) in controls.items():
            if value is None:
                continue
            if not _valid_integer_control(value, minimum=1, maximum=maximum):
                raise ValueError(f"{name} must be a whole number between 1 and {maximum}")
            argv += [flag, str(int(value))]
        argv += ["--plan-path", str(plan_path)]
    if action == "plan" and source_manifest is not None:
        argv += ["--source-manifest", str(source_manifest)]
    if action == "status":
        argv.append("--json")
    return argv


def build_tmux_argv(session: str, command: list[str]) -> list[str]:
    """Return a shell-free detached tmux command."""
    if not _SAFE_SESSION.fullmatch(session):
        raise ValueError("tmux session name must contain only safe characters")
    if not command:
        raise ValueError("tmux command cannot be empty")
    return ["tmux", "new-session", "-d", "-s", session, "--", *command]


def launch_campaign_tmux(
    session: str, command: list[str], *, claim_path: Path | None = None, runner: Callable[..., Any] = subprocess.run
) -> tuple[bool, str]:
    """Launch once, verify the named session, and return a user-facing result."""
    if not _SAFE_SESSION.fullmatch(session):
        return False, "tmux session name must contain only safe characters"
    if claim_path is not None and claim_path.exists():
        return False, f"campaign claim exists at {claim_path}; clear it explicitly before launching"
    if shutil.which("tmux") is None:
        return False, "tmux is unavailable; command preview remains available"
    probe = runner(["tmux", "has-session", "-t", session], check=False, capture_output=True, shell=False)
    if getattr(probe, "returncode", 1) == 0:
        return False, f"tmux session {session!r} already exists"
    result = runner(build_tmux_argv(session, command), check=False, capture_output=True, text=True, shell=False)
    if getattr(result, "returncode", 1) != 0:
        return False, (getattr(result, "stderr", "") or "tmux launch failed").strip()
    verify = runner(["tmux", "has-session", "-t", session], check=False, capture_output=True, shell=False)
    if getattr(verify, "returncode", 1) != 0:
        return False, "tmux session exited immediately; inspect command/logs"
    return True, f"started tmux session {session}"


def capture_tmux_tail(session: str, *, runner: Callable[..., Any] = subprocess.run, limit: int = 4000) -> str:
    """Capture a bounded named-session tail without shell interpolation."""
    if not _SAFE_SESSION.fullmatch(session) or shutil.which("tmux") is None:
        return ""
    result = runner(
        ["tmux", "capture-pane", "-p", "-t", session, "-S", "-80"],
        check=False,
        capture_output=True,
        text=True,
        shell=False,
    )
    if getattr(result, "returncode", 1) != 0:
        return ""
    return (getattr(result, "stdout", "") or "")[-limit:]


def _campaign(config_path: Path):
    return CudaRolloutCampaignConfig.from_toml(config_path).setup_target()


def _launch_ready(campaign: Any, plan_path: Path) -> bool:
    try:
        plan = campaign.load_plan(plan_path)
        evidence = campaign.smoke_evidence(plan)
        result = evidence.get("result")
        if not isinstance(result, dict) or result.get("outcome") != "succeeded" or result.get("validated") is not True:
            return False
        return not (campaign.config.output_root / "run-claim.json").exists()
    except (OSError, ValueError, TypeError, RuntimeError, json.JSONDecodeError):
        return False


def _valid_integer_control(value: Any, *, minimum: int, maximum: int) -> bool:
    """Return whether a UI control value is a finite integer in its safe range."""
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and int(value) == value
        and minimum <= value <= maximum
    )


def _disk_usage_path(path: Path) -> Path:
    """Return the nearest existing ancestor for a not-yet-created output root."""
    candidate = path
    while not candidate.exists() and candidate != candidate.parent:
        candidate = candidate.parent
    return candidate


def render_campaign_generation_page() -> None:  # pragma: no cover - Streamlit presentation
    """Render controls and typed status without owning campaign semantics."""
    st.header("Campaign Generation")
    config_text = st.selectbox("Reviewed campaign config", _REVIEWED_CONFIGS, key="campaign_config_path")
    try:
        config_path = resolve_config_toml_path(config_text)
        campaign = _campaign(config_path)
        config_error = None
    except Exception as exc:
        config_path, campaign, config_error = None, None, str(exc)
    if config_error:
        st.error(config_error)
        return
    cfg = campaign.config
    plan_path = cfg.output_root / "plan.json"
    number_input = getattr(st, "number_input", lambda _label, **_kwargs: 1)
    max_new_units = number_input(
        "Max new work units",
        min_value=1,
        max_value=_MAX_NEW_UNITS,
        value=1,
        step=1,
        key="campaign_max_units",
    )
    time_budget_minutes = number_input(
        "Time budget (minutes)",
        min_value=1,
        max_value=_MAX_TIME_BUDGET_MINUTES,
        value=120,
        step=1,
        key="campaign_time_budget",
    )
    free_disk_floor_gb = number_input(
        "Free-disk floor (GB)",
        min_value=1,
        max_value=_MAX_FREE_DISK_FLOOR_GB,
        value=10,
        step=1,
        key="campaign_free_disk_floor",
    )
    free_disk_gb = shutil.disk_usage(_disk_usage_path(cfg.output_root)).free / (1024**3)
    controls_valid = all(
        (
            _valid_integer_control(max_new_units, minimum=1, maximum=_MAX_NEW_UNITS),
            _valid_integer_control(time_budget_minutes, minimum=1, maximum=_MAX_TIME_BUDGET_MINUTES),
            _valid_integer_control(free_disk_floor_gb, minimum=1, maximum=_MAX_FREE_DISK_FLOOR_GB),
        )
    )
    if not controls_valid:
        st.warning("Operational controls must be finite whole numbers within their displayed bounds.")
    if free_disk_gb < free_disk_floor_gb:
        st.warning(f"Free disk {free_disk_gb:.1f} GB is below the configured floor.")
    manifest_text = st.text_input("Source manifest (plan only)", "", key="campaign_source_manifest")
    source_manifest = Path(manifest_text).expanduser() if manifest_text else None
    if source_manifest is not None and source_manifest.exists():
        try:
            from aria_nbv.rollouts.shard_manifest import read_rollout_source_manifest

            reviewed_source = read_rollout_source_manifest(source_manifest)
            st.json(
                {
                    "source_manifest": str(source_manifest),
                    "rows": len(reviewed_source.rows),
                    "scenes": len({row.scene_id for row in reviewed_source.rows}),
                    "split": reviewed_source.split,
                    "split_manifest_hash": reviewed_source.split_manifest_hash,
                    "selection": "all actor-visible detections are audited; only strict unambiguous matches are planned",
                }
            )
        except (OSError, TypeError, ValueError) as exc:
            st.warning(f"Source manifest unavailable: {exc}")
    profile_name = st.selectbox(
        "Inspect reviewed profile", [p.name for p in cfg.profiles], key="campaign_profile_inspect"
    )
    profile = next(p for p in cfg.profiles if p.name == profile_name)
    if len(profile.recipes) != 1:
        st.warning("Reviewed profile must expose exactly one current campaign recipe.")
    recipe = profile.recipes[0] if len(profile.recipes) == 1 else {}
    session = st.text_input("Named tmux session", f"{cfg.campaign_id}-campaign", key="campaign_tmux_session")
    st.caption(
        "CUDA / PyTorch3D required · "
        f"{recipe.get('policy', 'invalid')} H={recipe.get('horizon', '?')} "
        f"branch {recipe.get('branch', '?')} / beam {recipe.get('beam', '?')} · "
        f"60 candidates · balanced temperatures {list(cfg.temperatures)} · "
        f"support gate {cfg.min_valid_root_candidates} · watchdog 120s / 3600s"
    )
    st.json(
        {
            "campaign_id": cfg.campaign_id,
            "output_root": str(cfg.output_root),
            "profiles": [p.name for p in cfg.profiles],
            "plan": str(plan_path),
            "writer_config": str(cfg.writer_config_path or ""),
            "scientific_contract": {
                "profile": profile.name,
                "components": profile.components,
                "total_candidates": profile.total_count,
                "device": profile.device,
                "recipes": [
                    {
                        "name": r["name"],
                        "policy": r["policy"],
                        "horizon": r["horizon"],
                        "branch": r["branch"],
                        "beam": r["beam"],
                        "temperatures": list(cfg.temperatures),
                    }
                    for r in profile.recipes
                ],
                "strict_iou": f"> {cfg.observed_target_iou_threshold} (equality rejected)",
                "seed": cfg.seed,
                "expected_scenes": cfg.expected_scene_count,
                "min_valid_root_candidates": cfg.min_valid_root_candidates,
                "watchdogs_seconds": [cfg.stage_timeout_seconds, cfg.work_unit_timeout_seconds],
                "execution": "one serial CUDA worker; no CPU fallback",
            },
        }
    )
    _render_admission_section(campaign, plan_path)

    action = None
    cols = st.columns(6)
    labels = [
        ("Validate / preflight", "preflight"),
        ("Render deterministic plan", "plan"),
        ("Run one-target CUDA smoke", "smoke"),
        ("Launch in tmux", "run"),
        ("Resume in tmux", "resume"),
        ("Refresh status", "status"),
    ]
    tmux_available = shutil.which("tmux") is not None
    ready = _launch_ready(campaign, plan_path)
    for col, (label, value) in zip(cols, labels, strict=True):
        disabled = value in {"run", "resume"} and (
            not ready or not tmux_available or not controls_valid or free_disk_gb < free_disk_floor_gb
        )
        if col.button(label, key=f"campaign_{value}", disabled=disabled):
            action = value
    if action:
        try:
            if action == "plan" and source_manifest is None:
                raise ValueError("source manifest is required for plan")
            command = build_campaign_argv(
                action,
                config_path=config_path,
                plan_path=plan_path,
                source_manifest=source_manifest,
                max_new_units=int(max_new_units),
                time_budget_minutes=int(time_budget_minutes),
                free_disk_floor_gb=int(free_disk_floor_gb),
            )
            st.code(shlex.join(command), language="shell")
            if action in {"run", "resume"}:
                if not ready:
                    raise RuntimeError("launch/resume requires current plan and passing smoke evidence")
                ok, message = launch_campaign_tmux(session, command, claim_path=cfg.output_root / "run-claim.json")
                st.session_state["campaign_generation_last_action"] = {
                    "key": (str(config_path), str(plan_path)),
                    "command": shlex.join(command),
                    "message": message,
                }
                (st.success if ok else st.warning)(message)
            elif action != "status":
                result = subprocess.run(command, check=False, capture_output=True, text=True, shell=False)
                stdout = (result.stdout or "")[-4000:]
                stderr = (result.stderr or "")[-4000:]
                (st.success if result.returncode == 0 else st.error)(stdout or stderr or "command completed")
                st.session_state["campaign_generation_last_action"] = {
                    "key": (str(config_path), str(plan_path)),
                    "command": shlex.join(command),
                    "stdout": stdout,
                    "stderr": stderr,
                }
        except Exception as exc:
            st.error(str(exc))
    if controls_valid:
        preview = build_campaign_argv(
            "run",
            config_path=config_path,
            plan_path=plan_path,
            max_new_units=int(max_new_units),
            time_budget_minutes=int(time_budget_minutes),
            free_disk_floor_gb=int(free_disk_floor_gb),
        )
        st.caption(f"Foreground preview: {shlex.join(preview)}")
    else:
        st.caption("Foreground preview unavailable until operational controls are valid.")
    if not tmux_available:
        st.info("tmux unavailable; launch/resume disabled. Run the foreground command above manually after validation.")
    last_action = st.session_state.get("campaign_generation_last_action")
    if last_action and last_action.get("key") != (str(config_path), str(plan_path)):
        st.session_state.pop("campaign_generation_last_action", None)
        last_action = None
    if last_action and last_action.get("key") == (str(config_path), str(plan_path)):
        st.caption("Last action (bounded output)")
        st.code(json.dumps(last_action, sort_keys=True, indent=2), language="json")
    refresh = action == "status"
    cached = st.session_state.get("campaign_generation_view")
    cache_key = (str(config_path), str(plan_path), plan_path.stat().st_mtime_ns if plan_path.exists() else 0)
    if cached and cached.get("key") != cache_key:
        st.session_state.pop("campaign_generation_view", None)
        cached = None
    try:
        summary = campaign.progress_summary() if refresh else (cached["summary"] if cached else None)
        st.subheader("Campaign status")
        if summary is None:
            st.info("Refresh status to load typed campaign progress.")
        else:
            st.json(
                {
                    k: summary.get(k)
                    for k in (
                        "state",
                        "counts",
                        "current_work_unit",
                        "current_target_id",
                        "current_profile",
                        "current_stage",
                        "elapsed_seconds",
                        "active_pid",
                        "active_process_group",
                        "latest_failure_reason",
                        "last_work_unit",
                        "last_timeout",
                        "bounded_error",
                        "started_at",
                        "finished_at",
                    )
                }
            )
            artifact_records = summary.get("artifact_records", [])
            if artifact_records:
                st.subheader("Campaign artifact records")
                st.dataframe(artifact_records, use_container_width=True)
            artifacts = summary.get("validated_artifacts", [])
            if artifacts:
                st.subheader("Validated campaign artifacts")
                compact = [
                    {
                        key: artifact.get(key)
                        for key in (
                            "work_unit_hash",
                            "target_id",
                            "profile",
                            "validation",
                            "outcome",
                            "store_path",
                            "owner_evidence_path",
                            "success_evidence_path",
                            "owner_sha256",
                            "rollout_manifest_sha256",
                        )
                    }
                    for artifact in artifacts
                ]
                st.dataframe(compact, use_container_width=True)
                for index, artifact in enumerate(artifacts):
                    store_path = artifact.get("store_path")
                    if not isinstance(store_path, str) or not Path(store_path).is_absolute():
                        continue
                    if st.button(f"Inspect {artifact.get('work_unit_hash', index)}", key=f"campaign_inspect_{index}"):
                        st.session_state["rollout_store_manual_path"] = store_path
                        st.info("Validated path selected. Open Rollout Supervision to inspect it.")
        st.caption(f"Progress ledger: {cfg.output_root / 'progress.jsonl'} · artifacts: {cfg.output_root}")
        st.info("Detailed completed-store inspection remains in Training Data → Rollout Supervision.")
        if refresh:
            events = [asdict(event) for event in campaign.read_events()]
            tmux_output = capture_tmux_tail(session)
            st.session_state["campaign_generation_view"] = {
                "key": cache_key,
                "summary": summary,
                "events": events,
                "tmux_output": tmux_output,
            }
        view = st.session_state.get("campaign_generation_view", cached or {})
        if view.get("events"):
            st.dataframe(view["events"][-50:], use_container_width=True)
        if view.get("tmux_output"):
            st.caption("tmux output (bounded)")
            st.code(view["tmux_output"], language="text")
    except Exception as exc:
        st.warning(f"Status unavailable: {exc}")


__all__ = [
    "build_campaign_argv",
    "build_tmux_argv",
    "capture_tmux_tail",
    "launch_campaign_tmux",
    "render_campaign_generation_page",
]
