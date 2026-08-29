#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs
#import "../../draft_markers.typ": thesis_status
#import "../../../shared/tables.typ": publication-table

== Selected Actor State <sec:thesis-scene-representation>

#thesis_status(
  implementation: "implemented",
  evidence: "pending",
  citation: [@EFM3D-straub2024],
  source: "aria_nbv/aria_nbv/data_handling/qh_data/views.py; aria_nbv/aria_nbv/rollouts/qh_reader.py; aria_nbv/aria_nbv/vin/models/target_finite_horizon.py; aria_nbv/tests/lightning/test_qh_module.py",
  gate: [name the actor-state and target-source protocols in every run; establish held-out task sufficiency],
)[The selected method uses the `S0-pose` actor state: immutable root evidence, an admitted target descriptor, the current finite candidate table and hard mask, factual selected-pose history, and remaining budget. The interface is implemented and tested; task sufficiency and policy value remain unestablished.]

The actor state is the information available before selecting action $a_t$, not
every quantity co-located in a replay row. Oracle target gains, mesh crops,
ground-truth associations, current all-candidate renders, and labels are
excluded from the scorer graph. The non-deployable `v0_gt_input` target
protocol supplies privileged target geometry for a controlled oracle task;
`v1_observed` requires a descriptor constructed from observations and binds its
source and construction provenance. These protocols define different claims
even when their tensors share a shape.

The selected state read is

$
  #eqs.scene.actor_state_read
$

Its immutable root component contains semidense evidence and lossy global
moments of locally supported EFM3D features. Its dynamic component is only the
strictly causal selected-pose prefix. Candidate regeneration updates the
reference pose, prefix, remaining budget, and action table; it does not imply a
new RGB observation, a refreshed EFM3D field, or fused selected depth.

#figure(
  publication-table(
    text-size: 8.2pt,
    columns: (0.82fr, 1.24fr, 1.48fr),
    header: ([*State component*], [*Selected evidence*], [*Interpretation boundary*]),
    rows: (
      [Root scene], [semidense and supported EFM3D summary], [Immutable logged context; missing local support is not measured free space.],
      [Target], [protocol-admitted identity and geometry], [Privileged oracle instruction or actor-visible descriptor, never an unlabelled mixture.],
      [Dynamic history], [selected poses $bold(H)_t$], [Causal action history, but no selected appearance, depth fusion, or free/unknown memory.],
      [Decision context], [candidate rows, hard mask, $b_t$, and $h$], [Finite support and value query; invalidity remains external to conditional value.],
    ),
  ),
  caption: [Selected `S0-pose` state protocol. The table states what the method consumes and, equally importantly, what it cannot represent.],
) <tab:thesis-counterfactual-state-protocols>

=== Sufficiency and the local-evidence limit

A decision state is task-sufficient only if it preserves every distinction that
can change target-specific future return. `S0-pose` cannot satisfy that
condition by construction when two histories share poses but reveal different
surfaces, occlusions, or free-space evidence. It is therefore a deliberately
compact baseline and an interface test, not a claim that pose history is a
complete reconstruction state.

EFM3D reinforces this limit. Its gravity-aligned voxel field has an explicit
pose and finite extent @EFM3D-straub2024. A target or candidate outside that
extent may remain physically valid while lacking local lifted evidence. Global
moments further remove spatial correspondence. The selected method can test
whether this compact context contains usable signal, but a failure cannot be
attributed to value learning alone, and a success cannot establish spatial
state sufficiency. Richer causal surface or ray memories are kept outside the
thesis-core method until a frozen comparison isolates their added information.
