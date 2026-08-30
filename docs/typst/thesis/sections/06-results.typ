= Results <sec:thesis-results>

#import "../experiment_data.typ": thesis-report-settings, load-thesis-report, report-store-fact, report-store-gate-passed, report-store-facts-match-contract, short-store-label, format-report-value
#import "../draft_markers.typ": validation_todo
#import "../../shared/tables.typ": publication-table, index-cell

#validation_todo(
  [Populate one result row per inferential stage from a confirmatory bundle: population, estimate, uncertainty, admitted conclusion, and blocking condition. Every value must resolve to its raw and derived artifact provenance.],
  source: [confirmatory report bundle, exact-Q2 receipt, and analysis manifest],
  gate: [all seven evidence stages resolve without fixture or pilot substitution],
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
#let store-has-sha256-facts(store-id, keys) = keys.all(key => {
  let matches = thesis_data.tables.facts.rows.filter(row => row.store_id == store-id and row.key == key)
  matches.len() == 1 and type(matches.first().value) == str and matches.first().value.len() == 64
})
#let fact-value(store-id, key, digits: none) = {
  let row = report-store-fact(thesis_data, store-id, key)
  format-report-value(row.value, digits: digits, unit: row.unit)
}
#let stores-pass-gate(key) = thesis_data.tables.stores.rows.len() > 0 and thesis_data.tables.stores.rows.all(
  store => report-store-gate-passed(thesis_data, store.store_id, key),
)
#let stage-status(evidence, prerequisites, decision) = if not evidence {
  [not available]
} else if not prerequisites {
  [blocked]
} else if decision {
  [passed]
} else {
  [failed]
}
#let stage-conclusion(evidence, prerequisites, decision, positive, negative) = if not evidence {
  [no conclusion: required evidence is absent]
} else if not prerequisites {
  [no downstream conclusion: a prerequisite failed]
} else if decision {
  positive
} else {
  negative
}

