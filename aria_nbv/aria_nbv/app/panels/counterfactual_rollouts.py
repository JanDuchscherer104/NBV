"""Live counterfactual rollout generation, scoring, and audit panels.

This module owns actor-visible target and finite-candidate controls, optional
oracle RRI scoring, rollout-path diagnostics, and explicit separation between
hard invalidity and unavailable labels.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import torch
from efm3d.aria.pose import PoseTW

from ...configs import PathConfig
from ...data_handling import (
    VinOfflineDatasetConfig,
    VinOfflineStoreConfig,
)
from ...data_handling.vin_store.dataset import VinOfflineSample
from ...oracle.evidence import target_gt_obb_world
from ...oracle.pipelines.evaluated_rollout import (
    EvaluatedRollout,
    EvaluatedRolloutStep,
    OracleReplayAdapter,
    OracleReplayInvalidityError,
)
from ...oracle.pipelines.rollout_dataset import RolloutDatasetWriterConfig
from ...oracle.scene_rri import SceneRriScorerConfig
from ...oracle.target_rri import TargetRriScorerConfig
from ...oracle.target_selection import (
    ORACLE_TARGET_TASK_SOURCE,
    OracleTargetTask,
    OracleTargetTaskSampler,
    OracleTargetTaskSamplerConfig,
    TargetTaskIdentityStatus,
)
from ...pose_generation import (
    CandidateGenerationRuntimeContext,
    CandidateMixtureComponentConfig,
    CandidateMixtureViewGeneratorConfig,
    CandidatePositionMode,
    CandidateViewGeneratorConfig,
    ViewDirectionMode,
)
from ...pose_generation.config import (
    CandidateGazeConfig,
    SampledCenterConfig,
    SampledCenterMode,
)
from ...pose_generation.plotting import CounterfactualPlotBuilder, plot_counterfactual_paths_simple
from ...rendering import CandidateDepthRendererConfig
from ...rendering.plotting import (
    DepthBoxOverlay,
    depth_grid,
    depth_grid_with_box_overlays,
    project_world_points_to_image,
)
from ...rollouts import (
    CounterfactualPoseGeneratorConfig,
    RolloutPolicySpec,
)
from ...rollouts.inspection import (
    candidate_result_diagnostic_counts,
    decode_position_id,
    decode_strategy_id,
)
from ...rollouts.replay.policy import CounterfactualSelectionPolicy
from ...rollouts.replay.state import CounterfactualStepResult
from ...rri_metrics.returns import summarize_target_rollout_metrics
from ...utils import Console, Verbosity
from ..scene_view import ROLLOUT_SCENE_DEFAULTS, apply_scene_plot_options, scene_plot_options_ui
from ..state_types import config_signature
from .common import (
    _info_popover,
    _plot_with_y_axis_control,
    _pretty_label,
    _report_exception,
    _strip_ansi,
    current_scientific_label,
    render_scientific_notation,
)
from .configuration import trusted_config_patterns
from .target_audit import render_target_selection_audit, target_selection_audit_rows

_SOURCE_TARGET_INFO = """
This block chooses the immutable VIN offline root and the oracle-specified target tasks.

- `VIN offline store`: source rows with cached EFM/backbone state and attached mesh assets.
- `Split` / `Split-local sample index`: which source row is inspected.
- `Max target tasks`: how many finite positive GT target tasks are sampled for rollout generation.
- `Selection seed`: deterministic uniform-without-replacement oracle target-task sampling.
- Oracle task admission: finite positive GT OBB geometry before evidence validation.
"""

_LOADED_SAMPLE_INFO = """
Loaded sample metrics:

- `Scene`: ASE scene id for the source row.
- `Snippet`: source snippet/window id.
- `Source`: privileged target-task source used by the Oracle sampler.
- `Selected targets`: number of geometry-valid Oracle tasks retained for rollout generation.

Target table fields:

- `target_row_id`: split-local target row id used by rollouts and stored targets.
- `selected_rank`: rank among selected targets; `None` means retained for inspection but not selected.
- `class`: human-readable class name when available.
- `sem_id` / `inst_id`: semantic and instance ids from the privileged task source.
- `confidence`: source confidence retained for audit.
- `selection_probability`: stochastic target-selection probability when available.
- `admitted`: whether finite positive GT geometry admits the task.
- `identity_status`: whether finite positive GT geometry admits the Oracle task.
"""

_ACTIVE_TARGET_INFO = """
The active target is the object conditioned into target-RRI rollout generation.

Label format: `target 0 · window · sem=28 inst=51297 · matched`.

- `target 0`: target row id.
- `window`: class name resolved from the EFM semantic-id map.
- `sem=... inst=...`: privileged semantic and instance ids retained for audit.
- `matched`: Oracle task-admission status.
- `valid`: GT-only matching succeeded, so target-RRI labels/evaluation crops can be computed.

Candidate generation receives only the sanitized target descriptor. GT identity,
matching, invalidity, and crop fields stay in Oracle evaluation.
"""

_ROLLOUT_GENERATION_INFO = """
This block defines the finite-candidate rollout tree.

- `Scoring mode`: `target_rri` is thesis-core; `scene_rri` and `geometry` are diagnostics.
- `Candidates per step`: requested valid candidate budget regenerated at each rollout step.
- `Generator device`: CUDA is the preferred default when available; a preflight catches PyTorch3D builds without GPU rasterization support.
- `Horizon` (`H`): maximum rollout length.
- `Branch factor` (`B`): number of child actions retained per expanded state.
- `Beam width`: optional cap on retained partial trajectories.
- `Selection policy`: how candidates are selected from the scored valid set.
- `Softmax temperature`: stochastic-policy temperature.
- `Seed`: controls repeatable sampling.
- `Min history distance` / `Min sibling distance`: geometric guards against duplicate or near-duplicate actions.
- `Log rollout/scorer timing`: emits timing diagnostics in the Logs tab.
"""

_TARGET_MIXTURE_INFO = """
Target-RRI rollouts use a mixed finite candidate set.

- `target_bearing_local`: centers biased along the sanitized target bearing.
- `forward_local`: local forward continuity around the reference pose.
- `lateral_target_bypass`: target-bearing views with signed lateral bypass.
- `local_refinement`: short local refinement views around the current pose.
- `revisit_backtrack`: controlled backward-looking revisit views.

Stored rollout stores persist `position_id`, `strategy_id`, `mixture_id`, and sampler probability so these families can be audited after generation. These are candidate-set sampling counts, not rollout branch counts.
"""

_SCORER_CONTROLS_INFO = """
These controls affect oracle scoring cost and validity.

- `Backprojection stride`: depth-to-point-cloud stride used after rendering candidate views.
- `Target crop margin`: margin around the matched GT target OBB for target-RRI evaluation.
- `Min current target points`: minimum current target support required before target-RRI is meaningful.
- `Also compute scene RRI audit`: optional diagnostic scene-RRI pass; off by default for speed.
"""

_ROLLOUT_RESULT_INFO = """
Result table and plots:

- `cumulative_score`: cumulative score used by the selected policy.
- `cumulative_rri`: cumulative RRI when an RRI scorer is attached; intentionally empty in geometry mode.
- `G_target`: selected-branch cumulative root-normalized target return when target metrics are available.
- `J_endpoint`: endpoint target-error gain from rollout root to final selected state.
- `log_gain`: endpoint log target-error reduction used as a diagnostic companion.
- `terminated_early`: rollout stopped before `H`, usually because no valid successor action remained.
- `final_x/y/z`: final selected rig pose translation in world coordinates.
- `Paths`: trajectory-level visualization.
- `Step Shell`: per-step candidate shell and selected candidate view.
- `Logs`: captured Console output from generation/scoring.

The metric dashboard has plot-specific info boxes with the equations used for
target return, endpoint gain, candidate bands, and top-k candidate headroom.
"""

_LIVE_TRAJECTORY_OBJECTIVE_INFO = r"""
These headline metrics summarize the selected rollout branches.

Target-cropped point-mesh error for target \(e\) is

$$
\Delta_t^e =
d(C_e(\mathcal{P}_t), M_e).
$$

`Best G_0^(H)` is the largest selected-branch finite-horizon return rooted at
the loaded sample:

$$
G_0^{(H)}(\tau)=
\sum_{t=0}^{H-1}\gamma^t r_{t,\mathrm{root}}^e.
$$

`Best J_e^(H)` is endpoint target-error gain:

$$
J_{e,\Delta}^{(H)}(\tau)=
\frac{\Delta_0^e-\Delta_H^e}{\Delta_0^e+\varepsilon}.
$$

`Mean valid fanout` is the mean number of valid candidate actions available
across expanded rollout states. Invalid candidates are hard masks, not low-RRI
examples.
"""

_LIVE_SELECTED_RETURN_INFO = r"""
This plot shows the selected action at each rollout step and the cumulative
prefix return for each branch.

The immediate rollout/Q_H reward is root-normalized target gain:

$$
r_{t,\mathrm{root}}^e =
\frac{\Delta_t^e-\Delta_{t+1}^e}{\Delta_0^e+\varepsilon}.
$$

The dashed line is the displayed undiscounted cumulative prefix after chart
step \(s\):

$$
G_{0:s}^{(H)} =
\sum_{k=0}^{s-1} r_{k,\mathrm{root}}^e.
$$

using the emitted selected `target_root_gain` values. Legacy or diagnostic rows
fall back to state-relative target RRI when root-normalized gain is unavailable:

$$
\mathrm{RRI}_{t,\mathrm{state}}^e =
\frac{\Delta_t^e-\Delta_{t+1}^e}{\Delta_t^e+\varepsilon}.
$$
"""

_LIVE_FANOUT_BAND_INFO = r"""
This plot compares the chosen action with the valid candidate shell available
at each rollout step.

For each expanded state, the shaded region is the empirical central 95% range
over valid candidate target gains:

$$
\left[
Q_{0.025}\{r_{t,\mathrm{root}}^e(a_i): m_{t,i}=1\},
Q_{0.975}\{r_{t,\mathrm{root}}^e(a_i): m_{t,i}=1\}
\right].
$$

The selected line is the action actually retained by the rollout policy. This
range is a candidate-shell diagnostic, not a statistical confidence interval.
When root-normalized gain is missing, the plot falls back to target RRI.
"""

_LIVE_TOPK_CANDIDATE_INFO = r"""
This plot shows per-step headroom in the valid candidate shell.

For each expanded state, the displayed lines are

$$
\operatorname{TopK}_t =
\operatorname{TopK}_{i:m_{t,i}=1}
r_{t,\mathrm{root}}^e(a_i).
$$

Large gaps between the selected action and top-k candidates indicate selection
or sampling-policy headroom. Flat or near-zero top-k curves indicate the current
candidate families are not exposing target-improving views for that state.
"""

_LIVE_ENDPOINT_METRIC_INFO = r"""
Endpoint metrics evaluate the whole selected branch after the fixed horizon or
early termination.

