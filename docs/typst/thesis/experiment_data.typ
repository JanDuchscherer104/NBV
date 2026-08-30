#let report-schema-version = "aria-nbv-thesis-report-v1"
#let scientific-report-schema-version = "aria-nbv-report-bundle-v2"

#let required-report-columns = (
  stores: ("store_id", "name", "manifest_sha256", "validation_ok"),
  parameters: ("store_id", "key", "value_type", "is_missing"),
  statistics: ("store_id", "key", "value_type", "is_missing"),
  facts: ("store_id", "key", "value", "unit", "n", "aggregation", "status", "source"),
  source_coverage: ("store_id", "dimension", "value", "count"),
  targets: ("store_id", "target_id", "target_valid", "target_invalid_reason"),
  validity: ("store_id", "stage", "count", "fraction_of_full"),
  candidate_groups: ("store_id", "group_by", "group", "total", "actor_valid"),
  steps: ("store_id", "step_index", "policy", "cumulative_target_rri"),
  rollout_tree: ("store_id", "policy", "step_index", "selected_steps"),
  selected_depth: ("store_id", "step_index", "available", "valid_fraction"),
  runtime_storage: ("store_id", "file_count", "total_bytes", "status", "source"),
  failures: ("store_id", "kind", "severity", "status", "source"),
  sidecars: ("sidecar_id", "path", "sha256", "status"),
  sidecar_values: ("sidecar_id", "key", "value_type", "is_missing"),
)

#let required-report-facts = (
  "candidate_validity.valid",
  "candidate_validity.total",
  "candidate_validity.fraction",
  "candidate_validity.valid_per_step.mean",
  "candidate_validity.valid_per_step.median",
  "selected.total",
  "selected.path_length_m.mean",
  "selected.path_length_m.median",
  "selected.path_length_m.p5",
  "selected.path_length_m.p95",
)

