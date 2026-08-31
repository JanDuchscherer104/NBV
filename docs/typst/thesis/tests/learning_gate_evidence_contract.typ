#import "../experiment_data.typ": candidate-support-benchmark-name, candidate-support-benchmark-schema, candidate-support-decision-rule, candidate-support-receipt-name, candidate-support-receipt-schema, measurement-benchmark-name, measurement-benchmark-schema, measurement-protocol-receipt-name, measurement-protocol-receipt-schema, measurement-rank-direction, measurement-rank-tie-policy, paired-interval-method, q1-decision-rule, q1-pairwise-chance, q1-protocol-receipt-name, q1-protocol-receipt-schema, q1-scene-role, q1-target-source-protocol, q2-decision-rule, repeatability-decision-rule, report-store-population-evidence-valid, report-store-measurement-evidence-valid, report-store-candidate-support-evidence-valid, report-store-q1-evidence-valid, report-store-q2-evidence-valid

#let sidecar-a = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
#let sidecar-b = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
#let digest-a = "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
#let digest-b = "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"
#let protocol-sidecar = "1c562d9babd0f28634d46b6b1e1e4fe71f340625b51b35669944d28ff06dc7bf"
#let protocol-digest = "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
#let support-sidecar = "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
#let support-digest = "1212121212121212121212121212121212121212121212121212121212121212"
#let support-benchmark-sidecar = "1313131313131313131313131313131313131313131313131313131313131313"
#let measurement-sidecar = "9999999999999999999999999999999999999999999999999999999999999999"
#let measurement-digest = "3434343434343434343434343434343434343434343434343434343434343434"
#let measurement-benchmark-sidecar = "3535353535353535353535353535353535353535353535353535353535353535"
#let measurement-benchmark = "3636363636363636363636363636363636363636363636363636363636363636"
#let store-manifest = "5555555555555555555555555555555555555555555555555555555555555555"
#let support-benchmark = "6666666666666666666666666666666666666666666666666666666666666666"
#let support-config = "7777777777777777777777777777777777777777777777777777777777777777"
#let measurement-config = "8888888888888888888888888888888888888888888888888888888888888888"
#let measurement-input = "abababababababababababababababababababababababababababababababab"
#let measurement-input-b = "bcbcbcbcbcbcbcbcbcbcbcbcbcbcbcbcbcbcbcbcbcbcbcbcbcbcbcbcbcbcbcbc"
#let measurement-artifacts = (
  "0101010101010101010101010101010101010101010101010101010101010101",
  "0202020202020202020202020202020202020202020202020202020202020202",
  "0303030303030303030303030303030303030303030303030303030303030303",
  "0404040404040404040404040404040404040404040404040404040404040404",
  "0505050505050505050505050505050505050505050505050505050505050505",
  "0606060606060606060606060606060606060606060606060606060606060606",
  "0707070707070707070707070707070707070707070707070707070707070707",
  "0808080808080808080808080808080808080808080808080808080808080808",
  "0909090909090909090909090909090909090909090909090909090909090909",
  "0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a0a",
  "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
)
#let measurement-protocol = "target-rri-measurement-v1"
#let source = "analysis/qh-gates.json|sidecar:" + sidecar-a
#let protocol-source = "analysis/q1-actor-protocol.json|sidecar:" + protocol-sidecar
#let support-source = "analysis/candidate-support-attempts.json|sidecar:" + support-sidecar
#let measurement-source = "analysis/oracle-measurement-repeatability.json|sidecar:" + measurement-sidecar
#let sidecars = (
  (sidecar_id: sidecar-a, path: "qh-gates", name: "qh-gates", sha256: digest-a, format: "json", status: "confirmatory"),
  (sidecar_id: sidecar-b, path: "other", name: "other", sha256: digest-b, format: "json", status: "confirmatory"),
  (sidecar_id: protocol-sidecar, path: q1-protocol-receipt-name, name: q1-protocol-receipt-name, sha256: protocol-digest, format: "json", status: "confirmatory"),
  (sidecar_id: support-sidecar, path: candidate-support-receipt-name, name: candidate-support-receipt-name, sha256: support-digest, format: "json", status: "confirmatory"),
  (sidecar_id: support-benchmark-sidecar, path: candidate-support-benchmark-name, name: candidate-support-benchmark-name, sha256: support-benchmark, format: "json", status: "confirmatory"),
  (sidecar_id: measurement-sidecar, path: measurement-protocol-receipt-name, name: measurement-protocol-receipt-name, sha256: measurement-digest, format: "json", status: "confirmatory"),
  (sidecar_id: measurement-benchmark-sidecar, path: measurement-benchmark-name, name: measurement-benchmark-name, sha256: measurement-benchmark, format: "json", status: "confirmatory"),
)
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
  let envelope = (
    typed-sidecar-row(sidecar-id, "schema_version", "aria-nbv-analysis-facts-v1"),
    typed-sidecar-row(sidecar-id, "bundle_role", "analysis_facts"),
    typed-sidecar-row(sidecar-id, "logical_name", logical-name),
    typed-sidecar-row(sidecar-id, "status", "confirmatory"),
  )
  let facts = rows.enumerate().map(((index, row)) => {
    let prefix = "facts[" + str(index) + "]"
    let sidecar-marker = "|sidecar:" + sidecar-id
    let provenance = row.source.replace(sidecar-marker, "")
    (
      typed-sidecar-row(sidecar-id, prefix + ".store_id", row.store_id),
      typed-sidecar-row(sidecar-id, prefix + ".key", row.key),
      typed-sidecar-row(sidecar-id, prefix + ".value", row.value),
      typed-sidecar-row(sidecar-id, prefix + ".unit", row.unit),
      typed-sidecar-row(sidecar-id, prefix + ".n", row.n),
      typed-sidecar-row(sidecar-id, prefix + ".aggregation", row.aggregation),
      typed-sidecar-row(sidecar-id, prefix + ".provenance", provenance),
    )
  }).flatten()
  envelope + facts
}
#let support-benchmark-sidecar-value-rows(root-counts) = {
  let expected-attempts = root-counts.sum()
  let envelope = (
    typed-sidecar-row(support-benchmark-sidecar, "schema_version", candidate-support-benchmark-schema),
    typed-sidecar-row(support-benchmark-sidecar, "bundle_role", "candidate_support_benchmark_plan"),
    typed-sidecar-row(support-benchmark-sidecar, "logical_name", candidate-support-benchmark-name),
    typed-sidecar-row(support-benchmark-sidecar, "status", "confirmatory"),
    typed-sidecar-row(support-benchmark-sidecar, "expected_attempts", expected-attempts),
  )
  let roots = root-counts.enumerate().map(((scene-index, root-count)) => range(
    root-count,
  ).map(root-index => {
      let attempt-index = root-counts.slice(0, scene-index).sum(default: 0) + root-index
      let prefix = "roots[" + str(attempt-index) + "]"
      (
        typed-sidecar-row(support-benchmark-sidecar, prefix + ".scene_id", "scene-" + str(scene-index)),
        typed-sidecar-row(support-benchmark-sidecar, prefix + ".root_id", "root-" + str(root-index)),
      )
    }).flatten()).flatten()
  envelope + roots
}
#let measurement-benchmark-sidecar-value-rows(measurement-unit-count, repeat-count: 3) = {
  let envelope = (
    typed-sidecar-row(measurement-benchmark-sidecar, "schema_version", measurement-benchmark-schema),
    typed-sidecar-row(measurement-benchmark-sidecar, "bundle_role", "oracle_measurement_benchmark_plan"),
    typed-sidecar-row(measurement-benchmark-sidecar, "logical_name", measurement-benchmark-name),
    typed-sidecar-row(measurement-benchmark-sidecar, "status", "confirmatory"),
    typed-sidecar-row(measurement-benchmark-sidecar, "expected_repeats", repeat-count),
    typed-sidecar-row(measurement-benchmark-sidecar, "expected_measurement_units", measurement-unit-count),
    typed-sidecar-row(measurement-benchmark-sidecar, "rank_direction", measurement-rank-direction),
    typed-sidecar-row(measurement-benchmark-sidecar, "rank_tie_policy", measurement-rank-tie-policy),
  )
  let repeats = range(repeat-count).map(repeat-index => {
    let prefix = "repeats[" + str(repeat-index) + "]"
    typed-sidecar-row(
      measurement-benchmark-sidecar,
      prefix + ".repeat_id",
      "repeat-" + str(repeat-index),
    )
  })
  let units = range(measurement-unit-count).map(measurement-index => {
    let prefix = "units[" + str(measurement-index) + "]"
    (
      typed-sidecar-row(measurement-benchmark-sidecar, prefix + ".measurement_id", "measurement-" + str(measurement-index)),
      typed-sidecar-row(measurement-benchmark-sidecar, prefix + ".ranking_group_id", "ranking-group-0"),
    )
  }).flatten()
  envelope + repeats + units
}
#let report(
  rows,
  sidecar-rows: sidecars,
  sidecar-value-rows: none,
  support-plan-values: none,
  measurement-plan-values: none,
) = {
  let projected-sidecar-values = if sidecar-value-rows != none {
    sidecar-value-rows
  } else {
    let sidecar-id = rows.first().source.split("|sidecar:").last()
    let matches = sidecar-rows.filter(sidecar => sidecar.sidecar_id == sidecar-id)
    if matches.len() == 1 {
      analysis-sidecar-value-rows(sidecar-id, matches.first().name, rows)
    } else { () }
  }
  let projected-support-plan = if support-plan-values == none {
    support-benchmark-sidecar-value-rows((4, 4, 4, 4, 4))
  } else { support-plan-values }
  let projected-measurement-plan = if measurement-plan-values == none {
    measurement-benchmark-sidecar-value-rows(2, repeat-count: 3)
  } else { measurement-plan-values }
  (
    tables: (
      stores: (rows: ((store_id: "store-a", manifest_sha256: store-manifest),)),
      facts: (rows: rows),
      sidecars: (rows: sidecar-rows),
      sidecar_values: (rows: projected-sidecar-values + projected-support-plan + projected-measurement-plan),
    ),
  )
}

