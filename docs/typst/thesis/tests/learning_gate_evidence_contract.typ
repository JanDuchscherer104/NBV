#import "../experiment_data.typ": repeatability-decision-rule, report-store-population-evidence-valid, report-store-measurement-evidence-valid, report-store-candidate-support-evidence-valid, report-store-q1-evidence-valid, report-store-q2-evidence-valid

#let sidecar-a = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
#let sidecar-b = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
#let digest-a = "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
#let digest-b = "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"
#let source = "analysis/qh-gates.json|sidecar:" + sidecar-a
#let sidecars = (
  (sidecar_id: sidecar-a, path: "qh-gates", name: "qh-gates", sha256: digest-a, format: "json", status: "confirmatory"),
  (sidecar_id: sidecar-b, path: "other", name: "other", sha256: digest-b, format: "json", status: "confirmatory"),
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
#let report(rows, sidecar-rows: sidecars) = (
  tables: (
    stores: (rows: ((store_id: "store-a"),)),
    facts: (rows: rows),
    sidecars: (rows: sidecar-rows),
  ),
)

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
  discrepancy-value: 0.0001,
  tolerance-value: 0.001,
  rule-value: repeatability-decision-rule,
  passed-value: true,
  discrepancy-unit: "fraction",
  discrepancy-aggregation: "repeatability_max_abs_difference",
  decision-aggregation: "repeatability_decision",
  row-n: 3,
  source: source,
  gate-source: source,
) = (
  fact("oracle.metric.repeatability.max_abs_diff", discrepancy-value, discrepancy-unit, row-n, discrepancy-aggregation, source: source),
  fact("oracle.metric.repeatability.tolerance", tolerance-value, "fraction", row-n, "analysis_threshold", source: source),
  fact("oracle.metric.repeatability.rule", rule-value, "identity", row-n, "analysis_identity", source: source),
  fact("oracle.metric.repeatability.n_repeats", repeat-count-value, "count", row-n, "count", source: source),
  fact("oracle.metric.repeatability.passed", passed-value, "bool", row-n, decision-aggregation, source: gate-source),
)

#let support-rows(
  scene-count-value: 5,
  gate-n: 5,
  metric-unit: "fraction",
  metric-value: 0.8,
  metric-aggregation: "state_then_scene_macro",
  source: source,
  gate-source: source,
) = (
  fact("study.population.scenes", scene-count-value, "count", 5, "count", source: source),
  fact("candidate-support.actor-valid-fraction", metric-value, metric-unit, 5, metric-aggregation, source: source),
  fact("candidate-support.valid-support-p05", 2.0, "count", 5, "state_then_scene_p05", source: source),
  fact("candidate-support.configured-family-zero-rate", 0.1, "fraction", 5, "state_then_scene_macro", source: source),
  fact("candidate-support.target-side-balance", 0.5, "fraction", 5, "state_then_scene_macro", source: source),
  fact("candidate-support.circular-orbit-span", 45.0, "deg", 5, "state_then_scene_macro", source: source),
  fact("candidate-support.gate.passed", true, "bool", gate-n, "state_then_scene_decision", source: gate-source),
)

#let q1-rows(
  count-value: 5,
  ranking-value: 0.8,
  ranking-unit: "fraction",
  ranking-aggregation: "state_then_scene_macro",
  calibration-value: 0.1,
  source: source,
  gate-source: source,
) = (
  fact("q1.ranking.pairwise_accuracy", ranking-value, ranking-unit, 5, ranking-aggregation, source: source),
  fact("q1.calibration.mae", calibration-value, "fraction", 5, "state_then_scene_macro", source: source),
  fact("q1.population.n_scenes", count-value, "count", 5, "count", source: source),
  fact("q1.gate.passed", true, "bool", 5, "state_then_scene_decision", source: gate-source),
)

#let q2-rows(
  count-value: 5,
  mae-value: 0.1,
  coverage-value: 0.9,
  coverage-unit: "fraction",
  coverage-aggregation: "independent_unit_fraction",
  source: source,
  gate-source: source,
) = (
  fact("q2.exact.mae", mae-value, "fraction", 5, "independent_unit_macro", source: source),
  fact("q2.exact.coverage", coverage-value, coverage-unit, 5, coverage-aggregation, source: source),
  fact("q2.exact.n_independent_units", count-value, "count", 5, "count", source: source),
  fact("q2.exact.passed", true, "bool", 5, "all_units_v1", source: gate-source),
)

#assert(report-store-candidate-support-evidence-valid(report(support-rows()), "store-a"))
#assert(not report-store-candidate-support-evidence-valid(report(support-rows(scene-count-value: "5")), "store-a"))
#assert(not report-store-candidate-support-evidence-valid(report(support-rows(gate-n: 4)), "store-a"))
#assert(not report-store-candidate-support-evidence-valid(report(support-rows(metric-value: "0.8")), "store-a"))
#assert(not report-store-candidate-support-evidence-valid(report(support-rows(metric-value: 1.1)), "store-a"))
#assert(not report-store-candidate-support-evidence-valid(report(support-rows(metric-unit: "count")), "store-a"))
#assert(not report-store-candidate-support-evidence-valid(report(support-rows(metric-aggregation: "candidate_row_mean")), "store-a"))
#assert(not report-store-candidate-support-evidence-valid(report(support-rows(source: "analysis/unbound.json", gate-source: "analysis/unbound.json")), "store-a"))
#assert(not report-store-candidate-support-evidence-valid(report(support-rows(gate-source: "analysis/other.json|sidecar:" + sidecar-b)), "store-a"))
#assert(not report-store-candidate-support-evidence-valid(report(support-rows(source: "analysis/qh-gates.json|sidecar:", gate-source: "analysis/qh-gates.json|sidecar:")), "store-a"))

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