#let population-facts = ("study.population.scenes", "study.population.targets", "study.population.exclusions")
#let measurement-facts = ("oracle.metric.repeatability.max_abs_diff", "oracle.metric.repeatability.n_repeats", "oracle.metric.repeatability.passed")
#let candidate-support-facts = (
  "candidate-support.actor-valid-fraction",
  "candidate-support.valid-support-p05",
  "candidate-support.configured-family-zero-rate",
  "candidate-support.target-side-balance",
  "candidate-support.circular-orbit-span",
  "candidate-support.gate.passed",
)
#let candidate-support-contract = (
  (key: "candidate-support.actor-valid-fraction", aggregation: "state_then_scene_macro"),
  (key: "candidate-support.valid-support-p05", aggregation: "state_then_scene_p05"),
  (key: "candidate-support.configured-family-zero-rate", aggregation: "state_then_scene_macro"),
  (key: "candidate-support.target-side-balance", aggregation: "state_then_scene_macro"),
  (key: "candidate-support.circular-orbit-span", aggregation: "state_then_scene_macro"),
  (key: "candidate-support.gate.passed", aggregation: "state_then_scene_decision"),
)
#let headroom-facts = ("policy.paired_scene_endpoint.effect", "policy.paired_scene_endpoint.ci_low", "policy.paired_scene_endpoint.ci_high", "policy.paired_scene_endpoint.n_scenes", "headroom_gate.passed")
#let headroom-contract = (
  (key: "policy.paired_scene_endpoint.effect", aggregation: "paired_scene_mean_difference"),
  (key: "policy.paired_scene_endpoint.ci_low", aggregation: "paired_scene_mean_difference"),
  (key: "policy.paired_scene_endpoint.ci_high", aggregation: "paired_scene_mean_difference"),
  (key: "policy.paired_scene_endpoint.n_scenes", aggregation: "count"),
  (key: "headroom_gate.passed", aggregation: "paired_scene_decision"),
)
#let actor-protocol-decisions = (
  "q1.protocol.target_matching.passed",
  "q1.protocol.actor_input_identity.passed",
  "q1.protocol.leakage_audit.passed",
)
#let actor-protocol-facts = (
  "q1.protocol.target_matching.n_attempts",
  "q1.protocol.target_matching.n_failures",
  "q1.protocol.target_matching.failure_rate",
  "q1.protocol.population.n_scenes",
  ..actor-protocol-decisions,
)
#let actor-matching-contract = (
  (key: "q1.protocol.target_matching.n_attempts", aggregation: "count"),
  (key: "q1.protocol.target_matching.n_failures", aggregation: "count"),
  (key: "q1.protocol.target_matching.failure_rate", aggregation: "target_match_attempt_rate"),
  (key: "q1.protocol.target_matching.passed", aggregation: "target_match_attempt_decision"),
)
#let actor-audit-contract = (
  (key: "q1.protocol.population.n_scenes", aggregation: "count"),
  (key: "q1.protocol.actor_input_identity.passed", aggregation: "scene_protocol_decision"),
  (key: "q1.protocol.leakage_audit.passed", aggregation: "scene_protocol_decision"),
)
#let q1-facts = (
  "q1.ranking.pairwise_accuracy",
  "q1.ranking.ci_low",
  "q1.ranking.ci_high",
  "q1.calibration.mae",
  "q1.calibration.ci_low",
  "q1.calibration.ci_high",
  "q1.population.n_scenes",
  "q1.passed",
)
#let q1-contract = (
  (key: "q1.ranking.pairwise_accuracy", aggregation: "scene_clustered_pairwise_accuracy"),
  (key: "q1.ranking.ci_low", aggregation: "scene_clustered_pairwise_accuracy"),
  (key: "q1.ranking.ci_high", aggregation: "scene_clustered_pairwise_accuracy"),
  (key: "q1.calibration.mae", aggregation: "scene_clustered_calibration_mae"),
  (key: "q1.calibration.ci_low", aggregation: "scene_clustered_calibration_mae"),
  (key: "q1.calibration.ci_high", aggregation: "scene_clustered_calibration_mae"),
  (key: "q1.population.n_scenes", aggregation: "count"),
  (key: "q1.passed", aggregation: "scene_clustered_decision"),
)
#let q2-identity-facts = ("q2.exact.receipt_sha256", "q2.exact.analysis_manifest_sha256")
#let q2-facts = (
  "q2.exact.mae",
  "q2.exact.coverage",
  "q2.exact.n_independent_units",
  ..q2-identity-facts,
  "q2.exact.passed",
)
#let q2-contract = (
  (key: "q2.exact.mae", aggregation: "all_units_v1"),
  (key: "q2.exact.coverage", aggregation: "balanced-hash-within-scene-target-support-strata-v2"),
  (key: "q2.exact.n_independent_units", aggregation: "count"),
  (key: "q2.exact.receipt_sha256", aggregation: "identity"),
  (key: "q2.exact.analysis_manifest_sha256", aggregation: "identity"),
  (key: "q2.exact.passed", aggregation: "all_units_v1_decision"),
)
#let recovery-identity-facts = ("policy.q_recovery.analysis_manifest_sha256",)
#let recovery-facts = (
  "policy.q_recovery.fraction",
  "policy.q_recovery.ci_low",
  "policy.q_recovery.ci_high",
  "policy.q_recovery.n_scenes",
  ..recovery-identity-facts,
  "policy.q_recovery.passed",
)
#let recovery-contract = (
  (key: "policy.q_recovery.fraction", aggregation: "paired_scene_gap_closure"),
  (key: "policy.q_recovery.ci_low", aggregation: "paired_scene_gap_closure"),
  (key: "policy.q_recovery.ci_high", aggregation: "paired_scene_gap_closure"),
  (key: "policy.q_recovery.n_scenes", aggregation: "count"),
  (key: "policy.q_recovery.analysis_manifest_sha256", aggregation: "identity"),
  (key: "policy.q_recovery.passed", aggregation: "paired_scene_gap_closure_decision"),
)
#let resource-facts = ("runtime.wall_time_s", "runtime.peak_gpu_bytes", "storage.total_bytes")

