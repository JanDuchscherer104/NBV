#import "../experiment_data.typ": format-report-value, report-fact, load-thesis-report, thesis-report-settings

#let report-settings = thesis-report-settings()
#let report = load-thesis-report(
  report-settings.path,
  evidence-status: report-settings.evidence-status,
  required-role: report-settings.required-role,
)
#assert(report.bundle_role in ("fixture", "evidence"), message: "bundle_role must be typed and validated")
#let missing-value = report-fact(report, "selected.path_length_m.p5").value
#let parameters = report.tables.parameters.rows

#if report.bundle_role == "fixture" {
  assert(report-fact(report, "selected.path_length_m.p5").key == "selected.path_length_m.p5", message: "fixture must retain the selected p5 fact")
  assert(parameters.any(row => row.value_type == "bool" and row.value_bool == true), message: "fixture must retain a boolean parameter")
  assert(parameters.any(row => row.value_type == "int" and row.value_int == 2), message: "fixture must retain an integer parameter")
  assert(parameters.any(row => row.value_type == "float" and row.value_float == 1.25), message: "fixture must retain a floating-point parameter")
  assert(parameters.any(row => row.value_type == "str" and row.value_text == "fixture-text"), message: "fixture must retain a text parameter")
  assert(parameters.any(row => row.is_missing and row.value_text == none), message: "fixture must retain a missing parameter as JSON null")
}
#let outcomes = report.tables.empirical_results.rows.map(row => row.outcome)
#assert(outcomes.len() == 4 and ("supporting", "negative", "failed", "missing").all(outcome => outcome in outcomes), message: "fixture must retain every typed empirical outcome")
#let failed = report.tables.empirical_results.rows.find(row => row.outcome == "failed")
#let negative = report.tables.empirical_results.rows.find(row => row.outcome == "negative")
#assert(failed != none and failed.estimate == none and failed.reason != none, message: "failed outcome must expose its reason")
#assert(negative != none and negative.estimate != none, message: "negative outcome must expose its estimate")

Empirical outcomes: #outcomes.join(", ")\\
Failed result: #failed.outcome — #failed.reason\\
Non-supporting result: #negative.outcome — estimate #format-report-value(negative.estimate)
Missing: #format-report-value(missing-value)