#let mutate-sidecar-fact-value(sidecar-value-rows, fact-key, replacement) = {
  let key-leaves = sidecar-value-rows.filter(row => (
    row.key.match(regex("^facts\\[[0-9]+\\]\\.key$")) != none,
    row.value_type == "str",
    row.value_text == fact-key,
  ).all(value => value))
  assert(key-leaves.len() == 1, message: "expected one synthetic sidecar fact key")
  let value-key = key-leaves.first().key.replace(regex("\\.key$"), ".value")
  sidecar-value-rows.map(row => if row.key == value-key {
    typed-sidecar-row(row.sidecar_id, row.key, replacement)
  } else { row })
}

#let population-rows(
  scene-count-value: 5,
  targets-value: 12,
  exclusions-value: 1,
  targets-unit: "count",
  targets-aggregation: "count",
  row-n: 5,
  source: source,
) = (
  fact("study.population.scenes", scene-count-value, "count", row-n, "count", source: source),
  fact("study.population.targets", targets-value, targets-unit, row-n, targets-aggregation, source: source),
  fact("study.population.exclusions", exclusions-value, "count", row-n, "count", source: source),
)

#let measurement-rows(
  repeat-count-value: 3,
  measurement-unit-count-value: 2,
  ranking-agreement-value: true,
  discrepancy-value: 0.0001,
  tolerance-value: 0.001,
  rule-value: repeatability-decision-rule,
  passed-value: true,
  discrepancy-unit: "fraction",
  discrepancy-aggregation: "repeatability_max_abs_difference",
  decision-aggregation: "repeatability_decision",
  row-n: 3,
  source: measurement-source,
  gate-source: measurement-source,
) = (
  fact("oracle.metric.protocol.receipt_schema", measurement-protocol-receipt-schema, "identity", row-n, "protocol_identity", source: source),
  fact("oracle.metric.protocol.id", measurement-protocol, "identity", row-n, "protocol_identity", source: source),
  fact("oracle.metric.protocol.benchmark_sha256", measurement-benchmark, "sha256", row-n, "protocol_binding_sha256", source: source),
  fact("oracle.metric.protocol.config_sha256", measurement-config, "sha256", row-n, "protocol_binding_sha256", source: source),
  fact("oracle.metric.protocol.store_manifest_sha256", store-manifest, "sha256", row-n, "protocol_binding_sha256", source: source),
  fact("oracle.metric.protocol.rank_direction", measurement-rank-direction, "identity", row-n, "protocol_identity", source: source),
  fact("oracle.metric.protocol.rank_tie_policy", measurement-rank-tie-policy, "identity", row-n, "protocol_identity", source: source),
  fact("oracle.metric.repeatability.max_abs_diff", discrepancy-value, discrepancy-unit, row-n, discrepancy-aggregation, source: source),
  fact("oracle.metric.repeatability.tolerance", tolerance-value, "fraction", row-n, "analysis_threshold", source: source),
  fact("oracle.metric.repeatability.rule", rule-value, "identity", row-n, "analysis_identity", source: source),
  fact("oracle.metric.repeatability.n_repeats", repeat-count-value, "count", row-n, "count", source: source),
  fact("oracle.metric.repeatability.n_measurement_units", measurement-unit-count-value, "count", row-n, "count", source: source),
  fact("oracle.metric.repeatability.ranking_agreement", ranking-agreement-value, "bool", row-n, "matched_unit_rank_identity", source: source),
  fact("oracle.metric.repeatability.passed", passed-value, "bool", row-n, decision-aggregation, source: gate-source),
)

