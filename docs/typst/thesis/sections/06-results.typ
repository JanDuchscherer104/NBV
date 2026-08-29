= Results <sec:thesis-results>

#import "../experiment_data.typ": thesis-report-settings, load-thesis-report, report-store-fact, report-store-facts-match-contract, short-store-label, format-report-value
#import "../draft_markers.typ": validation_todo
#import "../../shared/tables.typ": publication-table, index-cell

#validation_todo(
  [Populate one result row per inferential stage from a confirmatory bundle: population, estimate, uncertainty, admitted conclusion, and blocking condition. Every value must resolve to its raw and derived artifact provenance.],
  source: [confirmatory report bundle, exact-Q2 receipt, and analysis manifest],
  gate: [all six evidence gates resolve without fixture or pilot substitution],
)

#let report-settings = thesis-report-settings()
#let thesis_evidence_status = report-settings.evidence-status
#let thesis_data = load-thesis-report(
  report-settings.path,
  evidence-status: thesis_evidence_status,
  required-role: report-settings.required-role,
)
#let all-stores-valid = thesis_data.tables.stores.rows.len() > 0 and thesis_data.tables.stores.rows.all(store => store.validation_ok == true)
#let stores-have-facts(keys, denominators: false) = thesis_data.tables.stores.rows.len() > 0 and thesis_data.tables.stores.rows.all(store => keys.all(key => {
  let matches = thesis_data.tables.facts.rows.filter(row => row.store_id == store.store_id and row.key == key)
  matches.len() == 1 and matches.first().value != none and (not denominators or (matches.first().n != none and matches.first().n > 0))
}))
#let fact-value(store-id, key, digits: none) = {
  let row = report-store-fact(thesis_data, store-id, key)
  format-report-value(row.value, digits: digits, unit: row.unit)
}
#let result-status(predicate) = if predicate [available] else [not available]

#let population-facts = ("study.population.scenes", "study.population.targets", "study.population.exclusions")
#let measurement-facts = ("oracle.metric.repeatability.max_abs_diff", "oracle.metric.repeatability.n_repeats", "oracle.metric.repeatability.passed")
#let candidate-support-facts = (
  "candidate-support.actor-valid-fraction",
  "candidate-support.valid-support-p05",
  "candidate-support.configured-family-zero-rate",
  "candidate-support.target-side-balance",
  "candidate-support.circular-orbit-span",
)
#let candidate-support-contract = (
  (key: "candidate-support.actor-valid-fraction", aggregation: "state_then_scene_macro"),
  (key: "candidate-support.valid-support-p05", aggregation: "state_then_scene_p05"),
  (key: "candidate-support.configured-family-zero-rate", aggregation: "state_then_scene_macro"),
  (key: "candidate-support.target-side-balance", aggregation: "state_then_scene_macro"),
  (key: "candidate-support.circular-orbit-span", aggregation: "state_then_scene_macro"),
)
#let headroom-facts = ("policy.paired_scene_endpoint.effect", "policy.paired_scene_endpoint.ci_low", "policy.paired_scene_endpoint.ci_high", "policy.paired_scene_endpoint.n_scenes", "headroom_gate.passed")
#let headroom-contract = (
  (key: "policy.paired_scene_endpoint.effect", aggregation: "paired_scene_mean_difference"),
  (key: "policy.paired_scene_endpoint.ci_low", aggregation: "paired_scene_mean_difference"),
  (key: "policy.paired_scene_endpoint.ci_high", aggregation: "paired_scene_mean_difference"),
  (key: "policy.paired_scene_endpoint.n_scenes", aggregation: "count"),
  (key: "headroom_gate.passed", aggregation: "paired_scene_decision"),
)
#let q1-facts = ("q1.ranking.pairwise_accuracy", "q1.calibration.mae", "q1.population.n_scenes")
#let q2-facts = ("q2.exact.mae", "q2.exact.coverage", "q2.exact.n_independent_units", "q2.exact.passed")
#let recovery-facts = ("policy.q_recovery.fraction", "policy.q_recovery.ci_low", "policy.q_recovery.ci_high", "policy.q_recovery.n_scenes", "policy.q_recovery.passed")
#let resource-facts = ("runtime.wall_time_s", "runtime.peak_gpu_bytes", "storage.total_bytes")

