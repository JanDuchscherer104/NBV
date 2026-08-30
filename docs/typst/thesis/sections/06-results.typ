= Results <sec:thesis-results>

#import "../experiment_data.typ": thesis-report-settings, load-thesis-report, report-store-fact, report-store-facts-match-contract, report-stores-have-facts, report-stores-decision-passed, evidence-gate-state, short-store-label, format-report-value
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
#let fact-value(store-id, key, digits: none) = {
  let row = report-store-fact(thesis_data, store-id, key)
  format-report-value(row.value, digits: digits, unit: row.unit)
}
#let evidence-status(state) = if state.evidence_available [available] else [not available]
#let gate-status(state) = if not state.evidence_available {
  [not decided]
} else if state.gate_passed {
  [passed]
} else {
  [non-pass]
}
#let claim-status(state) = if state.claim_admissible [admissible] else [blocked]

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
)
#let headroom-facts = ("policy.paired_scene_endpoint.effect", "policy.paired_scene_endpoint.ci_low", "policy.paired_scene_endpoint.ci_high", "policy.paired_scene_endpoint.n_scenes", "headroom_gate.passed")
#let headroom-contract = (
  (key: "policy.paired_scene_endpoint.effect", aggregation: "paired_scene_mean_difference"),
  (key: "policy.paired_scene_endpoint.ci_low", aggregation: "paired_scene_mean_difference"),
  (key: "policy.paired_scene_endpoint.ci_high", aggregation: "paired_scene_mean_difference"),
  (key: "policy.paired_scene_endpoint.n_scenes", aggregation: "count"),
  (key: "headroom_gate.passed", aggregation: "paired_scene_decision"),
)
#let q1-facts = ("q1.ranking.pairwise_accuracy", "q1.calibration.mae", "q1.population.n_scenes", "q1.gate.passed")
#let q2-facts = ("q2.exact.mae", "q2.exact.coverage", "q2.exact.n_independent_units", "q2.exact.passed")
#let recovery-facts = ("policy.q_recovery.fraction", "policy.q_recovery.ci_low", "policy.q_recovery.ci_high", "policy.q_recovery.n_scenes", "policy.q_recovery.passed")
#let resource-facts = ("runtime.wall_time_s", "runtime.peak_gpu_bytes", "storage.total_bytes")

#let confirmatory-evidence = thesis_evidence_status == "confirmatory" and all-stores-valid
#let population-evidence-available = confirmatory-evidence and report-stores-have-facts(thesis_data, population-facts, denominators: true)
#let measurement-evidence-available = confirmatory-evidence and report-stores-have-facts(thesis_data, measurement-facts)
#let measurement-state = evidence-gate-state(
  measurement-evidence-available,
  report-stores-decision-passed(thesis_data, "oracle.metric.repeatability.passed"),
)
#let support-evidence-available = population-evidence-available and report-stores-have-facts(thesis_data, candidate-support-facts, denominators: true) and thesis_data.tables.stores.rows.all(store => {
  let scene-count = report-store-fact(thesis_data, store.store_id, "study.population.scenes").value
  scene-count != none and scene-count > 0 and report-store-facts-match-contract(
    thesis_data,
    store.store_id,
    candidate-support-contract,
    scene-count,
  )
})
#let support-state = evidence-gate-state(
  support-evidence-available,
  report-stores-decision-passed(thesis_data, "candidate-support.gate.passed"),
)
#let shared-foundations-pass = measurement-state.claim_admissible and support-state.claim_admissible
#let headroom-evidence-available = confirmatory-evidence and report-stores-have-facts(thesis_data, headroom-facts) and thesis_data.tables.stores.rows.all(store => {
  let paired-scenes = report-store-fact(thesis_data, store.store_id, "policy.paired_scene_endpoint.n_scenes").value
  paired-scenes != none and paired-scenes > 0 and report-store-facts-match-contract(
    thesis_data,
    store.store_id,
    headroom-contract,
    paired-scenes,
  )
})
#let headroom-state = evidence-gate-state(
  headroom-evidence-available,
  report-stores-decision-passed(thesis_data, "headroom_gate.passed"),
  prerequisites-passed: shared-foundations-pass,
)
#let q1-evidence-available = confirmatory-evidence and report-stores-have-facts(thesis_data, q1-facts, denominators: true)
#let q1-state = evidence-gate-state(
  q1-evidence-available,
  report-stores-decision-passed(thesis_data, "q1.gate.passed"),
  prerequisites-passed: shared-foundations-pass,
)
#let q2-evidence-available = confirmatory-evidence and report-stores-have-facts(thesis_data, q2-facts, denominators: true)
#let q2-state = evidence-gate-state(
  q2-evidence-available,
  report-stores-decision-passed(thesis_data, "q2.exact.passed"),
  prerequisites-passed: q1-state.claim_admissible,
)
#let recovery-evidence-available = confirmatory-evidence and report-stores-have-facts(thesis_data, recovery-facts, denominators: true)
#let recovery-state = evidence-gate-state(
  recovery-evidence-available,
  report-stores-decision-passed(thesis_data, "policy.q_recovery.passed"),
  prerequisites-passed: headroom-state.claim_admissible and q2-state.claim_admissible,
)
#let recovery-ratio-reportable = recovery-state.evidence_available and headroom-state.claim_admissible
#let resource-available = confirmatory-evidence and report-stores-have-facts(thesis_data, resource-facts)

