= Results <sec:thesis-results>

#import "../experiment_data.typ": thesis-report-settings, load-thesis-report, endpoint-evidence-facts, oracle-endpoint-evidence-facts, headroom-evidence-facts, recovery-evidence-facts, q2-evidence-facts, report-store-fact, report-store-endpoint-evidence-valid, report-store-oracle-endpoint-evidence-valid, report-store-headroom-evidence-valid, report-store-recovery-evidence-valid, report-store-headroom-identity-valid, report-store-recovery-identity-valid, report-store-population-evidence-valid, report-store-measurement-evidence-valid, report-store-candidate-support-evidence-valid, report-stores-q1-evidence-valid, report-store-q2-evidence-valid, report-store-facts-share-value, report-store-facts-share-source, report-stores-facts-share-sha256, report-stores-facts-share-values, report-stores-have-facts, report-stores-decision-passed, evidence-gate-state, conditional-ratio-gate-state, short-store-label, format-report-value
#import "../draft_markers.typ": validation_todo
#import "../../shared/tables.typ": publication-table, index-cell

#validation_todo(
  [Populate one result row per inferential stage from a confirmatory bundle: evidence availability, gate decision, claim admissibility, estimate, uncertainty, and blocking condition. Every value must resolve to its raw and derived artifact provenance.],
  source: [confirmatory report bundle, exact-Q2 receipt, and analysis manifest],
  gate: [both evidentiary lanes and their six gate decisions resolve without fixture or pilot substitution],
)

#let report-settings = thesis-report-settings()
#let thesis_evidence_status = report-settings.evidence-status
#let thesis_data = load-thesis-report(
  report-settings.path,
  evidence-status: thesis_evidence_status,
  required-role: report-settings.required-role,
)
#let all-stores-valid = thesis_data.tables.stores.rows.len() > 0 and thesis_data.tables.stores.rows.all(store => store.validation_ok == true)
#let evidence-status(state) = if state.evidence_available [available] else [not available]
#let gate-status(state) = if not state.evidence_available {
  [not decided]
} else if state.gate_passed {
  [passed]
} else {
  [non-pass]
}
#let claim-status(state) = if state.claim_admissible [admissible] else [blocked]

#let resource-facts = ("runtime.wall_time_s", "runtime.peak_gpu_bytes", "storage.total_bytes")