#let confirmatory-evidence = thesis_evidence_status == "confirmatory" and all-stores-valid
#let population-available = confirmatory-evidence and stores-have-facts(population-facts, denominators: true)
#let measurement-available = confirmatory-evidence and stores-have-facts(measurement-facts)
#let support-available = population-available and stores-have-facts(candidate-support-facts, denominators: true) and thesis_data.tables.stores.rows.all(store => {
  let scene-count = report-store-fact(thesis_data, store.store_id, "study.population.scenes").value
  scene-count != none and scene-count > 0 and report-store-facts-match-contract(
    thesis_data,
    store.store_id,
    candidate-support-contract,
    scene-count,
  )
})
#let headroom-available = measurement-available and support-available and stores-have-facts(headroom-facts) and thesis_data.tables.stores.rows.all(store => {
  let paired-scenes = report-store-fact(thesis_data, store.store_id, "policy.paired_scene_endpoint.n_scenes").value
  paired-scenes != none and paired-scenes > 0 and report-store-facts-match-contract(
    thesis_data,
    store.store_id,
    headroom-contract,
    paired-scenes,
  )
})
#let q1-available = headroom-available and stores-have-facts(q1-facts)
#let q2-available = q1-available and stores-have-facts(q2-facts)
#let recovery-available = q2-available and stores-have-facts(recovery-facts)
#let resource-available = confirmatory-evidence and stores-have-facts(resource-facts)

The loaded report declares evidence class #emph(thesis_evidence_status). Schema
validity proves that provenance and missingness are readable; it cannot promote
a development fixture, training pilot, or incomplete store. Availability is
therefore cumulative: a downstream gate is reported only when every prerequisite
and its own required facts are present.