#let confirmatory-evidence = thesis_evidence_status == "confirmatory" and all-stores-valid
#let population-evidence = confirmatory-evidence and stores-have-facts(population-facts, denominators: true)
#let measurement-evidence = confirmatory-evidence and stores-have-facts(measurement-facts)
#let measurement-passed = measurement-evidence and stores-pass-gate("oracle.metric.repeatability.passed")
#let support-evidence = population-evidence and stores-have-facts(candidate-support-facts, denominators: true) and thesis_data.tables.stores.rows.all(store => {
  let scene-count = report-store-fact(thesis_data, store.store_id, "study.population.scenes").value
  scene-count != none and scene-count > 0 and report-store-facts-match-contract(
    thesis_data,
    store.store_id,
    candidate-support-contract,
    scene-count,
  )
})
#let support-passed = support-evidence and stores-pass-gate("candidate-support.gate.passed")
#let actor-protocol-evidence = confirmatory-evidence and stores-have-facts(actor-protocol-facts, denominators: true) and thesis_data.tables.stores.rows.all(store => {
  let match-attempts = report-store-fact(thesis_data, store.store_id, "q1.protocol.target_matching.n_attempts").value
  let match-failures = report-store-fact(thesis_data, store.store_id, "q1.protocol.target_matching.n_failures").value
  let scene-count = report-store-fact(thesis_data, store.store_id, "q1.protocol.population.n_scenes").value
  match-attempts != none and match-attempts > 0 and match-failures != none and match-failures >= 0 and match-failures <= match-attempts and scene-count != none and scene-count > 0 and report-store-facts-match-contract(
    thesis_data,
    store.store_id,
    actor-matching-contract,
    match-attempts,
  ) and report-store-facts-match-contract(
    thesis_data,
    store.store_id,
    actor-audit-contract,
    scene-count,
  )
})
#let actor-protocol-passed = actor-protocol-evidence and actor-protocol-decisions.all(stores-pass-gate)
#let headroom-evidence = confirmatory-evidence and stores-have-facts(headroom-facts) and thesis_data.tables.stores.rows.all(store => {
  let paired-scenes = report-store-fact(thesis_data, store.store_id, "policy.paired_scene_endpoint.n_scenes").value
  paired-scenes != none and paired-scenes > 0 and report-store-facts-match-contract(
    thesis_data,
    store.store_id,
    headroom-contract,
    paired-scenes,
  )
})
#let headroom-prerequisites = measurement-passed and support-passed
#let headroom-passed = headroom-evidence and headroom-prerequisites and stores-pass-gate("headroom_gate.passed")
#let q1-evidence = confirmatory-evidence and stores-have-facts(q1-facts) and thesis_data.tables.stores.rows.all(store => {
  let scene-count = report-store-fact(thesis_data, store.store_id, "q1.population.n_scenes").value
  scene-count != none and scene-count > 0 and report-store-facts-match-contract(
    thesis_data,
    store.store_id,
    q1-contract,
    scene-count,
  )
})
#let q1-prerequisites = measurement-passed and support-passed and actor-protocol-passed
#let q1-passed = q1-evidence and q1-prerequisites and stores-pass-gate("q1.passed")
#let q2-evidence = confirmatory-evidence and stores-have-facts(q2-facts, denominators: true) and thesis_data.tables.stores.rows.all(store => {
  let independent-units = report-store-fact(thesis_data, store.store_id, "q2.exact.n_independent_units").value
  independent-units != none and independent-units > 0 and store-has-sha256-facts(store.store_id, q2-identity-facts) and report-store-facts-match-contract(
    thesis_data,
    store.store_id,
    q2-contract,
    independent-units,
  )
})
#let q2-prerequisites = q1-passed
#let q2-passed = q2-evidence and q2-prerequisites and stores-pass-gate("q2.exact.passed")
#let recovery-evidence = confirmatory-evidence and stores-have-facts(recovery-facts, denominators: true) and thesis_data.tables.stores.rows.all(store => {
  let paired-scenes = report-store-fact(thesis_data, store.store_id, "policy.q_recovery.n_scenes").value
  paired-scenes != none and paired-scenes > 0 and store-has-sha256-facts(store.store_id, recovery-identity-facts) and report-store-facts-match-contract(
    thesis_data,
    store.store_id,
    recovery-contract,
    paired-scenes,
  )
})
#let recovery-prerequisites = headroom-passed and q2-passed
#let recovery-passed = recovery-evidence and recovery-prerequisites and stores-pass-gate("policy.q_recovery.passed")
#let resource-evidence = confirmatory-evidence and stores-have-facts(resource-facts)