#let confirmatory-evidence = thesis_evidence_status == "confirmatory" and all-stores-valid
#let population-evidence-available = confirmatory-evidence and thesis_data.tables.stores.rows.all(store => report-store-population-evidence-valid(
  thesis_data,
  store.store_id,
))
#let measurement-evidence-available = confirmatory-evidence and thesis_data.tables.stores.rows.all(store => report-store-measurement-evidence-valid(
  thesis_data,
  store.store_id,
))
#let measurement-state = evidence-gate-state(
  measurement-evidence-available,
  report-stores-decision-passed(thesis_data, "oracle.metric.repeatability.passed"),
)
#let support-evidence-available = population-evidence-available and thesis_data.tables.stores.rows.all(store => report-store-candidate-support-evidence-valid(
  thesis_data,
  store.store_id,
))
#let support-state = evidence-gate-state(
  support-evidence-available,
  report-stores-decision-passed(thesis_data, "candidate-support.gate.passed"),
)
#let shared-foundations-pass = measurement-state.claim_admissible and support-state.claim_admissible
#let oracle-endpoint-evidence-available = confirmatory-evidence and report-stores-have-facts(thesis_data, oracle-endpoint-evidence-facts, denominators: true) and thesis_data.tables.stores.rows.all(store => {
  let endpoint-scenes = report-store-fact(thesis_data, store.store_id, "policy.endpoint_gain.n_scenes").value
  type(endpoint-scenes) == int and endpoint-scenes > 0 and report-store-oracle-endpoint-evidence-valid(
    thesis_data,
    store.store_id,
    endpoint-scenes,
  )
})
#let endpoint-evidence-available = oracle-endpoint-evidence-available and report-stores-have-facts(thesis_data, endpoint-evidence-facts, denominators: true) and thesis_data.tables.stores.rows.all(store => {
  let endpoint-scenes = report-store-fact(thesis_data, store.store_id, "policy.endpoint_gain.n_scenes").value
  report-store-endpoint-evidence-valid(
    thesis_data,
    store.store_id,
    endpoint-scenes,
  )
})
#let headroom-evidence-available = oracle-endpoint-evidence-available and report-stores-have-facts(thesis_data, headroom-evidence-facts, denominators: true) and thesis_data.tables.stores.rows.all(store => {
  let endpoint-scenes = report-store-fact(thesis_data, store.store_id, "policy.endpoint_gain.n_scenes").value
  let headroom-scenes = report-store-fact(thesis_data, store.store_id, "policy.paired_scene_endpoint.n_scenes").value
  endpoint-scenes != none and endpoint-scenes > 0 and headroom-scenes == endpoint-scenes and report-store-headroom-evidence-valid(
    thesis_data,
    store.store_id,
    endpoint-scenes,
  ) and report-store-facts-share-value(
    thesis_data,
    store.store_id,
    (
      "policy.endpoint_gain.cohort_sha256",
      "policy.paired_scene_endpoint.cohort_sha256",
    ),
  ) and report-store-facts-share-source(
    thesis_data,
    store.store_id,
    oracle-endpoint-evidence-facts + headroom-evidence-facts,
  ) and report-store-headroom-identity-valid(
    thesis_data,
    store.store_id,
  )
})
#let headroom-state = evidence-gate-state(
  headroom-evidence-available,
  report-stores-decision-passed(thesis_data, "headroom_gate.passed"),
  prerequisites-passed: shared-foundations-pass,
)
#let q1-evidence-available = confirmatory-evidence and report-stores-q1-evidence-valid(
  thesis_data,
)
#let q1-state = evidence-gate-state(
  q1-evidence-available,
  report-stores-decision-passed(thesis_data, "q1.gate.passed"),
  prerequisites-passed: shared-foundations-pass,
)
#let q2-evidence-available = confirmatory-evidence and thesis_data.tables.stores.rows.all(store => report-store-q2-evidence-valid(
  thesis_data,
  store.store_id,
)) and report-stores-facts-share-values(thesis_data, q2-evidence-facts)
#let q1-q2-lineage-consistent = q1-evidence-available and q2-evidence-available and report-stores-facts-share-sha256(
  thesis_data,
  (
    "q1.model.bundle_manifest_sha256",
    "q2.exact.bundle_manifest_sha256",
  ),
)
#let q2-state = evidence-gate-state(
  q2-evidence-available,
  report-stores-decision-passed(thesis_data, "q2.exact.passed"),
  prerequisites-passed: q1-state.claim_admissible and q1-q2-lineage-consistent,
)
#let learned-chain-lineage-consistent = q1-q2-lineage-consistent and endpoint-evidence-available and report-stores-facts-share-sha256(
  thesis_data,
  (
    "q1.model.bundle_manifest_sha256",
    "q2.exact.bundle_manifest_sha256",
    "policy.endpoint_gain.learned_q.bundle_manifest_sha256",
  ),
)
#let recovery-contract-available = endpoint-evidence-available and headroom-evidence-available and report-stores-have-facts(thesis_data, recovery-evidence-facts, denominators: true) and thesis_data.tables.stores.rows.all(store => {
  let endpoint-scenes = report-store-fact(thesis_data, store.store_id, "policy.endpoint_gain.n_scenes").value
  let recovery-scenes = report-store-fact(thesis_data, store.store_id, "policy.q_recovery.n_scenes").value
  endpoint-scenes != none and endpoint-scenes > 0 and recovery-scenes == endpoint-scenes and report-store-recovery-evidence-valid(
    thesis_data,
    store.store_id,
    endpoint-scenes,
  ) and report-store-facts-share-value(
    thesis_data,
    store.store_id,
    (
      "policy.endpoint_gain.cohort_sha256",
      "policy.paired_scene_endpoint.cohort_sha256",
      "policy.q_recovery.cohort_sha256",
    ),
  ) and report-store-facts-share-source(
    thesis_data,
    store.store_id,
    endpoint-evidence-facts + headroom-evidence-facts + recovery-evidence-facts,
  ) and report-store-recovery-identity-valid(
    thesis_data,
    store.store_id,
  )
})
#let recovery-evidence = conditional-ratio-gate-state(
  endpoint-evidence-available,
  headroom-state.claim_admissible,
  recovery-contract-available,
  report-stores-decision-passed(thesis_data, "policy.q_recovery.passed"),
  remaining-prerequisites-passed: q2-state.claim_admissible and learned-chain-lineage-consistent,
)
#let recovery-state = recovery-evidence.state
#let recovery-ratio-reportable = recovery-evidence.ratio_evidence_available
#let resource-available = confirmatory-evidence and report-stores-have-facts(thesis_data, resource-facts)