#figure(
  publication-table(
    text-size: 7.1pt,
    columns: (0.48fr, 0.92fr, 0.76fr, 0.78fr, 1.1fr, 1.16fr),
    header: ([*Gate / RQ*], [*Population*], [*Estimate*], [*Uncertainty*], [*Admitted conclusion*], [*Blocking condition*]),
    rows: (
      [measurement / RQ1], [frozen repeated oracle evaluations], [repeatability statistic: #result-status(measurement-available)], [declared numeric tolerance], [metric comparison is admissible], [mismatched identity, absent repeats, or tolerance failure],
      [population/action / RQ4], [held-out scenes, targets, and full candidate tables], [coverage and failures: #result-status(support-available)], [exact denominators and scene strata], [the population relevant to oracle headroom is described], [missing population, exclusions, or valid-action support],
      [headroom / RQ2], [paired lookahead and one-step oracle scenes], [endpoint effect: #result-status(headroom-available)], [paired scene interval], [bounded setup contains meaningful non-myopic structure], [measurement/support failure or non-meaningful effect],
      [actor $Q_1$ / RQ3], [held-out actor-visible candidate states], [ranking and calibration: #result-status(q1-available)], [scene-clustered interval], [actor information recovers immediate target value], [privileged input, matching failure, or inadequate calibration],
      [exact $Q_2$ / RQ2], [eligible held-out factual successors], [error and coverage: #result-status(q2-available)], [independent-unit tolerance rule], [first recursive target is recovered], [incomplete support or failed recursion tolerance],
      [endpoint recovery / RQ2], [paired held-out learned and reference policies], [recovered fraction: #result-status(recovery-available)], [paired scene interval], [learned policy recovers prespecified headroom], [any earlier gate or recovery-rule failure],
    ),
  ),
  caption: [Evidence availability by inferential stage. “Not available” preserves missingness and names the blocker; it is not a zero estimate.],
) <tab:thesis-result-availability>

#let result-summary-families = {
  let families = ()
  if population-available {
    families.push((label: [Population], metrics: (
      (label: [Scenes], key: "study.population.scenes"),
      (label: [Targets], key: "study.population.targets"),
      (label: [Exclusions], key: "study.population.exclusions"),
    )))
  }
  if measurement-available {
    families.push((label: [Measurement], metrics: (
      (label: [Maximum repeat discrepancy], key: "oracle.metric.repeatability.max_abs_diff", denominator-key: "oracle.metric.repeatability.n_repeats", digits: 5),
      (label: [Repeatability gate], key: "oracle.metric.repeatability.passed"),
    )))
  }
  if support-available {
    families.push((label: [Candidate support], metrics: (
      (label: [Actor-valid fraction], key: "candidate-support.actor-valid-fraction", digits: 3),
      (label: [P05 valid support], key: "candidate-support.valid-support-p05", digits: 1),
      (label: [Configured-family zero rate], key: "candidate-support.configured-family-zero-rate", digits: 3),
      (label: [Target-side balance], key: "candidate-support.target-side-balance", digits: 3),
      (label: [Circular orbit span], key: "candidate-support.circular-orbit-span", digits: 2),
    )))
  }
  if headroom-available {
    families.push((label: [Oracle headroom], metrics: (
      (label: [Paired endpoint effect], key: "policy.paired_scene_endpoint.effect", low-key: "policy.paired_scene_endpoint.ci_low", high-key: "policy.paired_scene_endpoint.ci_high", denominator-key: "policy.paired_scene_endpoint.n_scenes", digits: 3),
      (label: [Meaningful-headroom gate], key: "headroom_gate.passed", denominator-key: "policy.paired_scene_endpoint.n_scenes"),
    )))
  }
  if q1-available {
    families.push((label: [Actor Q1], metrics: (
      (label: [Pairwise ranking], key: "q1.ranking.pairwise_accuracy", denominator-key: "q1.population.n_scenes", digits: 3),
      (label: [Calibration MAE], key: "q1.calibration.mae", denominator-key: "q1.population.n_scenes", digits: 4),
    )))
  }
  if q2-available {
    families.push((label: [Exact Q2], metrics: (
      (label: [Recursive MAE], key: "q2.exact.mae", denominator-key: "q2.exact.n_independent_units", digits: 4),
      (label: [Complete-support coverage], key: "q2.exact.coverage", denominator-key: "q2.exact.n_independent_units", digits: 3),
      (label: [Exact-Q2 gate], key: "q2.exact.passed", denominator-key: "q2.exact.n_independent_units"),
    )))
  }
  if recovery-available {
    families.push((label: [Endpoint recovery], metrics: (
      (label: [Recovered headroom], key: "policy.q_recovery.fraction", low-key: "policy.q_recovery.ci_low", high-key: "policy.q_recovery.ci_high", denominator-key: "policy.q_recovery.n_scenes", digits: 3),
      (label: [Recovery gate], key: "policy.q_recovery.passed", denominator-key: "policy.q_recovery.n_scenes"),
    )))
  }
  if resource-available {
    families.push((label: [Resources], metrics: (
      (label: [Wall time], key: "runtime.wall_time_s", digits: 1),
      (label: [Peak GPU memory], key: "runtime.peak_gpu_bytes"),
      (label: [Storage], key: "storage.total_bytes"),
    )))
  }
  families
}

#let result-summary-rows = {
  let rows = ()
  let profile-span = result-summary-families.fold(0, (total, family) => total + family.metrics.len())
  for store in thesis_data.tables.stores.rows {
    let store-id = store.store_id
    let label = short-store-label(thesis_data, store-id)
    let first-profile-row = true
    for family in result-summary-families {
      let first-family-row = true
      for metric in family.metrics {
        if first-profile-row {
          rows.push(index-cell([#label], rowspan: profile-span))
          first-profile-row = false
        }
        if first-family-row {
          rows.push(index-cell(family.label, rowspan: family.metrics.len()))
          first-family-row = false
        }
        let digits = metric.at("digits", default: none)
        let low-key = metric.at("low-key", default: none)
        let high-key = metric.at("high-key", default: none)
        let denominator-key = metric.at("denominator-key", default: none)
        let fact = report-store-fact(thesis_data, store-id, metric.key)
        rows.push(metric.label)
        rows.push([#format-report-value(fact.value, digits: digits)])
        rows.push(if low-key == none { [—] } else { [#fact-value(store-id, low-key, digits: digits)] })
        rows.push(if high-key == none { [—] } else { [#fact-value(store-id, high-key, digits: digits)] })
        rows.push(if fact.unit == none { [—] } else { [#fact.unit] })
        rows.push(if denominator-key == none { [#format-report-value(fact.n)] } else { [#fact-value(store-id, denominator-key)] })
      }
    }
  }
  rows
}

#if result-summary-rows.len() > 0 [
  #figure(
    publication-table(
      columns: (0.72fr, 0.95fr, 1.05fr, 0.62fr, 0.62fr, 0.62fr, 0.55fr, 0.5fr),
      align: (left, left, left, right, right, right, left, right),
      text-size: 7.2pt,
      header: ([*Profile*], [*Gate*], [*Measure*], [*Estimate*], [*CI low*], [*CI high*], [*Unit*], [*$n$*]),
      rows: result-summary-rows,
    ),
    caption: [Available confirmatory values by profile and gate. Neutral rows are grouped without aggregation across profiles.],
  ) <tab:thesis-confirmatory-values>
]

== Measurement Validity

#if measurement-available [
  The confirmatory bundle contains the frozen repeatability population, statistic, tolerance decision, and provenance needed to admit downstream comparisons; values appear in @tab:thesis-confirmatory-values.
] else [
  The loaded evidence does not establish repeatability of the frozen target-specific endpoint metric. All downstream policy quantities therefore remain unavailable.
]

== Population and Action Support

#if support-available [
  The report supplies scene, target, and exclusion denominators together with
  actor-valid fraction, lower-tail valid support, configured-family zero rate,
  target-side balance, and circular orbit span. These state--scene summaries
  delimit the supported action population; they are not paired policy effects.
] else [
  No validated held-out bundle currently defines the study population and
  complete candidate-support denominators. The available Phase-A audit is a
  bounded proposal-support result, not a substitute for that confirmatory
  population.

  The frozen 100-scene Phase-A proposal audit attempted $6,000$ candidates and
  admitted $3,146$ into the compact valid shells. It nevertheless failed its
  support gate: $44$ applicable state--family cells had no selected row, $24$
  states missed the aggregate non-forward target-aware-family floor, and $8$
  states missed the root-support threshold. All $100$ reviewed source rows,
  scenes, and target states were represented without exclusions. Because this
  no-render audit contains no reward labels, flat-gain status is unavailable
  with label and eligible-state denominators both zero. The result diagnoses
  proposal support; it provides no evidence about RRI, candidate quality,
  rollout throughput, or policy performance and does not admit broad rollout
  generation.

  Separately, training-source rollout attempts reached mesh rendering,
  target-specific oracle scoring, and selected-action replay. An out-of-memory
  failure during unbatched candidate rendering and subsequent memory-bounded
  attempts identify rendering as a scale gate; they do not establish population
  throughput or storage feasibility.

  // Display provenance:
  // - source -> docs/contents/evidence/candidate_family_phase_a_wp02.json (canonical 100-state Phase-A evidence and internal artifact identity)
  // - transform -> provenance_correction_revision plus embedded phase-a-target-aligned-z-up-v1 coordinate contract; no candidate regeneration
  // - aggregate -> preflight.coverage, preflight.blockers, preflight.flat_gain, and records[].points actor_valid counts
  // - representative selection -> sort composite (scene_key, state_key) identities and, for each persisted audit stratum in insertion order, retain the first identity whose scene belongs to that stratum; this matches _candidate_family_funnel_identities in aria_nbv/aria_nbv/app/panels/_stored_rollouts/validity_support.py
  // - plot/export -> use the selected/attempted matrix semantics of candidate_family_preflight_figures in aria_nbv/aria_nbv/rollouts/candidate_support_plotting.py and export the Plotly heatmap as SVG; the exact historical shell command was not retained, so the checked-in SVG remains the display owner
  // - display -> docs/contents/evidence/candidate_family_phase_a_wp02_audit_heatmap.svg and this bounded Results interpretation

  #figure(
    image(
      "../../../contents/evidence/candidate_family_phase_a_wp02_audit_heatmap.svg",
      width: 100%,
    ),
    caption: [
      Candidate-family survival for one deterministic scene from each of the
      ten persisted Phase-A audit strata. Each cell reports compact-valid-shell
      membership divided by attempted rows for one factual state and proposal
      family; the complete 100-state matrix remains in the hash-bound evidence
      bundle. The underlying artifact geometry uses correction revision
      `phase-a-target-aligned-z-up-v1`; the stored shells, support counts,
      verdict, and execution identity are unchanged. The artifact is bound to
      clean execution revision `2baf7cf6b276b81c50d01d45b152016d7cf68033` and
      SHA-256 `6d33e9e3d68737c8a6a5589ae5117c1e4d7fcaa89056fcfcaec1d315e4509c83`.
    ],
  ) <fig:candidate-family-phase-a-support>
]

== Oracle Headroom

#if headroom-available [
  The paired scene endpoint effect, interval, denominator, and meaningful-headroom decision are available in @tab:thesis-confirmatory-values. Interpretation remains conditional on the frozen support definition and metric protocol.
] else [
  Meaningful equal-budget lookahead headroom over one-step oracle greedy is not estimable from the loaded evidence.
]

== Actor-Visible One-Step Value

#if q1-available [
  Held-out actor-visible ranking and calibration are available with scene denominators. They establish only immediate target-value recovery under the admitted target and state protocols.
] else [
  No validated held-out result currently shows target-conditioned one-step ranking and calibration from actor-visible inputs.
]

== Exact Two-Step Recursion

#if q2-available [
  Exact-Q2 error, complete-support coverage, independent-unit count, and the frozen tolerance decision are available. This admits the first recursive target, not endpoint policy success.
] else [
  No qualifying held-out exact-Q2 receipt is available; recursive finite-horizon accuracy is therefore unestablished.
]

== Endpoint Recovery

#if recovery-available [
  The recovered-headroom fraction, paired scene interval, denominator, and recovery decision are available under the admitted upstream gates.
] else [
  The thesis cannot estimate learned endpoint recovery because the prerequisite gate chain is incomplete.
]

== Resource Feasibility

#if resource-available [
  Completed profiles report observed wall time, peak GPU memory, and storage. Extrapolation beyond those runs still requires an explicit scaling model.
] else [
  Renderer memory failures motivate bounded rendering and retained failure provenance, but no validated completed-store evidence supports throughput or dataset-volume extrapolation.
]