#let support-rows(
  scene-count-value: 5,
  row-n: 5,
  gate-n: 5,
  expected-attempts: 20,
  metric-unit: "fraction",
  metric-value: 0.8,
  metric-aggregation: "state_then_scene_macro",
  support-p05: 2.0,
  failed-root-rate: 0.0,
  zero-rate: 0.1,
  side-balance: 0.5,
  orbit-span: 45.0,
  support-minimum: 1.0,
  failed-root-maximum: 0.2,
  rule: candidate-support-decision-rule,
  passed: true,
  source: support-source,
  gate-source: support-source,
) = (
  fact("study.population.scenes", scene-count-value, "count", row-n, "count", source: source),
  fact("candidate-support.receipt.schema", candidate-support-receipt-schema, "identity", row-n, "protocol_identity", source: source),
  fact("candidate-support.receipt.benchmark_sha256", support-benchmark, "sha256", row-n, "protocol_binding_sha256", source: source),
  fact("candidate-support.receipt.config_sha256", support-config, "sha256", row-n, "protocol_binding_sha256", source: source),
  fact("candidate-support.receipt.store_manifest_sha256", store-manifest, "sha256", row-n, "protocol_binding_sha256", source: source),
  fact("candidate-support.receipt.expected_attempts", expected-attempts, "count", row-n, "protocol_expected_count", source: source),
  fact("candidate-support.actor-valid-fraction", metric-value, metric-unit, row-n, metric-aggregation, source: source),
  fact("candidate-support.valid-support-p05", support-p05, "count", row-n, "state_then_scene_p05", source: source),
  fact("candidate-support.failed-root-rate", failed-root-rate, "fraction", row-n, "state_then_scene_macro", source: source),
  fact("candidate-support.configured-family-zero-rate", zero-rate, "fraction", row-n, "state_then_scene_macro", source: source),
  fact("candidate-support.target-side-balance", side-balance, "fraction", row-n, "state_then_scene_macro", source: source),
  fact("candidate-support.circular-orbit-span", orbit-span, "deg", row-n, "state_then_scene_macro", source: source),
  fact("candidate-support.valid-support-p05.minimum", support-minimum, "count", row-n, "analysis_threshold", source: source),
  fact("candidate-support.failed-root-rate.maximum", failed-root-maximum, "fraction", row-n, "analysis_threshold", source: source),
  fact("candidate-support.gate.rule", rule, "identity", row-n, "analysis_identity", source: source),
  fact("candidate-support.gate.passed", passed, "bool", gate-n, "state_then_scene_decision", source: gate-source),
)

#let support-attempt-rows(
  scene-count: 5,
  attempts-per-scene: 4,
  failed-per-scene: 0,
  scene-mean: 2,
  minimum-valid-count: 1,
  source: support-source,
) = {
  let attempt-count = scene-count * attempts-per-scene
  let successful-per-scene = attempts-per-scene - failed-per-scene
  let target-total = scene-mean * attempts-per-scene
  let base = if successful-per-scene == 0 { 0 } else {
    calc.floor(target-total / successful-per-scene)
  }
  let bonus = if successful-per-scene == 0 { 0 } else {
    target-total - base * successful-per-scene
  }
  range(scene-count).map(scene-index => range(attempts-per-scene).map(
    root-index => {
      let success-index = root-index - failed-per-scene
      let valid-count = if root-index < failed-per-scene {
        0
      } else if success-index < bonus {
        base + 1
      } else {
        base
      }
      let prefix = "candidate-support.attempts[" + str(scene-index * attempts-per-scene + root-index) + "]"
      (
        fact(prefix + ".scene_id", "scene-" + str(scene-index), "identity", attempt-count, "attempt_identity", source: source),
        fact(prefix + ".root_id", "root-" + str(root-index), "identity", attempt-count, "attempt_identity", source: source),
        fact(prefix + ".valid_count", valid-count, "count", attempt-count, "attempt_count", source: source),
        fact(prefix + ".minimum_valid_count", minimum-valid-count, "count", attempt-count, "attempt_threshold", source: source),
        fact(prefix + ".passed", valid-count >= minimum-valid-count, "bool", attempt-count, "attempt_outcome", source: source),
      )
    },
  ).flatten()).flatten()
}

#let support-attempt-rows-from-scenes(
  scene-valid-counts,
  minimum-valid-count: 1,
  source: support-source,
) = {
  let attempt-count = scene-valid-counts.map(values => values.len()).sum()
  scene-valid-counts.enumerate().map(((scene-index, valid-counts)) => valid-counts.enumerate().map(
    ((root-index, valid-count)) => {
      let attempt-index = scene-valid-counts.slice(0, scene-index).map(
        values => values.len(),
      ).sum(default: 0) + root-index
      let prefix = "candidate-support.attempts[" + str(attempt-index) + "]"
      (
        fact(prefix + ".scene_id", "scene-" + str(scene-index), "identity", attempt-count, "attempt_identity", source: source),
        fact(prefix + ".root_id", "root-" + str(root-index), "identity", attempt-count, "attempt_identity", source: source),
        fact(prefix + ".valid_count", valid-count, "count", attempt-count, "attempt_count", source: source),
        fact(prefix + ".minimum_valid_count", minimum-valid-count, "count", attempt-count, "attempt_threshold", source: source),
        fact(prefix + ".passed", valid-count >= minimum-valid-count, "bool", attempt-count, "attempt_outcome", source: source),
      )
    },
  ).flatten()).flatten()
}

#let support-report-from-scenes(scene-valid-counts) = {
  let scene-count = scene-valid-counts.len()
  let attempt-count = scene-valid-counts.map(values => values.len()).sum()
  let scene-means = scene-valid-counts.map(
    values => values.sum() / values.len(),
  )
  let ordered-means = scene-means.sorted()
  let p05 = ordered-means.at(calc.ceil(0.05 * scene-count) - 1)
  let failed-rate = scene-valid-counts.map(values => (
    values.filter(value => value < 1).len() / values.len()
  )).sum() / scene-count
  let passed = p05 >= 1 and failed-rate <= 0.2
  let rows = support-rows(
    scene-count-value: scene-count,
    row-n: scene-count,
    gate-n: scene-count,
    expected-attempts: attempt-count,
    support-p05: p05,
    failed-root-rate: failed-rate,
    passed: passed,
  ) + support-attempt-rows-from-scenes(scene-valid-counts)
  report(
    rows,
    support-plan-values: support-benchmark-sidecar-value-rows(
      scene-valid-counts.map(values => values.len()),
    ),
  )
}