The loaded report declares evidence class #emph(thesis_evidence_status). Schema
validity proves that provenance and missingness are readable; it cannot promote
a development fixture, training pilot, or incomplete store. The report keeps
three states separate: whether a gate's evidence is available, whether its
predeclared decision passes, and whether all prerequisites make its scientific
claim admissible. A measured non-pass remains reported. It neither becomes zero
nor suppresses independently measured evidence on the other lane. An immutable
digest is provenance only; evidence additionally requires its exact sidecar
payload to reproduce every claimed row.

#figure(
  publication-table(
    text-size: 7.1pt,
    columns: (0.62fr, 0.62fr, 0.6fr, 0.65fr, 1.3fr, 1.42fr),
    header: ([*Gate / RQ*], [*Evidence*], [*Decision*], [*Claim*], [*Interpretation if admissible*], [*Blocking condition*]),
    rows: (
      [measurement / RQ1], [#evidence-status(measurement-state)], [#gate-status(measurement-state)], [#claim-status(measurement-state)], [matched-unit error and rank stability pass], [missing pairs, rank mismatch, or tolerance non-pass],
      [population/action / RQ4], [#evidence-status(support-state)], [#gate-status(support-state)], [#claim-status(support-state)], [held-out attempts pass the lower-tail support rule], [missing attempts, low support, or excessive failed roots],
      [headroom / RQ2a], [#evidence-status(headroom-state)], [#gate-status(headroom-state)], [#claim-status(headroom-state)], [meaningful non-myopic endpoint headroom passes], [shared foundation or effect rule non-pass],
      [actor $Q_1$ / RQ3], [#evidence-status(q1-state)], [#gate-status(q1-state)], [#claim-status(q1-state)], [actor-protocol receipt and ranking/calibration rule pass], [shared foundation or actor-$Q_1$ rule non-pass],
      [learned/exact $Q_2$ / RQ2], [#evidence-status(q2-state)], [#gate-status(q2-state)], [#claim-status(q2-state)], [exact-$Q_2$ coverage, support, and rowwise tolerance pass], [$Q_1$/bundle prerequisite or exact-$Q_2$ non-pass],
      [endpoint recovery / RQ2b], [#evidence-status(recovery-state)], [#gate-status(recovery-state)], [#claim-status(recovery-state)], [threshold and positive interval support recovery], [headroom/bundle prerequisite or recovery non-pass],
    ),
  ),
  caption: [Evidence state, gate decision, and claim admissibility by inferential stage. Available evidence remains reported after a non-pass; only claims whose prerequisites pass are admitted.],
) <tab:thesis-result-availability>

#let population-summary-family = (band: "foundations", label: [Population], metrics: (
  (label: [Scenes], key: "study.population.scenes"),
  (label: [Targets], key: "study.population.targets"),
  (label: [Exclusions], key: "study.population.exclusions"),
))
#let measurement-summary-family = (band: "foundations", label: [Measurement], metrics: (
  (label: [Maximum repeat discrepancy], key: "oracle.metric.repeatability.max_abs_diff", denominator-key: "oracle.metric.repeatability.n_repeats", digits: 5),
  (label: [Measurement units], key: "oracle.metric.repeatability.n_measurement_units"),
  (label: [Matched-unit rank identity], key: "oracle.metric.repeatability.ranking_agreement"),
  (label: [Declared repeatability tolerance], key: "oracle.metric.repeatability.tolerance", digits: 5),
  (label: [Repeatability gate], key: "oracle.metric.repeatability.passed"),
))
#let support-summary-family = (band: "foundations", label: [Candidate support], metrics: (
  (label: [Actor-valid fraction], key: "candidate-support.actor-valid-fraction", digits: 3),
  (label: [P05 valid support], key: "candidate-support.valid-support-p05", digits: 1),
  (label: [P05 support minimum], key: "candidate-support.valid-support-p05.minimum", digits: 1),
  (label: [Failed-root rate], key: "candidate-support.failed-root-rate", digits: 3),
  (label: [Failed-root maximum], key: "candidate-support.failed-root-rate.maximum", digits: 3),
  (label: [Configured-family zero rate], key: "candidate-support.configured-family-zero-rate", digits: 3),
  (label: [Target-side balance], key: "candidate-support.target-side-balance", digits: 3),
  (label: [Circular orbit span], key: "candidate-support.circular-orbit-span", digits: 2),
  (label: [Support gate], key: "candidate-support.gate.passed", denominator-key: "study.population.scenes"),
))
#let endpoint-summary-family = (band: "policy", label: [Matched endpoints], metrics: (
  (label: [Oracle one-step gain], key: "policy.endpoint_gain.oracle_one_step.mean", low-key: "policy.endpoint_gain.oracle_one_step.ci_low", high-key: "policy.endpoint_gain.oracle_one_step.ci_high", denominator-key: "policy.endpoint_gain.n_scenes", digits: 3),
  (label: [Oracle lookahead gain], key: "policy.endpoint_gain.oracle_lookahead.mean", low-key: "policy.endpoint_gain.oracle_lookahead.ci_low", high-key: "policy.endpoint_gain.oracle_lookahead.ci_high", denominator-key: "policy.endpoint_gain.n_scenes", digits: 3),
  (label: [Learned-$Q$ gain], key: "policy.endpoint_gain.learned_q.mean", low-key: "policy.endpoint_gain.learned_q.ci_low", high-key: "policy.endpoint_gain.learned_q.ci_high", denominator-key: "policy.endpoint_gain.n_scenes", digits: 3),
))
#let headroom-summary-family = (band: "policy", label: [Oracle headroom], metrics: (
  (label: [Paired endpoint effect], key: "policy.paired_scene_endpoint.effect", low-key: "policy.paired_scene_endpoint.ci_low", high-key: "policy.paired_scene_endpoint.ci_high", denominator-key: "policy.paired_scene_endpoint.n_scenes", digits: 3),
  (label: [Declared minimum effect], key: "headroom_gate.minimum_effect", denominator-key: "policy.paired_scene_endpoint.n_scenes", digits: 3),
  (label: [Meaningful-headroom gate], key: "headroom_gate.passed", denominator-key: "policy.paired_scene_endpoint.n_scenes"),
))
#let q1-summary-family = (band: "q1", label: [Actor Q1], metrics: (
  (label: [Pairwise ranking], key: "q1.ranking.pairwise_accuracy", low-key: "q1.ranking.pairwise_accuracy.ci_low", high-key: "q1.ranking.pairwise_accuracy.ci_high", denominator-key: "q1.population.n_scenes", digits: 3),
  (label: [Ranking minimum], key: "q1.ranking.pairwise_accuracy.minimum", denominator-key: "q1.population.n_scenes", digits: 3),
  (label: [Calibration MAE], key: "q1.calibration.mae", denominator-key: "q1.population.n_scenes", digits: 4),
  (label: [Calibration maximum], key: "q1.calibration.mae.maximum", denominator-key: "q1.population.n_scenes", digits: 4),
  (label: [Actor-Q1 gate], key: "q1.gate.passed", denominator-key: "q1.population.n_scenes"),
))
#let q2-summary-family = (band: "q2", label: [Learned / exact $Q_2$ agreement], metrics: (
  (label: [Recursive MAE], key: "q2.exact.mae", denominator-key: "q2.exact.n_independent_units", digits: 4),
  (label: [Selected-chain coverage], key: "q2.exact.coverage", denominator-key: "q2.exact.n_independent_units", digits: 3),
  (label: [Coverage minimum], key: "q2.exact.coverage.minimum", denominator-key: "q2.exact.n_independent_units", digits: 3),
  (label: [Minimum support-stratum rows], key: "q2.exact.minimum_support_stratum_rows", denominator-key: "q2.exact.n_independent_units"),
  (label: [Independent units], key: "q2.exact.n_independent_units"),
  (label: [Required independent units], key: "q2.exact.minimum_independent_units", denominator-key: "q2.exact.n_independent_units"),
  (label: [Minimum rows per unit], key: "q2.exact.minimum_rows_per_independent_unit", denominator-key: "q2.exact.n_independent_units"),
  (label: [Required rows per unit], key: "q2.exact.minimum_rows_per_independent_unit.required", denominator-key: "q2.exact.n_independent_units"),
  (label: [Absolute tolerance], key: "q2.exact.absolute_tolerance", denominator-key: "q2.exact.n_independent_units", digits: 5),
  (label: [Relative tolerance], key: "q2.exact.relative_tolerance", denominator-key: "q2.exact.n_independent_units", digits: 5),
  (label: [Maximum tolerance excess], key: "q2.exact.maximum_tolerance_excess", denominator-key: "q2.exact.n_independent_units", digits: 5),
  (label: [Learned/exact agreement gate], key: "q2.exact.passed", denominator-key: "q2.exact.n_independent_units"),
))
#let recovery-summary-family = (band: "policy", label: [Endpoint recovery], metrics: (
  (label: [Recovered headroom], key: "policy.q_recovery.fraction", low-key: "policy.q_recovery.ci_low", high-key: "policy.q_recovery.ci_high", denominator-key: "policy.q_recovery.n_scenes", digits: 3),
  (label: [Required recovery fraction], key: "policy.q_recovery.minimum_fraction", denominator-key: "policy.q_recovery.n_scenes", digits: 3),
  (label: [Recovery gate], key: "policy.q_recovery.passed", denominator-key: "policy.q_recovery.n_scenes"),
))
#let resources-summary-family = (band: "resources", label: [Resources], metrics: (
  (label: [Wall time], key: "runtime.wall_time_s", digits: 1),
  (label: [Peak GPU memory], key: "runtime.peak_gpu_bytes"),
  (label: [Storage], key: "storage.total_bytes"),
))

