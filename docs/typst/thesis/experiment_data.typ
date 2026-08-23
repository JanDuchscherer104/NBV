#let report-schema-version = "aria-nbv-thesis-report-v2"

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
  empirical_results: ("result_id", "store_id", "experimental_unit", "denominator_name", "denominator_value", "data_identity", "split_identity", "estimand", "estimate", "unit", "aggregation", "uncertainty_type", "uncertainty_lower", "uncertainty_upper", "uncertainty_inapplicable_reason", "variability_source", "comparison_family", "outcome", "status", "actor_visible_inputs_json", "oracle_only_inputs_json", "source_revision", "environment", "command", "artifact_path", "artifact_sha256", "wall_time_s", "gpu_hours", "peak_gpu_memory_bytes", "storage_bytes", "provenance", "sidecar_id", "reason"),
)

#let empirical-result-columns = ("result_id", "store_id", "experimental_unit", "denominator_name", "denominator_value", "data_identity", "split_identity", "estimand", "estimate", "unit", "aggregation", "uncertainty_type", "uncertainty_lower", "uncertainty_upper", "uncertainty_inapplicable_reason", "variability_source", "comparison_family", "outcome", "status", "actor_visible_inputs_json", "oracle_only_inputs_json", "source_revision", "environment", "command", "artifact_path", "artifact_sha256", "wall_time_s", "gpu_hours", "peak_gpu_memory_bytes", "storage_bytes", "provenance", "sidecar_id", "reason")

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

#let status-report-tables = ("facts", "runtime_storage", "failures", "sidecars", "empirical_results")

#let default-thesis-report-path = "/typst/thesis/data/report-bundle-fixture.json"

#let thesis-report-settings() = {
  let mode = sys.inputs.at("aria-thesis-mode", default: "development")
  assert(mode in ("development", "submission"), message: "invalid aria-thesis-mode")

  let explicit-path = sys.inputs.at("aria-thesis-data", default: none)
  let evidence-status = sys.inputs.at("aria-thesis-evidence-status", default: "pilot")
  if mode == "submission" {
    assert(type(explicit-path) == str and explicit-path.trim().len() > 0, message: "submission mode requires explicit aria-thesis-data")
    assert(
      evidence-status == "confirmatory",
      message: "submission mode requires aria-thesis-evidence-status=confirmatory",
    )
    let code-ref = sys.inputs.at("aria-code-ref", default: none)
    assert(
      type(code-ref) == str and code-ref.matches(regex("^[0-9a-f]{40}$")).len() == 1,
      message: "submission mode requires a lower-hex 40-character aria-code-ref",
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
  assert(evidence-status in ("exploratory", "pilot", "confirmatory"), message: "invalid thesis evidence status")
  let report = json(path)
  assert(report.at("schema_version", default: none) == report-schema-version, message: "unsupported thesis report schema")
  let bundle-role = report.at("bundle_role", default: none)
  assert(bundle-role in ("fixture", "evidence"), message: "invalid or missing thesis report bundle_role")
  if required-role != none {
    assert(bundle-role == required-role, message: "thesis report bundle_role does not satisfy publication gate")
    assert(report.at("fixture_notice", default: none) == none, message: "submission evidence bundle must not carry fixture_notice")
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
  assert(
    tables.empirical_results.columns == empirical-result-columns,
    message: "empirical_results columns must match the exact report contract",
  )

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
  let empirical = tables.empirical_results.rows
  if required-role == "evidence" {
    assert(empirical.len() > 0, message: "submission evidence bundle requires nonempty empirical_results")
    assert(empirical.all(row => row.status == "confirmatory"), message: "submission evidence results must be confirmatory")
    let code-ref = sys.inputs.at("aria-code-ref", default: none)
    assert(report.at("source_revision", default: none) == code-ref, message: "report source_revision does not match aria-code-ref")
    assert(empirical.all(row => row.source_revision == code-ref), message: "empirical result source_revision does not match aria-code-ref")
  }
  report
}

#let report-fact(report, key) = {
  let matches = report.tables.facts.rows.filter(row => row.key == key)
  assert(matches.len() == 1, message: "expected one thesis report fact: " + key)
  matches.first()
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