#let support-report(
  scene-count: 5,
  scene-count-value: none,
  row-n: none,
  gate-n: none,
  expected-attempts: none,
  scene-mean: 2,
  failed-per-scene: 0,
  attempts-per-scene: 4,
  claimed-p05: none,
  claimed-failed-rate: none,
  ..args,
) = {
  let declared-scene-count = if scene-count-value == none { scene-count } else { scene-count-value }
  let declared-row-n = if row-n == none { scene-count } else { row-n }
  let declared-gate-n = if gate-n == none { scene-count } else { gate-n }
  let declared-attempts = if expected-attempts == none {
    scene-count * attempts-per-scene
  } else { expected-attempts }
  let p05 = if claimed-p05 == none { scene-mean } else { claimed-p05 }
  let failed-rate = if claimed-failed-rate == none {
    failed-per-scene / attempts-per-scene
  } else { claimed-failed-rate }
  let rows = support-rows(
    scene-count-value: declared-scene-count,
    row-n: declared-row-n,
    gate-n: declared-gate-n,
    expected-attempts: declared-attempts,
    support-p05: p05,
    failed-root-rate: failed-rate,
    ..args,
  ) + support-attempt-rows(
    scene-count: scene-count,
    scene-mean: scene-mean,
    failed-per-scene: failed-per-scene,
    attempts-per-scene: attempts-per-scene,
  )
  report(
    rows,
    support-plan-values: support-benchmark-sidecar-value-rows(
      range(scene-count).map(_ => attempts-per-scene),
    ),
  )
}

#let measurement-observation-rows(
  repeat-count: 3,
  measurement-unit-count: 2,
  discrepancy: 0.0001,
  protocol-id: measurement-protocol,
  protocol-config: measurement-config,
  input: measurement-input,
  ranking-reversal: false,
  tied-baseline: false,
  source: measurement-source,
) = {
  let observation-count = repeat-count * measurement-unit-count
  range(repeat-count).map(repeat-index => range(measurement-unit-count).map(
    measurement-index => {
      let index = repeat-index * measurement-unit-count + measurement-index
      let baseline = if tied-baseline and measurement-index < 2 {
        -0.4
      } else { -0.4 + measurement-index * 0.0004 }
      let changed-index = if ranking-reversal { 0 } else { measurement-unit-count - 1 }
      let value = if repeat-index == 1 and measurement-index == changed-index {
        baseline + discrepancy
      } else { baseline }
      let artifact = if repeat-index == 1 and measurement-index == changed-index {
        measurement-artifacts.last()
      } else { measurement-artifacts.at(measurement-index) }
      let prefix = "oracle.metric.observations[" + str(index) + "]"
      (
        fact(prefix + ".repeat_id", "repeat-" + str(repeat-index), "identity", observation-count, "repeat_identity", source: source),
        fact(prefix + ".measurement_id", "measurement-" + str(measurement-index), "identity", observation-count, "measurement_identity", source: source),
        fact(prefix + ".ranking_group_id", "ranking-group-0", "identity", observation-count, "ranking_group_identity", source: source),
        fact(prefix + ".input_sha256", if calc.rem(measurement-index, 2) == 0 { input } else { measurement-input-b }, "sha256", observation-count, "measurement_input_sha256", source: source),
        fact(prefix + ".artifact_sha256", artifact, "sha256", observation-count, "measurement_output_sha256", source: source),
        fact(prefix + ".protocol_id", protocol-id, "identity", observation-count, "protocol_identity", source: source),
        fact(prefix + ".protocol_config_sha256", protocol-config, "sha256", observation-count, "protocol_binding_sha256", source: source),
        fact(prefix + ".root_normalized_gain", value, "fraction", observation-count, "matched_unit_measurement", source: source),
      )
    },
  ).flatten()).flatten()
}

#let measurement-report(
  repeat-count: 3,
  measurement-unit-count: 2,
  discrepancy: 0.0001,
  protocol-id: measurement-protocol,
  protocol-config: measurement-config,
  input: measurement-input,
  ranking-reversal: false,
  tied-baseline: false,
  ranking-agreement-value: true,
  ..args,
) = report(
  measurement-rows(
    repeat-count-value: repeat-count,
    measurement-unit-count-value: measurement-unit-count,
    ranking-agreement-value: ranking-agreement-value,
    discrepancy-value: discrepancy,
    row-n: repeat-count,
    ..args,
  ) + measurement-observation-rows(
    repeat-count: repeat-count,
    measurement-unit-count: measurement-unit-count,
    discrepancy: discrepancy,
    protocol-id: protocol-id,
    protocol-config: protocol-config,
    input: input,
    ranking-reversal: ranking-reversal,
    tied-baseline: tied-baseline,
  ),
  measurement-plan-values: measurement-benchmark-sidecar-value-rows(
    measurement-unit-count,
    repeat-count: repeat-count,
  ),
)

#let q1-rows(
  count-value: 5,
  ranking-value: 0.8,
  ranking-ci-low: 0.65,
  ranking-ci-high: 0.9,
  interval-method: paired-interval-method,
  ranking-unit: "fraction",
  ranking-aggregation: "state_then_scene_macro",
  calibration-value: 0.1,
  chance: q1-pairwise-chance,
  ranking-minimum: 0.7,
  calibration-maximum: 0.2,
  rule: q1-decision-rule,
  passed: true,
  receipt-schema: q1-protocol-receipt-schema,
  scene-role: q1-scene-role,
  target-source: q1-target-source-protocol,
  target-matching-passed: true,
  actor-oracle-leakage-absent: true,
  hard-mask-applied: true,
  causal-history-only: true,
  source: protocol-source,
  gate-source: protocol-source,
) = (
  fact("q1.protocol.receipt_schema", receipt-schema, "identity", 5, "protocol_identity", source: source),
  fact("q1.protocol.scene_role", scene-role, "identity", 5, "protocol_identity", source: source),
  fact("q1.protocol.target_source", target-source, "identity", 5, "protocol_identity", source: source),
  fact("q1.protocol.target_matching_passed", target-matching-passed, "bool", 5, "protocol_audit", source: source),
  fact("q1.protocol.actor_oracle_leakage_absent", actor-oracle-leakage-absent, "bool", 5, "protocol_audit", source: source),
  fact("q1.protocol.hard_mask_applied", hard-mask-applied, "bool", 5, "protocol_audit", source: source),
  fact("q1.protocol.causal_history_only", causal-history-only, "bool", 5, "protocol_audit", source: source),
  fact("q1.ranking.pairwise_accuracy", ranking-value, ranking-unit, 5, ranking-aggregation, source: source),
  fact("q1.ranking.pairwise_accuracy.ci_low", ranking-ci-low, "fraction", 5, "scene_clustered_interval", source: source),
  fact("q1.ranking.pairwise_accuracy.ci_high", ranking-ci-high, "fraction", 5, "scene_clustered_interval", source: source),
  fact("q1.ranking.interval_method", interval-method, "identity", 5, "analysis_identity", source: source),
  fact("q1.calibration.mae", calibration-value, "root_normalized_return", 5, "state_then_scene_macro", source: source),
  fact("q1.population.n_scenes", count-value, "count", 5, "count", source: source),
  fact("q1.ranking.chance", chance, "fraction", 5, "analysis_threshold", source: source),
  fact("q1.ranking.pairwise_accuracy.minimum", ranking-minimum, "fraction", 5, "analysis_threshold", source: source),
  fact("q1.calibration.mae.maximum", calibration-maximum, "root_normalized_return", 5, "analysis_threshold", source: source),
  fact("q1.gate.rule", rule, "identity", 5, "analysis_identity", source: source),
  fact("q1.gate.passed", passed, "bool", 5, "state_then_scene_decision", source: gate-source),
)