#let all-result-summary-families = (
  population-summary-family,
  measurement-summary-family,
  support-summary-family,
  endpoint-summary-family,
  headroom-summary-family,
  q1-summary-family,
  q2-summary-family,
  recovery-summary-family,
  resources-summary-family,
)

#let result-summary-families = {
  let families = ()
  if population-evidence-available { families.push(population-summary-family) }
  if measurement-state.evidence_available { families.push(measurement-summary-family) }
  if support-state.evidence_available { families.push(support-summary-family) }
  if endpoint-evidence-available { families.push(endpoint-summary-family) }
  if headroom-state.evidence_available { families.push(headroom-summary-family) }
  if q1-state.evidence_available { families.push(q1-summary-family) }
  if q2-state.evidence_available { families.push(q2-summary-family) }
  if recovery-ratio-reportable { families.push(recovery-summary-family) }
  if resource-available { families.push(resources-summary-family) }
  families
}

#let result-unit-label(unit) = if unit == none or unit == "dimensionless" {
  [—]
} else if unit == "root_normalized_return" {
  [norm. return]
} else {
  [#unit]
}

#let result-summary-rows-for(report, families, scope: "profile") = {
  assert(scope in ("profile", "global"), message: "invalid result-summary scope")
  let rows = ()
  let profile-span = families.fold(0, (total, family) => total + family.metrics.len())
  let stores = if scope == "global" {
    report.tables.stores.rows.slice(0, 1)
  } else {
    report.tables.stores.rows
  }
  for store in stores {
    let store-id = store.store_id
    let label = if scope == "global" { [Global] } else { short-store-label(report, store-id) }
    let first-profile-row = true
    for family in families {
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
        let fact = report-store-fact(report, store-id, metric.key)
        rows.push(metric.label)
        rows.push([#format-report-value(fact.value, digits: digits)])
        rows.push(if low-key == none { [—] } else {
          let low = report-store-fact(report, store-id, low-key)
          [#format-report-value(low.value, digits: digits)]
        })
        rows.push(if high-key == none { [—] } else {
          let high = report-store-fact(report, store-id, high-key)
          [#format-report-value(high.value, digits: digits)]
        })
        rows.push(result-unit-label(fact.unit))
        rows.push(if denominator-key == none { [#format-report-value(fact.n)] } else {
          let denominator = report-store-fact(report, store-id, denominator-key)
          [#format-report-value(denominator.value)]
        })
      }
    }
  }
  rows
}

#let result-summary-table(rows) = publication-table(
  columns: (0.72fr, 0.95fr, 1.05fr, 0.62fr, 0.62fr, 0.62fr, 0.55fr, 0.5fr),
  align: (left, left, left, right, right, right, left, right),
  text-size: 7.2pt,
  header: ([*Scope*], [*Gate*], [*Measure*], [*Estimate*], [*CI low*], [*CI high*], [*Unit*], [*$n$*]),
  rows: rows,
)

#let foundation-summary-rows = result-summary-rows-for(
  thesis_data,
  result-summary-families.filter(family => family.band == "foundations"),
)
#let policy-summary-rows = result-summary-rows-for(
  thesis_data,
  result-summary-families.filter(family => family.band == "policy"),
)
#let q1-summary-rows = result-summary-rows-for(
  thesis_data,
  result-summary-families.filter(family => family.band == "q1"),
  scope: "global",
)
#let q2-summary-rows = result-summary-rows-for(
  thesis_data,
  result-summary-families.filter(family => family.band == "q2"),
  scope: "global",
)
#let resource-summary-rows = result-summary-rows-for(
  thesis_data,
  result-summary-families.filter(family => family.band == "resources"),
)

