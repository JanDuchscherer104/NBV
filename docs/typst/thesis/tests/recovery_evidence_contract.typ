#import "../experiment_data.typ": conditional-ratio-gate-state, evidence-gate-state, endpoint-evidence-facts, headroom-evidence-facts, recovery-evidence-facts, paired-interval-method, recovery-ratio-definition, report-store-endpoint-evidence-valid, report-store-headroom-evidence-valid, report-store-recovery-evidence-valid, report-store-headroom-identity-valid, report-store-recovery-identity-valid, report-store-fact, report-store-facts-share-source, report-store-facts-share-value, report-stores-have-facts

#let sidecar-a = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
#let sidecar-b = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
#let digest-a = "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
#let digest-b = "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"
#let source = "analysis/paired-policy.json|sidecar:" + sidecar-a
#let sidecars = (
  (sidecar_id: sidecar-a, path: "paired-policy", name: "paired-policy", sha256: digest-a, format: "json", status: "confirmatory"),
  (sidecar_id: sidecar-b, path: "other", name: "other", sha256: digest-b, format: "json", status: "confirmatory"),
)
#let cohort-a = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
#let cohort-b = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
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
#let endpoint-rows(cohort: cohort-a, source: source, scene-value: 5) = (
  fact("policy.endpoint_gain.oracle_one_step.mean", 0.20, "fraction", 5, "paired_scene_endpoint_gain", source: source),
  fact("policy.endpoint_gain.oracle_one_step.ci_low", 0.10, "fraction", 5, "paired_scene_endpoint_gain", source: source),
  fact("policy.endpoint_gain.oracle_one_step.ci_high", 0.30, "fraction", 5, "paired_scene_endpoint_gain", source: source),
  fact("policy.endpoint_gain.oracle_lookahead.mean", 0.50, "fraction", 5, "paired_scene_endpoint_gain", source: source),
  fact("policy.endpoint_gain.oracle_lookahead.ci_low", 0.40, "fraction", 5, "paired_scene_endpoint_gain", source: source),
  fact("policy.endpoint_gain.oracle_lookahead.ci_high", 0.60, "fraction", 5, "paired_scene_endpoint_gain", source: source),
  fact("policy.endpoint_gain.learned_q.mean", 0.38, "fraction", 5, "paired_scene_endpoint_gain", source: source),
  fact("policy.endpoint_gain.learned_q.ci_low", 0.28, "fraction", 5, "paired_scene_endpoint_gain", source: source),
  fact("policy.endpoint_gain.learned_q.ci_high", 0.48, "fraction", 5, "paired_scene_endpoint_gain", source: source),
  fact("policy.endpoint_gain.interval_method", paired-interval-method, "identity", 5, "analysis_identity", source: source),
  fact("policy.endpoint_gain.n_scenes", scene-value, "count", 5, "count", source: source),
  fact("policy.endpoint_gain.cohort_sha256", cohort, "sha256", 5, "cohort_binding_sha256", source: source),
)
#let headroom-rows(cohort: cohort-a, source: source, effect: 0.30) = (
  fact("policy.paired_scene_endpoint.effect", effect, "fraction", 5, "paired_scene_mean_difference", source: source),
  fact("policy.paired_scene_endpoint.ci_low", 0.18, "fraction", 5, "paired_scene_mean_difference", source: source),
  fact("policy.paired_scene_endpoint.ci_high", 0.42, "fraction", 5, "paired_scene_mean_difference", source: source),
  fact("policy.paired_scene_endpoint.interval_method", paired-interval-method, "identity", 5, "analysis_identity", source: source),
  fact("policy.paired_scene_endpoint.n_scenes", 5, "count", 5, "count", source: source),
  fact("policy.paired_scene_endpoint.cohort_sha256", cohort, "sha256", 5, "cohort_binding_sha256", source: source),
  fact("headroom_gate.passed", true, "bool", 5, "paired_scene_decision", source: source),
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
  interval-method: paired-interval-method,
  ratio-aggregation: "paired_scene_ratio_of_mean_differences",
) = (
  fact("policy.q_recovery.fraction", metric-value, metric-unit, row-n, ratio-aggregation, source: source),
  fact("policy.q_recovery.ci_low", ci-low, metric-unit, row-n, ratio-aggregation, source: ci-source),
  fact("policy.q_recovery.ci_high", ci-high, metric-unit, row-n, ratio-aggregation, source: source),
  fact("policy.q_recovery.ratio_definition", recovery-ratio-definition, "identity", row-n, "analysis_identity", source: source),
  fact("policy.q_recovery.interval_method", interval-method, "identity", row-n, "analysis_identity", source: source),
  fact("policy.q_recovery.n_scenes", 5, "count", row-n, "count", source: source),
  fact("policy.q_recovery.cohort_sha256", cohort, "sha256", row-n, "cohort_binding_sha256", source: source),
  fact("policy.q_recovery.passed", true, "bool", row-n, "paired_scene_decision", source: source),
)
#let report(rows, sidecar-rows: sidecars) = (
  tables: (
    stores: (rows: ((store_id: "store-a"),)),
    facts: (rows: rows),
    sidecars: (rows: sidecar-rows),
  ),
)
#let accepted = report(endpoint-rows() + headroom-rows() + recovery-rows())
#let endpoint-valid = report-store-endpoint-evidence-valid(accepted, "store-a", 5)
#let headroom-valid = report-store-headroom-evidence-valid(accepted, "store-a", 5)
#let recovery-valid = report-store-recovery-evidence-valid(accepted, "store-a", 5)
#assert(endpoint-valid)
#assert(headroom-valid)
#assert(recovery-valid)
#assert(report-store-headroom-identity-valid(accepted, "store-a"))
#assert(report-store-recovery-identity-valid(accepted, "store-a"))
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
#let mismatched-source = report(endpoint-rows() + headroom-rows() + recovery-rows(source: "analysis/other.json|sidecar:" + sidecar-b, ci-source: "analysis/other.json|sidecar:" + sidecar-b))
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