The loaded report declares evidence class #emph(thesis_evidence_status). Schema
validity proves that provenance and missingness are readable; it cannot promote
a development fixture, training pilot, or incomplete store. Evidence presence,
the gate's own decision, and satisfaction of upstream prerequisites remain
separate. A failed gate retains its estimate as a bounded negative result while
preventing downstream admission.

#figure(
  publication-table(
    text-size: 7.1pt,
    columns: (0.48fr, 0.92fr, 0.76fr, 0.78fr, 1.1fr, 1.16fr),
    header: ([*Gate / RQ*], [*Population*], [*Estimate*], [*Uncertainty*], [*Admitted conclusion*], [*Blocking condition*]),
    rows: (
      [measurement / RQ1], [frozen repeated oracle evaluations], [repeatability: #stage-status(measurement-evidence, true, stores-pass-gate("oracle.metric.repeatability.passed"))], [declared numeric tolerance], [#stage-conclusion(measurement-evidence, true, stores-pass-gate("oracle.metric.repeatability.passed"), [metric comparison is admissible], [metric repeatability failed under the frozen tolerance])], [mismatched identity, absent repeats, or tolerance failure],
      [population/action / RQ4], [held-out scenes, targets, and full candidate tables], [support: #stage-status(support-evidence, true, stores-pass-gate("candidate-support.gate.passed"))], [exact denominators and scene strata], [#stage-conclusion(support-evidence, true, stores-pass-gate("candidate-support.gate.passed"), [the evaluated population and action support are adequate], [the frozen support criterion failed for this population])], [missing population, exclusions, or valid-action support],
      [actor protocol / RQ3], [target-match attempts and held-out protocol scenes], [audit: #stage-status(actor-protocol-evidence, support-passed, actor-protocol-decisions.all(stores-pass-gate))], [match failures plus exact attempt and scene denominators], [#stage-conclusion(actor-protocol-evidence, support-passed, actor-protocol-decisions.all(stores-pass-gate), [the actor-visible protocol is admissible], [matching, actor-input identity, or leakage audit failed])], [support failure, privileged input, or target mismatch],
      [headroom / RQ2], [paired lookahead and one-step oracle scenes], [endpoint effect: #stage-status(headroom-evidence, headroom-prerequisites, stores-pass-gate("headroom_gate.passed"))], [paired scene interval], [#stage-conclusion(headroom-evidence, headroom-prerequisites, stores-pass-gate("headroom_gate.passed"), [bounded setup contains meaningful non-myopic structure], [no meaningful headroom was detected in this bounded setup])], [measurement/support failure or non-meaningful effect],
      [actor $Q_1$ / RQ3], [held-out actor-visible candidate states], [ranking and calibration: #stage-status(q1-evidence, q1-prerequisites, stores-pass-gate("q1.passed"))], [scene-clustered ranking and calibration intervals], [#stage-conclusion(q1-evidence, q1-prerequisites, stores-pass-gate("q1.passed"), [the evaluated learner recovers immediate target value], [the evaluated learner fails the frozen immediate-value criterion])], [protocol failure or inadequate ranking/calibration],
      [exact $Q_2$ / RQ2], [eligible held-out factual successors], [error and coverage: #stage-status(q2-evidence, q2-prerequisites, stores-pass-gate("q2.exact.passed"))], [positive independent-unit denominator and receipt-bound rule], [#stage-conclusion(q2-evidence, q2-prerequisites, stores-pass-gate("q2.exact.passed"), [the first recursive target is recovered], [the evaluated learner fails the exact-$Q_2$ criterion])], [failed $Q_1$, incomplete support, or recursion error],
      [endpoint recovery / RQ2], [paired held-out learned and reference policies], [gap closure: #stage-status(recovery-evidence, recovery-prerequisites, stores-pass-gate("policy.q_recovery.passed"))], [positive paired-scene denominator and interval], [#stage-conclusion(recovery-evidence, recovery-prerequisites, stores-pass-gate("policy.q_recovery.passed"), [learned policy closes the prespecified endpoint gap], [the evaluated learned policy fails the frozen recovery criterion])], [headroom, recursion, or recovery-rule failure],
    ),
  ),
  caption: [Evidence status by inferential stage. “Failed” retains a measured negative outcome, “blocked” marks a failed prerequisite, and “not available” preserves missingness.],
) <tab:thesis-result-availability>

#let result-summary-families = {
  let families = ()
  if population-evidence {
    families.push((label: [Population], metrics: (
      (label: [Scenes], key: "study.population.scenes"),
      (label: [Targets], key: "study.population.targets"),
      (label: [Exclusions], key: "study.population.exclusions"),
    )))
  }
  if measurement-evidence {
    families.push((label: [Measurement], metrics: (
      (label: [Maximum repeat discrepancy], key: "oracle.metric.repeatability.max_abs_diff", denominator-key: "oracle.metric.repeatability.n_repeats", digits: 5),
      (label: [Repeatability gate], key: "oracle.metric.repeatability.passed"),
    )))
  }
  if support-evidence {
    families.push((label: [Candidate support], metrics: (
      (label: [Actor-valid fraction], key: "candidate-support.actor-valid-fraction", digits: 3),
      (label: [P05 valid support], key: "candidate-support.valid-support-p05", digits: 1),
      (label: [Configured-family zero rate], key: "candidate-support.configured-family-zero-rate", digits: 3),
      (label: [Target-side balance], key: "candidate-support.target-side-balance", digits: 3),
      (label: [Circular orbit span], key: "candidate-support.circular-orbit-span", digits: 2),
      (label: [Support gate], key: "candidate-support.gate.passed"),
    )))
  }
  if actor-protocol-evidence {
    families.push((label: [Actor protocol], metrics: (
      (label: [Target-match failures], key: "q1.protocol.target_matching.n_failures", denominator-key: "q1.protocol.target_matching.n_attempts"),
      (label: [Target-match failure rate], key: "q1.protocol.target_matching.failure_rate", denominator-key: "q1.protocol.target_matching.n_attempts", digits: 3),
      (label: [Target matching audit], key: "q1.protocol.target_matching.passed"),
      (label: [Actor-input identity audit], key: "q1.protocol.actor_input_identity.passed"),
      (label: [Leakage audit], key: "q1.protocol.leakage_audit.passed"),
    )))
  }
  if headroom-evidence {
    families.push((label: [Oracle headroom], metrics: (
      (label: [Paired endpoint effect], key: "policy.paired_scene_endpoint.effect", low-key: "policy.paired_scene_endpoint.ci_low", high-key: "policy.paired_scene_endpoint.ci_high", denominator-key: "policy.paired_scene_endpoint.n_scenes", digits: 3),
      (label: [Meaningful-headroom gate], key: "headroom_gate.passed", denominator-key: "policy.paired_scene_endpoint.n_scenes"),
    )))
  }
  if q1-evidence {
    families.push((label: [Actor Q1], metrics: (
      (label: [Pairwise ranking], key: "q1.ranking.pairwise_accuracy", low-key: "q1.ranking.ci_low", high-key: "q1.ranking.ci_high", denominator-key: "q1.population.n_scenes", digits: 3),
      (label: [Calibration MAE], key: "q1.calibration.mae", low-key: "q1.calibration.ci_low", high-key: "q1.calibration.ci_high", denominator-key: "q1.population.n_scenes", digits: 4),
      (label: [Actor-Q1 gate], key: "q1.passed", denominator-key: "q1.population.n_scenes"),
    )))
  }
  if q2-evidence {
    families.push((label: [Exact Q2], metrics: (
      (label: [Recursive MAE], key: "q2.exact.mae", denominator-key: "q2.exact.n_independent_units", digits: 4),
      (label: [Complete-support coverage], key: "q2.exact.coverage", denominator-key: "q2.exact.n_independent_units", digits: 3),
      (label: [Exact-Q2 gate], key: "q2.exact.passed", denominator-key: "q2.exact.n_independent_units"),
    )))
  }
  if recovery-evidence {
    families.push((label: [Endpoint recovery], metrics: (
      (label: [Learned endpoint-gap closure], key: "policy.q_recovery.fraction", low-key: "policy.q_recovery.ci_low", high-key: "policy.q_recovery.ci_high", denominator-key: "policy.q_recovery.n_scenes", digits: 3),
      (label: [Recovery gate], key: "policy.q_recovery.passed", denominator-key: "policy.q_recovery.n_scenes"),
    )))
  }
  if resource-evidence {
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

#if measurement-evidence [
  The confirmatory bundle contains the frozen repeatability population,
  statistic, tolerance decision, and provenance; values appear in
  @tab:thesis-confirmatory-values. #if measurement-passed [The metric passes the
  frozen repeatability rule and may support downstream comparisons.] else [The
  metric fails that rule, so its estimate is retained but policy comparisons
  are blocked.]
] else [
  The loaded evidence does not establish repeatability of the frozen target-specific endpoint metric. All downstream policy quantities therefore remain unavailable.
]

== Population and Action Support

#if support-evidence [
  The report supplies scene, target, and exclusion denominators together with
  actor-valid fraction, lower-tail valid support, configured-family zero rate,
  target-side balance, and circular orbit span. These state--scene summaries
  delimit the evaluated action population; they are not paired policy effects.
  #if support-passed [The frozen support rule admits that population for the
  downstream claims.] else [The support estimate remains reportable, but the
  failed rule blocks population-level headroom and learned-value claims.]
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

== Actor-Visible Protocol

#if actor-protocol-evidence [
  The report binds target-match failures to the exact attempted-match
  population and binds actor-input identity and actor--oracle leakage decisions
  to the held-out scene population. These audits remain independent of policy
  headroom. #if actor-protocol-passed [All three audits pass, so actor-visible
  value estimates may be interpreted under the declared protocol.] else [At
  least one audit fails; any stored predictive score remains descriptive and
  cannot establish actor-visible recovery.]
] else [
  The loaded evidence does not establish the target-matching, actor-input, and
  leakage boundary required by RQ3.
]

== Oracle Headroom

#if headroom-evidence [
  The paired scene endpoint effect, interval, denominator, and
  meaningful-headroom decision are available in @tab:thesis-confirmatory-values.
  #if headroom-passed [The effect is admitted under the passed measurement and
  support prerequisites.] else [The stored effect does not admit downstream
  recovery: either a prerequisite failed or the bounded setup did not pass the
  meaningful-headroom rule.]
] else [
  Meaningful equal-budget lookahead headroom over one-step oracle greedy is not estimable from the loaded evidence.
]

