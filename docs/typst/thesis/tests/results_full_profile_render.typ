// Layout-only fixture: synthetic values exercise every confirmatory result row.
// It is not a thesis evidence bundle and must never be cited as scientific data.
#import "../experiment_data.typ": endpoint-evidence-contract, headroom-evidence-contract, recovery-evidence-contract, population-evidence-contract, measurement-evidence-contract, candidate-support-evidence-contract, q1-evidence-contract, q2-evidence-contract, report-value-matches-kind
#import "../sections/06-results.typ": all-result-summary-families, result-summary-rows-for, result-summary-table

#set page(paper: "a4", margin: 25mm)
#set text(font: "New Computer Modern", size: 10pt)

#let store-id = "synthetic-layout-only"
#let evidence-fact-contract = (
  population-evidence-contract,
  measurement-evidence-contract,
  candidate-support-evidence-contract,
  endpoint-evidence-contract,
  headroom-evidence-contract,
  q1-evidence-contract,
  q2-evidence-contract,
  recovery-evidence-contract,
).flatten()
// Resource rows are presentation-only: experiment_data.typ does not yet define
// a canonical evidence contract for them, so keep their exact writer units local.
#let resource-fact-contract = (
  (key: "runtime.wall_time_s", unit: "s", value_kind: "number"),
  (key: "runtime.peak_gpu_bytes", unit: "byte", value_kind: "integer"),
  (key: "storage.total_bytes", unit: "byte", value_kind: "integer"),
)
#let fact-contract = evidence-fact-contract + resource-fact-contract
#let contract-for(key) = {
  let matches = fact-contract.filter(contract => contract.key == key)
  assert(matches.len() == 1, message: "expected one result fact contract: " + key)
  matches.first()
}
#let fixture-value(contract) = if contract.value_kind == "boolean" {
  true
} else if contract.value_kind == "integer" {
  24
} else if contract.value_kind == "number" {
  0.125
} else if contract.value_kind == "string" {
  "synthetic-layout-only"
} else {
  assert(false, message: "unsupported result fact value kind: " + contract.value_kind)
}
#let keys = ()
#for family in all-result-summary-families {
  for metric in family.metrics {
    keys.push(metric.key)
    for optional-key in (
      metric.at("low-key", default: none),
      metric.at("high-key", default: none),
      metric.at("denominator-key", default: none),
    ) {
      if optional-key != none { keys.push(optional-key) }
    }
  }
}
#let keys = keys.dedup()
#let facts = keys.map(key => {
  let contract = contract-for(key)
  (
    store_id: store-id,
    key: key,
    value: fixture-value(contract),
    unit: contract.unit,
    n: 24,
  )
})
#assert(facts.all(fact => {
  let contract = contract-for(fact.key)
  fact.unit == contract.unit and report-value-matches-kind(fact.value, contract.value_kind)
}), message: "result fixture facts must match their exact unit and value-kind contracts")
#let report = (
  tables: (
    stores: (rows: ((store_id: store-id, name: "synthetic-layout-only"),)),
    facts: (rows: facts),
  ),
)

= Full-profile results layout fixture

This page set exercises every current result family at final A4 size. Values are
synthetic layout tokens only.

#let bands = (
  (id: "foundations", expected: 17, caption: [Population, measurement, and candidate-support rows]),
  (id: "policy", expected: 14, caption: [Endpoint, headroom, actor-$Q_1$, and recovery rows]),
  (id: "q2", expected: 12, caption: [Exact-$Q_2$ agreement and threshold rows]),
  (id: "resources", expected: 3, caption: [Resource rows]),
)

#for band in bands {
  let families = all-result-summary-families.filter(family => family.band == band.id)
  let metric-count = families.fold(0, (total, family) => total + family.metrics.len())
  assert(metric-count == band.expected, message: "result-summary family size drift: " + band.id)
  let rows = result-summary-rows-for(report, families)
  figure(
    result-summary-table(rows),
    caption: [Layout-only render of #band.caption.],
  )
}
