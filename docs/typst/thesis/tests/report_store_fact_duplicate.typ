#import "../experiment_data.typ": report-store-fact

#let report = (
  tables: (
    facts: (
      rows: (
        (store_id: "store-a", key: "metric", value: 1),
        (store_id: "store-a", key: "metric", value: 2),
      ),
    ),
  ),
)

#report-store-fact(report, "store-a", "metric")
