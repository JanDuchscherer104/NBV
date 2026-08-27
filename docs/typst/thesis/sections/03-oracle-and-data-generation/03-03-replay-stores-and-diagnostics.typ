#import "../../../shared/macros.typ": *
#import "../../../shared/symbols.typ": symb
#import "../../draft_markers.typ": prune_todo, development_only
#import "../../experiment_data.typ": load-scientific-report, report-value, report-figure-path, format-report-value
#import "@preview/booktabs:0.0.4": *

== Replay Stores and Diagnostic Evidence

#prune_todo(
  [Move schema names, directory names, joins, codecs, and DTO-level mechanics that do not change the scientific protocol to the implementation appendix. Keep lineage, missingness, leakage prevention, and reproducibility guarantees in the main text.],
  source: [this section; aria_nbv/aria_nbv/rollouts/zarr_store.py],
  gate: [every remaining implementation term is necessary to reproduce or interpret the experiment],
)

The pipeline materializes two stores with different ownership. Immutable `vin_offline/` caches logged snippet evidence and expensive one-step oracle products. Standalone `rollouts.zarr/` references those source rows and stores target tasks, retained rollout chains, per-step finite candidate shells, masks, reason codes, selected-action successor evidence, and a derived #symb.rl.qh view. This separation prevents counterfactual experiments from mutating the source substrate and prevents one-step candidate labels from being mistaken for multi-step replay.

The source store is immutable because it defines the logged actor substrate. Its manifest records source identity, split, schema, materialized blocks, and provenance. A source row may contain frozen EVL/VIN fields, one-step candidate poses and labels, compact rendering payloads, and semidense geometry/history. These fields support scorer training and rollout construction, but they do not themselves define target-conditioned finite-horizon data. Exact directory names, array groups, chunking, and codec choices are versioned reproducibility metadata rather than scientific entities, so they are not reproduced as directory-tree figures in the main text.

The rollout store is normalized around replay identity. One source can produce multiple target rows, each target can produce multiple recipe and retained-chain rows, each chain expands into selected steps, and each step owns a full candidate shell. The store therefore captures selected or beam-retained chain evidence, not the complete counterfactual search tree. Padded `q_h/` arrays are a validated cache over the factual row tables. Invalid candidate rows remain inspectable, but action, training, and bootstrap masks exclude them.

#figure(
  align(center, image(
    "../../figures/replay_lineage_relations.pdf",
    width: 100%,
  )),
  caption: [Normalized lineage of the implemented replay evidence. An immutable VIN source row may define several oracle target tasks; each target may produce several retained policy chains; each chain contains ordered steps; and each step owns one full candidate shell. The step row may identify one chosen candidate through `selected_candidate_row_id`; selected-action successor and TD fields are then constructed in the derived `q_h/` join rather than persisted as a separate transition table.],
) <fig:offline-rollout-store-relation>

#figure(
  table(
    columns: (0.8fr, 1.35fr),
    toprule(),
    table.header([*Evidence family*], [*Interpretation contract*]),
    midrule(),
    [Sources and targets],
    [Manifest-backed task coverage; not proof of actor-visible target discovery.],
    [Candidates and invalidity],
    [Full-shell support with separate hard-action, training, padding, and future deployable-feasibility roles.],
    [Retained chains and steps],
    [Recipe-selected evidence; not a persisted exhaustive search tree.],
    [Selected depth],
    [Chosen-action successor observation with calibration and source role; actor input only under an explicitly admitted later-state protocol.],
    [#symb.rl.qh view],
    [Derived training cache whose rewards and masks must agree with factual rows; not a scene-memory representation.],
    bottomrule(),
  ),
  caption: [Interpretation contract for rollout-store audits. Numeric values are rendered from the resolved report bundle in the experiment and reproducibility sections.],
) <tab:current-rollout-store-audit>

Selected-depth persistence stores only the depth raster and calibration for the chosen action at each retained step. It is sufficient to reconstruct the selected-observation prefix without duplicating dense all-candidate renders, but persistence does not decide visibility. A `CF-GT` reader may use previously selected GT-mesh depths to build a privileged dynamic state; a deployable reader must instead consume a declared sensor-like or observed source. The current unselected candidate renders remain oracle-only in every student protocol. Selected depth is also not an independently scored endpoint artifact.

Likewise, rollout rows summarize final cumulative selected-chain metrics; they do not preserve every rejected branch or a policy-neutral endpoint reconstruction. These limitations must be resolved by matched endpoint re-evaluation before confirmatory policy comparison.

