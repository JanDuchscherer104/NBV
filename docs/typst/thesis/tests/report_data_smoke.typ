#import "../experiment_data.typ": load-thesis-report, report-fact, report-store-fact, report-store-gate-passed, report-store-facts-match-contract, report-store-sha256-facts-resolve, format-report-value

#let data-path = sys.inputs.at(
  "aria-thesis-data",
  default: "/typst/thesis/data/report-bundle-fixture.json",
)
#let evidence-status = sys.inputs.at("aria-thesis-evidence-status", default: "pilot")
#let required-role = sys.inputs.at("aria-thesis-required-role", default: none)
#let report = load-thesis-report(
  data-path,
  evidence-status: evidence-status,
  required-role: required-role,
)
#assert(report.bundle_role in ("fixture", "evidence"), message: "bundle_role must be typed and validated")
#let missing-value = report-fact(report, "selected.path_length_m.p5").value
#let store-missing-value = report-store-fact(
  report,
  "synthetic-nonscientific-fixture",
  "selected.path_length_m.p5",
).value
#let parameters = report.tables.parameters.rows

#assert(missing-value == none, message: "fixture must retain JSON null")
#assert(store-missing-value == none, message: "store-qualified lookup must retain JSON null")
#assert(parameters.any(row => row.value_type == "bool" and row.value_bool == true), message: "fixture must retain a boolean parameter")
#assert(parameters.any(row => row.value_type == "int" and row.value_int == 2), message: "fixture must retain an integer parameter")
#assert(parameters.any(row => row.value_type == "float" and row.value_float == 1.25), message: "fixture must retain a floating-point parameter")
#assert(parameters.any(row => row.value_type == "str" and row.value_text == "fixture-text"), message: "fixture must retain a text parameter")
#assert(parameters.any(row => row.is_missing and row.value_text == none), message: "fixture must retain a missing parameter as JSON null")
#let support-contract = ((key: "candidate-support.actor-valid-fraction", aggregation: "state_then_scene_macro"),)
#assert(
  report-store-facts-match-contract(report, "synthetic-nonscientific-fixture", support-contract, 2),
  message: "matching aggregation and scene denominator must pass",
)
#assert(
  not report-store-facts-match-contract(report, "synthetic-nonscientific-fixture", support-contract, 12),
  message: "candidate-row denominator must not satisfy the scene-level contract",
)
#let wrong-aggregation = ((key: "candidate-support.actor-valid-fraction", aggregation: "candidate_row_mean"),)
#assert(
  not report-store-facts-match-contract(report, "synthetic-nonscientific-fixture", wrong-aggregation, 2),
  message: "incorrect aggregation identity must not satisfy the scene-level contract",
)
#let inferential-contract-report = (
  tables: (
    facts: (
      rows: (
        (store_id: "store-a", key: "q1.protocol.target_matching.failure_rate", value: 0.1, n: 12, aggregation: "target_match_attempt_rate"),
        (store_id: "store-a", key: "q1.calibration.mae", value: 0.02, n: 5, aggregation: "scene_clustered_calibration_mae"),
        (store_id: "store-a", key: "q2.exact.mae", value: 0.03, n: 7, aggregation: "all_units_v1"),
        (store_id: "store-a", key: "policy.q_recovery.fraction", value: 0.4, n: 4, aggregation: "paired_scene_gap_closure"),
      ),
    ),
  ),
)
#let actor-matching-contract = ((key: "q1.protocol.target_matching.failure_rate", aggregation: "target_match_attempt_rate"),)
#let q1-calibration-contract = ((key: "q1.calibration.mae", aggregation: "scene_clustered_calibration_mae"),)
#let q2-contract = ((key: "q2.exact.mae", aggregation: "all_units_v1"),)
#let recovery-contract = ((key: "policy.q_recovery.fraction", aggregation: "paired_scene_gap_closure"),)
#assert(
  report-store-facts-match-contract(inferential-contract-report, "store-a", actor-matching-contract, 12),
  message: "target-matching evidence must bind its attempted-match denominator",
)
#assert(
  not report-store-facts-match-contract(inferential-contract-report, "store-a", actor-matching-contract, 5),
  message: "a wrong target-matching denominator must fail closed",
)
#assert(
  report-store-facts-match-contract(inferential-contract-report, "store-a", q1-calibration-contract, 5),
  message: "Q1 calibration evidence must bind its scene-clustered aggregation",
)
#assert(
  not report-store-facts-match-contract(inferential-contract-report, "store-a", ((key: "q1.calibration.mae", aggregation: "state_then_scene_macro"),), 5),
  message: "a wrong Q1 calibration aggregation must fail closed",
)
#assert(
  report-store-facts-match-contract(inferential-contract-report, "store-a", q2-contract, 7),
  message: "exact-Q2 evidence must bind its independent-unit contract",
)
#assert(
  not report-store-facts-match-contract(inferential-contract-report, "store-a", q2-contract, 0),
  message: "a zero exact-Q2 denominator must fail closed",
)
#assert(
  report-store-facts-match-contract(inferential-contract-report, "store-a", recovery-contract, 4),
  message: "endpoint recovery must bind its paired-scene contract",
)
#assert(
  not report-store-facts-match-contract(inferential-contract-report, "store-a", ((key: "policy.q_recovery.fraction", aggregation: "candidate_row_mean"),), 4),
  message: "a wrong endpoint-recovery aggregation must fail closed",
)
#let identity-report = (
  tables: (
    facts: (rows: (
      (store_id: "store-a", key: "q2.exact.receipt_sha256", value: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", source: "receipt.json|sidecar:receipt-a"),
      (store_id: "store-a", key: "q2.exact.nonhex_sha256", value: "zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz", source: "receipt.json|sidecar:receipt-a"),
      (store_id: "store-a", key: "q2.exact.unresolved_sha256", value: "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb", source: "missing.json|sidecar:missing"),
    )),
    sidecars: (rows: (
      (sidecar_id: "receipt-a", path: "receipt.json", sha256: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"),
    )),
  ),
)
#assert(
  report-store-sha256-facts-resolve(identity-report, "store-a", ("q2.exact.receipt_sha256",)),
  message: "a canonical digest must resolve to its declared sidecar",
)
#assert(
  not report-store-sha256-facts-resolve(identity-report, "store-a", ("q2.exact.nonhex_sha256",)),
  message: "a non-hexadecimal 64-character identity must fail closed",
)
#assert(
  not report-store-sha256-facts-resolve(identity-report, "store-a", ("q2.exact.unresolved_sha256",)),
  message: "an unreferenced digest must fail closed",
)
#let gate-report = (
  tables: (
    facts: (
      rows: (
        (store_id: "store-a", key: "gate.false", value: false),
        (store_id: "store-a", key: "gate.true", value: true),
      ),
    ),
  ),
)
#assert(
  not report-store-gate-passed(gate-report, "store-a", "gate.false"),
  message: "an explicit false decision must fail a gate rather than count as available",
)
#assert(
  report-store-gate-passed(gate-report, "store-a", "gate.true"),
  message: "only an explicit true decision may pass a gate",
)
Missing: #format-report-value(missing-value)
