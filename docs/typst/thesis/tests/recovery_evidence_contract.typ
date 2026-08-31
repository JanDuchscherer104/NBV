#import "../experiment_data.typ": canonical-sidecar-id, conditional-ratio-gate-state, evidence-gate-state, endpoint-evidence-facts, oracle-endpoint-evidence-facts, headroom-evidence-facts, recovery-evidence-facts, headroom-decision-rule, paired-interval-method, recovery-decision-rule, recovery-interval-method, recovery-ratio-definition, report-sidecar-projection-sha256, report-store-endpoint-evidence-valid, report-store-oracle-endpoint-evidence-valid, report-store-headroom-evidence-valid, report-store-recovery-evidence-valid, report-store-headroom-identity-valid, report-store-recovery-identity-valid, report-store-fact, report-store-facts-share-source, report-store-facts-share-value, report-stores-have-facts

#let digest-a = "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
#let digest-b = "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"
#let sidecar-a = canonical-sidecar-id("paired-policy", digest-a)
#let sidecar-b = canonical-sidecar-id("other", digest-b)
#let source = "analysis/paired-policy.json|sidecar:" + sidecar-a
#let sidecars = (
  (sidecar_id: sidecar-a, path: "paired-policy", name: "paired-policy", sha256: digest-a, format: "json", status: "confirmatory"),
  (sidecar_id: sidecar-b, path: "other", name: "other", sha256: digest-b, format: "json", status: "confirmatory"),
)
#let cohort-a = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
#let cohort-b = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
#let bundle-manifest = "8181818181818181818181818181818181818181818181818181818181818181"
#let fact(key, value, unit, n, aggregation, source: source) = (
  store_id: "store-a",
  key: key,
  value: value,
  unit: unit,
  n: n,
  aggregation: aggregation,
  status: "confirmatory",
  source: source,
)
#let typed-sidecar-row(sidecar-id, key, value) = {
  let base = (
    sidecar_id: sidecar-id,
    key: key,
    value_bool: none,
    value_int: none,
    value_float: none,
    value_text: none,
    is_missing: false,
  )
  if type(value) == bool {
    base + (value_type: "bool", value_bool: value)
  } else if type(value) == int {
    base + (value_type: "int", value_int: value)
  } else if type(value) == float {
    base + (value_type: "float", value_float: value)
  } else if type(value) == str {
    base + (value_type: "str", value_text: value)
  } else {
    assert(false, message: "unsupported synthetic sidecar value")
  }
}
#let analysis-sidecar-value-rows(sidecar-id, logical-name, rows) = {
  let output = (
    typed-sidecar-row(sidecar-id, "schema_version", "aria-nbv-analysis-facts-v1"),
    typed-sidecar-row(sidecar-id, "bundle_role", "analysis_facts"),
    typed-sidecar-row(sidecar-id, "logical_name", logical-name),
    typed-sidecar-row(sidecar-id, "status", "confirmatory"),
  )
  for (index, row) in rows.enumerate() {
    let prefix = "facts[" + str(index) + "]"
    let provenance = row.source.replace("|sidecar:" + sidecar-id, "")
    output += (
      typed-sidecar-row(sidecar-id, prefix + ".store_id", row.store_id),
      typed-sidecar-row(sidecar-id, prefix + ".key", row.key),
      typed-sidecar-row(sidecar-id, prefix + ".value", row.value),
      typed-sidecar-row(sidecar-id, prefix + ".unit", row.unit),
      typed-sidecar-row(sidecar-id, prefix + ".n", row.n),
      typed-sidecar-row(sidecar-id, prefix + ".aggregation", row.aggregation),
      typed-sidecar-row(sidecar-id, prefix + ".provenance", provenance),
    )
  }
  output
}
#let mutate-sidecar-fact-value(sidecar-value-rows, fact-key, replacement) = {
  let key-row = sidecar-value-rows.find(row => (
    row.key.match(regex("^facts\\[[0-9]+\\]\\.key$")) != none,
    row.value_type == "str",
    row.value_text == fact-key,
  ).all(value => value))
  let prefix = key-row.key.replace(regex("\\.key$"), "")
  sidecar-value-rows.map(row => if row.key == prefix + ".value" {
    typed-sidecar-row(row.sidecar_id, row.key, replacement)
  } else { row })
}
#let mutate-fact-value(rows, fact-key, replacement) = rows.map(row => if row.key == fact-key {
  row + (value: replacement)
} else { row })
#let endpoint-rows(cohort: cohort-a, bundle: bundle-manifest, source: source, scene-value: 5) = (
  fact("policy.endpoint_gain.oracle_one_step.mean", 0.20, "fraction", 5, "paired_scene_endpoint_gain", source: source),
  fact("policy.endpoint_gain.oracle_one_step.ci_low", 0.10, "fraction", 5, "paired_scene_endpoint_gain", source: source),
  fact("policy.endpoint_gain.oracle_one_step.ci_high", 0.30, "fraction", 5, "paired_scene_endpoint_gain", source: source),
  fact("policy.endpoint_gain.oracle_lookahead.mean", 0.50, "fraction", 5, "paired_scene_endpoint_gain", source: source),
  fact("policy.endpoint_gain.oracle_lookahead.ci_low", 0.40, "fraction", 5, "paired_scene_endpoint_gain", source: source),
  fact("policy.endpoint_gain.oracle_lookahead.ci_high", 0.60, "fraction", 5, "paired_scene_endpoint_gain", source: source),
  fact("policy.endpoint_gain.learned_q.mean", 0.38, "fraction", 5, "paired_scene_endpoint_gain", source: source),
  fact("policy.endpoint_gain.learned_q.ci_low", 0.28, "fraction", 5, "paired_scene_endpoint_gain", source: source),
  fact("policy.endpoint_gain.learned_q.ci_high", 0.48, "fraction", 5, "paired_scene_endpoint_gain", source: source),
  fact("policy.endpoint_gain.learned_q.bundle_manifest_sha256", bundle, "sha256", 5, "policy_identity", source: source),
  fact("policy.endpoint_gain.interval_method", paired-interval-method, "identity", 5, "analysis_identity", source: source),
  fact("policy.endpoint_gain.n_scenes", scene-value, "count", 5, "count", source: source),
  fact("policy.endpoint_gain.cohort_sha256", cohort, "sha256", 5, "cohort_binding_sha256", source: source),
)
#let headroom-rows(
  cohort: cohort-a,
  source: source,
  effect: 0.30,
  ci-low: 0.18,
  ci-high: 0.42,
  minimum-effect: 0.20,
  rule: headroom-decision-rule,
  passed: true,
) = (
  fact("policy.paired_scene_endpoint.effect", effect, "fraction", 5, "paired_scene_mean_difference", source: source),
  fact("policy.paired_scene_endpoint.ci_low", ci-low, "fraction", 5, "paired_scene_mean_difference", source: source),
  fact("policy.paired_scene_endpoint.ci_high", ci-high, "fraction", 5, "paired_scene_mean_difference", source: source),
  fact("policy.paired_scene_endpoint.interval_method", paired-interval-method, "identity", 5, "analysis_identity", source: source),
  fact("policy.paired_scene_endpoint.n_scenes", 5, "count", 5, "count", source: source),
  fact("policy.paired_scene_endpoint.cohort_sha256", cohort, "sha256", 5, "cohort_binding_sha256", source: source),
  fact("headroom_gate.minimum_effect", minimum-effect, "fraction", 5, "analysis_threshold", source: source),
  fact("headroom_gate.rule", rule, "identity", 5, "analysis_identity", source: source),
  fact("headroom_gate.passed", passed, "bool", 5, "paired_scene_decision", source: source),
)
#let recovery-rows(
  cohort: cohort-a,
  source: source,
  ci-source: source,
  row-n: 5,
  metric-value: 0.6,
  metric-unit: "fraction",
  ci-low: 0.4,
  ci-high: 0.8,
  interval-method: recovery-interval-method,
  ratio-aggregation: "paired_scene_ratio_of_mean_differences",
  minimum-fraction: 0.5,
  rule: recovery-decision-rule,
  passed: true,
) = (
  fact("policy.q_recovery.fraction", metric-value, metric-unit, row-n, ratio-aggregation, source: source),
  fact("policy.q_recovery.ci_low", ci-low, metric-unit, row-n, ratio-aggregation, source: ci-source),
  fact("policy.q_recovery.ci_high", ci-high, metric-unit, row-n, ratio-aggregation, source: source),
  fact("policy.q_recovery.ratio_definition", recovery-ratio-definition, "identity", row-n, "analysis_identity", source: source),
  fact("policy.q_recovery.interval_method", interval-method, "identity", row-n, "analysis_identity", source: source),
  fact("policy.q_recovery.n_scenes", 5, "count", row-n, "count", source: source),
  fact("policy.q_recovery.cohort_sha256", cohort, "sha256", row-n, "cohort_binding_sha256", source: source),
  fact("policy.q_recovery.minimum_fraction", minimum-fraction, "fraction", row-n, "analysis_threshold", source: source),
  fact("policy.q_recovery.rule", rule, "identity", row-n, "analysis_identity", source: source),
  fact("policy.q_recovery.passed", passed, "bool", row-n, "paired_scene_decision", source: source),
)
#let report(rows, sidecar-rows: sidecars, sidecar-value-rows: none) = {
  let projected-sidecar-values = if sidecar-value-rows != none {
    sidecar-value-rows
  } else {
    let sidecar-id = rows.first().source.split("|sidecar:").last()
    let matches = sidecar-rows.filter(sidecar => sidecar.sidecar_id == sidecar-id)
    if matches.len() == 1 {
      analysis-sidecar-value-rows(sidecar-id, matches.first().name, rows)
    } else { () }
  }
  let bound-sidecars = sidecar-rows.map(sidecar => sidecar + (
    projection_sha256: () => true,
  ))
  (
    tables: (
      stores: (rows: ((store_id: "store-a"),)),
      facts: (rows: rows),
      sidecars: (rows: bound-sidecars),
      sidecar_values: (rows: projected-sidecar-values),
    ),
  )
}
#let accepted = report(endpoint-rows() + headroom-rows() + recovery-rows())
#let endpoint-valid = report-store-endpoint-evidence-valid(accepted, "store-a", 5)
#let headroom-valid = report-store-headroom-evidence-valid(accepted, "store-a", 5)
#let recovery-valid = report-store-recovery-evidence-valid(accepted, "store-a", 5)
#assert(endpoint-valid)
#assert(report-store-oracle-endpoint-evidence-valid(accepted, "store-a", 5))
#assert(headroom-valid)
#assert(recovery-valid)
#let oracle-only-rows = endpoint-rows().filter(
  row => row.key in oracle-endpoint-evidence-facts,
) + headroom-rows()
#let oracle-only-report = report(oracle-only-rows)
#assert(report-store-oracle-endpoint-evidence-valid(oracle-only-report, "store-a", 5))
#assert(report-store-headroom-evidence-valid(oracle-only-report, "store-a", 5))
#assert(not report-store-endpoint-evidence-valid(oracle-only-report, "store-a", 5))
#assert(report-store-oracle-endpoint-evidence-valid(report(endpoint-rows(bundle: "invalid")), "store-a", 5))
#assert(not report-store-endpoint-evidence-valid(report(endpoint-rows(bundle: "invalid")), "store-a", 5))
#let bounded-endpoint-keys = (
  "policy.endpoint_gain.oracle_one_step.mean",
  "policy.endpoint_gain.oracle_one_step.ci_low",
  "policy.endpoint_gain.oracle_one_step.ci_high",
  "policy.endpoint_gain.oracle_lookahead.mean",
  "policy.endpoint_gain.oracle_lookahead.ci_low",
  "policy.endpoint_gain.oracle_lookahead.ci_high",
  "policy.endpoint_gain.learned_q.mean",
  "policy.endpoint_gain.learned_q.ci_low",
  "policy.endpoint_gain.learned_q.ci_high",
)
#for key in bounded-endpoint-keys {
  assert(not report-store-endpoint-evidence-valid(
    report(mutate-fact-value(endpoint-rows(), key, 1.0001)),
    "store-a",
    5,
  ))
}
#assert(report-store-oracle-endpoint-evidence-valid(
  report(mutate-fact-value(endpoint-rows(), "policy.endpoint_gain.oracle_lookahead.ci_high", 1)),
  "store-a",
  5,
))
#assert(report-store-endpoint-evidence-valid(
  report(mutate-fact-value(endpoint-rows(), "policy.endpoint_gain.learned_q.ci_high", 1)),
  "store-a",
  5,
))
#let accepted-rows = endpoint-rows() + headroom-rows() + recovery-rows()
#let accepted-payload = analysis-sidecar-value-rows(
  sidecar-a,
  "paired-policy",
  accepted-rows,
)
#assert(not report-store-endpoint-evidence-valid(report(
  accepted-rows,
  sidecar-value-rows: mutate-sidecar-fact-value(
    accepted-payload,
    "policy.endpoint_gain.oracle_lookahead.mean",
    0.49,
  ),
), "store-a", 5))
#assert(not report-store-endpoint-evidence-valid(report(
  accepted-rows,
  sidecar-value-rows: mutate-sidecar-fact-value(
    accepted-payload,
    "policy.endpoint_gain.learned_q.bundle_manifest_sha256",
    cohort-b,
  ),
), "store-a", 5))
#assert(not report-store-headroom-evidence-valid(report(
  accepted-rows,
  sidecar-value-rows: mutate-sidecar-fact-value(
    accepted-payload,
    "policy.paired_scene_endpoint.effect",
    0.29,
  ),
), "store-a", 5))
#assert(not report-store-recovery-evidence-valid(report(
  accepted-rows,
  sidecar-value-rows: mutate-sidecar-fact-value(
    accepted-payload,
    "policy.q_recovery.fraction",
    0.59,
  ),
), "store-a", 5))
#assert(report-store-recovery-evidence-valid(
  report(recovery-rows(metric-value: 0.5, ci-low: 0.2)),
  "store-a",
  5,
))
#assert(report-store-recovery-evidence-valid(
  report(recovery-rows(metric-value: 0.4, ci-low: 0.2, passed: false)),
  "store-a",
  5,
))
#assert(report-store-recovery-evidence-valid(
  report(recovery-rows(ci-low: 0, passed: false)),
  "store-a",
  5,
))
#assert(not report-store-recovery-evidence-valid(
  report(recovery-rows(metric-value: 0.4, ci-low: 0.2)),
  "store-a",
  5,
))
#assert(not report-store-recovery-evidence-valid(
  report(recovery-rows(ci-low: 0)),
  "store-a",
  5,
))
#assert(not report-store-recovery-evidence-valid(
  report(recovery-rows(passed: false)),
  "store-a",
  5,
))
#assert(not report-store-recovery-evidence-valid(
  report(recovery-rows(minimum-fraction: 0)),
  "store-a",
  5,
))
#assert(not report-store-recovery-evidence-valid(
  report(recovery-rows(minimum-fraction: 1.1)),
  "store-a",
  5,
))
#assert(not report-store-recovery-evidence-valid(
  report(recovery-rows(rule: "unfrozen_recovery_rule")),
  "store-a",
  5,
))
#assert(report-store-headroom-identity-valid(accepted, "store-a"))
#assert(report-store-recovery-identity-valid(accepted, "store-a"))
#assert(report-store-headroom-evidence-valid(
  report(headroom-rows(effect: 0.19, passed: false)),
  "store-a",
  5,
))
#assert(report-store-headroom-evidence-valid(
  report(headroom-rows(effect: 0.20)),
  "store-a",
  5,
))
#assert(report-store-headroom-evidence-valid(
  report(headroom-rows(ci-low: -0.01, passed: false)),
  "store-a",
  5,
))
#assert(report-store-headroom-evidence-valid(
  report(headroom-rows(ci-low: 0, passed: false)),
  "store-a",
  5,
))
#assert(not report-store-headroom-evidence-valid(
  report(headroom-rows(effect: 0.19, passed: true)),
  "store-a",
  5,
))
#assert(not report-store-headroom-evidence-valid(
  report(headroom-rows(ci-low: -0.01, passed: true)),
  "store-a",
  5,
))
#assert(not report-store-headroom-evidence-valid(
  report(headroom-rows(ci-low: 0, passed: true)),
  "store-a",
  5,
))
#assert(not report-store-headroom-evidence-valid(
  report(headroom-rows(passed: false)),
  "store-a",
  5,
))
#assert(not report-store-headroom-evidence-valid(
  report(headroom-rows(minimum-effect: -0.01)),
  "store-a",
  5,
))
#assert(not report-store-headroom-evidence-valid(
  report(headroom-rows(minimum-effect: 0)),
  "store-a",
  5,
))
#assert(not report-store-headroom-evidence-valid(
  report(headroom-rows(minimum-effect: "0.20")),
  "store-a",
  5,
))
#assert(not report-store-headroom-evidence-valid(
  report(headroom-rows(rule: "unfrozen_headroom_rule")),
  "store-a",
  5,
))
#assert(not report-store-headroom-evidence-valid(
  report(headroom-rows().filter(row => row.key != "headroom_gate.minimum_effect")),
  "store-a",
  5,
))
#assert(not report-store-headroom-evidence-valid(
  report(headroom-rows().filter(row => row.key != "headroom_gate.rule")),
  "store-a",
  5,
))
#assert(not report-store-headroom-evidence-valid(
  report(headroom-rows().map(row => if row.key == "headroom_gate.minimum_effect" {
    row + (unit: "count",)
  } else { row })),
  "store-a",
  5,
))
#assert(not report-store-headroom-evidence-valid(
  report(headroom-rows().map(row => if row.key == "headroom_gate.minimum_effect" {
    row + (aggregation: "post_hoc_threshold",)
  } else { row })),
  "store-a",
  5,
))
#assert(not report-store-headroom-evidence-valid(
  report(headroom-rows(passed: "true")),
  "store-a",
  5,
))
#assert(not report-store-headroom-identity-valid(
  report(endpoint-rows() + headroom-rows(effect: 0.90)),
  "store-a",
))
#assert(not report-store-recovery-identity-valid(
  report(endpoint-rows() + recovery-rows(metric-value: 0.70)),
  "store-a",
))
#assert(not report-store-endpoint-evidence-valid(
  report(endpoint-rows(scene-value: "5")),
  "store-a",
  5,
))
#assert(report-store-facts-share-value(
  accepted,
  "store-a",
  (
    "policy.endpoint_gain.cohort_sha256",
    "policy.paired_scene_endpoint.cohort_sha256",
    "policy.q_recovery.cohort_sha256",
  ),
))
#assert(report-store-facts-share-source(
  accepted,
  "store-a",
  endpoint-evidence-facts + headroom-evidence-facts + recovery-evidence-facts,
))

