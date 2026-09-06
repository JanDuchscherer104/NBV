#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs
#import "../../draft_markers.typ": thesis_status
#import "../../../shared/tables.typ": publication-table

== Current and Target Actor State <sec:thesis-scene-representation>

#thesis_status(
  implementation: "partial",
  evidence: "pending",
  citation: [@EFM3D-straub2024 @POMDPRobotics-lauri2023],
  source: "aria_nbv/aria_nbv/targets/protocol.py; aria_nbv/aria_nbv/targets/selection.py; aria_nbv/aria_nbv/oracle/pipelines/campaign.py; aria_nbv/aria_nbv/oracle/pipelines/rollout_dataset.py; aria_nbv/aria_nbv/data_handling/qh_data/views.py; aria_nbv/aria_nbv/vin/modules/qh_scene_encoders.py; aria_nbv/aria_nbv/rollouts/qh_reader.py; aria_nbv/aria_nbv/vin/models/target_finite_horizon.py",
  gate: [freeze and evaluate an actor-visible target corpus and action-support protocol; implement the causal state-update contract; pass source-dropout, no-future-observation, leakage, and held-out task-sufficiency tests],
)[The selected #symb.rl.s_pose baseline and the independent `v1_observed` descriptor path are implemented and tested. The current selected experiment still uses privileged `v0_gt_input` and `oracle_action_mask_v1`; no frozen actor-visible target, action-support, or causal observation-updated state evidence yet supports the scientific target.]

The @rollout-state:short is the information available before selecting action
#symb.rl.a, not every quantity co-located in a replay row. Oracle target gains, mesh crops,
ground-truth associations, current all-candidate renders, and labels are
excluded from the scorer graph. Three independent protocol axes matter. The
target-source axis distinguishes non-deployable `v0_gt_input` geometry from a
`v1_observed` descriptor constructed from actor-visible observations with bound
source and construction provenance. The dynamic-state axis distinguishes the
pose-only #symb.rl.s_pose carrier from a state updated with selected observations.
The action-support axis distinguishes the current mesh-derived
`oracle_action_mask_v1` from actor-observed support or a separately calibrated
learned-feasibility route. Sharing tensor shapes or field names across these
axes does not make their scientific claims interchangeable.

Both the current and target states retain the same decision interface,

$
  #eqs.scene.actor_state_read
$

but differ in what the state makes available to that read. The current root
component contains semidense evidence and lossy global moments of locally
supported EFM3D features. Its dynamic component is only the strictly causal
selected-pose prefix. Candidate regeneration updates the reference pose,
prefix, remaining budget, and action table; it does not imply a new RGB
observation, a refreshed EFM3D field, or fused selected depth.

#figure(
  publication-table(
    text-size: 8.2pt,
    columns: (0.72fr, 1.18fr, 1.58fr),
    header: ([*Component*], [*Current realization*], [*Scientific target*]),
    rows: (
      [Root scene], [immutable semidense points and global moments of locally supported EFM3D features], [immutable actor-visible evidence with explicit finite support and missingness; absent evidence must not mean observed free space],
      [Target], [selected experiment: privileged `v0_gt_input`; an independent `v1_observed` admission and I/O path is implemented but not frozen or evaluated], [`v1_observed`: actor-visible identity and geometry with support, source, construction provenance, and explicit matching failures],
      [Dynamic state], [#symb.rl.selected_pose_prefix only], [a strictly causal update from the selected observation that preserves observed surface, observed free, unknown, support, uncertainty, source, and recency],
      [Action support], [`oracle_action_mask_v1`: privileged mesh-derived physical-validity support], [`actor_observed_action_mask_v1`, or a learned-feasibility route with frozen calibration, threshold, abstention, and false-valid evidence],
      [Decision context], [#symb.rl.candidate_table, #symb.rl.budget, and #symb.rl.requested_horizon under the named oracle-support protocol], [the same finite-candidate interface under actor-visible target, state, and action-support protocols],
    ),
  ),
  caption: [Current baseline and scientific target. The right column is a promotion contract: it states information that must be represented and tested, not an architecture already implemented or a result already obtained.],
) <tab:thesis-counterfactual-state-protocols>

The @minimal-counterfactual-state:short is intentionally a semantic contract
rather than a premature choice among points, voxels, rays, or another carrier. A proposed
carrier is admissible only if its deterministic fusion rule exposes source and
availability, uses the selected actor-visible observation and no future or
unselected render, and preserves the distinctions in
@tab:thesis-counterfactual-state-protocols. Source-dropout,
no-future-observation, and leakage tests establish the information boundary; held-out
task-sufficiency evidence must then show that the retained distinctions are
useful for the target-specific value task.

=== Sufficiency and the local-evidence limit

A decision state is task-sufficient for this study only if it preserves the
distinctions needed to predict target-specific future return. Under partial
observability, this is an empirical representation requirement rather than a
claim that the study solves a general belief-state POMDP
@POMDPRobotics-lauri2023. #symb.rl.s_pose cannot satisfy that
condition by construction when two histories share poses but reveal different
surfaces, occlusions, or free-space evidence. It is therefore a deliberately
compact baseline and an interface test, not a claim that pose history is a
complete reconstruction state.

// Evidence map:
// - @POMDPRobotics-lauri2023 -> docs/literature/tex-src/arXiv-POMDP-Robotics-Survey/root.tex:589-606 (history, belief state, and sufficient statistic under partial observability)
// - @EFM3D-straub2024 -> docs/literature/tex-src/arXiv-EFM3D/method.tex:15-42 (calibrated feature lifting and finite local voxel support)

@egocentric-foundation-model-3d:short reinforces this limit. Its
@egocentric-voxel-lifting:short field has an explicit pose and finite extent
@EFM3D-straub2024. A target or candidate outside that
extent may remain physically valid while lacking local lifted evidence. Global
moments further remove spatial correspondence. The selected method can test
whether this compact context contains usable signal, but a failure cannot be
attributed to value learning alone, and a success cannot establish spatial
state sufficiency.

=== Candidate realizations of the state contract

The scientific target determines which distinctions must survive; it does not
determine the carrier. This separates a representational question—what
information is retained—from an encoder question—how that information is
compressed and queried. The relevant alternatives therefore remain visible,
but their status is explicit.

#figure(
  publication-table(
    text-size: 7.8pt,
    columns: (0.8fr, 0.82fr, 1.34fr, 1.45fr),
    header: ([*Carrier or context*], [*Scientific role*], [*Distinction retained*], [*Limitation and promotion condition*]),
    rows: (
      [Root moments + #symb.rl.selected_pose_prefix], [selected #symb.rl.s_pose], [Cheap root context and causal pose history.], [No selected-observation update or spatial correspondence; interface baseline only.],
      [Selected-surface point residual], [implemented privileged control #symb.rl.s_surface], [Causal selected surfaces in the current-camera frame.], [Conflates observed free with unknown and is density weighted; requires a frozen matched receipt.],
      [Sparse ray-aware memory #symb.scene.ray_memory_t], [planned candidate #symb.rl.s_ray], [Observed surface, free, unknown, support, uncertainty, source, and recency @EFM3D-straub2024.], [Requires deterministic actor-visible fusion, leakage tests, and candidate-relative query evidence.],
      [Candidate-relative readout of persisted local EVL], [contingent readout ablation], [Pool target support, candidate-frustum support, and their intersection from #symb.scene.evl_local without rerunning EFM3D.], [Tests whether root moments discard spatial correspondence; does not add evidence outside the persisted local field.],
      [Target-centred EVL re-lifting], [contingent representation ablation], [Logged EFM3D evidence when target support lies outside the root field @EFM3D-straub2024.], [May shift the learned 3D-neck distribution; compare first with simpler logged-feature pooling.],
      [Appearance attached to observed points], [contingent representation ablation], [Logged semantics or texture beyond the local EVL extent @EFM3D-straub2024.], [Requires visibility, source lineage, compression, and explicit missingness.],
      [Sparse TSDF/SDF or point encoder], [contingent encoder ablation], [Metric spatial structure with fixed-width learned tokens @EFM3D-straub2024.], [Must preserve observation weight and unknown-space semantics rather than only occupied surfaces.],
      [Object-aware 3DGS], [exploratory idea], [Renderable memory, soft target membership, and primitive confidence @ObjectCentricNBV-jeong2026.], [Per-scene optimization and mask supervision redefine cost and state; justify only after a renderability failure.],
      [SceneScript context], [exploratory idea], [Broad layout and object hypotheses @SceneScript-avetisyan2024.], [Global semantics do not replace causal local free/unknown evidence.],
    ),
  ),
  caption: [Representation design space ordered by scientific role, not presumed performance. A carrier is promoted only when it tests a diagnosed information loss under the same task, action, replay, and evaluation contracts.],
) <tab:thesis-scene-representation-design-space>

The first comparison is #symb.rl.s_pose against the source-matched privileged
#symb.rl.s_surface control with identity-start initialization because it asks
whether any selected-surface signal survives the current compression seam.
This is not a parameter-, capacity-, runtime-, or optimization-matched contrast:
it estimates the complete S1 package of geometry consumption, point encoding,
initialization, and training. A positive result would motivate an actor-visible
version; a null result would remain ambiguous between absent signal and a lossy
point summary. Before re-lifting EFM3D or introducing a new carrier, a
candidate-relative readout of #symb.scene.evl_local can separate missing evidence
from correspondence lost by root pooling. #symb.rl.s_ray is therefore the primary
planned realization of the complete state contract, but it is promoted only
after actor-visible observations and deterministic fusion exist. The remaining
carriers are conditional probes of specific failures, not parallel thesis
methods and not discarded ideas.

// Evidence map:
// - @EFM3D-straub2024 -> docs/literature/tex-src/arXiv-EFM3D/method.tex:15-42; docs/literature/tex-src/arXiv-EFM3D/supplemental_text.tex:113-124; docs/literature/tex-src/arXiv-EFM3D/persistence.tex:42-48 (finite lifted support, surface/free-space evidence, and weighted TSDF or occupancy fusion)
// - @ObjectCentricNBV-jeong2026 -> docs/literature/tex-src/arXiv-Instance-NBV/ver3_rpm/3_method_ver3_rpm.tex:48-99,179-214 (per-Gaussian object features, opacity/confidence, renderable outputs, and repeated map optimization)
// - @SceneScript-avetisyan2024 -> docs/literature/tex-src/arXiv-scene-script/sections/introduction.tex:14-28; docs/literature/tex-src/arXiv-scene-script/sections/structured_scene_language.tex:19-63 (structured layout and object commands, global scene representation, and scope)