#let paired-interval-method = "scene_clustered_percentile_bootstrap_95"
#let recovery-ratio-definition = "ratio_of_paired_scene_mean_differences"
#let endpoint-evidence-facts = (
  "policy.endpoint_gain.oracle_one_step.mean",
  "policy.endpoint_gain.oracle_one_step.ci_low",
  "policy.endpoint_gain.oracle_one_step.ci_high",
  "policy.endpoint_gain.oracle_lookahead.mean",
  "policy.endpoint_gain.oracle_lookahead.ci_low",
  "policy.endpoint_gain.oracle_lookahead.ci_high",
  "policy.endpoint_gain.learned_q.mean",
  "policy.endpoint_gain.learned_q.ci_low",
  "policy.endpoint_gain.learned_q.ci_high",
  "policy.endpoint_gain.interval_method",
  "policy.endpoint_gain.n_scenes",
  "policy.endpoint_gain.cohort_sha256",
)
#let endpoint-evidence-contract = (
  (key: "policy.endpoint_gain.oracle_one_step.mean", aggregation: "paired_scene_endpoint_gain", unit: "fraction", value_kind: "number"),
  (key: "policy.endpoint_gain.oracle_one_step.ci_low", aggregation: "paired_scene_endpoint_gain", unit: "fraction", value_kind: "number"),
  (key: "policy.endpoint_gain.oracle_one_step.ci_high", aggregation: "paired_scene_endpoint_gain", unit: "fraction", value_kind: "number"),
  (key: "policy.endpoint_gain.oracle_lookahead.mean", aggregation: "paired_scene_endpoint_gain", unit: "fraction", value_kind: "number"),
  (key: "policy.endpoint_gain.oracle_lookahead.ci_low", aggregation: "paired_scene_endpoint_gain", unit: "fraction", value_kind: "number"),
  (key: "policy.endpoint_gain.oracle_lookahead.ci_high", aggregation: "paired_scene_endpoint_gain", unit: "fraction", value_kind: "number"),
  (key: "policy.endpoint_gain.learned_q.mean", aggregation: "paired_scene_endpoint_gain", unit: "fraction", value_kind: "number"),
  (key: "policy.endpoint_gain.learned_q.ci_low", aggregation: "paired_scene_endpoint_gain", unit: "fraction", value_kind: "number"),
  (key: "policy.endpoint_gain.learned_q.ci_high", aggregation: "paired_scene_endpoint_gain", unit: "fraction", value_kind: "number"),
  (key: "policy.endpoint_gain.interval_method", aggregation: "analysis_identity", unit: "identity", value_kind: "string"),
  (key: "policy.endpoint_gain.n_scenes", aggregation: "count", unit: "count", value_kind: "integer"),
  (key: "policy.endpoint_gain.cohort_sha256", aggregation: "cohort_binding_sha256", unit: "sha256", value_kind: "string"),
)
#let headroom-evidence-facts = (
  "policy.paired_scene_endpoint.effect",
  "policy.paired_scene_endpoint.ci_low",
  "policy.paired_scene_endpoint.ci_high",
  "policy.paired_scene_endpoint.interval_method",
  "policy.paired_scene_endpoint.n_scenes",
  "policy.paired_scene_endpoint.cohort_sha256",
  "headroom_gate.passed",
)
#let headroom-evidence-contract = (
  (key: "policy.paired_scene_endpoint.effect", aggregation: "paired_scene_mean_difference", unit: "fraction", value_kind: "number"),
  (key: "policy.paired_scene_endpoint.ci_low", aggregation: "paired_scene_mean_difference", unit: "fraction", value_kind: "number"),
  (key: "policy.paired_scene_endpoint.ci_high", aggregation: "paired_scene_mean_difference", unit: "fraction", value_kind: "number"),
  (key: "policy.paired_scene_endpoint.interval_method", aggregation: "analysis_identity", unit: "identity", value_kind: "string"),
  (key: "policy.paired_scene_endpoint.n_scenes", aggregation: "count", unit: "count", value_kind: "integer"),
  (key: "policy.paired_scene_endpoint.cohort_sha256", aggregation: "cohort_binding_sha256", unit: "sha256", value_kind: "string"),
  (key: "headroom_gate.passed", aggregation: "paired_scene_decision", unit: "bool", value_kind: "boolean"),
)
#let recovery-evidence-facts = (
  "policy.q_recovery.fraction",
  "policy.q_recovery.ci_low",
  "policy.q_recovery.ci_high",
  "policy.q_recovery.ratio_definition",
  "policy.q_recovery.interval_method",
  "policy.q_recovery.n_scenes",
  "policy.q_recovery.cohort_sha256",
  "policy.q_recovery.passed",
)
#let recovery-evidence-contract = (
  (key: "policy.q_recovery.fraction", aggregation: "paired_scene_ratio_of_mean_differences", unit: "fraction", value_kind: "number"),
  (key: "policy.q_recovery.ci_low", aggregation: "paired_scene_ratio_of_mean_differences", unit: "fraction", value_kind: "number"),
  (key: "policy.q_recovery.ci_high", aggregation: "paired_scene_ratio_of_mean_differences", unit: "fraction", value_kind: "number"),
  (key: "policy.q_recovery.ratio_definition", aggregation: "analysis_identity", unit: "identity", value_kind: "string"),
  (key: "policy.q_recovery.interval_method", aggregation: "analysis_identity", unit: "identity", value_kind: "string"),
  (key: "policy.q_recovery.n_scenes", aggregation: "count", unit: "count", value_kind: "integer"),
  (key: "policy.q_recovery.cohort_sha256", aggregation: "cohort_binding_sha256", unit: "sha256", value_kind: "string"),
  (key: "policy.q_recovery.passed", aggregation: "paired_scene_decision", unit: "bool", value_kind: "boolean"),
)

#let status-report-tables = ("facts", "runtime_storage", "failures", "sidecars")

#let default-thesis-report-path = "/typst/thesis/data/report-bundle-fixture.json"