#let q2-rows(
  count-value: 5,
  row-n: 5,
  mae-value: 0.1,
  coverage-value: 0.9,
  coverage-unit: "fraction",
  coverage-aggregation: "selected_chain_fraction",
  minimum-support-stratum-rows: 2,
  minimum-unit-rows: 2,
  maximum-tolerance-excess: -0.01,
  coverage-minimum: 0.8,
  minimum-independent-units: 5,
  required-unit-rows: 1,
  absolute-tolerance: 0.01,
  relative-tolerance: 0.05,
  rule: q2-decision-rule,
  passed: true,
  source: source,
  gate-source: source,
) = (
  fact("q2.exact.mae", mae-value, "root_normalized_return", row-n, "independent_unit_macro", source: source),
  fact("q2.exact.coverage", coverage-value, coverage-unit, row-n, coverage-aggregation, source: source),
  fact("q2.exact.minimum_support_stratum_rows", minimum-support-stratum-rows, "count", row-n, "support_stratum_minimum", source: source),
  fact("q2.exact.minimum_rows_per_independent_unit", minimum-unit-rows, "count", row-n, "independent_unit_minimum", source: source),
  fact("q2.exact.maximum_tolerance_excess", maximum-tolerance-excess, "root_normalized_return", row-n, "exact_row_maximum", source: source),
  fact("q2.exact.n_independent_units", count-value, "count", row-n, "count", source: source),
  fact("q2.exact.coverage.minimum", coverage-minimum, "fraction", row-n, "analysis_threshold", source: source),
  fact("q2.exact.minimum_independent_units", minimum-independent-units, "count", row-n, "analysis_threshold", source: source),
  fact("q2.exact.minimum_rows_per_independent_unit.required", required-unit-rows, "count", row-n, "analysis_threshold", source: source),
  fact("q2.exact.absolute_tolerance", absolute-tolerance, "root_normalized_return", row-n, "analysis_threshold", source: source),
  fact("q2.exact.relative_tolerance", relative-tolerance, "dimensionless", row-n, "analysis_threshold", source: source),
  fact("q2.exact.rule", rule, "identity", row-n, "analysis_identity", source: source),
  fact("q2.exact.passed", passed, "bool", row-n, "all_units_v1", source: gate-source),
)

#assert(report-store-candidate-support-evidence-valid(support-report(), "store-a"))
#assert(report-store-candidate-support-evidence-valid(support-report(scene-mean: 1), "store-a"))
#assert(report-store-candidate-support-evidence-valid(support-report(scene-mean: 0, failed-per-scene: 4, passed: false), "store-a"))
#assert(report-store-candidate-support-evidence-valid(support-report(failed-per-scene: 1, passed: false), "store-a"))
#assert(not report-store-candidate-support-evidence-valid(support-report(scene-mean: 0, failed-per-scene: 4), "store-a"))
#assert(not report-store-candidate-support-evidence-valid(support-report(failed-per-scene: 1), "store-a"))
#assert(report-store-candidate-support-evidence-valid(support-report(
  scene-mean: 0,
  failed-per-scene: 4,
  metric-value: 0,
  zero-rate: 1,
  side-balance: 0,
  orbit-span: 0,
  passed: false,
), "store-a"))
#assert(not report-store-candidate-support-evidence-valid(support-report(
  scene-mean: 0,
  failed-per-scene: 4,
  metric-value: 0,
  zero-rate: 1,
  side-balance: 0,
  orbit-span: 0,
), "store-a"))
#assert(not report-store-candidate-support-evidence-valid(support-report(passed: false), "store-a"))
#assert(not report-store-candidate-support-evidence-valid(support-report(support-minimum: 0), "store-a"))
#assert(not report-store-candidate-support-evidence-valid(support-report(failed-root-maximum: 1), "store-a"))
#assert(not report-store-candidate-support-evidence-valid(support-report(rule: "unfrozen_support_rule"), "store-a"))
#assert(not report-store-candidate-support-evidence-valid(support-report(scene-count-value: "5"), "store-a"))
#assert(not report-store-candidate-support-evidence-valid(support-report(gate-n: 4), "store-a"))
#assert(not report-store-candidate-support-evidence-valid(support-report(metric-value: "0.8"), "store-a"))
#assert(not report-store-candidate-support-evidence-valid(support-report(metric-value: 1.1), "store-a"))
#assert(not report-store-candidate-support-evidence-valid(support-report(metric-unit: "count"), "store-a"))
#assert(not report-store-candidate-support-evidence-valid(support-report(metric-aggregation: "candidate_row_mean"), "store-a"))
#assert(not report-store-candidate-support-evidence-valid(support-report(source: "analysis/unbound.json", gate-source: "analysis/unbound.json"), "store-a"))
#assert(not report-store-candidate-support-evidence-valid(support-report(gate-source: "analysis/other.json|sidecar:" + sidecar-b), "store-a"))
#assert(not report-store-candidate-support-evidence-valid(support-report(source: "analysis/qh-gates.json|sidecar:", gate-source: "analysis/qh-gates.json|sidecar:"), "store-a"))
#assert(not report-store-candidate-support-evidence-valid(report(support-rows()), "store-a"))
#assert(not report-store-candidate-support-evidence-valid(support-report(claimed-p05: 3), "store-a"))
#assert(not report-store-candidate-support-evidence-valid(support-report(claimed-failed-rate: 0.1), "store-a"))
#assert(not report-store-candidate-support-evidence-valid(support-report(expected-attempts: 19), "store-a"))
#let quantile-scenes = ((0,),) + range(20).map(_ => (2,))
#assert(report-store-candidate-support-evidence-valid(
  support-report-from-scenes(quantile-scenes),
  "store-a",
))
#assert(report-store-candidate-support-evidence-valid(
  support-report-from-scenes(((0,), (1, 1, 1))),
  "store-a",
))
#let support-scale-scenes = range(20).map(
  _ => range(5).map(_ => 2),
)
#assert(report-store-candidate-support-evidence-valid(
  support-report-from-scenes(support-scale-scenes),
  "store-a",
))

