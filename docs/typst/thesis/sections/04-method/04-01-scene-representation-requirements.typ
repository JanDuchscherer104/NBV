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
  gate: [freeze and evaluate an actor-visible target corpus; implement the causal state-update contract; pass source-dropout, no-future-observation, leakage, and held-out task-sufficiency tests],
)[The `S0-pose` baseline and the independent `v1_observed` descriptor path are implemented and tested. The current selected experiment still uses privileged `v0_gt_input`; no frozen `v1_observed` evaluation or causal observation-updated actor state yet supports the scientific target.]

The actor state is the information available before selecting action $a_t$, not
every quantity co-located in a replay row. Oracle target gains, mesh crops,
ground-truth associations, current all-candidate renders, and labels are
excluded from the scorer graph. Two independent protocol axes matter. The
target-source axis distinguishes non-deployable `v0_gt_input` geometry from a
`v1_observed` descriptor constructed from actor-visible observations with bound
source and construction provenance. The dynamic-state axis distinguishes the
pose-only `S0-pose` carrier from a state updated with selected observations.
Sharing tensor shapes across either axis does not make their scientific claims
interchangeable.

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
      [Dynamic state], [selected poses $bold(H)_t$ only], [a strictly causal update from the selected observation that preserves observed surface, observed free, unknown, support, uncertainty, source, and recency],
      [Decision context], [candidate rows, hard mask, $b_t$, and $h$], [the same finite support plus target- and candidate-relative access to the actor-visible state needed for target-specific return],
    ),
  ),
  caption: [Current baseline and scientific target. The right column is a promotion contract: it states information that must be represented and tested, not an architecture already implemented or a result already obtained.],
) <tab:thesis-counterfactual-state-protocols>

The scientific target is intentionally a semantic contract rather than a
premature choice among points, voxels, rays, or another carrier. A proposed
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
@POMDPRobotics-lauri2023. `S0-pose` cannot satisfy that
condition by construction when two histories share poses but reveal different
surfaces, occlusions, or free-space evidence. It is therefore a deliberately
compact baseline and an interface test, not a claim that pose history is a
complete reconstruction state.

// Evidence map:
// - @POMDPRobotics-lauri2023 -> docs/literature/tex-src/arXiv-POMDP-Robotics-Survey/root.tex:589-606 (history, belief state, and sufficient statistic under partial observability)
// - @EFM3D-straub2024 -> docs/literature/tex-src/arXiv-EFM3D/method.tex:15-42 (calibrated feature lifting and finite local voxel support)

EFM3D reinforces this limit. Its gravity-aligned voxel field has an explicit
pose and finite extent @EFM3D-straub2024. A target or candidate outside that
extent may remain physically valid while lacking local lifted evidence. Global
moments further remove spatial correspondence. The selected method can test
whether this compact context contains usable signal, but a failure cannot be
attributed to value learning alone, and a success cannot establish spatial
state sufficiency. Richer causal surface or ray memories are kept outside the
selected method until a frozen comparison isolates their added information.