#let thesis-report-settings() = {
  let mode = sys.inputs.at("aria-thesis-mode", default: "development")
  assert(mode in ("development", "submission"), message: "invalid aria-thesis-mode")

  let explicit-path = sys.inputs.at("aria-thesis-data", default: none)
  let evidence-status = sys.inputs.at("aria-thesis-evidence-status", default: "pilot")
  if mode == "submission" {
    assert(explicit-path != none, message: "submission mode requires explicit aria-thesis-data")
    assert(
      evidence-status == "confirmatory",
      message: "submission mode requires aria-thesis-evidence-status=confirmatory",
    )
  }

  (
    mode: mode,
    path: if explicit-path == none { default-thesis-report-path } else { explicit-path },
    evidence-status: evidence-status,
    required-role: if mode == "submission" { "evidence" } else { none },
  )
}

#let load-thesis-report(path, evidence-status: "pilot", required-role: none) = {
  assert(evidence-status in ("pilot", "confirmatory"), message: "invalid thesis evidence status")
  let report = json(path)
  assert(report.at("schema_version", default: none) == report-schema-version, message: "unsupported thesis report schema")
  let bundle-role = report.at("bundle_role", default: none)
  assert(bundle-role in ("fixture", "evidence"), message: "invalid or missing thesis report bundle_role")
  if required-role != none {
    assert(bundle-role == required-role, message: "thesis report bundle_role does not satisfy publication gate")
  }
  let tables = report.at("tables", default: none)
  assert(type(tables) == dictionary, message: "thesis report tables must be a dictionary")

  for (name, required-columns) in required-report-columns {
    let table-data = tables.at(name, default: none)
    assert(type(table-data) == dictionary, message: "missing thesis report table: " + name)
    let columns = table-data.at("columns", default: ())
    assert(type(columns) == array, message: "invalid columns for thesis report table: " + name)
    assert(required-columns.all(column => column in columns), message: "missing required columns in thesis report table: " + name)
    assert(type(table-data.at("rows", default: none)) == array, message: "invalid rows for thesis report table: " + name)
  }

  let fact-rows = tables.facts.rows
  for key in required-report-facts {
    assert(fact-rows.any(row => row.at("key", default: none) == key), message: "missing required thesis report fact: " + key)
  }
  for name in status-report-tables {
    assert(
      tables.at(name).rows.all(row => row.at("status", default: none) == evidence-status),
      message: "thesis report status does not match aria-thesis-evidence-status: " + name,
    )
  }
  report
}

#let report-stores-have-facts(report, keys, denominators: false) = {
  report.tables.stores.rows.len() > 0 and report.tables.stores.rows.all(store => {
    keys.all(key => {
      let matches = report.tables.facts.rows.filter(
        row => row.store_id == store.store_id and row.key == key,
      )
      matches.len() == 1 and matches.first().value != none and (
        not denominators or (
          matches.first().n != none and matches.first().n > 0
        )
      )
    })
  })
}

#let report-stores-have-boolean-fact(report, key) = {
  report-stores-have-facts(report, (key,)) and report.tables.stores.rows.all(store => {
    let matches = report.tables.facts.rows.filter(
      row => row.store_id == store.store_id and row.key == key,
    )
    type(matches.first().value) == bool
  })
}

#let report-stores-decision-passed(report, key) = {
  report-stores-have-boolean-fact(report, key) and report.tables.stores.rows.all(store => {
    let matches = report.tables.facts.rows.filter(
      row => row.store_id == store.store_id and row.key == key,
    )
    matches.first().value == true
  })
}

#let report-store-facts-have-provenance(
  report,
  store-id,
  keys,
  required-fragment: none,
) = {
  keys.all(key => {
    let matches = report.tables.facts.rows.filter(
      row => row.store_id == store-id and row.key == key,
    )
    matches.len() == 1 and {
      let source = matches.first().source
      type(source) == str and source.len() > 0 and (
        required-fragment == none or source.contains(required-fragment)
      )
    }
  })
}

#let report-store-facts-share-value(report, store-id, keys) = {
  let rows = keys.map(key => {
    let matches = report.tables.facts.rows.filter(
      row => row.store_id == store-id and row.key == key,
    )
    if matches.len() == 1 { matches.first() } else { none }
  })
  rows.all(row => row != none and row.value != none) and rows.all(
    row => row.value == rows.first().value,
  )
}

