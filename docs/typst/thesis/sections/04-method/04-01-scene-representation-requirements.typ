#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../../shared/equations.typ": eqs
#import "../../draft_markers.typ": development_only
#import "@preview/booktabs:0.0.4": *

== Actor State and Representation Boundary <sec:thesis-scene-representation>

=== Implemented actor boundary

// evidence:
// - aria_nbv/aria_nbv/data_handling/qh_data/views.py:40-63,177-227 -> named Q_H profiles, actor tensors, masks, history, budget, and selected-observation provenance.
// - aria_nbv/tests/data_handling/test_qh.py:179-214,613-622 -> qh_cf0_v1/qh_cfplus_gt_depth_v1 admission and explicit privilege checks.

The implemented actor DTO carries root evidence, target fields, root-relative candidate poses, factual selected-pose history, remaining budget, candidate support, and actor-validity masks. It does not carry rewards, target-RRI labels, or audit lineage. The `qh_cf0_v1` profile has no selected counterfactual depth. `qh_cfplus_gt_depth_v1` is a named privileged selected-depth profile and is rejected for deployable construction unless privilege is explicit. These profiles are not interchangeable evidence cohorts.

The actor/oracle separation is strict. GT meshes, target crops, current all-candidate renders, associations, target gains, state-relative RRI diagnostics, and returns are supervision, evaluation, or audit fields. GT target geometry may define the current oracle-task instruction, but it is not an ordinary actor observation. Previously selected GT depth can enter only the explicitly privileged CF+ protocol; it must not be described as the actor-visible CF0 path.

The implemented carrier is an information boundary, not a production scorer. In particular, the DTO does not prove task-sufficient dynamic reconstruction memory, scorer invariance, or policy utility.

#development_only(() => [
  === Planned actor state and support limits

The planned production state for target $e$, candidate $q_(t,i)$, and step $t$ is expressed with existing shared notation:

$
  #eqs.scene.actor_state_read
$

The fixed-horizon path uses remaining budget $b_t$ as time-to-go context. A requested residual horizon is not a second primary interface. The actor state may combine immutable root evidence, causal selected-observation memory, target context, candidate-local queries, and ordered history, but every field needs a declared source and availability mask. No future observation or unselected candidate render may enter the state.

EFM3D/EVL support is local. Its persisted voxel pose and finite extent define where lifted features are supported; outside that extent is missing evidence, not an ordinary zero feature and not automatically an invalid action. The planned state may add semidense or fused points and sparse ray-aware support, but no task-sufficient dynamic memory is currently available. The state remains bounded by the logged EVL/support fields and by the finite candidate and replay support.

#figure(
  text(size: 8.2pt, table(
    columns: (1fr, 1.55fr),
    toprule(),
    table.header([*Carrier*], [*Role in the primary path*]),
    midrule(),
    [root semidense/EVL evidence], [bounded actor context with explicit support metadata],
    [causal selected-observation memory], [not part of this substrate; requires source and leakage tests],
    [GT mesh and rendered depth], [oracle label/evaluation evidence, never ordinary actor input],
    bottomrule(),
  )),
  caption: [Scene-carrier design space and information roles.]
) <tab:thesis-scene-representation-design-space>

An origin or yaw convention must not become a shortcut. Relative geometry is an adapter/DTO contract: world-frame facts are retained for provenance, while candidate features are derived in the admitted root or local frame. This does not claim scorer-level exact $op("SE")(3)$ invariance; gravity, scale, target extent, camera direction, occlusion, and temporal order remain task variables.
])

#figure(
  text(size: 8.2pt, table(
    columns: (0.82fr, 1.2fr, 1.42fr),
    toprule(),
    table.header([*Protocol*], [*Selected evidence*], [*Scientific role*]),
    midrule(),
    [`qh_cf0_v1`], [root actor evidence; no selected CF-GT depth], [actor-safe protocol; deployable only with an observed target protocol],
    [`qh_cfplus_gt_depth_v1`], [root evidence plus selected GT depth], [explicit privileged upper-bound/control cohort; never ordinary actor evidence],
    [Oracle], [GT mesh, target crop, rendered candidates and labels], [label generation and re-evaluation only],
    bottomrule(),
  )),
  caption: [Q_H information protocols and their roles.]
) <tab:thesis-counterfactual-state-protocols>

#development_only(() => [
  === Development and future representation evidence

  The planned carrier ladder starts with root semidense/EVL evidence, then tests selected-observation point or ray memory only when a diagnosed support failure requires it. Target-centred re-lifting, point appearance descriptors, sparse encoders, object-aware renderable memory, and global scene-language carriers are alternatives. They remain outside the primary method until matched support, leakage, runtime, and held-out target-RRI evidence exists.

  #figure(
    text(size: 8.2pt, table(
      columns: (1fr, 1.2fr),
      toprule(),
      table.header([*Alternative*], [*Promotion condition*]),
      midrule(),
      [selected point/ray memory], [causal fusion, source masks, and target-conditioned held-out benefit],
      [target-centred EVL or appearance carrier], [logged-source visibility and matched support ablation],
      [sparse, equivariant, or renderable encoder], [simpler carrier failure plus fair architecture control],
      bottomrule(),
    )),
    caption: [Development-only representation alternatives.]
  )
])