Scientific reporting is generated from the same inspection frames used by the diagnostic application. The main text needs target-task coverage, candidate validity and invalid reasons, family survival and selection, selected-history sanity, gain distributions, source-role counts, and runtime/storage summaries. Exact schema columns, compression, chunking, hashes, and cluster invocation belong in the reproducibility appendix and must be read from the resolved manifest and report bundle. Development bandwidth pilots are train-only feasibility checks; their counts and throughput may size later jobs but cannot support held-out reconstruction or policy claims.

#development_only(() => {
  let s2-report = load-scientific-report(
    "/typst/thesis/data/s2-rollout-pilot/report.json",
    evidence-status: "pilot",
  )
  let source-sample-count = report-value(s2-report, "s2.quantity.s01.source-sample-count")
  let source-snippet-count = report-value(s2-report, "s2.quantity.s01.source-snippet-count")
  let source-scene-count = report-value(s2-report, "s2.quantity.s01.source-scene-count")
  let target-count = report-value(s2-report, "s2.quantity.s01.target-count")
  let rollout-count = report-value(s2-report, "s2.quantity.s01.rollout-count")
  let selected-step-count = report-value(s2-report, "s2.quantity.s01.selected-step-count")
  let movement-count = report-value(s2-report, "s2.quantity.s01.movement-count")
  let view-count = report-value(s2-report, "s2.quantity.s01.view-direction-count")
  let frustum-count = report-value(s2-report, "s2.quantity.s01.frustum-count")
  let mean-solid-angle = report-value(s2-report, "s2.quantity.s01.mean-frustum-solid-angle")
  let mean-proxy-fraction = report-value(s2-report, "s2.quantity.s01.mean-proxy-surface-fraction")
  let union-proxy-fraction = report-value(s2-report, "s2.quantity.s01.union-proxy-surface-fraction")

  [
    === Development pilot: target-frame $cal(S)^2$ diagnostics

    The following frozen figures are generated by the same Python reporting and plotting owners as the stored-rollout application. For the selected real-data shard, the report records these support counts: source samples #format-report-value(source-sample-count.value), snippets #format-report-value(source-snippet-count.value), scenes #format-report-value(source-scene-count.value), targets #format-report-value(target-count.value), retained rollout chains #format-report-value(rollout-count.value), and selected steps #format-report-value(selected-step-count.value). It remains pilot evidence: its purpose is to validate the representation and reporting contract, not to estimate policy quality. The two point-direction views contain #format-report-value(movement-count.value) factual displacements and #format-report-value(view-count.value) factual optical axes. Colour denotes rollout-chain identity, marker shape denotes decision-step identity, and the sphere heat map is computed from the complete equal-solid-angle count grid rather than from the bounded incidence overlay.

    #figure(
      align(center, image(
        report-figure-path(s2-report, "s2.figure.s01.movement"),
        width: 82%,
      )),
      caption: [Target-frame $cal(S)^2$ movement directions from the frozen pilot report. This view records how the camera moved; it is not a visibility measurement.],
    ) <fig:s2-pilot-movement>

    #figure(
      align(center, image(
        report-figure-path(s2-report, "s2.figure.s01.view-direction"),
        width: 82%,
      )),
      caption: [Target-frame $cal(S)^2$ selected-camera optical-axis directions from the same frozen pilot report. This view records where the camera pointed; it is distinct from both camera motion and calibrated surface support.],
    ) <fig:s2-pilot-view-direction>

    The calibrated proxy diagnostic integrates #format-report-value(frustum-count.value) selected frusta. Their mean intrinsic field-of-view solid angle is #format-report-value(mean-solid-angle.value, digits: 3, unit: mean-solid-angle.unit). On the geometric-mean-scale proxy sphere, one view covers a mean fraction of #format-report-value(mean-proxy-fraction.value, digits: 3), while their union covers #format-report-value(union-proxy-fraction.value, digits: 3). These fractions express geometric potential support under the proxy and front-facing tests; they exclude true target shape, depth ordering, and scene occlusion.

    #figure(
      align(center, image(
        report-figure-path(s2-report, "s2.figure.s01.frustum"),
        width: 70%,
      )),
      caption: [Calibrated selected-frustum support on the target-centred proxy sphere. The surface heat map is the complete equal-solid-angle coverage field; overlaid incidence samples preserve rollout and time heritage. This is not measured target-mesh visibility.],
    ) <fig:s2-pilot-frustum-support>
  ]
})
