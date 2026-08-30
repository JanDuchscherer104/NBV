#import "../experiment_data.typ": evidence-gate-state, report-stores-decision-passed, report-stores-have-facts

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