#let support-baseline-rows = support-rows() + support-attempt-rows()
#let duplicate-support-root = support-baseline-rows.map(row => if row.key == "candidate-support.attempts[1].root_id" {
  row + (value: "root-0",)
} else { row })
#assert(not report-store-candidate-support-evidence-valid(report(duplicate-support-root), "store-a"))
#let drifted-support-threshold = support-baseline-rows.map(row => if row.key == "candidate-support.attempts[1].minimum_valid_count" {
  row + (value: 2,)
} else { row })
#assert(not report-store-candidate-support-evidence-valid(report(drifted-support-threshold), "store-a"))
#let contradictory-support-outcome = support-baseline-rows.map(row => if row.key == "candidate-support.attempts[1].passed" {
  row + (value: false,)
} else { row })
#assert(not report-store-candidate-support-evidence-valid(report(contradictory-support-outcome), "store-a"))
#assert(not report-store-candidate-support-evidence-valid(report(
  support-baseline-rows.filter(row => not row.key.starts-with("candidate-support.attempts[0].")),
), "store-a"))
#let adjusted-truncated-support = support-baseline-rows.filter(
  row => not row.key.starts-with("candidate-support.attempts[0]."),
).map(row => if row.key == "candidate-support.receipt.expected_attempts" {
  row + (value: 19,)
} else if row.key.match(regex("^candidate-support\\.attempts\\[[0-9]+\\]\\.")) != none {
  row + (n: 19,)
} else { row })
#assert(not report-store-candidate-support-evidence-valid(
  report(adjusted-truncated-support),
  "store-a",
))
#let malformed-support-record-n = support-baseline-rows.map(row => if row.key == "candidate-support.attempts[1].valid_count" {
  row + (n: 19,)
} else { row })
#assert(not report-store-candidate-support-evidence-valid(
  report(malformed-support-record-n),
  "store-a",
))
#let support-baseline-payload = analysis-sidecar-value-rows(
  support-sidecar,
  candidate-support-receipt-name,
  support-baseline-rows,
)
#assert(not report-store-candidate-support-evidence-valid(report(
  support-baseline-rows,
  sidecar-value-rows: mutate-sidecar-fact-value(
    support-baseline-payload,
    "candidate-support.attempts[0].valid_count",
    3,
  ),
), "store-a"))

#assert(report-store-population-evidence-valid(report(population-rows()), "store-a"))
#assert(not report-store-population-evidence-valid(report(population-rows(scene-count-value: "5")), "store-a"))
#assert(not report-store-population-evidence-valid(report(population-rows(targets-value: 0)), "store-a"))
#assert(not report-store-population-evidence-valid(report(population-rows(exclusions-value: -1)), "store-a"))
#assert(not report-store-population-evidence-valid(report(population-rows(targets-unit: "fraction")), "store-a"))
#assert(not report-store-population-evidence-valid(report(population-rows(targets-aggregation: "scene_macro")), "store-a"))
#assert(not report-store-population-evidence-valid(report(population-rows(row-n: 4)), "store-a"))
#assert(not report-store-population-evidence-valid(report(population-rows(source: "analysis/population.json")), "store-a"))
#assert(not report-store-population-evidence-valid(report(population-rows(source: "analysis/population.json|sidecar:")), "store-a"))
#assert(not report-store-population-evidence-valid(report(
  population-rows(),
  sidecar-rows: sidecars + ((sidecar_id: sidecar-a, path: "duplicate", name: "duplicate", sha256: digest-b, format: "json", status: "confirmatory"),),
), "store-a"))
#assert(not report-store-population-evidence-valid(report(
  population-rows(),
  sidecar-rows: ((sidecar_id: sidecar-a, path: "qh-gates", name: "qh-gates", sha256: "invalid", format: "json", status: "confirmatory"),),
), "store-a"))
#let population-baseline-rows = population-rows()
#assert(report-store-population-evidence-valid(report(
  population-baseline-rows,
  sidecar-value-rows: analysis-sidecar-value-rows(
    sidecar-a,
    "qh-gates",
    population-baseline-rows,
  ).filter(row => row.key != "logical_name"),
), "store-a"))

#assert(report-store-measurement-evidence-valid(measurement-report(), "store-a"))
#assert(report-store-measurement-evidence-valid(measurement-report(discrepancy: 0.002, passed-value: false), "store-a"))
#assert(report-store-measurement-evidence-valid(measurement-report(
  discrepancy: 0.0005,
  ranking-reversal: true,
  ranking-agreement-value: false,
  passed-value: false,
), "store-a"))
#assert(report-store-measurement-evidence-valid(measurement-report(
  discrepancy: 0.0,
  tied-baseline: true,
), "store-a"))
#assert(report-store-measurement-evidence-valid(measurement-report(
  discrepancy: 0.0001,
  ranking-reversal: true,
  tied-baseline: true,
  ranking-agreement-value: false,
  passed-value: false,
), "store-a"))
#assert(not report-store-measurement-evidence-valid(measurement-report(
  discrepancy: 0.0001,
  ranking-reversal: true,
  tied-baseline: true,
  ranking-agreement-value: true,
), "store-a"))
#assert(not report-store-measurement-evidence-valid(measurement-report(
  discrepancy: 0.0005,
  ranking-reversal: true,
  ranking-agreement-value: false,
), "store-a"))
#assert(not report-store-measurement-evidence-valid(measurement-report(
  ranking-agreement-value: false,
  passed-value: false,
), "store-a"))
#assert(not report-store-measurement-evidence-valid(measurement-report(discrepancy: 0.002, passed-value: true), "store-a"))
#assert(not report-store-measurement-evidence-valid(measurement-report(passed-value: false), "store-a"))
#assert(not report-store-measurement-evidence-valid(measurement-report(repeat-count: 1), "store-a"))
#assert(not report-store-measurement-evidence-valid(measurement-report(measurement-unit-count-value: 3), "store-a"))
#assert(not report-store-measurement-evidence-valid(report(measurement-rows(repeat-count-value: "3")), "store-a"))
#assert(not report-store-measurement-evidence-valid(report(measurement-rows(discrepancy-value: "0.0001")), "store-a"))
#assert(not report-store-measurement-evidence-valid(measurement-report(discrepancy: -0.0001), "store-a"))
#assert(not report-store-measurement-evidence-valid(measurement-report(tolerance-value: -0.001), "store-a"))
#assert(not report-store-measurement-evidence-valid(measurement-report(rule-value: "unfrozen_rule"), "store-a"))
#assert(not report-store-measurement-evidence-valid(measurement-report(discrepancy-unit: "count"), "store-a"))
#assert(not report-store-measurement-evidence-valid(measurement-report(discrepancy-aggregation: "mean_abs_difference"), "store-a"))
#assert(not report-store-measurement-evidence-valid(measurement-report(decision-aggregation: "decision"), "store-a"))
#assert(not report-store-measurement-evidence-valid(report(measurement-rows(row-n: 2)), "store-a"))
#assert(not report-store-measurement-evidence-valid(measurement-report(gate-source: "analysis/other.json|sidecar:" + sidecar-b), "store-a"))
#assert(not report-store-measurement-evidence-valid(measurement-report(source: "analysis/repeatability.json|sidecar:", gate-source: "analysis/repeatability.json|sidecar:"), "store-a"))
#assert(not report-store-measurement-evidence-valid(report(measurement-rows()), "store-a"))
#assert(not report-store-measurement-evidence-valid(measurement-report(protocol-config: digest-b), "store-a"))
#assert(report-store-measurement-evidence-valid(measurement-report(
  repeat-count: 4,
  measurement-unit-count: 3,
), "store-a"))