#assert(not report-store-recovery-evidence-valid(report(recovery-rows(row-n: 4)), "store-a", 5))
#assert(not report-store-recovery-evidence-valid(report(recovery-rows(cohort: "cohort-a")), "store-a", 5))
#assert(not report-store-recovery-evidence-valid(report(recovery-rows(metric-unit: "count")), "store-a", 5))
#assert(not report-store-recovery-evidence-valid(report(recovery-rows(metric-value: "0.6")), "store-a", 5))
#assert(not report-store-recovery-evidence-valid(report(recovery-rows(ci-low: 0.9, ci-high: 0.8)), "store-a", 5))
#assert(not report-store-recovery-evidence-valid(report(recovery-rows(interval-method: "unfrozen_interval")), "store-a", 5))
#assert(not report-store-recovery-evidence-valid(report(recovery-rows(ratio-aggregation: "mean_of_scene_ratios")), "store-a", 5))
#assert(not report-store-recovery-evidence-valid(report(recovery-rows(source: "analysis/unbound.json")), "store-a", 5))
#assert(not report-store-recovery-evidence-valid(report(recovery-rows(source: "analysis/paired-policy.json|sidecar:")), "store-a", 5))
#assert(not report-store-recovery-evidence-valid(report(recovery-rows(ci-source: "analysis/other.json|sidecar:" + sidecar-b)), "store-a", 5))
#assert(not report-store-recovery-evidence-valid(report(
  recovery-rows(),
  sidecar-rows: sidecars + ((sidecar_id: sidecar-a, path: "duplicate", name: "duplicate", sha256: digest-b, format: "json", status: "confirmatory"),),
), "store-a", 5))

