#import "../experiment_data.typ": load-scientific-report, report-value, report-table, report-figure, report-figure-path, format-report-value

#let report = load-scientific-report(
  "/typst/thesis/data/report-bundle-v2-fixture.json",
  evidence-status: "pilot",
)
#let quantity = report-value(report, "fixture.quantity")
#let values = report-table(report, "fixture.table")
#let figure-data = report-figure(report, "fixture.figure")

#assert(quantity.symbol_id == "oracle.rri", message: "quantity must retain canonical symbol ID")
#assert(values.rows.len() == 2, message: "table rows must remain frozen")
#assert(figure-data.static_path == "assets/fixture.svg", message: "figure must expose its frozen static asset")

Fixture value: #format-report-value(quantity.value, digits: 2, unit: quantity.unit)

#figure(
  image(report-figure-path(report, "fixture.figure"), width: 45%),
  caption: [Frozen static report asset],
)