#let report-store-facts-share-source(report, store-id, keys) = {
  let rows = keys.map(key => {
    let matches = report.tables.facts.rows.filter(
      row => row.store_id == store-id and row.key == key,
    )
    if matches.len() == 1 { matches.first() } else { none }
  })
  rows.all(
    row => row != none and type(row.source) == str and row.source.len() > 0,
  ) and rows.all(row => row.source == rows.first().source)
}

#let evidence-gate-state(
  evidence-available,
  decision-passed,
  prerequisites-passed: true,
) = {
  let gate-passed = evidence-available and decision-passed
  (
    evidence_available: evidence-available,
    gate_passed: gate-passed,
    claim_admissible: prerequisites-passed and gate-passed,
  )
}

#let conditional-ratio-gate-state(
  raw-evidence-available,
  denominator-admissible,
  ratio-contract-available,
  decision-passed,
  remaining-prerequisites-passed: true,
) = {
  let ratio-evidence-available = raw-evidence-available and denominator-admissible and ratio-contract-available
  let state = evidence-gate-state(
    ratio-evidence-available,
    decision-passed,
    prerequisites-passed: remaining-prerequisites-passed,
  )
  (
    raw_evidence_available: raw-evidence-available,
    ratio_evidence_available: ratio-evidence-available,
    state: state,
  )
}

#let report-fact(report, key) = {
  let matches = report.tables.facts.rows.filter(row => row.key == key)
  assert(matches.len() == 1, message: "expected one thesis report fact: " + key)
  matches.first()
}

#let report-store-fact(report, store-id, key) = {
  let matches = report.tables.facts.rows.filter(
    row => row.store_id == store-id and row.key == key,
  )
  assert(
    matches.len() == 1,
    message: "expected one thesis report fact for store and key: " + store-id + " / " + key,
  )
  matches.first()
}

#let report-value-matches-kind(value, value-kind) = {
  if value-kind == "number" {
    type(value) == int or type(value) == float
  } else if value-kind == "integer" {
    type(value) == int
  } else if value-kind == "string" {
    type(value) == str
  } else if value-kind == "boolean" {
    type(value) == bool
  } else {
    false
  }
}

#let report-store-facts-match-contract(report, store-id, contracts, expected-n) = {
  contracts.all(contract => {
    let matches = report.tables.facts.rows.filter(
      row => row.store_id == store-id and row.key == contract.key,
    )
    matches.len() == 1 and {
      let row = matches.first()
      let expected-unit = contract.at("unit", default: none)
      let expected-kind = contract.at("value_kind", default: none)
      row.value != none and row.n == expected-n and row.aggregation == contract.aggregation and (
        expected-unit == none or row.at("unit", default: none) == expected-unit
      ) and (
        expected-kind == none or report-value-matches-kind(row.value, expected-kind)
      )
    }
  })
}

#let report-store-fact-values-match(report, store-id, expected-values) = {
  expected-values.all(expected => {
    let matches = report.tables.facts.rows.filter(
      row => row.store_id == store-id and row.key == expected.key,
    )
    matches.len() == 1 and matches.first().value == expected.value
  })
}

#let report-store-interval-is-ordered(report, store-id, low-key, high-key) = {
  let low-matches = report.tables.facts.rows.filter(
    row => row.store_id == store-id and row.key == low-key,
  )
  let high-matches = report.tables.facts.rows.filter(
    row => row.store_id == store-id and row.key == high-key,
  )
  low-matches.len() == 1 and high-matches.len() == 1 and {
    let low = low-matches.first().value
    let high = high-matches.first().value
    report-value-matches-kind(low, "number") and report-value-matches-kind(
      high,
      "number",
    ) and low <= high
  }
}

#let report-store-fact-is-sha256(report, store-id, key) = {
  let matches = report.tables.facts.rows.filter(
    row => row.store_id == store-id and row.key == key,
  )
  matches.len() == 1 and {
    let value = matches.first().value
    type(value) == str and value.match(regex("^[0-9a-f]{64}$")) != none
  }
}