#assert(report-store-measurement-evidence-valid(report(measurement-rows()), "store-a"))
#assert(report-store-measurement-evidence-valid(report(measurement-rows(discrepancy-value: 0.002, passed-value: false)), "store-a"))
#assert(not report-store-measurement-evidence-valid(report(measurement-rows(discrepancy-value: 0.002, passed-value: true)), "store-a"))
#assert(not report-store-measurement-evidence-valid(report(measurement-rows(discrepancy-value: 0.0001, passed-value: false)), "store-a"))
#assert(not report-store-measurement-evidence-valid(report(measurement-rows(repeat-count-value: 1, row-n: 1)), "store-a"))
#assert(not report-store-measurement-evidence-valid(report(measurement-rows(repeat-count-value: "3")), "store-a"))
#assert(not report-store-measurement-evidence-valid(report(measurement-rows(discrepancy-value: "0.0001")), "store-a"))
#assert(not report-store-measurement-evidence-valid(report(measurement-rows(discrepancy-value: -0.0001)), "store-a"))
#assert(not report-store-measurement-evidence-valid(report(measurement-rows(tolerance-value: -0.001)), "store-a"))
#assert(not report-store-measurement-evidence-valid(report(measurement-rows(rule-value: "unfrozen_rule")), "store-a"))
#assert(not report-store-measurement-evidence-valid(report(measurement-rows(discrepancy-unit: "count")), "store-a"))
#assert(not report-store-measurement-evidence-valid(report(measurement-rows(discrepancy-aggregation: "mean_abs_difference")), "store-a"))
#assert(not report-store-measurement-evidence-valid(report(measurement-rows(decision-aggregation: "decision")), "store-a"))
#assert(not report-store-measurement-evidence-valid(report(measurement-rows(row-n: 2)), "store-a"))
#assert(not report-store-measurement-evidence-valid(report(measurement-rows(gate-source: "analysis/other.json|sidecar:" + sidecar-b)), "store-a"))
#assert(not report-store-measurement-evidence-valid(report(measurement-rows(source: "analysis/repeatability.json|sidecar:", gate-source: "analysis/repeatability.json|sidecar:")), "store-a"))

#assert(report-store-q1-evidence-valid(report(q1-rows()), "store-a"))
#assert(not report-store-q1-evidence-valid(report(q1-rows(count-value: 4)), "store-a"))
#assert(not report-store-q1-evidence-valid(report(q1-rows(ranking-value: "0.8")), "store-a"))
#assert(not report-store-q1-evidence-valid(report(q1-rows(ranking-value: 1.1)), "store-a"))
#assert(not report-store-q1-evidence-valid(report(q1-rows(calibration-value: -0.1)), "store-a"))
#assert(not report-store-q1-evidence-valid(report(q1-rows(ranking-unit: "count")), "store-a"))
#assert(not report-store-q1-evidence-valid(report(q1-rows(ranking-aggregation: "candidate_row_mean")), "store-a"))
#assert(not report-store-q1-evidence-valid(report(q1-rows(source: "analysis/unbound.json", gate-source: "analysis/unbound.json")), "store-a"))
#assert(not report-store-q1-evidence-valid(report(q1-rows(gate-source: "analysis/other.json|sidecar:" + sidecar-b)), "store-a"))

#assert(report-store-q2-evidence-valid(report(q2-rows()), "store-a"))
#assert(not report-store-q2-evidence-valid(report(q2-rows(count-value: 4)), "store-a"))
#assert(not report-store-q2-evidence-valid(report(q2-rows(mae-value: "0.1")), "store-a"))
#assert(not report-store-q2-evidence-valid(report(q2-rows(mae-value: -0.1)), "store-a"))
#assert(not report-store-q2-evidence-valid(report(q2-rows(coverage-value: 1.1)), "store-a"))
#assert(not report-store-q2-evidence-valid(report(q2-rows(coverage-unit: "count")), "store-a"))
#assert(not report-store-q2-evidence-valid(report(q2-rows(coverage-aggregation: "candidate_row_mean")), "store-a"))
#assert(not report-store-q2-evidence-valid(report(q2-rows(source: "analysis/unbound.json", gate-source: "analysis/unbound.json")), "store-a"))
#assert(not report-store-q2-evidence-valid(report(q2-rows(gate-source: "analysis/other.json|sidecar:" + sidecar-b)), "store-a"))

Population, repeatability, candidate support, actor-visible one-step evidence,
and learned-versus-exact two-step evidence are admitted only through typed,
range-checked, population-bound, provenance-complete row families.