#let mismatched-cohort = report(endpoint-rows() + headroom-rows() + recovery-rows(cohort: cohort-b))
#assert(report-store-recovery-evidence-valid(mismatched-cohort, "store-a", 5))
#assert(not report-store-facts-share-value(
  mismatched-cohort,
  "store-a",
  (
    "policy.endpoint_gain.cohort_sha256",
    "policy.paired_scene_endpoint.cohort_sha256",
    "policy.q_recovery.cohort_sha256",
  ),
))
#let mismatched-source-primary-rows = endpoint-rows() + headroom-rows()
#let mismatched-source-recovery-rows = recovery-rows(
  source: "analysis/other.json|sidecar:" + sidecar-b,
  ci-source: "analysis/other.json|sidecar:" + sidecar-b,
)
#let mismatched-source = report(
  mismatched-source-primary-rows + mismatched-source-recovery-rows,
  sidecar-value-rows: analysis-sidecar-value-rows(
    sidecar-a,
    "paired-policy",
    mismatched-source-primary-rows,
  ) + analysis-sidecar-value-rows(
    sidecar-b,
    "other",
    mismatched-source-recovery-rows,
  ),
)
#assert(report-store-recovery-evidence-valid(mismatched-source, "store-a", 5))
#assert(not report-store-facts-share-source(
  mismatched-source,
  "store-a",
  endpoint-evidence-facts + headroom-evidence-facts + recovery-evidence-facts,
))