== Actor-Visible One-Step Value

#if q1-evidence [
  Held-out actor-visible ranking and calibration each carry a scene-clustered
  interval, positive scene denominator, aggregation identity, and joint
  decision independently of oracle headroom. #if q1-passed [They establish immediate target-value
  recovery for the evaluated learner under the admitted protocol.] else [They
  do not establish immediate-value recovery: a prerequisite or the frozen
  learner criterion failed. Model class, optimization, capacity, and finite
  sample error remain alternative explanations.]
] else [
  No validated held-out result currently supplies the complete target-matching,
  leakage, aggregation, uncertainty, ranking, and calibration contract required
  for actor-visible one-step value.
]

== Exact Two-Step Recursion

#if q2-evidence [
  Exact-$Q_2$ error, complete-support coverage, independent-unit count, and the
  frozen tolerance decision are bound to the exact receipt and analysis
  manifest hashes under the `all_units_v1` independent-unit rule. #if q2-passed [This admits the first recursive target, not endpoint policy success.] else [The estimate remains a measured diagnostic, but failed $Q_1$ prerequisites
  or the exact-$Q_2$ rule block endpoint interpretation.]
] else [
  No qualifying held-out exact-Q2 receipt is available; recursive finite-horizon accuracy is therefore unestablished.
]

== Endpoint Recovery

#if recovery-evidence [
  The learned-myopic-to-oracle-lookahead endpoint-gap closure, paired scene
  interval, positive denominator, recovery decision, and analysis-manifest hash
  are available under one paired-scene contract. #if recovery-passed [They are
  admitted under passed headroom and recursive-value prerequisites.] else [The
  estimate is retained, but a failed prerequisite or recovery rule prevents a
  positive learned-policy conclusion.]
] else [
  The thesis cannot estimate learned endpoint recovery because the prerequisite gate chain is incomplete.
]

== Resource Feasibility

#if resource-evidence [
  Completed profiles report observed wall time, peak GPU memory, and storage. Extrapolation beyond those runs still requires an explicit scaling model.
] else [
  Renderer memory failures motivate bounded rendering and retained failure provenance, but no validated completed-store evidence supports throughput or dataset-volume extrapolation.
]
