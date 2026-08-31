#import "../experiment_data.typ": canonical-sidecar-id, conditional-ratio-gate-state, evidence-gate-state, endpoint-evidence-facts, oracle-endpoint-evidence-facts, headroom-bootstrap-algorithm, headroom-bootstrap-confidence, headroom-bootstrap-interval, headroom-bootstrap-quantile, headroom-bootstrap-samples, headroom-bootstrap-seed, headroom-cohort-sha256, headroom-decision-rule, headroom-estimator, headroom-evidence-facts, headroom-receipt-schema, paired-interval-method, recovery-bootstrap-algorithm, recovery-bootstrap-interval, recovery-decision-rule, recovery-evidence-facts, recovery-interval-method, recovery-ratio-definition, recovery-receipt-schema, report-sidecar-projection-sha256, report-store-endpoint-evidence-valid, report-store-oracle-endpoint-evidence-valid, report-store-headroom-evidence-valid, report-store-recovery-evidence-valid, report-store-headroom-identity-valid, report-store-recovery-identity-valid, report-store-fact, report-store-facts-share-source, report-store-facts-share-value, report-stores-have-facts

#let digest-a = "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
#let digest-b = "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"
#let sidecar-a = canonical-sidecar-id("paired-policy", digest-a)
#let sidecar-b = canonical-sidecar-id("other", digest-b)
#let source = "analysis/paired-policy.json|sidecar:" + sidecar-a
#let sidecars = (
  (sidecar_id: sidecar-a, path: "paired-policy", name: "paired-policy", sha256: digest-a, format: "json", status: "confirmatory"),
  (sidecar_id: sidecar-b, path: "other", name: "other", sha256: digest-b, format: "json", status: "confirmatory"),
)
#let default-headroom-scenes = range(5).map(index => (
  scene: "scene-" + str(index),
  one-step: 0.20,
  lookahead: 0.30 + 0.10 * index,
))
#let default-recovery-scenes = (
  (scene: "scene-0", one-step: 0.20, lookahead: 0.30, learned: 0.22),
  (scene: "scene-1", one-step: 0.20, lookahead: 0.40, learned: 0.26),
  (scene: "scene-2", one-step: 0.20, lookahead: 0.50, learned: 0.38),
  (scene: "scene-3", one-step: 0.20, lookahead: 0.60, learned: 0.46),
  (scene: "scene-4", one-step: 0.20, lookahead: 0.70, learned: 0.58),
)
#let cohort-a = headroom-cohort-sha256(default-headroom-scenes.map(scene => scene.scene))
#let cohort-b = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
#let fixed-headroom-bootstrap = headroom-bootstrap-interval((0.10, 0.20, 0.30, 0.40, 0.50))
#assert(calc.abs(fixed-headroom-bootstrap.low - 0.18) <= 1e-10)
#assert(calc.abs(fixed-headroom-bootstrap.high - 0.42) <= 1e-10)
#let fixed-headroom-bootstrap-four = headroom-bootstrap-interval((1.0, 2.0, 3.0, 4.0))
#assert(calc.abs(fixed-headroom-bootstrap-four.low - 1.5) <= 1e-10)
#assert(calc.abs(fixed-headroom-bootstrap-four.high - 3.5) <= 1e-10)
#let fixed-headroom-bootstrap-eight = headroom-bootstrap-interval((1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0))
#assert(calc.abs(fixed-headroom-bootstrap-eight.low - 2.875) <= 1e-10)
#assert(calc.abs(fixed-headroom-bootstrap-eight.high - 6.125) <= 1e-10)
#let fixed-recovery-bootstrap = recovery-bootstrap-interval(default-recovery-scenes)
#assert(calc.abs(fixed-recovery-bootstrap.low - 0.3777777777777778) <= 1e-10)
#assert(calc.abs(fixed-recovery-bootstrap.high - 0.71) <= 1e-10)
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
#let endpoint-rows(cohort: cohort-a, bundle: bundle-manifest, source: source, scene-value: 5) = {
  let one-step-interval = headroom-bootstrap-interval(default-headroom-scenes.map(scene => scene.one-step))
  let lookahead-interval = headroom-bootstrap-interval(default-headroom-scenes.map(scene => scene.lookahead))
  let learned-interval = headroom-bootstrap-interval(default-recovery-scenes.map(scene => scene.learned))
  (
    fact("policy.endpoint_gain.oracle_one_step.mean", 0.20, "fraction", 5, "paired_scene_endpoint_gain", source: source),
    fact("policy.endpoint_gain.oracle_one_step.ci_low", one-step-interval.low, "fraction", 5, "paired_scene_endpoint_gain", source: source),
    fact("policy.endpoint_gain.oracle_one_step.ci_high", one-step-interval.high, "fraction", 5, "paired_scene_endpoint_gain", source: source),
    fact("policy.endpoint_gain.oracle_lookahead.mean", 0.50, "fraction", 5, "paired_scene_endpoint_gain", source: source),
    fact("policy.endpoint_gain.oracle_lookahead.ci_low", lookahead-interval.low, "fraction", 5, "paired_scene_endpoint_gain", source: source),
    fact("policy.endpoint_gain.oracle_lookahead.ci_high", lookahead-interval.high, "fraction", 5, "paired_scene_endpoint_gain", source: source),
    fact("policy.endpoint_gain.learned_q.mean", 0.38, "fraction", 5, "paired_scene_endpoint_gain", source: source),
    fact("policy.endpoint_gain.learned_q.ci_low", learned-interval.low, "fraction", 5, "paired_scene_endpoint_gain", source: source),
    fact("policy.endpoint_gain.learned_q.ci_high", learned-interval.high, "fraction", 5, "paired_scene_endpoint_gain", source: source),
    fact("policy.endpoint_gain.learned_q.bundle_manifest_sha256", bundle, "sha256", 5, "policy_identity", source: source),
    fact("policy.endpoint_gain.interval_method", paired-interval-method, "identity", 5, "analysis_identity", source: source),
    fact("policy.endpoint_gain.n_scenes", scene-value, "count", 5, "count", source: source),
    fact("policy.endpoint_gain.cohort_sha256", cohort, "sha256", 5, "cohort_binding_sha256", source: source),
  )
}
#let headroom-rows(
  cohort: none,
  source: source,
  scenes: default-headroom-scenes,
  effect: none,
  ci-low: none,
  ci-high: none,
  minimum-effect: 0.20,
  rule: headroom-decision-rule,
  passed: none,
) = {
  let scene-count = scenes.len()
  let ordered-scenes = scenes.sorted(key: scene => scene.scene)
  let differences = ordered-scenes.map(scene => scene.lookahead - scene.one-step)
  let interval = headroom-bootstrap-interval(differences)
  let derived-effect = differences.sum() / scene-count
  let effect-value = if effect == none { derived-effect } else { effect }
  let ci-low-value = if ci-low == none { interval.low } else { ci-low }
  let ci-high-value = if ci-high == none { interval.high } else { ci-high }
  let passed-value = if passed == none and (type(minimum-effect) == int or type(minimum-effect) == float) {
    derived-effect >= minimum-effect and interval.low > 0
  } else if passed == none { false } else { passed }
  let cohort-value = if cohort == none {
    headroom-cohort-sha256(ordered-scenes.map(scene => scene.scene))
  } else { cohort }
  let ledger = scenes.enumerate().map(((index, scene)) => {
    let prefix = "policy.paired_scene_endpoint.scenes[" + str(index) + "]"
    (
      fact(prefix + ".scene_id", scene.scene, "identity", scene-count, "paired_scene_identity", source: source),
      fact(prefix + ".oracle_one_step", scene.one-step, "fraction", scene-count, "paired_scene_endpoint_input", source: source),
      fact(prefix + ".oracle_lookahead", scene.lookahead, "fraction", scene-count, "paired_scene_endpoint_input", source: source),
    )
  }).flatten()
  (
    fact("policy.paired_scene_endpoint.receipt_schema", headroom-receipt-schema, "identity", scene-count, "analysis_identity", source: source),
    fact("policy.paired_scene_endpoint.estimator", headroom-estimator, "identity", scene-count, "analysis_identity", source: source),
    fact("policy.paired_scene_endpoint.bootstrap_algorithm", headroom-bootstrap-algorithm, "identity", scene-count, "analysis_identity", source: source),
    fact("policy.paired_scene_endpoint.bootstrap_samples", headroom-bootstrap-samples, "count", scene-count, "analysis_identity", source: source),
    fact("policy.paired_scene_endpoint.bootstrap_seed", headroom-bootstrap-seed, "identity", scene-count, "analysis_identity", source: source),
    fact("policy.paired_scene_endpoint.bootstrap_confidence", headroom-bootstrap-confidence, "fraction", scene-count, "analysis_identity", source: source),
    fact("policy.paired_scene_endpoint.bootstrap_quantile", headroom-bootstrap-quantile, "identity", scene-count, "analysis_identity", source: source),
    fact("policy.paired_scene_endpoint.effect", effect-value, "fraction", scene-count, "paired_scene_mean_difference", source: source),
    fact("policy.paired_scene_endpoint.ci_low", ci-low-value, "fraction", scene-count, "paired_scene_mean_difference", source: source),
    fact("policy.paired_scene_endpoint.ci_high", ci-high-value, "fraction", scene-count, "paired_scene_mean_difference", source: source),
    fact("policy.paired_scene_endpoint.interval_method", paired-interval-method, "identity", scene-count, "analysis_identity", source: source),
    fact("policy.paired_scene_endpoint.n_scenes", scene-count, "count", scene-count, "count", source: source),
    fact("policy.paired_scene_endpoint.cohort_sha256", cohort-value, "sha256", scene-count, "cohort_binding_sha256", source: source),
    fact("headroom_gate.minimum_effect", minimum-effect, "fraction", scene-count, "analysis_threshold", source: source),
    fact("headroom_gate.rule", rule, "identity", scene-count, "analysis_identity", source: source),
    fact("headroom_gate.passed", passed-value, "bool", scene-count, "paired_scene_decision", source: source),
  ) + ledger
}
#let recovery-rows(
  cohort: none,
  source: source,
  ci-source: source,
  scenes: default-recovery-scenes,
  row-n: 5,
  metric-value: none,
  metric-unit: "fraction",
  ci-low: none,
  ci-high: none,
  interval-method: recovery-interval-method,
  ratio-aggregation: "paired_scene_ratio_of_mean_differences",
  minimum-fraction: 0.5,
  rule: recovery-decision-rule,
  passed: none,
) = {
  let scene-count = scenes.len()
  let ordered-scenes = scenes.sorted(key: scene => scene.scene)
  let one-step-mean = ordered-scenes.map(scene => scene.one-step).sum() / scene-count
  let lookahead-mean = ordered-scenes.map(scene => scene.lookahead).sum() / scene-count
  let learned-mean = ordered-scenes.map(scene => scene.learned).sum() / scene-count
  let derived-fraction = (learned-mean - one-step-mean) / (lookahead-mean - one-step-mean)
  let interval = recovery-bootstrap-interval(ordered-scenes)
  let fraction-value = if metric-value == none { derived-fraction } else { metric-value }
  let ci-low-value = if ci-low == none { interval.low } else { ci-low }
  let ci-high-value = if ci-high == none { interval.high } else { ci-high }
  let passed-value = if passed == none and (type(minimum-fraction) == int or type(minimum-fraction) == float) {
    derived-fraction >= minimum-fraction and interval.low > 0
  } else if passed == none { false } else { passed }
  let cohort-value = if cohort == none {
    headroom-cohort-sha256(ordered-scenes.map(scene => scene.scene))
  } else { cohort }
  let ledger = scenes.enumerate().map(((index, scene)) => {
    let prefix = "policy.q_recovery.scenes[" + str(index) + "]"
    (
      fact(prefix + ".scene_id", scene.scene, "identity", scene-count, "paired_scene_identity", source: source),
      fact(prefix + ".learned_q", scene.learned, "fraction", scene-count, "paired_scene_recovery_input", source: source),
    )
  }).flatten()
  (
    fact("policy.q_recovery.receipt_schema", recovery-receipt-schema, "identity", row-n, "analysis_identity", source: source),
    fact("policy.q_recovery.bootstrap_algorithm", recovery-bootstrap-algorithm, "identity", row-n, "analysis_identity", source: source),
    fact("policy.q_recovery.bootstrap_samples", headroom-bootstrap-samples, "count", row-n, "analysis_identity", source: source),
    fact("policy.q_recovery.bootstrap_seed", headroom-bootstrap-seed, "identity", row-n, "analysis_identity", source: source),
    fact("policy.q_recovery.bootstrap_confidence", headroom-bootstrap-confidence, "fraction", row-n, "analysis_identity", source: source),
    fact("policy.q_recovery.bootstrap_quantile", headroom-bootstrap-quantile, "identity", row-n, "analysis_identity", source: source),
    fact("policy.q_recovery.fraction", fraction-value, metric-unit, row-n, ratio-aggregation, source: source),
    fact("policy.q_recovery.ci_low", ci-low-value, metric-unit, row-n, ratio-aggregation, source: ci-source),
    fact("policy.q_recovery.ci_high", ci-high-value, metric-unit, row-n, ratio-aggregation, source: source),
    fact("policy.q_recovery.ratio_definition", recovery-ratio-definition, "identity", row-n, "analysis_identity", source: source),
    fact("policy.q_recovery.interval_method", interval-method, "identity", row-n, "analysis_identity", source: source),
    fact("policy.q_recovery.n_scenes", scene-count, "count", row-n, "count", source: source),
    fact("policy.q_recovery.cohort_sha256", cohort-value, "sha256", row-n, "cohort_binding_sha256", source: source),
    fact("policy.q_recovery.minimum_fraction", minimum-fraction, "fraction", row-n, "analysis_threshold", source: source),
    fact("policy.q_recovery.rule", rule, "identity", row-n, "analysis_identity", source: source),
    fact("policy.q_recovery.passed", passed-value, "bool", row-n, "paired_scene_decision", source: source),
  ) + ledger
}
#let report(rows, sidecar-rows: sidecars, sidecar-value-rows: none) = {
  let has-headroom = rows.any(row => row.at("key", default: none) == "policy.paired_scene_endpoint.effect")
  let has-recovery = rows.any(row => row.at("key", default: none) == "policy.q_recovery.receipt_schema")
  let has-endpoints = rows.any(row => row.at("key", default: none) == "policy.endpoint_gain.oracle_one_step.mean")
  let report-rows = if has-recovery and not has-headroom {
    endpoint-rows() + headroom-rows() + rows
  } else if has-headroom and not has-endpoints {
    endpoint-rows() + rows
  } else { rows }
  let projected-sidecar-values = if sidecar-value-rows != none {
    sidecar-value-rows
  } else {
    let sidecar-id = report-rows.first().source.split("|sidecar:").last()
    let matches = sidecar-rows.filter(sidecar => sidecar.sidecar_id == sidecar-id)
    if matches.len() == 1 {
      analysis-sidecar-value-rows(sidecar-id, matches.first().name, report-rows)
    } else { () }
  }
  let bound-sidecars = sidecar-rows.map(sidecar => sidecar + (
    projection_sha256: () => true,
  ))
  (
    tables: (
      stores: (rows: ((store_id: "store-a"),)),
      facts: (rows: report-rows),
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
#assert(not report-store-oracle-endpoint-evidence-valid(report(endpoint-rows()), "store-a", 5))
#assert(not report-store-endpoint-evidence-valid(report(endpoint-rows() + headroom-rows()), "store-a", 5))
#assert(report-store-oracle-endpoint-evidence-valid(report(endpoint-rows(bundle: "invalid") + headroom-rows()), "store-a", 5))
#assert(not report-store-endpoint-evidence-valid(report(endpoint-rows(bundle: "invalid") + headroom-rows() + recovery-rows()), "store-a", 5))
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
    report(mutate-fact-value(endpoint-rows() + headroom-rows() + recovery-rows(), key, 1.0001)),
    "store-a",
    5,
  ))
}
#assert(not report-store-oracle-endpoint-evidence-valid(
  report(mutate-fact-value(endpoint-rows() + headroom-rows(), "policy.endpoint_gain.oracle_lookahead.ci_high", 1)),
  "store-a",
  5,
))
#assert(not report-store-endpoint-evidence-valid(
  report(mutate-fact-value(endpoint-rows() + headroom-rows() + recovery-rows(), "policy.endpoint_gain.learned_q.ci_high", 1)),
  "store-a",
  5,
))
#let tampered-oracle-marginal-interval = mutate-fact-value(
  mutate-fact-value(
    endpoint-rows() + headroom-rows() + recovery-rows(),
    "policy.endpoint_gain.oracle_lookahead.ci_low",
    0.45,
  ),
  "policy.endpoint_gain.oracle_lookahead.ci_high",
  0.55,
)
#assert(not report-store-oracle-endpoint-evidence-valid(
  report(tampered-oracle-marginal-interval),
  "store-a",
  5,
))
#let tampered-learned-marginal-interval = mutate-fact-value(
  mutate-fact-value(
    endpoint-rows() + headroom-rows() + recovery-rows(),
    "policy.endpoint_gain.learned_q.ci_low",
    0.30,
  ),
  "policy.endpoint_gain.learned_q.ci_high",
  0.49,
)
#assert(not report-store-endpoint-evidence-valid(
  report(tampered-learned-marginal-interval),
  "store-a",
  5,
))
#let accepted-rows = endpoint-rows() + headroom-rows() + recovery-rows()
#let accepted-payload = analysis-sidecar-value-rows(
  sidecar-a,
  "paired-policy",
  accepted-rows,
)
#let reversed-headroom-scenes = range(default-headroom-scenes.len()).map(
  index => default-headroom-scenes.at(default-headroom-scenes.len() - index - 1),
)
#assert(report-store-headroom-evidence-valid(
  report(headroom-rows(scenes: reversed-headroom-scenes)),
  "store-a",
  5,
))
#let negative-headroom-scenes = (
  (scene: "scene-0", one-step: -0.10, lookahead: 0.00),
  (scene: "scene-1", one-step: 0.10, lookahead: 0.30),
  (scene: "scene-2", one-step: 0.20, lookahead: 0.50),
  (scene: "scene-3", one-step: 0.30, lookahead: 0.70),
  (scene: "scene-4", one-step: 0.50, lookahead: 1.00),
)
#assert(report-store-headroom-evidence-valid(
  report(headroom-rows(scenes: negative-headroom-scenes)),
  "store-a",
  5,
))
#let duplicate-headroom-scenes = default-headroom-scenes.map(scene => if scene.scene == "scene-4" {
  scene + (scene: "scene-3",)
} else { scene })
#assert(not report-store-headroom-evidence-valid(
  report(headroom-rows(scenes: duplicate-headroom-scenes)),
  "store-a",
  5,
))
#assert(not report-store-headroom-evidence-valid(
  report(accepted-rows.filter(row => not row.key.starts-with("policy.paired_scene_endpoint.scenes[2]."))),
  "store-a",
  5,
))
#let extra-headroom-ledger = accepted-rows + accepted-rows.filter(
  row => row.key.starts-with("policy.paired_scene_endpoint.scenes[4]."),
).map(row => row + (key: row.key.replace("scenes[4]", "scenes[5]"),))
#assert(not report-store-headroom-evidence-valid(
  report(extra-headroom-ledger),
  "store-a",
  5,
))
#assert(not report-store-headroom-evidence-valid(
  report(mutate-fact-value(
    accepted-rows,
    "policy.paired_scene_endpoint.scenes[0].oracle_one_step",
    "-0.10",
  )),
  "store-a",
  5,
))
#assert(not report-store-headroom-evidence-valid(
  report(mutate-fact-value(
    accepted-rows,
    "policy.paired_scene_endpoint.scenes[0].oracle_lookahead",
    1.01,
  )),
  "store-a",
  5,
))
#assert(not report-store-headroom-evidence-valid(report(
  accepted-rows,
  sidecar-value-rows: mutate-sidecar-fact-value(
    accepted-payload,
    "policy.paired_scene_endpoint.scenes[0].oracle_lookahead",
    0.31,
  ),
), "store-a", 5))
#let malformed-key-fact = fact("malformed", 0, "count", 1, "fixture") + (key: 7,)
#assert(not report-store-headroom-evidence-valid(report(
  accepted-rows + (malformed-key-fact,),
  sidecar-value-rows: accepted-payload,
), "store-a", 5))
#let malformed-store-fact = fact("malformed", 0, "count", 1, "fixture") + (store_id: 7,)
#assert(not report-store-headroom-evidence-valid(report(
  accepted-rows + (malformed-store-fact,),
  sidecar-value-rows: accepted-payload,
), "store-a", 5))
#let missing-key-fact = (
  store_id: "store-a",
  value: 0,
  unit: "count",
  n: 1,
  aggregation: "fixture",
  status: "confirmatory",
  source: source,
)
#assert(not report-store-headroom-evidence-valid(report(
  accepted-rows + (missing-key-fact,),
  sidecar-value-rows: accepted-payload,
), "store-a", 5))
#assert(not report-store-recovery-evidence-valid(report(
  accepted-rows + (malformed-key-fact,),
  sidecar-value-rows: accepted-payload,
), "store-a", 5))
#assert(not report-store-recovery-evidence-valid(report(
  accepted-rows + (malformed-store-fact,),
  sidecar-value-rows: accepted-payload,
), "store-a", 5))
#assert(not report-store-recovery-evidence-valid(report(
  accepted-rows + (missing-key-fact,),
  sidecar-value-rows: accepted-payload,
), "store-a", 5))
#let missing-recovery-number-value = (
  store_id: "store-a",
  key: "policy.q_recovery.fraction",
  unit: "fraction",
  n: 5,
  aggregation: "paired_scene_ratio_of_mean_differences",
  status: "confirmatory",
  source: source,
)
#let missing-recovery-number-rows = accepted-rows.filter(
  row => row.key != "policy.q_recovery.fraction",
) + (missing-recovery-number-value,)
#assert(not report-store-recovery-evidence-valid(report(
  missing-recovery-number-rows,
  sidecar-value-rows: accepted-payload,
), "store-a", 5))
#let missing-recovery-bool-value = (
  store_id: "store-a",
  key: "policy.q_recovery.passed",
  unit: "bool",
  n: 5,
  aggregation: "paired_scene_decision",
  status: "confirmatory",
  source: source,
)
#let missing-recovery-bool-rows = accepted-rows.filter(
  row => row.key != "policy.q_recovery.passed",
) + (missing-recovery-bool-value,)
#assert(not report-store-recovery-evidence-valid(report(
  missing-recovery-bool-rows,
  sidecar-value-rows: accepted-payload,
), "store-a", 5))
#let missing-oracle-ledger-value = (
  store_id: "store-a",
  key: "policy.paired_scene_endpoint.scenes[0].oracle_one_step",
  unit: "fraction",
  n: 5,
  aggregation: "paired_scene_endpoint_input",
  status: "confirmatory",
  source: source,
)
#let missing-oracle-ledger-rows = accepted-rows.filter(
  row => row.key != "policy.paired_scene_endpoint.scenes[0].oracle_one_step",
) + (missing-oracle-ledger-value,)
#let missing-oracle-ledger-report = report(
  missing-oracle-ledger-rows,
  sidecar-value-rows: accepted-payload,
)
#assert(not report-store-headroom-evidence-valid(missing-oracle-ledger-report, "store-a", 5))
#assert(not report-store-recovery-evidence-valid(missing-oracle-ledger-report, "store-a", 5))
#let missing-learned-ledger-value = (
  store_id: "store-a",
  key: "policy.q_recovery.scenes[0].learned_q",
  unit: "fraction",
  n: 5,
  aggregation: "paired_scene_recovery_input",
  status: "confirmatory",
  source: source,
)
#let missing-learned-ledger-rows = accepted-rows.filter(
  row => row.key != "policy.q_recovery.scenes[0].learned_q",
) + (missing-learned-ledger-value,)
#assert(not report-store-recovery-evidence-valid(report(
  missing-learned-ledger-rows,
  sidecar-value-rows: accepted-payload,
), "store-a", 5))
#let unrelated-null-fact = (
  store_id: "store-b",
  key: "diagnostic.independent_lane.optional_value",
  value: none,
  unit: "fraction",
  n: 0,
  aggregation: "independent_diagnostic",
  status: "missing",
  source: "analysis/independent.json",
)
#let accepted-with-unrelated-null = report(
  accepted-rows + (unrelated-null-fact,),
  sidecar-value-rows: accepted-payload,
)
#assert(report-store-headroom-evidence-valid(accepted-with-unrelated-null, "store-a", 5))
#assert(report-store-recovery-evidence-valid(accepted-with-unrelated-null, "store-a", 5))
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
#let coordinated-headroom-aggregate-tamper = mutate-fact-value(
  accepted-rows,
  "policy.paired_scene_endpoint.effect",
  0.29,
)
#assert(not report-store-headroom-evidence-valid(
  report(coordinated-headroom-aggregate-tamper),
  "store-a",
  5,
))
#let coordinated-headroom-ledger-tamper = mutate-fact-value(
  accepted-rows,
  "policy.paired_scene_endpoint.scenes[0].oracle_lookahead",
  0.90,
)
#assert(not report-store-headroom-evidence-valid(
  report(coordinated-headroom-ledger-tamper),
  "store-a",
  5,
))
#assert(not report-store-headroom-evidence-valid(
  report(accepted-rows.filter(row => not row.key.starts-with("policy.paired_scene_endpoint.scenes[4]."))),
  "store-a",
  5,
))
#assert(not report-store-headroom-evidence-valid(
  report(mutate-fact-value(
    accepted-rows,
    "policy.paired_scene_endpoint.bootstrap_algorithm",
    "unfrozen_rng",
  )),
  "store-a",
  5,
))
#let shifted-endpoint-means = mutate-fact-value(
  mutate-fact-value(
    accepted-rows,
    "policy.endpoint_gain.oracle_one_step.mean",
    0.25,
  ),
  "policy.endpoint_gain.oracle_lookahead.mean",
  0.55,
)
#assert(not report-store-headroom-evidence-valid(
  report(shifted-endpoint-means),
  "store-a",
  5,
))
#assert(not report-store-recovery-evidence-valid(report(
  accepted-rows,
  sidecar-value-rows: mutate-sidecar-fact-value(
    accepted-payload,
    "policy.q_recovery.fraction",
    0.59,
  ),
), "store-a", 5))
#let reversed-recovery-scenes = range(default-recovery-scenes.len()).map(
  index => default-recovery-scenes.at(default-recovery-scenes.len() - index - 1),
)
#assert(report-store-recovery-evidence-valid(
  report(recovery-rows(scenes: reversed-recovery-scenes)),
  "store-a",
  5,
))
#assert(not recovery-rows().any(row => row.key.contains(".oracle_one_step") or row.key.contains(".oracle_lookahead")))
#let substituted-recovery-oracle-scenes = range(default-recovery-scenes.len()).map(index => {
  let reverse-index = default-recovery-scenes.len() - index - 1
  default-recovery-scenes.at(index) + (
    lookahead: default-recovery-scenes.at(reverse-index).lookahead,
  )
})
#assert(not report-store-recovery-evidence-valid(
  report(endpoint-rows() + headroom-rows() + recovery-rows(scenes: substituted-recovery-oracle-scenes)),
  "store-a",
  5,
))
#assert(not report-store-recovery-evidence-valid(
  report(mutate-fact-value(accepted-rows, "policy.q_recovery.ci_low", 0.50)),
  "store-a",
  5,
))
#assert(not report-store-recovery-evidence-valid(
  report(mutate-fact-value(
    accepted-rows,
    "policy.q_recovery.scenes[0].learned_q",
    0.90,
  )),
  "store-a",
  5,
))
#assert(not report-store-recovery-evidence-valid(report(
  accepted-rows,
  sidecar-value-rows: mutate-sidecar-fact-value(
    accepted-payload,
    "policy.q_recovery.scenes[0].learned_q",
    0.23,
  ),
), "store-a", 5))
#assert(not report-store-recovery-evidence-valid(
  report(accepted-rows.filter(row => not row.key.starts-with("policy.q_recovery.scenes[2]."))),
  "store-a",
  5,
))
#let duplicate-recovery-scenes = default-recovery-scenes.map(scene => if scene.scene == "scene-4" {
  scene + (scene: "scene-3",)
} else { scene })
#assert(not report-store-recovery-evidence-valid(
  report(recovery-rows(scenes: duplicate-recovery-scenes)),
  "store-a",
  5,
))
#assert(not report-store-recovery-evidence-valid(
  report(mutate-fact-value(
    accepted-rows,
    "policy.q_recovery.bootstrap_algorithm",
    "unfrozen_rng",
  )),
  "store-a",
  5,
))
#assert(report-store-recovery-evidence-valid(
  report(recovery-rows()),
  "store-a",
  5,
))
#assert(report-store-recovery-evidence-valid(
  report(recovery-rows(minimum-fraction: 0.7, passed: false)),
  "store-a",
  5,
))
#assert(not report-store-recovery-evidence-valid(
  report(recovery-rows(metric-value: 0.5)),
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
  report(headroom-rows(minimum-effect: 0.31, passed: false)),
  "store-a",
  5,
))
#assert(report-store-headroom-evidence-valid(
  report(headroom-rows(minimum-effect: 0.30)),
  "store-a",
  5,
))
#assert(not report-store-headroom-evidence-valid(
  report(headroom-rows(ci-low: -0.01, passed: false)),
  "store-a",
  5,
))
#assert(not report-store-headroom-evidence-valid(
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
#assert(not report-store-recovery-evidence-valid(mismatched-cohort, "store-a", 5))
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