#if foundation-summary-rows.len() > 0 [
  #figure(
    result-summary-table(foundation-summary-rows),
    caption: [Available confirmatory population, measurement, and candidate-support values by profile.],
  ) <tab:thesis-confirmatory-values>
]

#if policy-summary-rows.len() > 0 [
  #figure(
    result-summary-table(policy-summary-rows),
    caption: [Available confirmatory endpoint, headroom, and recovery values by profile.],
  ) <tab:thesis-confirmatory-policy-values>
]

#if q1-summary-rows.len() > 0 [
  #figure(
    result-summary-table(q1-summary-rows),
    caption: [One global actor-$Q_1$ ranking and calibration analysis over the complete frozen held-out population.],
  ) <tab:thesis-confirmatory-q1-values>
]

#if q2-summary-rows.len() > 0 [
  #figure(
    result-summary-table(q2-summary-rows),
    caption: [One global exact-$Q_2$ receipt over the complete certified population. Coverage is census-relative; error and tolerance summaries are conditional on selected admitted support.],
  ) <tab:thesis-confirmatory-q2-values>
]

#if resource-summary-rows.len() > 0 [
  #figure(
    result-summary-table(resource-summary-rows),
    caption: [Observed resource values by completed profile.],
  )
]

== Measurement Validity