#let report-store-analysis-family-valid(
  report,
  store-id,
  facts,
  contract,
  expected-n,
  expected-values: (),
  interval-pairs: (),
  digest-keys: (),
  required-source-fragment: none,
) = {
  report-store-facts-match-contract(
    report,
    store-id,
    contract,
    expected-n,
  ) and report-store-fact-values-match(
    report,
    store-id,
    expected-values,
  ) and interval-pairs.all(pair => report-store-interval-is-ordered(
    report,
    store-id,
    pair.low,
    pair.high,
  )) and digest-keys.all(key => report-store-fact-is-sha256(
    report,
    store-id,
    key,
  )) and report-store-facts-have-provenance(
    report,
    store-id,
    facts,
    required-fragment: required-source-fragment,
  ) and report-store-facts-share-source(report, store-id, facts)
}

#let report-store-endpoint-evidence-valid(report, store-id, expected-n) = {
  report-store-analysis-family-valid(
    report,
    store-id,
    endpoint-evidence-facts,
    endpoint-evidence-contract,
    expected-n,
    expected-values: ((key: "policy.endpoint_gain.interval_method", value: paired-interval-method),),
    interval-pairs: (
      (low: "policy.endpoint_gain.oracle_one_step.ci_low", high: "policy.endpoint_gain.oracle_one_step.ci_high"),
      (low: "policy.endpoint_gain.oracle_lookahead.ci_low", high: "policy.endpoint_gain.oracle_lookahead.ci_high"),
      (low: "policy.endpoint_gain.learned_q.ci_low", high: "policy.endpoint_gain.learned_q.ci_high"),
    ),
    digest-keys: ("policy.endpoint_gain.cohort_sha256",),
    required-source-fragment: "|sidecar:",
  )
}

#let report-store-headroom-evidence-valid(report, store-id, expected-n) = {
  report-store-analysis-family-valid(
    report,
    store-id,
    headroom-evidence-facts,
    headroom-evidence-contract,
    expected-n,
    expected-values: ((key: "policy.paired_scene_endpoint.interval_method", value: paired-interval-method),),
    interval-pairs: ((low: "policy.paired_scene_endpoint.ci_low", high: "policy.paired_scene_endpoint.ci_high"),),
    digest-keys: ("policy.paired_scene_endpoint.cohort_sha256",),
    required-source-fragment: "|sidecar:",
  )
}

#let report-store-recovery-evidence-valid(report, store-id, expected-n) = {
  report-store-analysis-family-valid(
    report,
    store-id,
    recovery-evidence-facts,
    recovery-evidence-contract,
    expected-n,
    expected-values: (
      (key: "policy.q_recovery.ratio_definition", value: recovery-ratio-definition),
      (key: "policy.q_recovery.interval_method", value: paired-interval-method),
    ),
    interval-pairs: ((low: "policy.q_recovery.ci_low", high: "policy.q_recovery.ci_high"),),
    digest-keys: ("policy.q_recovery.cohort_sha256",),
    required-source-fragment: "|sidecar:",
  )
}

#let short-store-label(report, store-id) = {
  let stores = report.tables.stores.rows
  let matches = stores.filter(store => store.store_id == store-id)
  assert(matches.len() == 1, message: "store_id must map to exactly one report store")
  let index = stores.position(store => store.store_id == store-id)
  assert(index != none, message: "store_id has no stable report position")
  let name = matches.first().name
  let profile = if name.contains("realistic") {
    "realistic"
  } else if name.contains("diverse") {
    "diverse"
  } else {
    "store"
  }
  profile + " S" + str(index + 1)
}

#let digest-prefix(value, length: 12) = {
  assert(type(value) == str, message: "manifest digest must be a string")
  if value.len() <= length { value } else { value.slice(0, length) + "…" }
}