Endpoint gain reports the fraction of initial target error removed:

$$
J_{e,\Delta}^{(H)}(\tau)=
\frac{\Delta_0^e-\Delta_H^e}{\Delta_0^e+\varepsilon}.
$$

Log gain is a diagnostic companion:

$$
L_e^{(H)}(\tau)=
\log(\Delta_0^e+\varepsilon)-\log(\Delta_H^e+\varepsilon).
$$

When all selected steps emit root-normalized gain and \(\gamma=1\), cumulative
root-normalized reward telescopes to endpoint gain up to numerical epsilon. Log
gain is not the default rollout/Q_H reward.
"""

_LIVE_SELECTED_DEPTH_INFO = """
Selected-depth inspection shows the retained depth image for the action chosen at each live rollout step.

- Live generation only shows images when `CounterfactualStepResult.selected_depth_m` is populated.
- Dataset-writer generated stores usually retain selected-depth rasters; plain live runs may not.
- Valid and finite pixel fractions expose broken renders or all-miss views.
- The preview uses the shared Plotly depth-grid builder and does not scan unrelated candidates.

If this tab reports no retained depths, inspect a persisted rollout store or add live selected-depth retention rather than inferring geometry from missing images.
"""

_LIVE_LOG_INFO = """
Rollout logs are captured from the project Console during generation/scoring.
Use them to verify renderer device, candidate generation counts, target-RRI scorer timings, invalidity warnings, and early termination causes.
"""

_LIVE_STEP_CANDIDATE_INFO = """
Step candidate diagnostics inspect the finite candidate shell generated for one rollout step.

