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