#let blocked-headroom = evidence-gate-state(headroom-valid, false)
#let blocked-denominator = conditional-ratio-gate-state(
  endpoint-valid,
  blocked-headroom.claim_admissible,
  recovery-valid,
  true,
)
#assert(blocked-denominator.raw_evidence_available)
#assert(not blocked-denominator.ratio_evidence_available)
#assert(not blocked-denominator.state.evidence_available)
#assert(not blocked-denominator.state.gate_passed)

#let bad-unit-contract = report-store-recovery-evidence-valid(
  report(recovery-rows(metric-unit: "count")),
  "store-a",
  5,
)
#let mismatched-contract = conditional-ratio-gate-state(
  endpoint-valid,
  headroom-valid,
  bad-unit-contract,
  true,
)
#assert(mismatched-contract.raw_evidence_available)
#assert(not mismatched-contract.ratio_evidence_available)
#assert(not mismatched-contract.state.gate_passed)

#let admitted = conditional-ratio-gate-state(
  endpoint-valid,
  headroom-valid,
  recovery-valid,
  true,
)
#assert(admitted.raw_evidence_available)
#assert(admitted.ratio_evidence_available)
#assert(admitted.state.evidence_available)
#assert(admitted.state.gate_passed)
#assert(admitted.state.claim_admissible)

#let partial-report = report((fact(
  "policy.q_recovery.fraction",
  0.6,
  "fraction",
  5,
  "paired_scene_ratio_of_mean_differences",
),))
#let endpoint-facts-present = report-stores-have-facts(
  partial-report,
  ("policy.endpoint_gain.n_scenes",),
  denominators: true,
)
#let partial-contract-available = endpoint-facts-present and partial-report.tables.stores.rows.all(store => {
  // This strict lookup must remain unreachable when raw endpoint evidence is absent.
  report-store-fact(
    partial-report,
    store.store_id,
    "policy.endpoint_gain.n_scenes",
  ).value > 0
})
#assert(not partial-contract-available)

Underlying aggregated endpoint evidence remains available after a measured
headroom non-pass. A recovery ratio is admitted only when the exact shared
scene, cohort, unit, interval, aggregation, and provenance contract is valid.