- Fanout counts show how many candidates each position family contributed before selection.
- Rejection counts are hard actor-action invalidity diagnostics, not low-RRI labels.
- Score rows are compact valid candidates aligned to selection scores, target-RRI metrics, probabilities, and family provenance.
- Selected markers identify the action that entered the rollout path; they should not be the only high-quality candidate unless the policy is intentionally greedy.
- Family score plots expose whether target-aware families contribute useful target-root-gain support or whether all reward mass comes from one generic family.
"""


class LiveRolloutScoringMode(StrEnum):
    """Available scoring modes for live rollout generation."""

    TARGET_RRI = "target_rri"
    SCENE_RRI = "scene_rri"
    GEOMETRY = "geometry"


@dataclass(slots=True)
class LiveRolloutScoreContext:
    """Evaluator and candidate-runtime state for one live rollout run."""

    score_label: str
    """Human-readable objective label shown beside rollout results."""

    evaluator: OracleReplayAdapter | None
    """Optional Oracle replay adapter; ``None`` selects geometry-only scoring."""

    runtime_context: CandidateGenerationRuntimeContext | None
    """Actor-visible target/history context passed to finite candidate generation."""


def _live_rollout_device_options() -> list[str]:
    """Return UI device choices with CUDA first when Torch can see a GPU."""

    return ["cuda", "cpu"] if torch.cuda.is_available() else ["cpu"]


def _validate_live_rollout_device(device: str) -> None:
    """Fail fast when CUDA is selected but PyTorch3D cannot rasterize on GPU."""

    if str(device) != "cuda":
        return
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA was selected, but torch.cuda.is_available() is false. Select CPU or fix CUDA.")
    if not _pytorch3d_cuda_rasterization_available():
        raise RuntimeError(
            "CUDA was selected, but the installed PyTorch3D rasterizer is not compiled with GPU support. "
            "Select CPU for this session or install a CUDA-enabled PyTorch3D build.",
        )


def _candidate_config_device(config: CandidateViewGeneratorConfig | CandidateMixtureViewGeneratorConfig) -> str:
    """Return the explicit runtime device stored in a live candidate config."""

    if isinstance(config, CandidateMixtureViewGeneratorConfig):
        return str(config.base.device)
    return str(config.device)


def _live_candidate_profile_paths() -> tuple[Path, ...]:
    """Return trusted rollout-writer TOMLs available to the live rollout lab."""

    root = PathConfig().configs_dir.expanduser().resolve()
    patterns = trusted_config_patterns().get("Rollout writer", ("build_rollouts*.toml",))
    return tuple(
        sorted(
            {path for pattern in patterns for path in root.glob(pattern)},
            key=lambda path: path.as_posix(),
        )
    )


def _load_live_candidate_profile(path: Path) -> CandidateMixtureViewGeneratorConfig:
    """Load and validate one trusted rollout-writer candidate mixture TOML."""

    return RolloutDatasetWriterConfig.from_toml(path).candidate_mixture


def _candidate_config_count(
    config: CandidateViewGeneratorConfig | CandidateMixtureViewGeneratorConfig,
) -> int:
    """Return the effective attempted candidate count for a live config."""

    return config.total_count if isinstance(config, CandidateMixtureViewGeneratorConfig) else int(config.num_samples)


@lru_cache(maxsize=1)
def _pytorch3d_cuda_rasterization_available() -> bool:
    """Return whether the installed PyTorch3D extension can rasterize on CUDA."""

    if not torch.cuda.is_available():
        return False
    try:
        from pytorch3d.renderer import FoVPerspectiveCameras, MeshRasterizer, RasterizationSettings
        from pytorch3d.structures import Meshes

        device = torch.device("cuda")
        verts = torch.tensor(
            [[-0.5, -0.5, 2.0], [0.5, -0.5, 2.0], [0.0, 0.5, 2.0]],
            dtype=torch.float32,
            device=device,
        )
        faces = torch.tensor([[0, 1, 2]], dtype=torch.int64, device=device)
        mesh = Meshes(verts=[verts], faces=[faces])
        cameras = FoVPerspectiveCameras(device=device)
        rasterizer = MeshRasterizer(
            cameras=cameras,
            raster_settings=RasterizationSettings(image_size=8, blur_radius=0.0, faces_per_pixel=1),
        )
        fragments = rasterizer(mesh)
        return bool(fragments.pix_to_face.numel())
    except Exception:
        return False


def _live_depth_config(*, max_candidates: int, device: str) -> CandidateDepthRendererConfig:
    """Build the scorer depth config on the same explicit device as rollout generation."""

    return CandidateDepthRendererConfig(
        device=torch.device(device),
        max_candidates_final=int(max_candidates),
    )


def _build_live_dataset_config(*, store_dir: Path, split: str) -> VinOfflineDatasetConfig:
    """Return the VIN offline reader config required by live target-RRI rollouts."""

    return VinOfflineDatasetConfig(
        store=VinOfflineStoreConfig(store_dir=store_dir),
        split=split,  # type: ignore[arg-type]
        return_format="sample",
        include_efm_snippet=True,
        include_gt_mesh=True,
        load_backbone=True,
        load_candidates=False,
        load_depths=False,
        load_candidate_pcs=False,
        load_gt_obbs=True,
        load_detected_obbs=True,
        load_trajectory_metadata=True,
    )


def _load_vin_offline_sample(*, store_dir: Path, split: str, sample_index: int) -> VinOfflineSample:
    """Load one split-local `VinOfflineSample` with live snippet and target assets."""

    dataset = _build_live_dataset_config(store_dir=store_dir, split=split).setup_target()
    if sample_index < 0 or sample_index >= len(dataset):
        raise IndexError(f"Sample index {sample_index} is outside split '{split}' length {len(dataset)}.")
    sample = dataset[int(sample_index)]
    if not isinstance(sample, VinOfflineSample):
        raise TypeError("Live rollout inspector requires VinOfflineDatasetConfig(return_format='sample').")
    if sample.efm_snippet_view is None or sample.efm_snippet_view.mesh is None:
        raise ValueError("Live rollout sample must include an attached EFM snippet and GT mesh.")
    return sample


def _target_mixture_counts_from_budget(candidate_budget: int) -> dict[str, int]:
    """Allocate the current five-family target-aware mixture for a requested budget."""

    budget = int(candidate_budget)
    if budget < 5:
        raise ValueError("Target-aware rollout mixtures require at least 5 candidates.")
    weights = {
        "target_bearing_local": 18.0,
        "forward_local": 18.0,
        "lateral_target_bypass": 12.0,
        "local_refinement": 6.0,
        "revisit_backtrack": 6.0,
    }
    total = sum(weights.values())
    counts = {mode: max(1, int(np.floor(budget * weight / total))) for mode, weight in weights.items()}
    while sum(counts.values()) < budget:
        deficits = {mode: (budget * weights[mode] / total) - counts[mode] for mode in counts}
        mode = max(deficits, key=lambda name: deficits[name])
        counts[mode] += 1
    while sum(counts.values()) > budget:
        mode = max((mode for mode in counts if counts[mode] > 1), key=lambda name: counts[name])
        counts[mode] -= 1
    return counts


def _target_mixture_config(
    base: CandidateViewGeneratorConfig,
    *,
    counts: dict[str, int],
) -> CandidateMixtureViewGeneratorConfig:
    """Build a target-aware mixed candidate generator from per-family counts."""

    def center(
        mode: SampledCenterMode,
        *,
        min_radius_m: float | None = None,
        max_radius_m: float | None = None,
    ) -> SampledCenterConfig:
        return SampledCenterConfig.from_legacy(
            base,
            mode=mode,
            min_radius_m=min_radius_m,
            max_radius_m=max_radius_m,
        )

    def gaze(mode: ViewDirectionMode) -> CandidateGazeConfig:
        yaw_half_width_deg = base.view_max_azimuth_deg
        pitch_half_width_deg = base.view_max_elevation_deg
        concentration = base.view_kappa
        assert yaw_half_width_deg is not None
        assert pitch_half_width_deg is not None
        assert concentration is not None
        return CandidateGazeConfig.from_legacy(
            mode=mode,
            sampling_strategy=base.view_sampling_strategy,
            concentration=concentration,
            yaw_half_width_deg=yaw_half_width_deg,
            pitch_half_width_deg=pitch_half_width_deg,
            roll_half_width_deg=base.view_roll_jitter_deg,
        )

    components = [
        CandidateMixtureComponentConfig(
            name="target_bearing_local",
            count=int(counts["target_bearing_local"]),
            center=center(CandidatePositionMode.TARGET_BEARING_LOCAL),
            gazes=(gaze(ViewDirectionMode.TARGET_POINT),),
        ),
        CandidateMixtureComponentConfig(
            name="forward_local",
            count=int(counts["forward_local"]),
            center=center(CandidatePositionMode.FORWARD_LOCAL),
            gazes=(gaze(ViewDirectionMode.FORWARD_RIG),),
        ),
        CandidateMixtureComponentConfig(
            name="lateral_target_bypass",
            count=int(counts["lateral_target_bypass"]),
            center=center(CandidatePositionMode.LATERAL_TARGET_BYPASS),
            gazes=(gaze(ViewDirectionMode.TARGET_POINT),),
        ),
        CandidateMixtureComponentConfig(
            name="local_refinement",
            count=int(counts["local_refinement"]),
            center=center(CandidatePositionMode.LOCAL_REFINEMENT, min_radius_m=0.2, max_radius_m=0.7),
            gazes=(gaze(ViewDirectionMode.RADIAL_TOWARDS),),
        ),
        CandidateMixtureComponentConfig(
            name="revisit_backtrack",
            count=int(counts["revisit_backtrack"]),
            center=center(CandidatePositionMode.REVISIT_BACKTRACK, min_radius_m=0.25, max_radius_m=0.9),
            gazes=(gaze(ViewDirectionMode.FORWARD_RIG),),
        ),
    ]
    return CandidateMixtureViewGeneratorConfig(base=base, components=tuple(components))


def _candidate_config_for_live_rollout(
    *,
    scoring_mode: LiveRolloutScoringMode,
    candidate_budget: int,
    seed: int | None,
    device: torch.device,
    counts: dict[str, int] | None = None,
    profile: CandidateMixtureViewGeneratorConfig | None = None,
) -> CandidateViewGeneratorConfig | CandidateMixtureViewGeneratorConfig:
    """Return the candidate generator used by one live rollout run."""

    if profile is not None:
        if scoring_mode is not LiveRolloutScoringMode.TARGET_RRI:
            raise ValueError("TOML candidate profiles currently require target_rri scoring.")
        payload = profile.model_dump()
        payload["base"]["device"] = torch.device(str(device))
        payload["base"]["seed"] = seed
        payload["base"]["num_samples"] = profile.total_count
        return CandidateMixtureViewGeneratorConfig.model_validate(payload)

    base = CandidateViewGeneratorConfig(
        num_samples=int(candidate_budget),
        oversample_factor=2.0,
        seed=seed,
        device=torch.device(str(device)),
        collect_rule_masks=True,
        collect_debug_stats=True,
        verbosity=Verbosity.NORMAL,
    )
    if scoring_mode is LiveRolloutScoringMode.TARGET_RRI:
        resolved_counts = counts or _target_mixture_counts_from_budget(candidate_budget)
        return _target_mixture_config(base, counts=resolved_counts)
    return base


def _validate_policy_for_scoring_mode(
    *,
    scoring_mode: LiveRolloutScoringMode,
    selection_policy: CounterfactualSelectionPolicy,
) -> None:
    """Reject policy/scoring combinations that would mislabel geometric scores."""

    if (
        scoring_mode is LiveRolloutScoringMode.GEOMETRY
        and selection_policy is CounterfactualSelectionPolicy.ORACLE_GREEDY
    ):
        raise ValueError("oracle_greedy requires an RRI scorer; choose target_rri, scene_rri, or a geometry policy.")


def _score_context_for_mode(
    *,
    scoring_mode: LiveRolloutScoringMode,
    sample: VinOfflineSample,
    target: OracleTargetTask | None,
    target_scorer_config: TargetRriScorerConfig,
    scene_scorer_config: SceneRriScorerConfig,
) -> LiveRolloutScoreContext:
    """Create the scorer and target runtime context for a live rollout."""

    if scoring_mode is LiveRolloutScoringMode.GEOMETRY:
        return LiveRolloutScoreContext(
            score_label=LiveRolloutScoringMode.GEOMETRY.value,
            evaluator=None,
            runtime_context=None,
        )

    if sample.efm_snippet_view is None:
        raise ValueError("Live RRI scoring requires sample.efm_snippet_view.")

    if scoring_mode is LiveRolloutScoringMode.SCENE_RRI:
        scorer = scene_scorer_config.setup_target(sample=sample.efm_snippet_view)
        return LiveRolloutScoreContext(
            score_label=LiveRolloutScoringMode.SCENE_RRI.value,
            evaluator=OracleReplayAdapter(scorer),
            runtime_context=None,
        )

    if target is None:
        raise ValueError("target_rri scoring requires a selected target row.")
    if target.identity_status != TargetTaskIdentityStatus.MATCHED.value:
        raise ValueError(f"Selected target is not GT-label valid: status={target.identity_status}.")
    scorer = target_scorer_config.setup_target(
        sample=sample.efm_snippet_view,
        target_sample=sample,
        target_task=target,
    )
    return LiveRolloutScoreContext(
        score_label=LiveRolloutScoringMode.TARGET_RRI.value,
        evaluator=OracleReplayAdapter(scorer),
        runtime_context=CandidateGenerationRuntimeContext(descriptor=target.descriptor),
    )


def _run_live_rollout(
    *,
    sample: VinOfflineSample,
    scoring_mode: LiveRolloutScoringMode,
    target: OracleTargetTask | None,
    candidate_config: CandidateViewGeneratorConfig | CandidateMixtureViewGeneratorConfig,
    rollout_config: CounterfactualPoseGeneratorConfig,
    target_scorer_config: TargetRriScorerConfig,
    scene_scorer_config: SceneRriScorerConfig,
) -> tuple[EvaluatedRollout, str]:
    """Generate one live rollout result and capture Console logs for display."""

    if sample.efm_snippet_view is None:
        raise ValueError("Live rollout generation requires sample.efm_snippet_view.")
    _validate_live_rollout_device(_candidate_config_device(candidate_config))
    _validate_policy_for_scoring_mode(
        scoring_mode=scoring_mode,
        selection_policy=rollout_config.policy.selection_policy,
    )
    context = _score_context_for_mode(
        scoring_mode=scoring_mode,
        sample=sample,
        target=target,
        target_scorer_config=target_scorer_config,
        scene_scorer_config=scene_scorer_config,
    )
    resolved_rollout_config = rollout_config.model_copy(update={"candidate_config": candidate_config})

    lines: list[str] = []

    def _sink(message: str) -> None:
        lines.append(_strip_ansi(message))

    Console.set_sink(_sink)
    try:
        result = resolved_rollout_config.setup_target().generate_from_typed_sample(
            sample.efm_snippet_view,
            score_candidates=context.evaluator,
            candidate_runtime_context=context.runtime_context,
        )
    finally:
        Console.set_sink(None)
    result.score_label = context.score_label
    evaluated = (
        EvaluatedRollout(result=result)
        if context.evaluator is None
        else context.evaluator.materialize(result, retain_target_crops=False)
    )
    return evaluated, "\n".join(lines)


def _counterfactual_trajectory_rows(
    evaluated: EvaluatedRollout,
) -> list[dict[str, int | float | bool | None]]:
    """Summarize rollout trajectories for compact panel tables."""

    rows: list[dict[str, int | float | bool | None]] = []
    for traj_idx, trajectory in enumerate(evaluated.result.trajectories):
        final_pos = trajectory.final_pose_world().t.detach().cpu().reshape(-1).tolist()
        selected_metrics = [
            evaluated_step.evaluation.labels.selected(evaluated_step.transition.selected_valid_index)
            for step in trajectory.steps
            if (evaluated_step := evaluated.step(traj_idx, step.step_index)) is not None
        ]
        metric_summary = summarize_target_rollout_metrics(selected_metrics)
        rows.append(
            {
                "trajectory": traj_idx,
                "steps": len(trajectory.steps),
                "cumulative_score": float(trajectory.cumulative_score),
                "cumulative_rri": sum(
                    float(metrics.get("rri", 0.0)) for metrics in selected_metrics if "rri" in metrics
                )
                or None,
                "G_target": metric_summary.cumulative_return,
                "J_endpoint": metric_summary.endpoint_gain,
                "log_gain": metric_summary.log_gain,
                "terminated_early": bool(trajectory.terminated_early),
                "final_x": float(final_pos[0]),
                "final_y": float(final_pos[1]),
                "final_z": float(final_pos[2]),
            }
        )
    return rows


def _trajectory_metric_rows(evaluated: EvaluatedRollout) -> pd.DataFrame:
    """Return selected-step and fanout metric rows for rollout dashboard plots."""

    rows: list[dict[str, Any]] = []
    for traj_idx, trajectory in enumerate(evaluated.result.trajectories):
        cumulative = 0.0
        for step in trajectory.steps:
            evaluated_step = evaluated.step(traj_idx, step.step_index)
            if evaluated_step is None:
                continue
            selected_metrics = evaluated_step.evaluation.labels.selected(
                evaluated_step.transition.selected_valid_index,
            )
            selected_target_rri = _metric_float(selected_metrics.get("target_rri", selected_metrics.get("rri")))
            selected_target_root_gain = _metric_float(selected_metrics.get("target_root_gain"))
            selected_return = selected_target_root_gain
            if selected_return is not None:
                cumulative += selected_return
            valid_target_gain = _valid_step_metric_values(evaluated_step, "target_root_gain")
            valid_target_rri = _valid_step_metric_values(evaluated_step, "target_rri")
            fanout_q025 = float(np.quantile(valid_target_rri, 0.025)) if valid_target_rri.size else None
            fanout_q975 = float(np.quantile(valid_target_rri, 0.975)) if valid_target_rri.size else None
            root_gain_q025 = float(np.quantile(valid_target_gain, 0.025)) if valid_target_gain.size else None
            root_gain_q975 = float(np.quantile(valid_target_gain, 0.975)) if valid_target_gain.size else None
            top_rri_values = sorted(valid_target_rri.tolist(), reverse=True)[:5]
            top_gain_values = sorted(valid_target_gain.tolist(), reverse=True)[:5]
            rows.append(
                {
                    "trajectory": traj_idx,
                    "step": int(step.step_index) + 1,
                    "selected_target_rri": selected_target_rri,
                    "selected_target_root_gain": selected_target_root_gain,
                    "G_target": cumulative if selected_return is not None else None,
                    "fanout_q025": fanout_q025,
                    "fanout_q975": fanout_q975,
                    "fanout_root_gain_q025": root_gain_q025,
                    "fanout_root_gain_q975": root_gain_q975,
                    "valid_candidates": int(step.candidates.mask_valid.sum().item()),
                    "top_target_rri": top_rri_values,
                    "top_target_root_gain": top_gain_values,
                }
            )
    return pd.DataFrame(rows)


def _valid_step_metric_values(step: EvaluatedRolloutStep, metric_name: str) -> np.ndarray:
    metric_vectors = step.evaluation.labels.metrics
    values = metric_vectors.get(metric_name)
    if values is None and metric_name == "target_rri":
        values = metric_vectors.get("rri")
    if values is None:
        return np.asarray([], dtype=float)
    values_np = values.detach().cpu().numpy().reshape(-1)
    mask = step.transition.candidates.mask_valid.detach().cpu().numpy().reshape(-1).astype(bool, copy=False)
    if mask.shape == values_np.shape:
        values_np = values_np[mask]
    elif values_np.shape[0] != int(mask.sum()):
        raise ValueError(
            f"Candidate validity mask shape {mask.shape} must match metric vector shape {values_np.shape} "
            f"or compact valid count {int(mask.sum())}."
        )
    finite = np.isfinite(values_np)
    return np.asarray(values_np[finite].astype(float, copy=False))


def _metric_float(value: Any) -> float | None:
    try:
        value_float = float(value)
    except (TypeError, ValueError):
        return None
    return value_float if np.isfinite(value_float) else None


def _int_scalar(value: Any) -> int:
    """Convert one finite integral scalar from a dataframe boundary."""

    if isinstance(value, bool) or not isinstance(value, int | float | np.integer | np.floating):
        raise TypeError(f"Expected an integral numeric scalar, got {type(value).__name__}.")
    numeric = float(value)
    if not np.isfinite(numeric) or not numeric.is_integer():
        raise ValueError(f"Expected an integral numeric scalar, got {value!r}.")
    return int(numeric)


def _format_optional_metric(value: Any) -> str:
    value_float = _metric_float(value)
    return "n/a" if value_float is None else f"{value_float:.4f}"


def _render_live_step_candidate_diagnostics(
    transition: CounterfactualStepResult,
    evaluated_step: EvaluatedRolloutStep | None,
) -> None:
    """Render per-step live candidate fanout by family and rejection reason."""

    _info_popover("step candidate diagnostics", _LIVE_STEP_CANDIDATE_INFO)
    counts = candidate_result_diagnostic_counts(transition.candidates)
    position_rows = counts.get("position", [])
    invalid_rows = counts.get("invalid_reason", [])
    if not position_rows and not invalid_rows:
        st.info("No candidate provenance or rule diagnostics were collected for this step.")
        return
    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        if position_rows:
            pos_df = pd.DataFrame(position_rows)
            st.dataframe(pos_df, width="stretch", hide_index=True)
            st.plotly_chart(
                px.bar(
                    pos_df,
                    x="position",
                    y=["valid", "invalid"],
                    barmode="stack",
                    title="Candidate Fanout by Position Family",
                ),
                width="stretch",
            )
        else:
            st.info("No position-family ids are available.")
    with chart_col2:
        if invalid_rows:
            reason_df = pd.DataFrame(invalid_rows)
            st.dataframe(reason_df, width="stretch", hide_index=True)
            st.plotly_chart(
                px.bar(
                    reason_df,
                    x="invalid_reason",
                    y="count",
                    title="Rejected Candidates by Primary Reason",
                ),
                width="stretch",
            )
        else:
            st.success("No rejected candidates in this step.")

    if evaluated_step is None:
        st.info("Oracle candidate labels are unavailable for this geometry-only rollout step.")
        return
    score_rows = _live_step_candidate_score_rows(evaluated_step)
    if not score_rows:
        st.info("No per-valid-candidate score/provenance rows are available for this step.")
        return
    score_df = pd.DataFrame(score_rows)
    st.dataframe(score_df, width="stretch", hide_index=True)
    score_metric = _first_available_step_score_metric(score_df)
    if score_metric is None:
        st.info("No finite target-RRI or selection score metric is available for candidate score plots.")
        return

    score_col1, score_col2 = st.columns(2)
    hover_cols = [
        name
        for name in (
            "valid_index",
            "shell_index",
            "selected",
            "position",
            "strategy",
            "mixture",
            "component",
            "selection_score",
            "selection_probability",
            "target_root_gain",
            "target_rri",
        )
        if name in score_df.columns
    ]
    with score_col1:
        st.plotly_chart(
            px.scatter(
                score_df,
                x="selection_score",
                y=score_metric,
                color="position",
                symbol="selected",
                hover_data=hover_cols,
                title=f"Selection Score vs {current_scientific_label(score_metric)}",
            ),
            width="stretch",
        )
    with score_col2:
        st.plotly_chart(
            px.box(
                score_df,
                x="position",
                y=score_metric,
                color="selected",
                points="outliers",
                hover_data=hover_cols,
                title=f"{current_scientific_label(score_metric)} by Position Family",
            ),
            width="stretch",
        )
    if "selection_probability" in score_df and score_df["selection_probability"].notna().any():
        st.plotly_chart(
            px.histogram(
                score_df,
                x="selection_probability",
                color="selected",
                nbins=40,
                title="Selection Probability Mass",
            ),
            width="stretch",
        )


def _live_step_candidate_score_rows(step: EvaluatedRolloutStep) -> list[dict[str, Any]]:
    transition = step.transition
    evaluation = step.evaluation
    candidates = transition.candidates
    mask = candidates.mask_valid.detach().cpu().numpy().reshape(-1).astype(bool, copy=False)
    shell_indices = np.flatnonzero(mask)
    if shell_indices.size == 0:
        return []
    rows: list[dict[str, Any]] = []
    selection_scores = _aligned_valid_vector(transition.selection_scores, shell_indices=shell_indices)
    probabilities = _aligned_valid_vector(transition.selection_probabilities, shell_indices=shell_indices)
    logits = _aligned_valid_vector(transition.selection_logits, shell_indices=shell_indices)
    metric_vectors = evaluation.labels.metrics
    target_root_gain = _aligned_valid_vector(metric_vectors.get("target_root_gain"), shell_indices=shell_indices)
    target_rri = _aligned_valid_vector(
        metric_vectors.get("target_rri", metric_vectors.get("rri")), shell_indices=shell_indices
    )
    position_ids = _full_shell_int_values(getattr(candidates, "position_id", None), expected=mask.shape[0])
    strategy_ids = _full_shell_int_values(getattr(candidates, "strategy_id", None), expected=mask.shape[0])
    mixture_ids = _full_shell_int_values(getattr(candidates, "mixture_id", None), expected=mask.shape[0])
    sampler_probability = _full_shell_float_values(
        getattr(candidates, "sampler_probability", None), expected=mask.shape[0]
    )
    component_names = getattr(candidates, "component_name", None)
    selected_valid_index = int(transition.selected_valid_index)
    selected_shell_index = int(transition.selected_shell_index)
    for valid_index, shell_index in enumerate(shell_indices.tolist()):
        position_id = None if position_ids is None else int(position_ids[shell_index])
        strategy_id = None if strategy_ids is None else int(strategy_ids[shell_index])
        mixture_id = None if mixture_ids is None else int(mixture_ids[shell_index])
        component = None
        if isinstance(component_names, tuple) and shell_index < len(component_names):
            component = component_names[shell_index]
        rows.append(
            {
                "valid_index": valid_index,
                "shell_index": int(shell_index),
                "selected": valid_index == selected_valid_index or int(shell_index) == selected_shell_index,
                "position": "unknown" if position_id is None else decode_position_id(position_id),
                "strategy": "unknown" if strategy_id is None else decode_strategy_id(strategy_id),
                "mixture": "unknown" if mixture_id is None else f"component_{mixture_id}",
                "component": component,
                "selection_score": _array_value(selection_scores, valid_index),
                "selection_probability": _array_value(probabilities, valid_index),
                "selection_logit": _array_value(logits, valid_index),
                "target_root_gain": _array_value(target_root_gain, valid_index),
                "target_rri": _array_value(target_rri, valid_index),
                "sampler_probability": (
                    None if sampler_probability is None else _array_value(sampler_probability, int(shell_index))
                ),
            }
        )
    return rows


def _aligned_valid_vector(values: Any, *, shell_indices: np.ndarray) -> np.ndarray | None:
    if values is None:
        return None
    values_np = torch.as_tensor(values).detach().cpu().numpy().reshape(-1).astype(float, copy=False)
    if values_np.shape[0] == shell_indices.shape[0]:
        return values_np
    if values_np.shape[0] > int(shell_indices.max()):
        return np.asarray(values_np[shell_indices])
    return None


def _full_shell_int_values(values: Any, *, expected: int) -> np.ndarray | None:
    if values is None:
        return None
    values_np = torch.as_tensor(values).detach().cpu().numpy().reshape(-1)
    if values_np.shape[0] != expected:
        return None
    return values_np.astype(np.int64, copy=False)


def _full_shell_float_values(values: Any, *, expected: int) -> np.ndarray | None:
    if values is None:
        return None
    values_np = torch.as_tensor(values).detach().cpu().numpy().reshape(-1)
    if values_np.shape[0] != expected:
        return None
    return values_np.astype(float, copy=False)


def _array_value(values: np.ndarray | None, index: int) -> float | None:
    if values is None or index < 0 or index >= values.shape[0]:
        return None
    value = float(values[index])
    return value if np.isfinite(value) else None


def _first_available_step_score_metric(score_df: pd.DataFrame) -> str | None:
    for column in ("target_root_gain", "target_rri", "selection_score"):
        if column in score_df.columns and score_df[column].notna().any():
            return column
    return None


_ROLLOUT_PLOT_COLORS = (
    "#636EFA",
    "#EF553B",
    "#00CC96",
    "#AB63FA",
    "#FFA15A",
    "#19D3F3",
    "#FF6692",
    "#B6E880",
)


def _hex_to_rgba(hex_color: str, alpha: float) -> str:
    hex_clean = hex_color.lstrip("#")
    red, green, blue = (int(hex_clean[idx : idx + 2], 16) for idx in (0, 2, 4))
    return f"rgba({red},{green},{blue},{alpha})"


def _build_fanout_band_figure(step_df: pd.DataFrame) -> go.Figure:
    """Build the empirical candidate-band plot for live target-RRI rollouts."""

    fig = go.Figure()
    for traj_idx, traj_df in step_df.groupby("trajectory", sort=True):
        traj_sorted = traj_df.sort_values("step")
        color = _ROLLOUT_PLOT_COLORS[_int_scalar(traj_idx) % len(_ROLLOUT_PLOT_COLORS)]
        selected_metric = traj_sorted["selected_target_rri"]
        selected_identifier = "selected_target_rri"
        if "selected_target_root_gain" in traj_sorted and traj_sorted["selected_target_root_gain"].notna().any():
            selected_metric = traj_sorted["selected_target_root_gain"].fillna(selected_metric)
            selected_identifier = "selected_target_root_gain"
        fig.add_trace(
            go.Scatter(
                x=traj_sorted["step"],
                y=traj_sorted["fanout_q025"],
                mode="lines",
                line={"width": 0, "color": color},
                hoverinfo="skip",
                showlegend=False,
                name=f"traj {traj_idx} candidate q2.5",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=traj_sorted["step"],
                y=traj_sorted["fanout_q975"],
                mode="lines",
                fill="tonexty",
                fillcolor=_hex_to_rgba(color, 0.18),
                line={"width": 0, "color": color},
                name=f"traj {traj_idx} empirical 95% band",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=traj_sorted["step"],
                y=selected_metric,
                mode="lines+markers",
                line={"color": color, "width": 3},
                marker={"color": color, "size": 7},
                name=f"traj {traj_idx} selected {current_scientific_label(selected_identifier)}",
            )
        )
    fig.update_layout(
        title="Valid-candidate empirical central 95% range",
        xaxis_title="rollout step",
        yaxis_title=(f"{current_scientific_label('target_root_gain')} / {current_scientific_label('target_rri')}"),
    )
    return fig


def _target_rows_table(rows: tuple[OracleTargetTask, ...]) -> list[dict[str, Any]]:
    """Return a compact dataframe payload for target rows."""

    return target_selection_audit_rows(rows)


def _target_detail_row(row: OracleTargetTask) -> dict[str, Any]:
    """Return one target row with pose/crop-relevant fields."""

    return {
        "target_id": row.target_id,
        "source": ORACLE_TARGET_TASK_SOURCE,
        "source_index": int(row.source_index),
        "center_world": tuple(float(v) for v in row.descriptor.center_world),
        "extents": tuple(float(v) for v in row.descriptor.extents_m),
        "pose_world_object": tuple(float(v) for v in row.descriptor.pose_world_object),
        "relative_pose_reference_object": tuple(float(v) for v in row.descriptor.relative_pose_reference_object),
        "identity_status": row.identity_status,
    }


def _format_target_option(row: OracleTargetTask) -> str:
    return (
        f"target {row.target_row_id} · {row.descriptor.class_name} · "
        f"sem={row.descriptor.sem_id} inst={row.inst_id} · {row.identity_status}"
    )


def _add_target_overlays(
    builder: CounterfactualPlotBuilder,
    sample: VinOfflineSample,
    target: OracleTargetTask | None,
    *,
    show_actor_target: bool,
    show_gt_target: bool,
) -> None:
    """Add descriptor and GT-only target OBB overlays to a rollout plot."""

    if target is None:
        return
    if show_actor_target:
        builder.add_actor_visible_target_obb(target.descriptor)
    if not show_gt_target:
        return
    if target.identity_status != TargetTaskIdentityStatus.MATCHED.value:
        st.warning(
            "The active target has no valid matched GT crop; only the descriptor target OBB can be shown.",
        )
        return
    try:
        builder.add_obb(
            target_gt_obb_world(target, sample),
            name="Matched GT / evaluation crop",
            color="#00d4ff",
            width=6,
            opacity=0.95,
        )
    except ValueError as exc:
        st.warning(f"Matched GT target OBB unavailable: {exc}")


def _add_target_semidense_crop(
    builder: CounterfactualPlotBuilder,
    sample: VinOfflineSample,
    target: OracleTargetTask | None,
    *,
    crop_basis: str,
    max_points: int = 12000,
) -> None:
    """Overlay semidense points cropped to the descriptor or GT target OBB."""

    if target is None:
        return
    if crop_basis == "GT/evaluation OBB":
        if target.identity_status != TargetTaskIdentityStatus.MATCHED.value:
            st.warning("GT semidense crop unavailable because the active target has no valid GT match.")
            return
        try:
            gt_obb = target_gt_obb_world(target, sample)
        except ValueError as exc:
            st.warning(f"GT semidense crop unavailable: {exc}")
            return
        extents = (gt_obb.bb3_max_object - gt_obb.bb3_min_object).detach().cpu().numpy()
        builder.add_semidense_in_oriented_box(
            pose_world_object=gt_obb.T_world_object,
            extents=extents,
            name="Target semidense crop / GT evaluation",
            max_points=max_points,
            last_frame_only=False,
            color="cyan",
            size=3,
            opacity=0.85,
        )
        return

    builder.add_semidense_in_oriented_box(
        pose_world_object=target.descriptor.pose_world_object,
        extents=target.descriptor.extents_m,
        name="Target semidense crop / descriptor",
        max_points=max_points,
        last_frame_only=False,
        color="gold",
        size=3,
        opacity=0.85,
    )


def _render_live_rollouts_tab() -> None:
    st.header("Live Rollout Lab")
    st.caption(
        "Generate multi-step rollouts from VIN offline roots. Target-RRI mode samples geometry-valid Oracle "
        "tasks and passes sanitized descriptors to candidate generation; scene and geometry modes are diagnostics."
    )

    default_store = VinOfflineStoreConfig().store_dir
    with st.expander("Source sample and target selection", expanded=True):
        _info_popover("source sample and target selection", _SOURCE_TARGET_INFO)
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            store_dir = Path(
                st.text_input("VIN offline store", value=str(default_store), key="cf_store_dir")
            ).expanduser()
            split = st.selectbox("Split", options=["all", "train", "val"], index=0, key="cf_split")
            sample_index = int(
                st.number_input("Split-local sample index", min_value=0, value=0, step=1, key="cf_sample_index")
            )
        with col_b:
            target_k = int(st.slider("Max target tasks", min_value=1, max_value=12, value=3, step=1, key="cf_target_k"))
            target_seed = int(st.number_input("Selection seed", min_value=0, value=0, step=1, key="cf_target_seed"))
        with col_c:
            st.metric("Task admission", "finite GT OBB")
            st.caption("Selection uses seeded uniform sampling without replacement.")

    selector_cfg = OracleTargetTaskSamplerConfig(
        max_targets_per_sample=int(target_k),
        seed=int(target_seed),
    )
    load_key = f"{store_dir.resolve() if store_dir.exists() else store_dir}|{split}|{sample_index}|{config_signature(selector_cfg)}"
    cache = st.session_state.setdefault("cf_live_source_cache", {})
    if st.button("Load sample and targets", key="cf_load_sample_targets"):
        try:
            sample = _load_vin_offline_sample(store_dir=store_dir, split=str(split), sample_index=int(sample_index))
            target_result = OracleTargetTaskSampler(selector_cfg).sample(sample)
            cache[load_key] = {"sample": sample, "target_result": target_result}
        except Exception as exc:  # pragma: no cover - UI guard
            _report_exception(exc, context="Failed to load VIN offline sample and targets")
            cache.pop(load_key, None)

    payload = cache.get(load_key)
    if payload is None:
        st.info("Load a VIN offline sample to inspect oracle target tasks and generate live rollouts.")
        return

    sample = payload["sample"]
    target_result = payload["target_result"]
    st.subheader("Loaded Sample")
    _info_popover("loaded sample fields", _LOADED_SAMPLE_INFO)
    col_s1, col_s2, col_s3, col_s4 = st.columns(4)
    col_s1.metric("Scene", sample.scene_id)
    col_s2.metric("Snippet", sample.snippet_id)
    col_s3.metric("Source", target_result.source or "none")
    col_s4.metric("Selected targets", len(target_result.selected_rows))
    if target_result.warnings:
        st.warning("\n".join(target_result.warnings))

    st.dataframe(_target_rows_table(target_result.rows), width="stretch", hide_index=True)
    with st.expander("Target-selection score audit", expanded=False):
        render_target_selection_audit(target_result.rows, title="Oracle Target Tasks")
    selected_target = None
    if target_result.selected_rows:
        _info_popover("active target label", _ACTIVE_TARGET_INFO)
        selected_target = st.selectbox(
            "Active target",
            options=list(target_result.selected_rows),
            format_func=_format_target_option,
            key="cf_active_target",
        )
        st.json(_target_detail_row(selected_target), expanded=False)

    selected_candidate_profile: CandidateMixtureViewGeneratorConfig | None = None
    selected_candidate_profile_name = "(interactive legacy mixture)"
    with st.expander("Rollout generation", expanded=True):
        _info_popover("rollout generation controls", _ROLLOUT_GENERATION_INFO)
        cfg_col1, cfg_col2, cfg_col3 = st.columns(3)
        with cfg_col1:
            scoring_mode = st.selectbox(
                "Scoring mode",
                options=list(LiveRolloutScoringMode),
                index=0,
                format_func=lambda mode: mode.value,
                key="cf_scoring_mode",
            )
            profile_paths = _live_candidate_profile_paths()
            profile_by_name = {path.name: path for path in profile_paths}
            profile_options = ("(interactive legacy mixture)", *profile_by_name)
            # A profile can disappear when the app switches worktrees or the
            # config directory is refreshed.  Clear the stale widget value so
            # Streamlit does not render an apparently selected profile with an
            # empty search result list.
            if st.session_state.get("cf_candidate_profile") not in profile_options:
                st.session_state["cf_candidate_profile"] = profile_options[0]
            selected_candidate_profile_name = st.selectbox(
                "Candidate profile TOML",
                options=profile_options,
                key="cf_candidate_profile",
                format_func=lambda name: (
                    "Interactive legacy mixture" if name == "(interactive legacy mixture)" else _pretty_label(name)
                ),
                disabled=scoring_mode is not LiveRolloutScoringMode.TARGET_RRI,
                help=(
                    "Load a validated RolloutDatasetWriterConfig candidate mixture. "
                    "Interactive mode retains the legacy five-family controls."
                ),
            )
            if (
                selected_candidate_profile_name != "(interactive legacy mixture)"
                and scoring_mode is LiveRolloutScoringMode.TARGET_RRI
            ):
                try:
                    selected_candidate_profile = _load_live_candidate_profile(
                        profile_by_name[selected_candidate_profile_name]
                    )
                    st.caption(
                        f"Loaded {_pretty_label(selected_candidate_profile_name)} · "
                        f"{selected_candidate_profile.total_count} attempted candidates per step"
                    )
                    st.json(
                        [
                            {
                                "name": component.name,
                                "count": component.count,
                                "center": component.center.model_dump(mode="json"),
                                "gazes": [gaze.model_dump(mode="json") for gaze in component.gazes],
                            }
                            for component in selected_candidate_profile.components
                        ],
                        expanded=False,
                    )
                except Exception as exc:  # pragma: no cover - UI guard
                    st.error(f"Candidate profile unavailable: {exc}")
                    selected_candidate_profile = None
            elif selected_candidate_profile_name != "(interactive legacy mixture)":
                st.info(
                    "Candidate TOML profiles are used for target-RRI generation; geometry/scene modes use the interactive generator."
                )
            candidate_budget = int(
                st.slider(
                    "Candidates per step",
                    5,
                    128,
                    60,
                    step=1,
                    key="cf_candidate_budget",
                    disabled=selected_candidate_profile is not None,
                )
            )
            if selected_candidate_profile is not None:
                candidate_budget = selected_candidate_profile.total_count
            device = st.selectbox(
                "Generator device",
                options=_live_rollout_device_options(),
                index=0,
                key="cf_generator_device",
            )
            if str(device) == "cuda":
                st.caption(
                    "CUDA is preflighted before rollout generation; select CPU if this environment lacks GPU PyTorch3D."
                )
        with cfg_col2:
            horizon = int(st.slider("Horizon", min_value=1, max_value=5, value=3, step=1, key="cf_horizon"))
            branch_factor = int(
                st.slider("Branch factor", min_value=1, max_value=6, value=2, step=1, key="cf_branch_factor")
            )
            cap_beam = st.checkbox("Cap beam width", value=True, key="cf_beam_enabled")
            beam_width = (
                int(st.slider("Beam width", min_value=1, max_value=12, value=4, step=1, key="cf_beam_width"))
                if cap_beam
                else None
            )
        with cfg_col3:
            policy_options = list(CounterfactualSelectionPolicy)
            if scoring_mode is LiveRolloutScoringMode.GEOMETRY:
                policy_options = [
                    policy for policy in policy_options if policy is not CounterfactualSelectionPolicy.ORACLE_GREEDY
                ]
            selection_policy = st.selectbox(
                "Selection policy",
                options=policy_options,
                index=policy_options.index(CounterfactualSelectionPolicy.TEMPERATURE_SOFTMAX),
                format_func=lambda policy: policy.value,
                key="cf_selection_policy",
            )
            temperature = float(st.slider("Softmax temperature", 0.05, 5.0, 1.0, step=0.05, key="cf_temperature"))
            seed = int(st.number_input("Seed", min_value=0, value=0, step=1, key="cf_seed"))

        guard_col1, guard_col2, guard_col3 = st.columns(3)
        with guard_col1:
            min_history_distance = float(
                st.slider("Min history distance (m)", 0.0, 2.0, 0.0, step=0.05, key="cf_min_history_distance")
            )
        with guard_col2:
            min_sibling_distance = float(
                st.slider("Min sibling distance (m)", 0.0, 2.0, 0.15, step=0.05, key="cf_min_sibling_distance")
            )
        with guard_col3:
            log_timing = st.checkbox("Log rollout/scorer timing", value=False, key="cf_log_timing")

        target_counts = None
        if scoring_mode is LiveRolloutScoringMode.TARGET_RRI:
            _info_popover("target mixture families", _TARGET_MIXTURE_INFO)
            advanced_counts = st.checkbox(
                "Advanced target-mixture counts",
                value=False,
                key="cf_advanced_mixture_counts",
                disabled=selected_candidate_profile is not None,
            )
            if selected_candidate_profile is not None:
                st.caption("Family counts and center/gaze parameters come from the selected TOML profile.")
            elif advanced_counts:
                mix_cols = st.columns(5)
                target_counts = {
                    "target_bearing_local": int(
                        mix_cols[0].number_input("target_bearing_local", min_value=1, value=18, step=1)
                    ),
                    "forward_local": int(mix_cols[1].number_input("forward_local", min_value=1, value=18, step=1)),
                    "lateral_target_bypass": int(
                        mix_cols[2].number_input("lateral_target_bypass", min_value=1, value=12, step=1)
                    ),
                    "local_refinement": int(mix_cols[3].number_input("local_refinement", min_value=1, value=6, step=1)),
                    "revisit_backtrack": int(
                        mix_cols[4].number_input("revisit_backtrack", min_value=1, value=6, step=1)
                    ),
                }
                st.caption(f"Advanced mixture total: {sum(target_counts.values())} candidates per step.")
            else:
                target_counts = _target_mixture_counts_from_budget(candidate_budget)
                st.caption(
                    "Default target mixture: " + ", ".join(f"{name}={count}" for name, count in target_counts.items())
                )

    with st.expander("Scorer controls", expanded=False):
        _info_popover("scorer controls", _SCORER_CONTROLS_INFO)
        score_col1, score_col2, score_col3 = st.columns(3)
        with score_col1:
            backprojection_stride = int(
                st.slider("Backprojection stride", 1, 16, 1, step=1, key="cf_backprojection_stride")
            )
        with score_col2:
            target_crop_margin = float(
                st.slider("Target crop margin (m)", 0.0, 0.5, 0.0, step=0.01, key="cf_target_crop_margin")
            )
        with score_col3:
            min_current_target_points = int(
                st.slider("Min current target points", 1, 512, 1, step=1, key="cf_min_current_target_points")
            )
        include_scene_audit = st.checkbox(
            "Also compute scene RRI audit in target mode", value=False, key="cf_include_scene_audit"
        )

    candidate_config = _candidate_config_for_live_rollout(
        scoring_mode=scoring_mode,
        candidate_budget=int(candidate_budget if target_counts is None else sum(target_counts.values())),
        seed=int(seed),
        device=torch.device(str(device)),
        counts=target_counts,
        profile=selected_candidate_profile,
    )
    rollout_cfg = CounterfactualPoseGeneratorConfig(
        candidate_config=candidate_config,
        policy=RolloutPolicySpec(
            horizon=int(horizon),
            branch_factor=int(branch_factor),
            beam_width=beam_width,
            selection_policy=selection_policy,
            selection_temperature=float(temperature),
            min_history_distance_m=float(min_history_distance),
            min_sibling_distance_m=float(min_sibling_distance),
            seed=int(seed),
        ),
        log_timing=bool(log_timing),
        verbosity=Verbosity.NORMAL,
    )
    live_candidate_count = _candidate_config_count(candidate_config)
    depth_cfg = _live_depth_config(max_candidates=live_candidate_count, device=str(device))
    target_scorer_cfg = TargetRriScorerConfig(
        depth=depth_cfg,
        backprojection_stride=int(backprojection_stride),
        target_crop_margin_m=float(target_crop_margin),
        min_current_target_points=int(min_current_target_points),
        include_scene_rri=bool(include_scene_audit),
        log_timing=bool(log_timing),
    )
    scene_scorer_cfg = SceneRriScorerConfig(
        depth=depth_cfg,
        backprojection_stride=int(backprojection_stride),
    )

    run_key = "|".join(
        [
            load_key,
            scoring_mode.value,
            "" if selected_target is None else selected_target.target_id,
            config_signature(candidate_config),
            config_signature(rollout_cfg),
            config_signature(target_scorer_cfg),
            config_signature(scene_scorer_cfg),
        ]
    )
    rollout_cache = st.session_state.setdefault("cf_live_rollout_cache", {})
    if st.button("Run / refresh live rollouts", key="cf_run_live_rollouts"):
        try:
            with st.spinner("Generating live counterfactual rollouts..."):
                rollouts, log_text = _run_live_rollout(
                    sample=sample,
                    scoring_mode=scoring_mode,
                    target=selected_target,
                    candidate_config=candidate_config,
                    rollout_config=rollout_cfg,
                    target_scorer_config=target_scorer_cfg,
                    scene_scorer_config=scene_scorer_cfg,
                )
            rollout_cache[run_key] = {"rollouts": rollouts, "logs": log_text}
        except OracleReplayInvalidityError as exc:
            st.error(f"Target-RRI invalid ({exc.invalidity.reason.value}): {exc.invalidity.message}")
            rollout_cache.pop(run_key, None)
        except Exception as exc:  # pragma: no cover - UI guard
            _report_exception(exc, context="Live rollout generation failed")
            rollout_cache.pop(run_key, None)

    cached_rollout = rollout_cache.get(run_key)
    if cached_rollout is None:
        st.caption("Configure the rollout, then click run to materialize trajectories.")
        return

    rollouts = cached_rollout["rollouts"]
    log_text = cached_rollout["logs"]
    _render_rollout_result(
        sample,
        rollouts,
        target=selected_target,
        log_text=log_text,
        scoring_mode=scoring_mode,
    )


def _render_rollout_result(
    sample: VinOfflineSample,
    evaluated: EvaluatedRollout,
    *,
    target: OracleTargetTask | None,
    log_text: str,
    scoring_mode: LiveRolloutScoringMode,
) -> None:
    """Render one live rollout result."""

    rollouts = evaluated.result
    rows = _counterfactual_trajectory_rows(evaluated)
    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
    metric_col1.metric("Trajectories", len(rollouts.trajectories))
    metric_col2.metric("Horizon", rollouts.horizon)
    metric_col3.metric("Score label", rollouts.score_label)
    best_score = max((traj.cumulative_score for traj in rollouts.trajectories), default=0.0)
    metric_col4.metric("Best cumulative score", f"{best_score:.3f}")
    _info_popover("rollout result table and plots", _ROLLOUT_RESULT_INFO)
    if scoring_mode is LiveRolloutScoringMode.GEOMETRY:
        st.info("Geometry mode does not compute RRI; cumulative_rri is intentionally empty.")

    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    _render_live_rollout_metric_dashboard(evaluated, rows=rows, scoring_mode=scoring_mode)

    plot_tab, step_tab, depth_tab, log_tab = st.tabs(["Paths", "Step Shell", "Selected Depth", "Logs"])
    snippet = sample.efm_snippet_view
    with plot_tab:
        if snippet is not None:
            scene_camera, scene_options = scene_plot_options_ui(
                snippet,
                key_prefix="cf_path_scene",
                title="3D rollout scene",
                defaults=ROLLOUT_SCENE_DEFAULTS,
            )
            target_col1, target_col2, target_col3, frustum_col = st.columns(4)
            show_actor_target = target_col1.checkbox(
                "Show descriptor target OBB",
                value=target is not None,
                key="cf_path_actor_target_obb",
            )
            show_gt_target = target_col2.checkbox(
                "Show matched GT target OBB",
                value=bool(target is not None and target.identity_status == TargetTaskIdentityStatus.MATCHED.value),
                key="cf_path_gt_target_obb",
            )
            show_target_crop = target_col3.checkbox(
                "Show target semidense crop",
                value=target is not None,
                key="cf_path_target_semidense_crop",
            )
            show_selected_frusta = frustum_col.checkbox(
                "Overlay selected frusta",
                value=True,
                key="cf_show_selected_frusta",
            )
            crop_basis = st.selectbox(
                "Target crop basis",
                options=["Descriptor OBB", "GT/evaluation OBB"],
                index=0,
                key="cf_path_target_crop_basis",
                disabled=not show_target_crop,
            )
            selected_frustum_scale = float(
                st.slider(
                    "Selected frustum scale",
                    min_value=0.1,
                    max_value=2.0,
                    value=0.45,
                    step=0.05,
                    key="cf_selected_frustum_scale",
                    disabled=not show_selected_frusta,
                )
            )
            builder = CounterfactualPlotBuilder.from_rollouts(
                snippet,
                rollouts,
                title=_pretty_label("Counterfactual rollout paths"),
            )
            apply_scene_plot_options(builder, snippet, camera=scene_camera, options=scene_options)
            _add_target_overlays(
                builder,
                sample,
                target,
                show_actor_target=show_actor_target,
                show_gt_target=show_gt_target,
            )
            if show_target_crop:
                _add_target_semidense_crop(builder, sample, target, crop_basis=str(crop_basis))
            builder.add_counterfactual_paths(show_step_markers=True)
            if show_selected_frusta:
                builder = builder.add_counterfactual_selected_frusta(scale=selected_frustum_scale)
            st.plotly_chart(builder.finalize(), width="stretch")
        else:
            st.plotly_chart(plot_counterfactual_paths_simple(rollouts), width="stretch")

    with step_tab:
        if not rollouts.trajectories:
            st.info("No trajectories were generated.")
        else:
            trajectory_index = st.selectbox(
                "Trajectory",
                options=list(range(len(rollouts.trajectories))),
                format_func=lambda idx: (
                    f"traj {idx} · steps={rows[idx]['steps']} · score={rows[idx]['cumulative_score']:.3f}"
                ),
                key="cf_step_traj_idx",
            )
            trajectory = rollouts.trajectories[int(trajectory_index)]
            if not trajectory.steps:
                st.info("Selected trajectory terminated before choosing any rollout step.")
            else:
                step_display_index = st.slider(
                    "Step",
                    min_value=1,
                    max_value=len(trajectory.steps),
                    value=1,
                    step=1,
                    key="cf_step_idx",
                )
                include_rejected = st.checkbox("Show rejected candidates", value=False, key="cf_step_include_rejected")
                if snippet is None:
                    st.info("Step-shell plot requires the attached EFM snippet.")
                else:
                    step_camera, step_scene_options = scene_plot_options_ui(
                        snippet,
                        key_prefix="cf_step_scene",
                        title="3D step-shell scene",
                        defaults=ROLLOUT_SCENE_DEFAULTS,
                    )
                    step_target_col1, step_target_col2, step_target_col3, step_frustum_col = st.columns(4)
                    show_step_actor_target = step_target_col1.checkbox(
                        "Show descriptor target OBB",
                        value=target is not None,
                        key="cf_step_actor_target_obb",
                    )
                    show_step_gt_target = step_target_col2.checkbox(
                        "Show matched GT target OBB",
                        value=bool(
                            target is not None and target.identity_status == TargetTaskIdentityStatus.MATCHED.value
                        ),
                        key="cf_step_gt_target_obb",
                    )
                    show_step_target_crop = step_target_col3.checkbox(
                        "Show target semidense crop",
                        value=target is not None,
                        key="cf_step_target_semidense_crop",
                    )
                    show_candidate_frusta = step_frustum_col.checkbox(
                        "Show candidate frusta",
                        value=True,
                        key="cf_step_candidate_frusta",
                    )
                    color_metric = st.selectbox(
                        "Candidate color metric",
                        options=["selection_score", "selection_probability", "position_family"],
                        index=0,
                        key="cf_step_candidate_color_metric",
                    )
                    step_crop_basis = st.selectbox(
                        "Step target crop basis",
                        options=["Descriptor OBB", "GT/evaluation OBB"],
                        index=0,
                        key="cf_step_target_crop_basis",
                        disabled=not show_step_target_crop,
                    )
                    step_builder = CounterfactualPlotBuilder.from_rollouts(
                        snippet,
                        rollouts,
                        title=_pretty_label(f"Counterfactual step {step_display_index}"),
                    )
                    apply_scene_plot_options(step_builder, snippet, camera=step_camera, options=step_scene_options)
                    _add_target_overlays(
                        step_builder,
                        sample,
                        target,
                        show_actor_target=show_step_actor_target,
                        show_gt_target=show_step_gt_target,
                    )
                    if show_step_target_crop:
                        _add_target_semidense_crop(step_builder, sample, target, crop_basis=str(step_crop_basis))
                    step_builder.add_counterfactual_step_shell(
                        trajectory_index=int(trajectory_index),
                        step_index=int(step_display_index - 1),
                        include_rejected=include_rejected,
                        show_frusta=show_candidate_frusta,
                        candidate_color_metric=str(color_metric),
                    )
                    step_fig = step_builder.finalize()
                    st.plotly_chart(step_fig, width="stretch")
                    with st.expander("Step candidate fanout diagnostics", expanded=True):
                        evaluated_step = evaluated.step(int(trajectory_index), int(step_display_index - 1))
                        _render_live_step_candidate_diagnostics(
                            trajectory.steps[int(step_display_index - 1)],
                            evaluated_step,
                        )

    with depth_tab:
        _info_popover("selected depth", _LIVE_SELECTED_DEPTH_INFO)
        _render_live_selected_depth_tab(evaluated, sample=sample, target=target)

    with log_tab:
        _info_popover("rollout logs", _LIVE_LOG_INFO)
        if log_text.strip():
            st.code(log_text, language="text")
        else:
            st.info("No Console output was captured for this rollout run.")


def _render_live_selected_depth_tab(
    evaluated: EvaluatedRollout,
    *,
    sample: VinOfflineSample,
    target: OracleTargetTask | None,
) -> None:
    rollouts = evaluated.result
    rows = pd.DataFrame(_live_selected_depth_rows(evaluated))
    if rows.empty:
        st.info("No rollout steps are available for selected-depth inspection.")
        return

    available = rows["available"].astype(bool)
    metric_cols = st.columns(4)
    metric_cols[0].metric("Selected steps", len(rows))
    metric_cols[1].metric("Retained depth rows", int(available.sum()))
    metric_cols[2].metric("Mean finite pixels", _format_optional_metric(rows["finite_fraction"].dropna().mean()))
    metric_cols[3].metric("Mean selected depth", _format_optional_metric(rows["depth_mean_m"].dropna().mean()))

    display_cols = [
        "trajectory",
        "step",
        "available",
        "valid_fraction",
        "finite_fraction",
        "depth_min_m",
        "depth_mean_m",
        "depth_max_m",
        "selected_score",
        "selected_policy",
        "warning",
    ]
    st.dataframe(rows[[col for col in display_cols if col in rows.columns]], width="stretch", hide_index=True)

    preview_rows = rows[available]
    if preview_rows.empty:
        st.warning("No selected-depth images were retained for this live rollout result.")
        return

    preview_options = list(range(len(preview_rows)))
    selected_preview_index = int(
        st.selectbox(
            "Live selected-depth step",
            options=preview_options,
            format_func=lambda index: _format_live_selected_depth_option(preview_rows.iloc[int(index)]),
            key="cf_live_selected_depth_step",
        )
    )
    selected = preview_rows.iloc[selected_preview_index]
    trajectory = rollouts.trajectories[int(selected["trajectory"])]
    transition = trajectory.steps[int(selected["step"]) - 1]
    step = evaluated.step(int(selected["trajectory"]), transition.step_index)
    if step is None:
        st.warning("Oracle evidence is unavailable for this selected step.")
        return
    overlay_col1, overlay_col2 = st.columns(2)
    show_actor_projection = overlay_col1.checkbox(
        "Project descriptor target OBB",
        value=target is not None,
        key="cf_live_depth_actor_obb",
    )
    show_gt_projection = overlay_col2.checkbox(
        "Project matched GT target OBB",
        value=bool(target is not None and target.identity_status == TargetTaskIdentityStatus.MATCHED.value),
        key="cf_live_depth_gt_obb",
    )
    depth = torch.as_tensor(step.evaluation.evidence.selected_depth_m, dtype=torch.float32)
    valid_mask = torch.as_tensor(step.evaluation.evidence.selected_depth_valid_mask, dtype=torch.bool)
    depth_plot = depth.clone()
    depth_plot[~(valid_mask & torch.isfinite(depth_plot))] = torch.nan
    finite = depth_plot[torch.isfinite(depth_plot)]
    zmax = float(finite.max().item()) if finite.numel() else None
    overlays = _live_depth_target_overlays(
        step,
        sample=sample,
        target=target,
        show_actor_target=show_actor_projection,
        show_gt_target=show_gt_projection,
    )
    title = f"traj {int(selected['trajectory'])} · step {int(selected['step'])}"
    if overlays:
        fig = depth_grid_with_box_overlays(
            depth_plot.unsqueeze(0),
            overlays=[overlays],
            titles=[title],
            max_cols=1,
            zmax=zmax,
        )
    else:
        fig = depth_grid(depth_plot.unsqueeze(0), titles=[title], max_cols=1, zmax=zmax)
        if show_actor_projection or show_gt_projection:
            st.warning(
                "Target OBB projection is unavailable for this step. Retained depth requires focal, principal-point, "
                "target OBB, and selected pose metadata."
            )
    st.plotly_chart(fig, width="stretch")
    st.json(
        {
            "focal_px": step.evaluation.evidence.selected_depth_focal_px,
            "principal_point_px": step.evaluation.evidence.selected_depth_principal_point_px,
            "image_size_hw": step.evaluation.evidence.selected_depth_image_size_hw,
            "selected_valid_index": int(step.transition.selected_valid_index),
            "selected_shell_index": int(step.transition.selected_shell_index),
        },
        expanded=False,
    )


def _live_selected_depth_rows(evaluated: EvaluatedRollout) -> list[dict[str, Any]]:
    """Return selected-depth availability and summary stats for live rollout steps."""

    rows: list[dict[str, Any]] = []
    for trajectory_index, trajectory in enumerate(evaluated.result.trajectories):
        for transition in trajectory.steps:
            step = evaluated.step(trajectory_index, transition.step_index)
            base = {
                "trajectory": int(trajectory_index),
                "step": int(transition.step_index) + 1,
                "available": False,
                "valid_pixels": None,
                "finite_pixels": None,
                "pixel_count": None,
                "valid_fraction": None,
                "finite_fraction": None,
                "depth_min_m": None,
                "depth_mean_m": None,
                "depth_max_m": None,
                "selected_score": float(transition.selection_score),
                "selected_policy": transition.selection_policy,
                "warning": "",
            }
            if (
                step is None
                or step.evaluation.evidence.selected_depth_m is None
                or step.evaluation.evidence.selected_depth_valid_mask is None
            ):
                rows.append({**base, "warning": "selected_depth_m/valid_mask not retained for this live step."})
                continue
            depth = torch.as_tensor(step.evaluation.evidence.selected_depth_m, dtype=torch.float32)
            valid_mask = torch.as_tensor(step.evaluation.evidence.selected_depth_valid_mask, dtype=torch.bool)
            if depth.ndim != 2 or valid_mask.shape != depth.shape:
                rows.append(
                    {
                        **base,
                        "warning": f"selected depth shape mismatch: depth={tuple(depth.shape)} mask={tuple(valid_mask.shape)}.",
                    }
                )
                continue
            finite_valid = valid_mask & torch.isfinite(depth)
            valid_depth = depth[finite_valid]
            pixel_count = int(depth.numel())
            valid_pixels = int(valid_mask.sum().item())
            finite_pixels = int(finite_valid.sum().item())
            rows.append(
                {
                    **base,
                    "available": True,
                    "valid_pixels": valid_pixels,
                    "finite_pixels": finite_pixels,
                    "pixel_count": pixel_count,
                    "valid_fraction": _safe_fraction(valid_pixels, pixel_count),
                    "finite_fraction": _safe_fraction(finite_pixels, pixel_count),
                    "depth_min_m": None if valid_depth.numel() == 0 else float(valid_depth.min().item()),
                    "depth_mean_m": None if valid_depth.numel() == 0 else float(valid_depth.mean().item()),
                    "depth_max_m": None if valid_depth.numel() == 0 else float(valid_depth.max().item()),
                }
            )
    return rows


def _live_depth_target_overlays(
    step: EvaluatedRolloutStep,
    *,
    sample: VinOfflineSample,
    target: OracleTargetTask | None,
    show_actor_target: bool,
    show_gt_target: bool,
) -> list[DepthBoxOverlay]:
    """Build projected actor/GT target overlays for one selected live depth."""

    if target is None:
        return []
    focal = step.evaluation.evidence.selected_depth_focal_px
    principal = step.evaluation.evidence.selected_depth_principal_point_px
    if focal is None or principal is None:
        return []

    overlays: list[DepthBoxOverlay] = []
    pose_world_cam = step.transition.selected_pose_world
    if show_actor_target:
        actor_corners = _oriented_box_corners_world(
            target.descriptor.pose_world_object,
            target.descriptor.extents_m,
        )
        overlays.append(
            DepthBoxOverlay(
                corners_px=project_world_points_to_image(
                    actor_corners,
                    pose_world_cam,
                    focal_px=(float(focal[0]), float(focal[1])),
                    principal_point_px=(float(principal[0]), float(principal[1])),
                ),
                name="Descriptor target OBB",
                color="#ff2f74",
                width=4,
            )
        )
    if show_gt_target and target.identity_status == TargetTaskIdentityStatus.MATCHED.value:
        try:
            gt_corners = target_gt_obb_world(target, sample).bb3corners_world.reshape(8, 3)
        except ValueError:
            gt_corners = None
        if gt_corners is not None:
            overlays.append(
                DepthBoxOverlay(
                    corners_px=project_world_points_to_image(
                        gt_corners,
                        pose_world_cam,
                        focal_px=(float(focal[0]), float(focal[1])),
                        principal_point_px=(float(principal[0]), float(principal[1])),
                    ),
                    name="Matched GT target OBB",
                    color="#00d4ff",
                    width=4,
                )
            )
    return overlays


def _oriented_box_corners_world(
    pose_world_object: tuple[float, ...] | np.ndarray | torch.Tensor,
    extents: tuple[float, ...] | np.ndarray | torch.Tensor,
) -> torch.Tensor:
    pose = PoseTW(torch.as_tensor(pose_world_object, dtype=torch.float32).reshape(-1))
    half = torch.as_tensor(extents, dtype=torch.float32).reshape(3) / 2.0
    signs = torch.tensor(
        [[-1, -1, -1], [1, -1, -1], [1, 1, -1], [-1, 1, -1], [-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1]],
        dtype=torch.float32,
    )
    transform: Callable[[torch.Tensor], Any] = pose.transform
    return cast(torch.Tensor, transform(signs * half))


def _format_live_selected_depth_option(row: pd.Series) -> str:
    return (
        f"traj {int(row['trajectory'])} · step {int(row['step'])} · "
        f"finite={_format_optional_metric(row.get('finite_fraction'))} · "
        f"mean={_format_optional_metric(row.get('depth_mean_m'))}m"
    )


def _safe_fraction(numerator: int, denominator: int) -> float | None:
    return None if denominator <= 0 else float(numerator) / float(denominator)


def _render_live_rollout_metric_dashboard(
    evaluated: EvaluatedRollout,
    *,
    rows: list[dict[str, int | float | bool | None]],
    scoring_mode: LiveRolloutScoringMode,
) -> None:
    """Render branch-summary RRI plots for live rollout evidence."""

    if scoring_mode is LiveRolloutScoringMode.GEOMETRY:
        return

    rows_df = pd.DataFrame(rows)
    step_df = _trajectory_metric_rows(evaluated)
    metric_cols = st.columns(4)
    if rows_df.empty:
        metric_cols[0].metric("Best branch", "n/a")
        metric_cols[1].metric("Best G_0^(H)", "n/a")
        metric_cols[2].metric("Best J_e^(H)", "n/a")
        metric_cols[3].metric("Mean valid fanout", "n/a")
        _info_popover("trajectory objective metrics", _LIVE_TRAJECTORY_OBJECTIVE_INFO)
        return

    cumulative_score = pd.to_numeric(rows_df["cumulative_score"], errors="coerce")
    g_target = pd.to_numeric(rows_df["G_target"], errors="coerce")
    j_endpoint = pd.to_numeric(rows_df["J_endpoint"], errors="coerce")
    best_idx = int(cumulative_score.idxmax())
    metric_cols[0].metric("Best branch", _int_scalar(rows_df.loc[best_idx, "trajectory"]))
    metric_cols[1].metric(current_scientific_label("return_h"), _format_optional_metric(g_target.max()))
    metric_cols[2].metric(current_scientific_label("endpoint_gain"), _format_optional_metric(j_endpoint.max()))
    mean_fanout = None if step_df.empty else step_df["valid_candidates"].mean()
    metric_cols[3].metric("Mean valid fanout", _format_optional_metric(mean_fanout))
    _info_popover("trajectory objective metrics", _LIVE_TRAJECTORY_OBJECTIVE_INFO)

    if step_df.empty:
        st.info("No selected rollout steps are available for metric plots.")
        return

    rri_fig = go.Figure()
    for traj_idx, traj_df in step_df.groupby("trajectory", sort=True):
        rri_fig.add_trace(
            go.Scatter(
                x=traj_df["step"],
                y=traj_df["selected_target_root_gain"].fillna(traj_df["selected_target_rri"]),
                mode="lines+markers",
                name=f"traj {traj_idx} selected {current_scientific_label('selected_target_root_gain')}",
            )
        )
        rri_fig.add_trace(
            go.Scatter(
                x=traj_df["step"],
                y=traj_df["G_target"],
                mode="lines+markers",
                name=f"traj {traj_idx} {current_scientific_label('cumulative_target_root_gain')} prefix",
                line={"dash": "dash"},
            )
        )
    rri_fig.update_layout(
        title="Selected target return by rollout step",
        xaxis_title="rollout step",
        yaxis_title=(f"{current_scientific_label('target_root_gain')} / {current_scientific_label('return_h')}"),
    )

    fanout_fig = _build_fanout_band_figure(step_df)
    render_scientific_notation(
        "selected_target_root_gain",
        "cumulative_target_root_gain",
        "return_h",
        "endpoint_gain",
        "log_gain",
    )

    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        _render_live_quality_plot(
            rri_fig,
            label="selected target return",
            context=_LIVE_SELECTED_RETURN_INFO,
            log_y_key="live-selected-target-return",
        )
    with chart_col2:
        _render_live_quality_plot(
            fanout_fig,
            label="valid candidate return band",
            context=_LIVE_FANOUT_BAND_INFO,
            log_y_key="live-valid-candidate-band",
        )
        st.caption(
            "Band shows the empirical 2.5-97.5 percentile range of valid candidate target root gain when "
            "available, falling back to target RRI; the selected line shows the action actually taken."
        )

    top_rows: list[dict[str, int | float]] = []
    for row in cast(list[dict[str, Any]], step_df.to_dict("records")):
        top_values = row.get("top_target_root_gain")
        if not isinstance(top_values, list):
            continue
        for rank, value in enumerate(top_values, start=1):
            top_rows.append(
                {
                    "trajectory": _int_scalar(row.get("trajectory")),
                    "step": _int_scalar(row.get("step")),
                    "rank": rank,
                    "top_target_root_gain": float(value),
                }
            )
    if top_rows:
        top_df = pd.DataFrame(top_rows)
        top_fig = go.Figure()
        for (traj_idx, rank), rank_df in top_df.groupby(["trajectory", "rank"], sort=True):
            top_fig.add_trace(
                go.Scatter(
                    x=rank_df["step"],
                    y=rank_df["top_target_root_gain"],
                    mode="lines+markers",
                    name=f"traj {traj_idx} top-{rank}",
                )
            )
        top_fig.update_layout(
            title="Top-k valid candidate target root gain per step",
            xaxis_title="rollout step",
            yaxis_title="target root gain",
        )
        _render_live_quality_plot(
            top_fig,
            label="top-k candidate headroom",
            context=_LIVE_TOPK_CANDIDATE_INFO,
            log_y_key="live-top-k-headroom",
        )

    if rows_df["J_endpoint"].notna().any() or rows_df["log_gain"].notna().any():
        endpoint_fig = go.Figure()
        endpoint_fig.add_trace(go.Bar(x=rows_df["trajectory"], y=rows_df["J_endpoint"], name="J_e,Delta^(H)"))
        endpoint_fig.add_trace(go.Bar(x=rows_df["trajectory"], y=rows_df["log_gain"], name="log gain"))
        endpoint_fig.update_layout(
            title="Endpoint target-quality metrics",
            xaxis_title="trajectory",
            yaxis_title="gain",
            barmode="group",
        )
        _render_live_quality_plot(
            endpoint_fig,
            label="endpoint target-quality metrics",
            context=_LIVE_ENDPOINT_METRIC_INFO,
            log_y_key="live-endpoint-quality",
        )
    else:
        _info_popover("endpoint target-quality metrics", _LIVE_ENDPOINT_METRIC_INFO)
        st.caption(
            "Endpoint `J_e^(H)` and log-gain are unavailable for this run because selected target point-mesh before/after fields were not emitted."
        )


def _render_live_quality_plot(
    fig: go.Figure,
    *,
    label: str,
    context: str,
    log_y_key: str,
) -> None:
    """Render one live trajectory with context and an independent axis control."""

    _info_popover(
        label,
        context + "\n\n**Axis scale:** Linear by default. Logarithmic scale is independently selectable for this plot; "
        "zero and negative observations are not visible on a logarithmic axis.",
    )
    rendered, _ = _plot_with_y_axis_control(fig, key=log_y_key)
    st.plotly_chart(rendered, width="stretch")


def render_counterfactual_rollouts_page() -> None:
    """Render live target-RRI rollout generation and evaluation."""

    _info_popover(
        "live target-rri rollouts",
        "Target-RRI mode loads a VIN offline sample, samples an Oracle target task, "
        "passes a sanitized descriptor to candidate generation, and scores rollout branches "
        "with target-specific oracle RRI. Inspect persisted rollout Zarr artifacts under "
        "Training Data → Rollout Supervision.",
    )
    _render_live_rollouts_tab()


__all__ = [
    "LiveRolloutScoringMode",
    "render_counterfactual_rollouts_page",
]