#let measurement-baseline-rows = measurement-rows() + measurement-observation-rows()
#let duplicate-repeat-id = measurement-baseline-rows.map(row => if row.key == "oracle.metric.observations[2].repeat_id" {
  row + (value: "repeat-0",)
} else { row })
#assert(not report-store-measurement-evidence-valid(report(duplicate-repeat-id), "store-a"))
#let mismatched-repeat-input = measurement-baseline-rows.map(row => if row.key == "oracle.metric.observations[2].input_sha256" {
  row + (value: digest-b,)
} else { row })
#assert(not report-store-measurement-evidence-valid(report(mismatched-repeat-input), "store-a"))
#let malformed-repeat-artifact = measurement-baseline-rows.map(row => if row.key == "oracle.metric.observations[2].artifact_sha256" {
  row + (value: "invalid",)
} else { row })
#assert(not report-store-measurement-evidence-valid(report(malformed-repeat-artifact), "store-a"))
#let contradictory-shared-artifact = measurement-baseline-rows.map(row => if row.key == "oracle.metric.observations[3].artifact_sha256" {
  row + (value: measurement-artifacts.at(1),)
} else { row })
#assert(not report-store-measurement-evidence-valid(report(contradictory-shared-artifact), "store-a"))
#assert(not report-store-measurement-evidence-valid(report(
  measurement-baseline-rows.filter(row => not row.key.starts-with("oracle.metric.observations[0].")),
), "store-a"))
#let malformed-observation-n = measurement-baseline-rows.map(row => if row.key == "oracle.metric.observations[2].ranking_group_id" {
  row + (n: 5,)
} else { row })
#assert(not report-store-measurement-evidence-valid(report(malformed-observation-n), "store-a"))
#let self-adjusted-truncated-measurements = measurement-baseline-rows.filter(
  row => not row.key.starts-with("oracle.metric.observations[1].") and not row.key.starts-with("oracle.metric.observations[3].") and not row.key.starts-with("oracle.metric.observations[5]."),
).map(row => if row.key == "oracle.metric.repeatability.n_measurement_units" {
  row + (value: 1,)
} else if row.key.match(regex("^oracle\\.metric\\.observations\\[[0-9]+\\]\\.")) != none {
  row + (n: 3,)
} else { row })
#assert(not report-store-measurement-evidence-valid(
  report(self-adjusted-truncated-measurements),
  "store-a",
))
#let self-adjusted-truncated-repeat = measurement-baseline-rows.filter(
  row => not row.key.starts-with("oracle.metric.observations[2].") and not row.key.starts-with("oracle.metric.observations[3]."),
).map(row => if row.key == "oracle.metric.repeatability.n_repeats" {
  row + (value: 2, n: 2)
} else if row.key == "oracle.metric.repeatability.max_abs_diff" {
  row + (value: 0.0, n: 2)
} else if row.key.match(regex("^oracle\\.metric\\.observations\\[[0-9]+\\]\\.")) != none {
  row + (n: 4,)
} else {
  row + (n: 2,)
})
#assert(not report-store-measurement-evidence-valid(
  report(self-adjusted-truncated-repeat),
  "store-a",
))
#let measurement-baseline-payload = analysis-sidecar-value-rows(
  measurement-sidecar,
  measurement-protocol-receipt-name,
  measurement-baseline-rows,
)
#assert(not report-store-measurement-evidence-valid(report(
  measurement-baseline-rows,
  sidecar-value-rows: mutate-sidecar-fact-value(
    measurement-baseline-payload,
    "oracle.metric.observations[0].root_normalized_gain",
    -0.3,
  ),
), "store-a"))

#assert(report-store-q1-evidence-valid(report(q1-rows()), "store-a"))
#assert(report-store-q1-evidence-valid(report(q1-rows(ranking-value: 0.6, passed: false)), "store-a"))
#assert(report-store-q1-evidence-valid(report(q1-rows(calibration-value: 0.3, passed: false)), "store-a"))
#assert(report-store-q1-evidence-valid(report(q1-rows(ranking-value: 0.7, calibration-value: 0.2)), "store-a"))
#assert(not report-store-q1-evidence-valid(report(q1-rows(ranking-value: 0.6)), "store-a"))
#assert(not report-store-q1-evidence-valid(report(q1-rows(calibration-value: 0.3)), "store-a"))
#assert(report-store-q1-evidence-valid(report(q1-rows(ranking-value: 0, ranking-ci-low: 0, ranking-ci-high: 0.2, calibration-value: 10, passed: false)), "store-a"))
#assert(report-store-q1-evidence-valid(report(q1-rows(ranking-ci-low: 0.5, passed: false)), "store-a"))
#assert(not report-store-q1-evidence-valid(report(q1-rows(ranking-value: 0, ranking-ci-low: 0, ranking-ci-high: 0.2, calibration-value: 10)), "store-a"))
#assert(not report-store-q1-evidence-valid(report(q1-rows(ranking-ci-low: 0.5)), "store-a"))
#assert(not report-store-q1-evidence-valid(report(q1-rows(passed: false)), "store-a"))
#assert(not report-store-q1-evidence-valid(report(q1-rows(ranking-minimum: 0.5)), "store-a"))
#assert(not report-store-q1-evidence-valid(report(q1-rows(calibration-maximum: 0)), "store-a"))
#assert(not report-store-q1-evidence-valid(report(q1-rows(chance: 0.4)), "store-a"))
#assert(not report-store-q1-evidence-valid(report(q1-rows(interval-method: "unfrozen_interval")), "store-a"))
#assert(not report-store-q1-evidence-valid(report(q1-rows(rule: "unfrozen_q1_rule")), "store-a"))
#assert(not report-store-q1-evidence-valid(report(q1-rows(receipt-schema: "unversioned_receipt")), "store-a"))
#assert(not report-store-q1-evidence-valid(report(q1-rows(scene-role: "training_scene")), "store-a"))
#assert(not report-store-q1-evidence-valid(report(q1-rows(target-source: "privileged_gt_obb")), "store-a"))
#assert(not report-store-q1-evidence-valid(report(q1-rows(target-matching-passed: false)), "store-a"))
#assert(not report-store-q1-evidence-valid(report(q1-rows(actor-oracle-leakage-absent: false)), "store-a"))
#assert(not report-store-q1-evidence-valid(report(q1-rows(hard-mask-applied: false)), "store-a"))
#assert(not report-store-q1-evidence-valid(report(q1-rows(causal-history-only: false)), "store-a"))
#assert(not report-store-q1-evidence-valid(report(
  q1-rows(),
  sidecar-rows: sidecars.filter(sidecar => sidecar.sidecar_id != protocol-sidecar),
), "store-a"))
#assert(not report-store-q1-evidence-valid(report(
  q1-rows(),
  sidecar-rows: sidecars.map(sidecar => if sidecar.sidecar_id == protocol-sidecar {
    (sidecar_id: sidecar.sidecar_id, path: sidecar.path, name: sidecar.name, sha256: "invalid", format: sidecar.format, status: sidecar.status)
  } else { sidecar }),
), "store-a"))
#let q1-baseline-rows = q1-rows()
#let q1-baseline-payload = analysis-sidecar-value-rows(
  protocol-sidecar,
  q1-protocol-receipt-name,
  q1-baseline-rows,
)
#for mutation in (
  (key: "q1.protocol.receipt_schema", value: "unversioned_receipt"),
  (key: "q1.protocol.scene_role", value: "training_scene"),
  (key: "q1.protocol.target_source", value: "privileged_gt_obb"),
  (key: "q1.protocol.target_matching_passed", value: false),
  (key: "q1.protocol.actor_oracle_leakage_absent", value: false),
  (key: "q1.protocol.hard_mask_applied", value: false),
  (key: "q1.protocol.causal_history_only", value: false),
) {
  assert(not report-store-q1-evidence-valid(report(
    q1-baseline-rows,
    sidecar-value-rows: mutate-sidecar-fact-value(
      q1-baseline-payload,
      mutation.key,
      mutation.value,
    ),
  ), "store-a"))
}
#let unrelated-source = "analysis/other.json|sidecar:" + sidecar-b
#let unrelated-payload = analysis-sidecar-value-rows(
  sidecar-b,
  "other",
  (fact("unrelated.audit", true, "bool", 5, "protocol_audit", source: unrelated-source),),
)
#assert(not report-store-q1-evidence-valid(report(
  q1-rows(source: unrelated-source, gate-source: unrelated-source),
  sidecar-value-rows: unrelated-payload,
), "store-a"))
#assert(not report-store-q1-evidence-valid(report(q1-rows(count-value: 4)), "store-a"))
#assert(not report-store-q1-evidence-valid(report(q1-rows(ranking-value: "0.8")), "store-a"))
#assert(not report-store-q1-evidence-valid(report(q1-rows(ranking-value: 1.1)), "store-a"))
#assert(not report-store-q1-evidence-valid(report(q1-rows(calibration-value: -0.1)), "store-a"))
#assert(not report-store-q1-evidence-valid(report(q1-rows(ranking-unit: "count")), "store-a"))
#assert(not report-store-q1-evidence-valid(report(q1-rows(ranking-aggregation: "candidate_row_mean")), "store-a"))
#assert(not report-store-q1-evidence-valid(report(q1-rows(source: "analysis/unbound.json", gate-source: "analysis/unbound.json")), "store-a"))
#assert(not report-store-q1-evidence-valid(report(q1-rows(gate-source: "analysis/other.json|sidecar:" + sidecar-b)), "store-a"))

