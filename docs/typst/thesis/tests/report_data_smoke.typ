#import "../experiment_data.typ": load-thesis-report, report-fact, report-store-fact, format-report-value

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
Missing: #format-report-value(missing-value)