#let format-report-value(value, digits: none, unit: none) = {
  let rendered = if value == none {
    [—]
  } else if type(value) == bool {
    if value { [true] } else { [false] }
  } else if digits != none and type(value) in (float, int) {
    str(calc.round(value, digits: digits))
  } else {
    str(value)
  }
  if unit == none or value == none { rendered } else { [#rendered #unit] }
}

// Bundle v2 is generated by aria_nbv.reporting from an immutable Python
// snapshot. Typst validates and selects frozen results; it performs no Python
// execution, network acquisition, aggregation, or figure construction.
#let load-scientific-report(path, evidence-status: "pilot", require-publication: false) = {
  assert(evidence-status in ("pilot", "confirmatory"), message: "invalid scientific report evidence status")
  let report = json(path)
  assert(
    report.at("schema_version", default: none) == scientific-report-schema-version,
    message: "unsupported scientific report schema",
  )
  assert(
    report.at("evidence_status", default: none) == evidence-status,
    message: "scientific report evidence status does not match the requested status",
  )
  if require-publication {
    assert(evidence-status == "confirmatory", message: "publication requires confirmatory scientific evidence")
    assert(report.at("snapshot_sha256", default: "").len() == 64, message: "publication requires snapshot identity")
    assert(report.at("config_sha256", default: "").len() == 64, message: "publication requires config identity")
    assert(report.at("notation_sha256", default: "").len() == 64, message: "publication requires notation identity")
  }
  assert(type(report.at("sources", default: none)) == array, message: "scientific report sources must be an array")
  assert(type(report.at("quantities", default: none)) == array, message: "scientific report quantities must be an array")
  assert(type(report.at("tables", default: none)) == array, message: "scientific report tables must be an array")
  assert(type(report.at("figures", default: none)) == array, message: "scientific report figures must be an array")
  if require-publication {
    assert(report.sources.len() > 0, message: "publication requires at least one scientific evidence source")
  }
  let source-ids = report.sources.map(source => source.at("id", default: none))
  assert(source-ids.all(id => type(id) == str and id != ""), message: "scientific report source IDs must be non-empty")
  assert(source-ids.dedup().len() == source-ids.len(), message: "scientific report source IDs must be unique")
  for source in report.sources {
    assert(source.at("sha256", default: "").len() == 64, message: "scientific report source requires identity digest")
    let provenance = source.at("provenance", default: none)
    assert(type(provenance) == array, message: "scientific report source provenance must be an array")
    if require-publication {
      assert(provenance.len() > 0, message: "publication requires source provenance")
    }
    if require-publication and source.at("kind", default: none) == "wandb" {
      let history-mode = provenance.find(pair => pair.len() == 2 and pair.first() == "history_mode")
      assert(history-mode != none and history-mode.last() == "complete", message: "publication requires complete W&B history")
      let history-complete = provenance.find(pair => pair.len() == 2 and pair.first() == "history_complete")
      assert(history-complete != none and history-complete.last() == true, message: "publication requires exhaustive W&B rows")
    }
  }
  let results = report.quantities + report.tables + report.figures
  if require-publication {
    assert(results.len() > 0, message: "publication requires at least one scientific report result")
  }
  let result-ids = results.map(result => result.at("id", default: none))
  assert(result-ids.all(id => type(id) == str and id != ""), message: "scientific report result IDs must be non-empty")
  assert(result-ids.dedup().len() == result-ids.len(), message: "scientific report result IDs must be unique")
  for result in results {
    if require-publication {
      assert(result.at("source_ids", default: ()).len() > 0, message: "publication results require source provenance")
    }
    assert(
      result.at("source_ids", default: ()).all(id => id in source-ids),
      message: "scientific report result references unknown source",
    )
  }
  report.insert("_bundle_dir", path.split("/").slice(0, -1).join("/"))
  report
}

#let _report-result(results, id, kind) = {
  let matches = results.filter(result => result.at("id", default: none) == id)
  assert(matches.len() == 1, message: "expected exactly one scientific report " + kind + ": " + id)
  matches.first()
}

#let report-value(report, id) = _report-result(report.quantities, id, "quantity")
#let report-table(report, id) = _report-result(report.tables, id, "table")
#let report-figure(report, id) = _report-result(report.figures, id, "figure")
#let report-figure-path(report, id) = {
  let static-path = report-figure(report, id).static_path
  if static-path.starts-with("/") { static-path } else { report._bundle_dir + "/" + static-path }
}