#if measurement-state.evidence_available [
  The confirmatory bundle contains an immutable matched-unit receipt whose
  repeat--measurement pairs bind inputs, metric-output artifacts, protocol,
  configuration, and store manifest. An independent benchmark plan fixes the
  expected repeat identifiers and count, measurement identities, and
  ranking-group membership. The report verifies rectangular
  completeness, reproduces the maximum discrepancy, and derives rank identity
  from the bound gains under the frozen order and tie rule. The values appear in
  @tab:thesis-confirmatory-values. The measurement gate
  #if measurement-state.gate_passed [passes, so its dependent claims may use
  the metric.] else [does not pass; the observed result remains auditable, but
  dependent claims are blocked.]
] else [
  No qualifying benchmark-plan and receipt pair binds a complete repeated
  matched-unit roster with recomputed error and rank stability for the frozen
  endpoint metric. Dependent claims are blocked without converting separate
  diagnostics to zero.
]

== Population and Action Support

#if support-state.evidence_available [
  An independently frozen benchmark plan fixes the scene/target-task/root
  roster over the declared admitted-task population, while an immutable
  per-attempt receipt binds each planned identity to valid count, threshold,
  outcome, configuration, and store manifest. This establishes support for the
  declared tasks, not actor-visible target discovery or universal target
  coverage. The report recomputes
  lower-tail valid support and failed-root rate from those rows, then
  supplies actor-valid fraction, configured-family zero rate, target-side
  balance, and circular orbit span as diagnostics. These state--scene summaries
  delimit the action population; they are not paired policy effects. The
  rule-checked minimum factual-support decision
  #if support-state.gate_passed [passes.] else [is a non-pass, so dependent
  claims are blocked.] Family survival and target-relative diversity remain
  diagnostics rather than being promoted by this minimum-support gate.
] else [
  No held-out bundle supplies the study population, independent benchmark
  roster, and per-attempt receipt from which the support summary and decision
  can be recomputed. Training-source
  reachability and renderer failures remain feasibility observations.
]

== Oracle Headroom

#if headroom-state.evidence_available [
  The paired scene endpoint effect, interval, denominator, declared minimum
  effect, and rule-checked meaningful-headroom decision are available in
  @tab:thesis-confirmatory-policy-values. The headroom claim is
  #if headroom-state.claim_admissible [admissible under the passed shared
  foundations.] else [blocked by a non-passing shared foundation or headroom
  decision; its measured effect remains reported.]
] else [
  No paired held-out endpoint estimate and meaningful-headroom decision are
  available; this does not determine accuracy on the separate learned-value
  lane.
]

== Actor-Visible One-Step Value