The loaded report declares evidence class #emph(thesis_evidence_status). Schema
validity proves that provenance and missingness are readable; it cannot promote
a development fixture, training pilot, or incomplete store. The report keeps
three states separate: whether a gate's evidence is available, whether its
predeclared decision passes, and whether all prerequisites make its scientific
claim admissible. A measured non-pass remains reported. It neither becomes zero
nor suppresses independently measured evidence on the other lane.

#figure(
  publication-table(
    text-size: 7.1pt,
    columns: (0.62fr, 0.62fr, 0.6fr, 0.65fr, 1.3fr, 1.42fr),
    header: ([*Gate / RQ*], [*Evidence*], [*Decision*], [*Claim*], [*Interpretation if admissible*], [*Blocking condition*]),
    rows: (
      [measurement / RQ1], [#evidence-status(measurement-state)], [#gate-status(measurement-state)], [#claim-status(measurement-state)], [metric comparisons are stable under the frozen protocol], [absent repeats, identity mismatch, or tolerance non-pass],
      [population/action / RQ4], [#evidence-status(support-state)], [#gate-status(support-state)], [#claim-status(support-state)], [the held-out task and finite-action population is supported], [missing denominators, exclusions, family survival, or feasibility],
      [headroom / RQ2a], [#evidence-status(headroom-state)], [#gate-status(headroom-state)], [#claim-status(headroom-state)], [the frozen setup exposes meaningful non-myopic endpoint headroom], [a shared foundation or meaningful-effect rule does not pass],
      [actor $Q_1$ / RQ3], [#evidence-status(q1-state)], [#gate-status(q1-state)], [#claim-status(q1-state)], [actor-visible evidence recovers immediate target value], [a shared foundation, actor protocol, matching, leakage, ranking, or calibration rule does not pass],
      [learned/exact $Q_2$ / RQ2], [#evidence-status(q2-state)], [#gate-status(q2-state)], [#claim-status(q2-state)], [the first learned recursive prediction agrees on complete exact support], [the $Q_1$ claim, complete support, or recursion tolerance does not pass],
      [endpoint recovery / RQ2b], [#evidence-status(recovery-state)], [#gate-status(recovery-state)], [#claim-status(recovery-state)], [the learned policy recovers the prespecified fraction of headroom], [headroom, the learned-value lane, or the recovery rule does not pass],
    ),
  ),
  caption: [Evidence state, gate decision, and claim admissibility by inferential stage. Available evidence remains reported after a non-pass; only claims whose prerequisites pass are admitted.],
) <tab:thesis-result-availability>

#let result-summary-families = {
  let families = ()
  if population-evidence-available {
    families.push((label: [Population], metrics: (
      (label: [Scenes], key: "study.population.scenes"),
      (label: [Targets], key: "study.population.targets"),
      (label: [Exclusions], key: "study.population.exclusions"),
    )))
  }
  if measurement-state.evidence_available {
    families.push((label: [Measurement], metrics: (
      (label: [Maximum repeat discrepancy], key: "oracle.metric.repeatability.max_abs_diff", denominator-key: "oracle.metric.repeatability.n_repeats", digits: 5),
      (label: [Repeatability gate], key: "oracle.metric.repeatability.passed"),
    )))
  }
  if support-state.evidence_available {
    families.push((label: [Candidate support], metrics: (
      (label: [Actor-valid fraction], key: "candidate-support.actor-valid-fraction", digits: 3),
      (label: [P05 valid support], key: "candidate-support.valid-support-p05", digits: 1),
      (label: [Configured-family zero rate], key: "candidate-support.configured-family-zero-rate", digits: 3),
      (label: [Target-side balance], key: "candidate-support.target-side-balance", digits: 3),
      (label: [Circular orbit span], key: "candidate-support.circular-orbit-span", digits: 2),
      (label: [Support gate], key: "candidate-support.gate.passed", denominator-key: "study.population.scenes"),
    )))
  }
  if headroom-state.evidence_available {
    families.push((label: [Oracle headroom], metrics: (
      (label: [Paired endpoint effect], key: "policy.paired_scene_endpoint.effect", low-key: "policy.paired_scene_endpoint.ci_low", high-key: "policy.paired_scene_endpoint.ci_high", denominator-key: "policy.paired_scene_endpoint.n_scenes", digits: 3),
      (label: [Meaningful-headroom gate], key: "headroom_gate.passed", denominator-key: "policy.paired_scene_endpoint.n_scenes"),
    )))
  }
  if q1-state.evidence_available {
    families.push((label: [Actor Q1], metrics: (
      (label: [Pairwise ranking], key: "q1.ranking.pairwise_accuracy", denominator-key: "q1.population.n_scenes", digits: 3),
      (label: [Calibration MAE], key: "q1.calibration.mae", denominator-key: "q1.population.n_scenes", digits: 4),
      (label: [Actor-Q1 gate], key: "q1.gate.passed", denominator-key: "q1.population.n_scenes"),
    )))
  }
  if q2-state.evidence_available {
    families.push((label: [Learned / exact $Q_2$ agreement], metrics: (
      (label: [Recursive MAE], key: "q2.exact.mae", denominator-key: "q2.exact.n_independent_units", digits: 4),
      (label: [Complete-support coverage], key: "q2.exact.coverage", denominator-key: "q2.exact.n_independent_units", digits: 3),
      (label: [Learned/exact agreement gate], key: "q2.exact.passed", denominator-key: "q2.exact.n_independent_units"),
    )))
  }
  if recovery-ratio-reportable {
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

#if measurement-state.evidence_available [
  The confirmatory bundle contains the frozen repeatability population,
  statistic, tolerance decision, and provenance; values appear in
  @tab:thesis-confirmatory-values. The measurement gate
  #if measurement-state.gate_passed [passes, so its dependent claims may use
  the metric.] else [does not pass; the observed result remains auditable, but
  dependent claims are blocked.]
] else [
  The loaded evidence does not contain the confirmatory repeatability statistic
  and decision for the frozen target-specific endpoint metric. Dependent claims
  are therefore blocked; separately recorded diagnostics are not converted to
  zero or erased.
]

== Population and Action Support

#if support-state.evidence_available [
  The report supplies scene, target, and exclusion denominators together with
  actor-valid fraction, lower-tail valid support, configured-family zero rate,
  target-side balance, and circular orbit span. These state--scene summaries
  delimit the action population; they are not paired policy effects. The
  prespecified support decision #if support-state.gate_passed [passes.] else [is
  a non-pass, so claims requiring adequate held-out task and action support are
  blocked.]
] else [
  No validated held-out bundle currently supplies both the study population,
  complete candidate-support denominators, and their prespecified support
  decision. Training-source reachability and renderer failures remain
  feasibility observations only.
]

== Oracle Headroom

#if headroom-state.evidence_available [
  The paired scene endpoint effect, interval, denominator, and
  meaningful-headroom decision are available in
  @tab:thesis-confirmatory-values. The headroom claim is
  #if headroom-state.claim_admissible [admissible under the passed shared
  foundations.] else [blocked by a non-passing shared foundation or headroom
  decision; its measured effect remains reported.]
] else [
  No complete paired held-out endpoint estimate and meaningful-headroom
  decision are available. This absence does not determine actor-visible
  one-step or recursive prediction accuracy on the separate learned-value lane.
]