#assert(report-store-q2-evidence-valid(report(q2-rows()), "store-a"))
#assert(report-store-q2-evidence-valid(report(q2-rows(coverage-value: 0, minimum-support-stratum-rows: 0, minimum-unit-rows: 0, maximum-tolerance-excess: 0.1, passed: false)), "store-a"))
#assert(report-store-q2-evidence-valid(report(q2-rows(coverage-value: 0.7, passed: false)), "store-a"))
#assert(report-store-q2-evidence-valid(report(q2-rows(minimum-support-stratum-rows: 0, passed: false)), "store-a"))
#assert(report-store-q2-evidence-valid(report(q2-rows(count-value: 4, row-n: 4, passed: false)), "store-a"))
#assert(report-store-q2-evidence-valid(report(q2-rows(minimum-unit-rows: 0, passed: false)), "store-a"))
#assert(report-store-q2-evidence-valid(report(q2-rows(maximum-tolerance-excess: 0.1, passed: false)), "store-a"))
#assert(report-store-q2-evidence-valid(report(q2-rows(coverage-value: 0.8, maximum-tolerance-excess: 0)), "store-a"))
#assert(not report-store-q2-evidence-valid(report(q2-rows(coverage-value: 0.7)), "store-a"))
#assert(not report-store-q2-evidence-valid(report(q2-rows(minimum-support-stratum-rows: 0)), "store-a"))
#assert(not report-store-q2-evidence-valid(report(q2-rows(count-value: 4, row-n: 4)), "store-a"))
#assert(not report-store-q2-evidence-valid(report(q2-rows(minimum-unit-rows: 0)), "store-a"))
#assert(not report-store-q2-evidence-valid(report(q2-rows(maximum-tolerance-excess: 0.1)), "store-a"))
#assert(not report-store-q2-evidence-valid(report(q2-rows(coverage-value: 0, minimum-support-stratum-rows: 0, minimum-unit-rows: 0, maximum-tolerance-excess: 0.1)), "store-a"))
#assert(not report-store-q2-evidence-valid(report(q2-rows(passed: false)), "store-a"))
#assert(not report-store-q2-evidence-valid(report(q2-rows(coverage-minimum: 0)), "store-a"))
#assert(not report-store-q2-evidence-valid(report(q2-rows(minimum-independent-units: 4)), "store-a"))
#assert(not report-store-q2-evidence-valid(report(q2-rows(required-unit-rows: 0)), "store-a"))
#assert(not report-store-q2-evidence-valid(report(q2-rows(absolute-tolerance: -0.01)), "store-a"))
#assert(not report-store-q2-evidence-valid(report(q2-rows(relative-tolerance: -0.01)), "store-a"))
#assert(not report-store-q2-evidence-valid(report(q2-rows(rule: "unfrozen_q2_rule")), "store-a"))
#assert(not report-store-q2-evidence-valid(report(q2-rows(count-value: 4)), "store-a"))
#assert(not report-store-q2-evidence-valid(report(q2-rows(mae-value: "0.1")), "store-a"))
#assert(not report-store-q2-evidence-valid(report(q2-rows(mae-value: -0.1)), "store-a"))
#assert(not report-store-q2-evidence-valid(report(q2-rows(coverage-value: 1.1)), "store-a"))
#assert(not report-store-q2-evidence-valid(report(q2-rows(coverage-unit: "count")), "store-a"))
#assert(not report-store-q2-evidence-valid(report(q2-rows(coverage-aggregation: "candidate_row_mean")), "store-a"))
#assert(not report-store-q2-evidence-valid(report(q2-rows(source: "analysis/unbound.json", gate-source: "analysis/unbound.json")), "store-a"))
#assert(not report-store-q2-evidence-valid(report(q2-rows(gate-source: "analysis/other.json|sidecar:" + sidecar-b)), "store-a"))
#let q2-baseline-rows = q2-rows()
#assert(not report-store-q2-evidence-valid(report(
  q2-baseline-rows,
  sidecar-value-rows: mutate-sidecar-fact-value(
    analysis-sidecar-value-rows(sidecar-a, "qh-gates", q2-baseline-rows),
    "q2.exact.coverage",
    0.7,
  ),
), "store-a"))

Population, repeatability, candidate support, actor-visible one-step evidence,
and learned-versus-exact two-step evidence are admitted only through typed,
range-checked, population-bound, provenance-complete row families.