#if q1-state.evidence_available [
  The content-addressed bundle manifest freezes the independent population
  benchmark, test provenance, and ordered store manifests; the protocol receipt
  must agree with that anchor and with the complete held-out target,
  realized-state, candidate, and selected-history rosters. For this campaign's
  detector-admitted targets, the report checks the observed-target admission
  rule, an exact allowlisted
  $Q_1$ actor-input leaf manifest, actor-action versus oracle-label mask
  separation, hard-mask use, and strictly causal history rather than trusting
  summary flags. Each leaf has a fixed schema, source owner, and independently
  anchored or derived content binding to the actor, rollout, implementation, or
  actor-state contract; the receipt does not establish provenance upstream of
  those bound artifacts.
  The same receipt binds every admitted candidate's decoded prediction and
  persisted one-step label. The report reconstructs strict statewise pair
  accuracy, candidate calibration error, scene macro-averages, the
  leave-one-scene-out interval, and the globally deduplicated scene denominator
  before checking the declared thresholds. These values and their rule-checked
  decision are available from one global analysis in
  @tab:thesis-confirmatory-q1-values.
  The actor-$Q_1$ claim is
  #if q1-state.claim_admissible [admissible under the passed target, state,
  measurement, and support protocols.] else [blocked by a shared foundation or
  the actor-$Q_1$ decision; the measurements remain reportable independently of
  oracle headroom.]
] else [
  No validated held-out result currently combines a qualifying actor-protocol
  receipt with target-conditioned one-step ranking and calibration from
  actor-visible inputs.
]

== Learned-versus-Exact $Q_2$ Agreement

#if q2-state.evidence_available [
  Learned-versus-exact $Q_2$ error, selected-chain coverage, support-stratum and
  per-unit minima, rowwise tolerance excess, independent-unit count, and the
  frozen `all_units_v1` decision are available from one global receipt in
  @tab:thesis-confirmatory-q2-values. Coverage is measured against the complete
  certified census; error and tolerance summaries condition on selected admitted
  support. Every exact row carries the complete identity-bearing successor
  reward ledger from which its factual maximum and Bellman target are
  recomputed. Aggregate MAE remains diagnostic;
  it cannot compensate for a failed row, stratum, or unit. The recursive claim
  is #if q2-state.claim_admissible [admissible on the passed
  actor-$Q_1$ path.] else [blocked by its shared foundations, actor-$Q_1$, or
  exact-$Q_2$ decision, or by a Q1/Q2 bundle mismatch; the mismatch is a
  prerequisite failure, not a measured non-pass.]
  Even an admitted result does not establish endpoint policy success.
] else [
  No qualifying held-out learned-versus-exact $Q_2$ receipt is available;
  recursive finite-horizon accuracy is therefore unestablished.
]

== Endpoint Recovery

#if recovery-ratio-reportable [
  The recovered-headroom point fraction, jointly bootstrapped paired-scene
  interval, required fraction, denominator, and rule-checked recovery decision
  are available. Passage means that the point estimate reaches the declared
  fraction and the interval supports positive mean recovery; it does not claim
  that the population recovery fraction exceeds that threshold. The endpoint
  claim is
  #if recovery-state.claim_admissible [admissible because both the oracle-
  headroom and learned-value lanes pass.] else [blocked by at least one lane or
  the recovery decision, or by a learned-endpoint bundle mismatch; that mismatch
  is a prerequisite failure, and the endpoint observations remain auditable.]
] else if endpoint-evidence-available [
  Matched per-policy endpoint estimates and intervals remain auditable in
  @tab:thesis-confirmatory-policy-values, but the recovered-headroom ratio and its
  decision are not reported because meaningful headroom is inadmissible or the
  frozen ratio, interval, denominator, cohort, and provenance contract is
  incomplete. The endpoint claim remains blocked without erasing those
  underlying aggregated per-policy estimates.
] else [
  No complete independently evaluated matched per-policy endpoints are
  available, so recovery is unavailable. It additionally requires passed
  oracle-headroom and learned-value lanes; either lane alone cannot answer RQ2.
]

== Resource Feasibility

#if resource-available [
  Completed profiles report observed wall time, peak GPU memory, and storage. Extrapolation beyond those runs still requires an explicit scaling model.
] else [
  Renderer memory failures motivate bounded rendering and retained failure provenance, but no validated completed-store evidence supports throughput or dataset-volume extrapolation.
]