== Actor-Visible One-Step Value

#if q1-state.evidence_available [
  Held-out actor-visible ranking, calibration, scene denominators, and their
  decision are available. The actor-$Q_1$ claim is
  #if q1-state.claim_admissible [admissible under the passed target, state,
  measurement, and support protocols.] else [blocked by a shared foundation or
  the actor-$Q_1$ decision; the measurements remain reportable independently of
  oracle headroom.]
] else [
  No validated held-out result currently shows target-conditioned one-step ranking and calibration from actor-visible inputs.
]

== Learned-versus-Exact $Q_2$ Agreement

#if q2-state.evidence_available [
  Learned-versus-exact $Q_2$ error, complete-support coverage,
  independent-unit count, and the frozen tolerance decision are available. The
  recursive claim is #if q2-state.claim_admissible [admissible on the passed
  actor-$Q_1$ path.] else [blocked by its shared foundations, actor-$Q_1$, or
  exact-$Q_2$ decision.] Even an admitted result does not establish endpoint
  policy success.
] else [
  No qualifying held-out learned-versus-exact $Q_2$ receipt is available;
  recursive finite-horizon accuracy is therefore unestablished.
]

== Endpoint Recovery

#if recovery-ratio-reportable [
  The recovered-headroom fraction, paired scene interval, denominator, and
  recovery decision are available. The endpoint claim is
  #if recovery-state.claim_admissible [admissible because both the oracle-
  headroom and learned-value lanes pass.] else [blocked by at least one lane or
  the recovery decision; the recorded endpoint observations remain auditable.]
] else if recovery-state.evidence_available [
  Matched endpoint observations and their recovery decision remain auditable,
  but the recovered-headroom ratio is not reported because its meaningful-
  headroom denominator is not admissible. The endpoint claim is blocked without
  erasing those underlying observations.
] else [
  The thesis has no complete matched endpoint-recovery estimate and decision.
  Endpoint recovery additionally requires passed oracle-headroom and learned-
  value lanes; a result on either lane alone cannot answer RQ2.
]

== Resource Feasibility

#if resource-available [
  Completed profiles report observed wall time, peak GPU memory, and storage. Extrapolation beyond those runs still requires an explicit scaling model.
] else [
  Renderer memory failures motivate bounded rendering and retained failure provenance, but no validated completed-store evidence supports throughput or dataset-volume extrapolation.
]
