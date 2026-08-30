#import "../experiment_data.typ": candidate-support-decision-rule, paired-interval-method, q1-decision-rule, q1-pairwise-chance, q2-decision-rule, repeatability-decision-rule, report-store-population-evidence-valid, report-store-measurement-evidence-valid, report-store-candidate-support-evidence-valid, report-store-q1-evidence-valid, report-store-q2-evidence-valid

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
  support-p05: 2.0,
  failed-root-rate: 0.05,
  zero-rate: 0.1,
  side-balance: 0.5,
  orbit-span: 45.0,
  support-minimum: 1.0,
  failed-root-maximum: 0.2,
  rule: candidate-support-decision-rule,
  passed: true,
  source: source,
  gate-source: source,
) = (
  fact("study.population.scenes", scene-count-value, "count", 5, "count", source: source),
  fact("candidate-support.actor-valid-fraction", metric-value, metric-unit, 5, metric-aggregation, source: source),
  fact("candidate-support.valid-support-p05", support-p05, "count", 5, "state_then_scene_p05", source: source),
  fact("candidate-support.failed-root-rate", failed-root-rate, "fraction", 5, "state_then_scene_macro", source: source),
  fact("candidate-support.configured-family-zero-rate", zero-rate, "fraction", 5, "state_then_scene_macro", source: source),
  fact("candidate-support.target-side-balance", side-balance, "fraction", 5, "state_then_scene_macro", source: source),
  fact("candidate-support.circular-orbit-span", orbit-span, "deg", 5, "state_then_scene_macro", source: source),
  fact("candidate-support.valid-support-p05.minimum", support-minimum, "count", 5, "analysis_threshold", source: source),
  fact("candidate-support.failed-root-rate.maximum", failed-root-maximum, "fraction", 5, "analysis_threshold", source: source),
  fact("candidate-support.gate.rule", rule, "identity", 5, "analysis_identity", source: source),
  fact("candidate-support.gate.passed", passed, "bool", gate-n, "state_then_scene_decision", source: gate-source),
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
  source: source,
  gate-source: source,
) = (
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

#assert(report-store-candidate-support-evidence-valid(report(support-rows()), "store-a"))
#assert(report-store-candidate-support-evidence-valid(report(support-rows(support-p05: 1, failed-root-rate: 0.2)), "store-a"))
#assert(report-store-candidate-support-evidence-valid(report(support-rows(support-p05: 0, passed: false)), "store-a"))
#assert(report-store-candidate-support-evidence-valid(report(support-rows(failed-root-rate: 0.3, passed: false)), "store-a"))
#assert(not report-store-candidate-support-evidence-valid(report(support-rows(support-p05: 0)), "store-a"))
#assert(not report-store-candidate-support-evidence-valid(report(support-rows(failed-root-rate: 0.3)), "store-a"))
#assert(report-store-candidate-support-evidence-valid(report(support-rows(
  metric-value: 0,
  support-p05: 0,
  failed-root-rate: 1,
  zero-rate: 1,
  side-balance: 0,
  orbit-span: 0,
  passed: false,
)), "store-a"))
#assert(not report-store-candidate-support-evidence-valid(report(support-rows(
  metric-value: 0,
  support-p05: 0,
  failed-root-rate: 1,
  zero-rate: 1,
  side-balance: 0,
  orbit-span: 0,
)), "store-a"))
#assert(not report-store-candidate-support-evidence-valid(report(support-rows(passed: false)), "store-a"))
#assert(not report-store-candidate-support-evidence-valid(report(support-rows(support-minimum: 0)), "store-a"))
#assert(not report-store-candidate-support-evidence-valid(report(support-rows(failed-root-maximum: 1)), "store-a"))
#assert(not report-store-candidate-support-evidence-valid(report(support-rows(rule: "unfrozen_support_rule")), "store-a"))
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

Population, repeatability, candidate support, actor-visible one-step evidence,
and learned-versus-exact two-step evidence are admitted only through typed,
range-checked, population-bound, provenance-complete row families.
