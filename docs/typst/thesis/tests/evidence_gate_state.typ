#import "../experiment_data.typ": evidence-gate-state, report-store-count-binds-facts, report-stores-decision-passed, report-stores-facts-share-sha256, report-stores-have-facts, report-stores-have-boolean-fact

#let report = (
  tables: (
    stores: (rows: (
      (store_id: "store-a"),
      (store_id: "store-b"),
    )),
    facts: (rows: (
      (store_id: "store-a", key: "gate.passed", value: true, n: 2),
      (store_id: "store-b", key: "gate.passed", value: false, n: 2),
    )),
  ),
)

#assert(
  report-stores-have-facts(report, ("gate.passed",), denominators: true),
  message: "a present false decision remains available evidence",
)
#assert(
  not report-stores-decision-passed(report, "gate.passed"),
  message: "present false must not pass the gate",
)

#let malformed-report = (
  tables: (
    stores: (rows: ((store_id: "store-a"),)),
    facts: (rows: (
      (store_id: "store-a", key: "gate.string", value: "false", n: 1),
      (store_id: "store-a", key: "gate.integer", value: 1, n: 1),
    )),
  ),
)
#assert(not report-stores-have-boolean-fact(malformed-report, "gate.string"))
#assert(not report-stores-have-boolean-fact(malformed-report, "gate.integer"))
#assert(not report-stores-decision-passed(malformed-report, "gate.string"))
#assert(not report-stores-decision-passed(malformed-report, "gate.integer"))

#let bundle-a = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
#let bundle-b = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
#let learned-lineage-keys = (
  "q1.model.bundle_manifest_sha256",
  "q2.exact.bundle_manifest_sha256",
  "policy.endpoint_gain.learned_q.bundle_manifest_sha256",
)
#let learned-lineage-report(
  store-a-values: (bundle-a, bundle-a, bundle-a),
  store-b-values: (bundle-a, bundle-a, bundle-a),
) = (
  tables: (
    stores: (rows: (
      (store_id: "store-a"),
      (store_id: "store-b"),
    )),
    facts: (rows: learned-lineage-keys.zip(store-a-values).map(((key, value)) => (
        store_id: "store-a",
        key: key,
        value: value,
      )) + learned-lineage-keys.zip(store-b-values).map(((key, value)) => (
        store_id: "store-b",
        key: key,
        value: value,
      ))),
  ),
)
#assert(report-stores-facts-share-sha256(
  learned-lineage-report(),
  learned-lineage-keys,
))
#assert(report-stores-facts-share-sha256(
  learned-lineage-report(
    store-a-values: (bundle-b, bundle-b, bundle-b),
    store-b-values: (bundle-b, bundle-b, bundle-b),
  ),
  learned-lineage-keys,
))
#assert(not report-stores-facts-share-sha256(
  learned-lineage-report(store-a-values: (bundle-a, bundle-b, bundle-a)),
  learned-lineage-keys,
))
#assert(not report-stores-facts-share-sha256(
  learned-lineage-report(store-b-values: (bundle-b, bundle-b, bundle-b)),
  learned-lineage-keys,
))
#assert(not report-stores-facts-share-sha256(
  learned-lineage-report(store-a-values: (bundle-a, "invalid", bundle-a)),
  learned-lineage-keys,
))
#let complete-lineage-report = learned-lineage-report()
#let missing-lineage-report = (
  tables: complete-lineage-report.tables + (
    facts: (rows: complete-lineage-report.tables.facts.rows.filter(
      row => not (row.store_id == "store-b" and row.key == learned-lineage-keys.last()),
    )),
  ),
)
#assert(not report-stores-facts-share-sha256(
  missing-lineage-report,
  learned-lineage-keys,
))
#let duplicate-lineage-report = (
  tables: complete-lineage-report.tables + (
    facts: (rows: complete-lineage-report.tables.facts.rows + (
      complete-lineage-report.tables.facts.rows.first(),
    )),
  ),
)
#assert(not report-stores-facts-share-sha256(
  duplicate-lineage-report,
  learned-lineage-keys,
))

#let count-binding-report(count-value: 5, row-n: 5) = (
  tables: (
    facts: (rows: (
      (store_id: "store-a", key: "gate.metric", value: 0.2, n: row-n),
      (store_id: "store-a", key: "gate.n_units", value: count-value, n: row-n),
      (store_id: "store-a", key: "gate.passed", value: true, n: row-n),
    )),
  ),
)
#let bound-keys = ("gate.metric", "gate.n_units", "gate.passed")
#assert(report-store-count-binds-facts(
  count-binding-report(),
  "store-a",
  "gate.n_units",
  bound-keys,
))
#assert(not report-store-count-binds-facts(
  count-binding-report(count-value: 0),
  "store-a",
  "gate.n_units",
  bound-keys,
))
#assert(not report-store-count-binds-facts(
  count-binding-report(count-value: "5"),
  "store-a",
  "gate.n_units",
  bound-keys,
))
#assert(not report-store-count-binds-facts(
  count-binding-report(row-n: 4),
  "store-a",
  "gate.n_units",
  bound-keys,
))

#let failed = evidence-gate-state(true, false)
#assert(failed.evidence_available)
#assert(not failed.gate_passed)
#assert(not failed.claim_admissible)

#let blocked = evidence-gate-state(
  true,
  true,
  prerequisites-passed: false,
)
#assert(blocked.evidence_available)
#assert(blocked.gate_passed)
#assert(not blocked.claim_admissible)

#let admitted = evidence-gate-state(true, true)
#assert(admitted.evidence_available)
#assert(admitted.gate_passed)
#assert(admitted.claim_admissible)

Evidence availability, gate passage, and claim admissibility remain distinct.
