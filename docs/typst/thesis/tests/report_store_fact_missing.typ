#import "../experiment_data.typ": report-store-fact

#let report = (
  tables: (
    facts: (
      rows: (
        (store_id: "store-a", key: "other", value: 1),
      ),
    ),
  ),
)

#report-store-fact(report, "store-a", "metric")
